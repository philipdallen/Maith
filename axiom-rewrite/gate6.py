#!/usr/bin/env python3
"""Gate 6 — adversarial significance check via independent external models (issue #34).

For any candidate that survived gate 5 (breadth), ask 2+ *genuinely distinct*
external models a mirrored for/against-significance question about the candidate,
and record whether they agree. Convergent "unremarkable" from independent models
is a cheap early reject *before human review*; disagreement, or convergent "looks
real", earns attention.

## Gate 6 is a signal, not a gate

DEC-060 (2026-10-26) decided gate 6 is a **non-blocking triage signal**: it never
blocks `reusable`, which still requires gate 5 (breadth). The scope questions were
settled by the maintainer's 2026-10-25 direction and this build is recorded as
DEC-063:

  * providers — `GOOGLE_API_KEY` (Google) + `NVIDIA_BUILD_KEY` (NVIDIA) are two
    genuinely distinct providers; no fourth is required. `OPENHANDS_API_KEY` is
    not a model provider and does not count toward independence.
  * blocking — signal only; never a gate on `reusable`.
  * volume cap — **10 gate-6 evaluations per run** to start, revisable.
  * retention — **no raw prompts or responses are stored.** Only per-model
    verdicts, the agreement value, and the prompt-template version are kept.

## The carve-out from ordered-gate validation

`axiom-rewrite/README.md` enforces "a candidate cannot pass a later gate while an
earlier one failed", and `candidates.py` validates `gates` as an ordered map of
`1..5`. A *signal* must not enter that machinery, or it would either become a gate
or trip the ordering check. So gate 6 is deliberately kept **outside**
`candidates.jsonl`:

  * `candidates.py` is untouched — gate 6 is not in `VALID_GATES`, and no
    `gate6` field is added to the candidate record.
  * Signals are appended to a **separate append-only ledger**,
    `axiom-rewrite/gate6_signals.jsonl`, keyed by `candidate_id`.

A separate ledger is also the only append-only-compatible shape: `candidates.jsonl`
is unique-per-candidate, and a gate-6 signal is produced *after* the candidate
record already exists, so it cannot be added to that record without rewriting it.

## Scope

One small script: a prompt template, calls to 2 provider APIs, and signal-ledger
writes. No pipeline infrastructure, no orchestration, no retry/queueing layer, no
caching service.

Usage:
    python3 axiom-rewrite/gate6.py run --candidate C-001
    python3 axiom-rewrite/gate6.py run --from-ledger          # all gate-5 survivors
    python3 axiom-rewrite/gate6.py list [--json]

Exit codes: 0 on success (signal recorded or nothing to do); 2 on usage/config
error; 1 on an unrecoverable runtime error. A per-model failure is data — the
model is recorded with verdict `error`, not a crash.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from tooling.net import safe_urlopen  # noqa: E402  (scheme-validated https fetch)

DEFAULT_LEDGER = HERE / "candidates.jsonl"
DEFAULT_SIGNALS = HERE / "gate6_signals.jsonl"

# The prompt template is versioned and the version is stored with every signal, so
# a later change to the wording is visible in the record rather than silent.
GATE6_TEMPLATE_VERSION = "gate6-v1"

# 10 evaluations per run to start (maintainer, 2026-10-26), revisable.
DEFAULT_CAP = 10

VALID_LABELS = ("significant", "unremarkable", "unclear")
VALID_VERDICTS = ("significant", "unremarkable", "unclear", "split", "error")
VALID_AGREEMENTS = ("significant", "unremarkable", "disagreement", "incomplete")
VALID_SIGNALS = ("attention", "early_reject", "incomplete")

# Two genuinely distinct providers (DEC-060). Each entry names the provider, the
# model id, and the env vars that may hold its key — the last is a list because
# the key name differs between the maintainer's environment and this sandbox.
PROVIDERS = (
    {
        "provider": "google",
        "model": "gemini-3.8-flash",
        "key_env": ("GOOGLE_API_KEY", "GEMINI_API_KEY", "Gemini_Key"),
    },
    {
        "provider": "nvidia",
        "model": "openai/gpt-oss-20b",
        "key_env": ("NVIDIA_BUILD_KEY", "NVIDIA_API_KEY", "NVIDIA_API_TOKEN"),
    },
)

# A transport maps (provider_spec, prompt) -> response text. Injectable so the
# tests exercise the real parsing/agreement/ledger paths without the network.
Transport = Callable[[dict, str], str]


class Gate6Error(Exception):
    """A usage or configuration error (not a per-model failure)."""


# ---------------------------------------------------------------------------
# Prompt template (mirrored for/against)
# ---------------------------------------------------------------------------

_PROMPT = """\
You are an adversarial reviewer for a formal-mathematics research pipeline. A
candidate map phi has already survived five gates (homomorphism, faithfulness,
transfer, compression, breadth). Your job is NOT to re-verify those; it is to
judge whether the candidate looks like a *significant structural result* or an
*unremarkable restatement* of something already known.

Candidate
  id: {candidate_id}
  target structure: {target_structure}
  domain: {domain}
  phi: {phi}
  provenance: {provenance}

Answer the two mirrored questions below, then nothing else.

FOR: give the strongest honest case that this candidate is a significant,
transferable structural result. Then label it.
AGAINST: give the strongest honest case that this candidate is unremarkable --
a restatement, a triviality, or an artifact of the benchmark. Then label it.

Labels are exactly one of: significant, unremarkable, unclear.

Reply with exactly two lines, in this order, and no other text:
FOR: <label>
AGAINST: <label>
"""


def build_prompt(candidate: dict) -> str:
    """Render the mirrored for/against prompt for one candidate.

    Only candidate metadata is interpolated -- no gate output, no other model's
    verdict -- so the two models judge independently.
    """
    return _PROMPT.format(
        candidate_id=candidate.get("candidate_id", ""),
        target_structure=candidate.get("target_structure", ""),
        domain=candidate.get("domain", ""),
        phi=candidate.get("phi", ""),
        provenance=candidate.get("provenance", ""),
    )


_LABEL_RE = {
    "for": re.compile(r"^\s*FOR:\s*(significant|unremarkable|unclear)\s*$",
                      re.IGNORECASE | re.MULTILINE),
    "against": re.compile(r"^\s*AGAINST:\s*(significant|unremarkable|unclear)\s*$",
                          re.IGNORECASE | re.MULTILINE),
}


def parse_labels(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract the (for_label, against_label) pair, or None where absent."""
    out = []
    for key in ("for", "against"):
        m = _LABEL_RE[key].search(text or "")
        out.append(m.group(1).lower() if m else None)
    return out[0], out[1]


def model_verdict(for_label: Optional[str], against_label: Optional[str]) -> str:
    """Collapse one model's mirrored pair into a single verdict.

    The mirror is the adversarial part: a model whose answer flips with the
    framing is recorded as `split`, not as agreement with either framing.
    """
    if for_label not in VALID_LABELS or against_label not in VALID_LABELS:
        return "error"
    if for_label == against_label:
        return for_label
    return "split"


def agreement(verdicts: list[str]) -> str:
    """Agreement across models, or `incomplete` if any model errored.

    `incomplete` rather than a majority vote: a signal built on a failed call is
    not evidence, and the contract is that a check which cannot fail is not a
    check. Convergent `unclear` is likewise `incomplete` — the models agreed, but
    on "no judgment", which is not a triage signal either way.
    """
    if not verdicts or any(v == "error" for v in verdicts):
        return "incomplete"
    if all(v == "unremarkable" for v in verdicts):
        return "unremarkable"
    if all(v == "significant" for v in verdicts):
        return "significant"
    if all(v == "unclear" for v in verdicts):
        return "incomplete"
    return "disagreement"


def signal_for(agr: str) -> str:
    """Map agreement to the triage signal. Never blocks `reusable`."""
    if agr == "unremarkable":
        return "early_reject"
    if agr in ("significant", "disagreement"):
        return "attention"
    return "incomplete"


# ---------------------------------------------------------------------------
# Provider calls
# ---------------------------------------------------------------------------

def resolve_key(key_env: tuple[str, ...]) -> Optional[str]:
    for name in key_env:
        val = os.environ.get(name)
        if val:
            return val
    return None


def _http_transport(spec: dict, prompt: str) -> str:
    """Real provider call. Kept behind the transport seam for testability."""
    key = resolve_key(spec["key_env"])
    if not key:
        raise Gate6Error(
            f"no API key for provider {spec['provider']!r} "
            f"(checked: {', '.join(spec['key_env'])})"
        )
    if spec["provider"] == "google":
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               f"{spec['model']}:generateContent?key={key}")
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0}}
    elif spec["provider"] == "nvidia":
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        body = {"model": spec["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0, "max_tokens": 900}
    else:  # pragma: no cover - guarded by the PROVIDERS table
        raise Gate6Error(f"unknown provider {spec['provider']!r}")

    headers = {"Content-Type": "application/json"}
    if spec["provider"] == "nvidia":
        headers["Authorization"] = f"Bearer {key}"
    import urllib.request
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    with safe_urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return _extract_text(spec["provider"], data)


def _extract_text(provider: str, data: dict) -> str:
    """Pull the assistant text out of either provider's response envelope.

    Reasoning models may put prose in `reasoning`/`reasoning_content` and leave
    `content` null; the labels are searched in whichever text is present.
    """
    if provider == "google":
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as e:
            raise Gate6Error(f"unexpected google response shape: {e}") from e
    try:
        msg = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as e:
        raise Gate6Error(f"unexpected nvidia response shape: {e}") from e
    for k in ("content", "reasoning_content", "reasoning"):
        if msg.get(k):
            return msg[k]
    return ""


# ---------------------------------------------------------------------------
# Evaluation + signal ledger
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    candidate_id: str
    template_version: str
    models: list[dict] = field(default_factory=list)
    agreement: str = "incomplete"
    signal: str = "incomplete"
    timestamp: str = ""
    run_id: str = ""

    def validate(self) -> None:
        if not self.candidate_id:
            raise Gate6Error("candidate_id is required")
        if self.agreement not in VALID_AGREEMENTS:
            raise Gate6Error(f"bad agreement {self.agreement!r}")
        if self.signal not in VALID_SIGNALS:
            raise Gate6Error(f"bad signal {self.signal!r}")
        for m in self.models:
            if m.get("verdict") not in VALID_VERDICTS:
                raise Gate6Error(f"bad model verdict {m.get('verdict')!r}")
            # Retention rule: verdicts only, never the raw prompt or response.
            extra = set(m) - {"provider", "model", "for_label", "against_label",
                              "verdict"}
            if extra:
                raise Gate6Error(
                    f"model record carries fields outside the retention rule "
                    f"(verdicts only): {sorted(extra)}"
                )

    def to_json(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "template_version": self.template_version,
            "models": self.models,
            "agreement": self.agreement,
            "signal": self.signal,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
        }


def evaluate_candidate(candidate: dict, *, transport: Transport,
                       run_id: str = "") -> Signal:
    """Ask every provider the mirrored prompt and collapse to one signal."""
    prompt = build_prompt(candidate)
    models: list[dict] = []
    for spec in PROVIDERS:
        try:
            text = transport(spec, prompt)
            f_lab, a_lab = parse_labels(text)
        except Exception as e:  # a per-model failure is data, not a crash
            models.append({"provider": spec["provider"], "model": spec["model"],
                           "for_label": None, "against_label": None,
                           "verdict": "error", "error": str(e)[:200]})
            continue
        models.append({
            "provider": spec["provider"], "model": spec["model"],
            "for_label": f_lab, "against_label": a_lab,
            "verdict": model_verdict(f_lab, a_lab),
        })
    agr = agreement([m["verdict"] for m in models])
    sig = Signal(
        candidate_id=candidate.get("candidate_id", ""),
        template_version=GATE6_TEMPLATE_VERSION,
        models=models,
        agreement=agr,
        signal=signal_for(agr),
        timestamp=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        run_id=run_id,
    )
    # `error` is a per-model verdict; the retention check tolerates it, but the
    # `error` field it carries is not part of the stored shape, so drop it.
    for m in sig.models:
        m.pop("error", None)
    sig.validate()
    return sig


def read_signals(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def append_signal(path: Path, sig: Signal) -> None:
    sig.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(sig.to_json(), sort_keys=True) + "\n")


def gate5_survivors(ledger_path: Path) -> list[dict]:
    """Candidate records whose gate 5 passed, as plain dicts."""
    if not ledger_path.exists():
        return []
    out = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("gates", {}).get("5") == "pass":
            out.append(rec)
    return out


def _load_candidate(ledger_path: Path, candidate_id: str) -> dict:
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("candidate_id") == candidate_id:
            return rec
    raise Gate6Error(f"candidate {candidate_id!r} not found in {ledger_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_run(args) -> int:
    ledger = Path(args.ledger)
    signals = Path(args.signals)

    if args.from_ledger:
        targets = gate5_survivors(ledger)
        if not targets:
            print("no gate-5 survivors in the ledger; nothing to evaluate")
            return 0
    else:
        if not args.candidate:
            raise Gate6Error("run needs --candidate ID (repeatable) or --from-ledger")
        targets = [_load_candidate(ledger, cid) for cid in args.candidate]

    cap = args.cap
    if cap < 1:
        raise Gate6Error(f"--cap must be >= 1, got {cap}")
    if len(targets) > cap:
        print(f"cap {cap} reached: evaluating {cap} of {len(targets)} candidates "
              f"({len(targets) - cap} deferred to the next run)", file=sys.stderr)
        targets = targets[:cap]

    transport = _http_transport
    if not any(resolve_key(s["key_env"]) for s in PROVIDERS):
        raise Gate6Error(
            "no provider API key found; checked "
            + ", ".join(n for s in PROVIDERS for n in s["key_env"])
        )

    run_id = args.run_id or ""
    results = []
    for cand in targets:
        sig = evaluate_candidate(cand, transport=transport, run_id=run_id)
        append_signal(signals, sig)
        results.append(sig)
        print(f"{sig.candidate_id}: agreement={sig.agreement} signal={sig.signal} "
              f"({', '.join(m['provider'] + '=' + m['verdict'] for m in sig.models)})")
    if args.json:
        print(json.dumps([s.to_json() for s in results], indent=2))
    return 0


def cmd_list(args) -> int:
    rows = read_signals(Path(args.signals))
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("no gate-6 signals recorded")
        return 0
    for r in rows:
        print(f"{r['candidate_id']:<8} {r['signal']:<12} "
              f"{r['agreement']:<13} {r['template_version']}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="gate 6 — adversarial significance signal")
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    ap.add_argument("--signals", default=str(DEFAULT_SIGNALS))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="evaluate candidate(s) and append signals")
    p_run.add_argument("--candidate", action="append", default=[],
                       help="candidate id (repeatable)")
    p_run.add_argument("--from-ledger", action="store_true",
                       help="evaluate every gate-5 survivor in the ledger")
    p_run.add_argument("--cap", type=int, default=DEFAULT_CAP,
                       help=f"max evaluations this run (default {DEFAULT_CAP})")
    p_run.add_argument("--run-id", default="", help="run id, stored with the signal")
    p_run.add_argument("--json", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_list = sub.add_parser("list", help="show recorded signals")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except Gate6Error as e:
        print(f"gate6: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
