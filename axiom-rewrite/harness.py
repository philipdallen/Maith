#!/usr/bin/env python3
"""The shared five-gate harness for the axiom-discovery track (issue #29).

`AXIOM_DISCOVERY.md` §"Validation pipeline" specifies five gates, in order:

  1. homomorphism obligation   — φ(x ∘ y) = φ(x) ⊕ φ(y)
  2. faithfulness / non-collapse — φ's kernel is trivial on the domain
  3. transfer test             — pull a theorem back through φ
  4. compression accounting    — bookkeeping, ONLY past gate 3
  5. breadth check             — replicate on a second, unrelated sub-domain

Gates 1-3 are **real Lean obligations**: the harness emits them as Lean source and
asks the kernel. A gate passes iff its obligation *elaborates* — a `sorry` or a
type error is a failure, not partial credit.

## One harness, many specs (the DoD's explicit constraint)

The DoD forbids "a new DSL or elaborator per candidate". So the spec is **data**:

    {
      "candidate_id": "...",
      "target_structure": "...",   # what φ maps INTO
      "domain": "...",             # what it is tested against
      "phi": "<one-line description>",
      "provenance": "...",
      "prelude": "<Lean source defining the objects and φ>",
      "obligations": {"1": "<Lean theorem statement>", "2": "...", "3": "..."}
    }

The harness concatenates `prelude` + the gate's obligation and runs
`lake env lean` on it. Only the spec changes between candidates; the harness never
does. This also means specifying a candidate requires writing Lean, which is the
honest requirement — the gates ARE Lean obligations.

## Gate 4 is not a Lean obligation

It is bookkeeping, recorded only for candidates already past gate 3. Its rule is
enforced here (and independently on ledger append, per #27): a candidate that
failed gate 3 gets NO compression number, rather than a plausible-looking one.

Usage:
    python3 axiom-rewrite/harness.py run <spec.json> [--json]
    python3 axiom-rewrite/harness.py batch <dir|glob> [--json] [--record LEDGER]
    python3 axiom-rewrite/harness.py list

Exit codes: `run` 0 if all gates the spec ran passed, else 1; `batch` 0 when every
spec was processed (per-spec verdicts are output, not exit codes) — a gate failure
is data, not an error; 2 on usage/spec error.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
SPECS_DIR = Path(__file__).resolve().parent / "specs"

GATES = {
    1: "homomorphism",
    2: "faithfulness",
    3: "transfer",
    4: "compression",
    5: "breadth",
}
# Gates discharged by the Lean kernel. 4 is bookkeeping; 5 needs a second domain.
LEAN_GATES = (1, 2, 3)


@dataclass
class Spec:
    candidate_id: str
    target_structure: str
    domain: str
    phi: str
    provenance: str
    prelude: str
    obligations: dict[int, str] = field(default_factory=dict)
    second_domain: Optional[str] = None
    second_obligation: Optional[str] = None
    note: str = ""

    @classmethod
    def load(cls, path: Path) -> "Spec":
        d = json.loads(path.read_text())
        return cls(
            candidate_id=d["candidate_id"],
            target_structure=d["target_structure"],
            domain=d["domain"],
            phi=d["phi"],
            provenance=d.get("provenance", ""),
            prelude=d["prelude"],
            obligations={int(k): v for k, v in d.get("obligations", {}).items()},
            second_domain=d.get("second_domain"),
            second_obligation=d.get("second_obligation"),
            note=d.get("note", ""),
        )


@dataclass
class GateResult:
    gate: int
    outcome: str          # "pass" | "fail" | "skip"
    obligation: str       # the Lean obligation discharged (or why none)
    detail: str = ""

    @property
    def name(self) -> str:
        return GATES[self.gate]


class Harness:
    """Runs a spec through the gates. Fixed machinery; only specs vary."""

    def __init__(self, lean_dir: Path = REPO, timeout: int = 600):
        self.lean_dir = lean_dir
        self.timeout = timeout
        self._scratch: list[Path] = []

    # -- the Lean oracle ---------------------------------------------------
    def discharge(self, source: str, label: str) -> tuple[bool, str]:
        """Ask the kernel to elaborate `source`. Returns (passed, detail).

        A `sorry` counts as failure: `set_option warningAsError true` turns it into
        an error, so a smuggled sorry cannot pass a gate. That mirrors the
        hygiene gate, but here it is enforced by the kernel rather than a grep.
        """
        body = "import Mathlib\nset_option warningAsError true\n\n" + source + "\n"
        with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False,
                                         dir=str(self.lean_dir)) as f:
            f.write(body)
            path = Path(f.name)
        self._scratch.append(path)
        try:
            proc = subprocess.run(
                ["lake", "env", "lean", str(path)],
                cwd=str(self.lean_dir), capture_output=True, text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return False, f"TIMEOUT after {self.timeout}s discharging {label}"
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            errs = [l for l in out.splitlines() if "error" in l.lower()]
            return False, (errs[0] if errs else out.strip()[:200]) or "lean failed"
        return True, "kernel-checked"

    def cleanup(self) -> None:
        for p in self._scratch:
            p.unlink(missing_ok=True)
        self._scratch.clear()

    # -- the gates ---------------------------------------------------------
    def run(self, spec: Spec) -> list[GateResult]:
        results: list[GateResult] = []

        for gate in LEAN_GATES:
            obligation = spec.obligations.get(gate)
            if not obligation:
                results.append(GateResult(gate, "skip", "(no obligation in spec)",
                                          "spec omits this gate"))
                continue
            source = spec.prelude + "\n\n" + obligation
            ok, detail = self.discharge(source, f"gate {gate} ({spec.candidate_id})")
            results.append(GateResult(
                gate, "pass" if ok else "fail",
                obligation.strip().splitlines()[0][:120], detail))

        results.append(self._gate4(spec, results))

        if spec.second_obligation:
            ok, detail = self.discharge(
                spec.prelude + "\n\n" + spec.second_obligation,
                f"gate 5 ({spec.candidate_id})")
            results.append(GateResult(
                5, "pass" if ok else "fail",
                spec.second_obligation.strip().splitlines()[0][:120],
                f"second domain: {spec.second_domain or '?'} — {detail}"))
        else:
            results.append(GateResult(
                5, "skip", "(no second-domain obligation)",
                "breadth check needs a second, unrelated sub-domain"))

        return results

    @staticmethod
    def _gate4(spec: Spec, prior: list[GateResult]) -> GateResult:
        """Bookkeeping gate. REFUSES to record compression unless gate 3 passed.

        This is the DoD's third requirement, and the reason gate 4 sits after gate 3
        rather than beside it: a compression number attached to a candidate that never
        transferred would be bookkeeping presented as evidence.

        Gate 4 is **declared non-failing** (issue #32): it either permits a
        compression number or withholds one. Withholding is `skip`, never `fail`,
        because compression accounting is bookkeeping on a result that already
        exists — a candidate is not *rejected* for lacking a compression number,
        it is rejected by gate 3. Emitting `fail` here would invent a failure mode
        gate 4 does not have, and the ledger now rejects `fail` at gate 4.

        The refusal is still made **observable** — the detail says explicitly that
        no number was emitted — so "gate 4 refuses" is testable rather than implied.
        """
        by_gate = {r.gate: r for r in prior}
        transfer = by_gate.get(3)
        if transfer is None or transfer.outcome != "pass":
            return GateResult(
                4, "skip", "(compression refused — no number emitted)",
                "gate 3 (transfer) did not pass, so NO compression number is "
                "recorded. Compression is bookkeeping on a result that exists; "
                "emitting one here would present bookkeeping as evidence. Gate 4 "
                "is non-failing, so this is `skip`, not `fail`.")
        return GateResult(
            4, "pass", "(compression permitted)",
            "gate 3 passed, so compression accounting may be recorded for this "
            "candidate")

    @staticmethod
    def summary(results: list[GateResult]) -> dict:
        failed = [r.gate for r in results if r.outcome == "fail"]
        return {
            "gates": {r.gate: r.outcome for r in results},
            "highest_gate_passed": max(
                (r.gate for r in results if r.outcome == "pass"), default=0),
            "failed_gates": failed,
            "all_passed": not failed,
        }


def render(spec: Spec, results: list[GateResult]) -> str:
    lines = [
        f"candidate {spec.candidate_id}  ({spec.phi})",
        f"  target structure: {spec.target_structure}",
        f"  domain:           {spec.domain}",
        f"  provenance:       {spec.provenance}",
        "",
    ]
    for r in results:
        mark = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}[r.outcome]
        lines.append(f"  [{mark}] gate {r.gate} ({r.name})")
        lines.append(f"         obligation: {r.obligation}")
        if r.detail:
            lines.append(f"         detail:     {r.detail}")
    s = Harness.summary(results)
    lines += ["", f"  summary: {s}"]
    return "\n".join(lines)


def _resolve_spec(name: str) -> Optional[Path]:
    """Resolve a spec argument to a file: as given, else under `specs/`."""
    path = Path(name)
    if path.exists():
        return path
    candidate = SPECS_DIR / name
    return candidate if candidate.exists() else None


def run_one(spec: Spec, ledger: Optional[Path], timeout: int) -> tuple[
        list[GateResult], Optional[str], Optional[str]]:
    """Run one spec and optionally record it.

    Returns `(results, recorded_candidate_id, record_error)`. A recording failure
    is returned rather than raised so a batch can continue past one bad record --
    but it is never silently swallowed (the caller prints it).
    """
    h = Harness(timeout=timeout)
    try:
        results = h.run(spec)
    finally:
        h.cleanup()
    recorded: Optional[str] = None
    record_error: Optional[str] = None
    if ledger is not None:
        try:
            recorded = record(spec, results, ledger)
        except Exception as e:  # LedgerError and friends: surface, do not swallow
            record_error = str(e)
    return results, recorded, record_error


def cmd_run(args) -> int:
    path = _resolve_spec(args.spec)
    if path is None:
        print(f"ERROR: spec not found: {args.spec}", file=sys.stderr)
        return 2
    try:
        spec = Spec.load(path)
    except (KeyError, json.JSONDecodeError) as e:
        print(f"ERROR: malformed spec {path}: {e}", file=sys.stderr)
        return 2

    ledger = Path(args.record) if args.record else None
    results, recorded, record_error = run_one(spec, ledger, args.timeout)
    if recorded:
        print(f"recorded {recorded} to {args.record}")
    if record_error:
        print(f"ERROR: could not record to ledger: {record_error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"spec": spec.candidate_id, "results": [
            {"gate": r.gate, "name": r.name, "outcome": r.outcome,
             "obligation": r.obligation, "detail": r.detail} for r in results],
            "summary": Harness.summary(results)}, indent=2))
    else:
        print(render(spec, results))

    return 0 if Harness.summary(results)["all_passed"] else 1


def cmd_list(args) -> int:
    if not SPECS_DIR.exists() or not any(SPECS_DIR.glob("*.json")):
        print("(no specs)")
        return 0
    for p in sorted(SPECS_DIR.glob("*.json")):
        try:
            s = Spec.load(p)
            print(f"{p.name}  {s.candidate_id}  {s.phi[:60]}")
        except Exception as e:
            print(f"{p.name}  UNREADABLE: {e}")
    return 0


def collect_specs(target: str) -> list[Path]:
    """Resolve a batch target to a sorted list of spec files.

    Accepts a directory (all `*.json` inside), a glob, or a single file. Sorted so
    a batch is deterministic and a re-run yields the same order.
    """
    p = Path(target)
    if p.is_dir():
        return sorted(p.glob("*.json"))
    if any(ch in target for ch in "*?["):
        # Anchor the glob at its own directory so absolute patterns work too:
        # `Path("/a/b").glob("*.json")` is the supported form; `Path().glob("/abs/*.json")`
        # raises "Non-relative patterns are unsupported".
        wildcard = min((target.index(ch) for ch in "*?[" if ch in target), default=len(target))
        base = Path(target[:wildcard] or ".").parent
        pattern = target[len(str(base)) + 1:] if str(base) != "." else target
        return sorted(base.glob(pattern))
    return [p] if p.exists() else []


def cmd_batch(args) -> int:
    """Run every spec in a batch and record each outcome (#37).

    One spec per invocation was #29's limit; a candidate batch (#30) wants a loop.
    Design choices that matter for a batch:

    * A spec that **fails a gate is data, not an error** -- the ledger keeps failed
      candidates on purpose -- so a failing spec does not abort the batch and the
      process still exits 0. Only a *usage* problem (no specs found, malformed
      spec, unrecordable ledger row) is exit 2.
    * Each spec is run and recorded independently, so one bad record cannot discard
      the outcomes already written.
    * Exit 0 when every spec was processed. The per-spec gate verdicts are in the
      output and the ledger, not in the exit code -- a batch's job is coverage, and
      "all specs failed" is a legitimate, informative result.
    """
    specs = collect_specs(args.batch)
    if not specs:
        print(f"ERROR: no specs found for: {args.batch}", file=sys.stderr)
        return 2

    ledger = Path(args.record) if args.record else None
    rows = []
    usage_errors = 0
    for path in specs:
        try:
            spec = Spec.load(path)
        except (KeyError, json.JSONDecodeError) as e:
            print(f"ERROR: malformed spec {path}: {e}", file=sys.stderr)
            usage_errors += 1
            continue
        results, recorded, record_error = run_one(spec, ledger, args.timeout)
        if record_error:
            print(f"ERROR: could not record {spec.candidate_id}: {record_error}",
                  file=sys.stderr)
            usage_errors += 1
        summary = Harness.summary(results)
        rows.append({
            "spec": spec.candidate_id,
            "file": path.name,
            "summary": summary,
            "recorded": recorded,
        })
        if not args.json:
            print(render(spec, results))
            print()

    if args.json:
        print(json.dumps({"batch": args.batch, "n": len(rows),
                          "runs": rows}, indent=2))
    else:
        passed = sum(1 for r in rows if r["summary"]["all_passed"])
        print(f"batch: {len(rows)} spec(s) processed, {passed} passed all gates, "
              f"{len(rows) - passed} failed at least one"
              + (f", {usage_errors} usage error(s)" if usage_errors else ""))
        if ledger:
            print(f"recorded to {ledger}")

    return 2 if usage_errors else 0


def candidate_from_run(spec: Spec, results: list[GateResult],
                                   compression: Optional[dict] = None):
    """Build a `candidates.Candidate` from a harness run (issue #29 follow-up).

    This is the bridge that was missing when #29 closed: the harness validated
    specs, but nothing wrote the outcome to the ledger, so a run left no record.

    The ledger enforces its own rules on append (see
    `axiom-rewrite/candidates.py:validate`), so this function does NOT re-implement
    them -- it passes through what the harness found and lets the ledger accept or
    reject. That matters: if the two disagreed, the ledger's check would be the
    authority, and a divergence would surface as a `LedgerError` rather than
    silently.

    `compression` is only forwarded when gate 3 passed; passing it otherwise would
    make the ledger reject the record, which is the correct outcome but obscures
    *why* at the call site.
    """
    # Import lazily: `candidates` lives alongside this module and importing at
    # module scope would couple the harness to the ledger for users who only run
    # specs.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from candidates import Candidate, FAILURE_MODES  # noqa: E402

    by_gate = {r.gate: r.outcome for r in results}
    transfer_passed = by_gate.get(3) == "pass"
    failed = sorted(g for g, o in by_gate.items() if o == "fail")
    return Candidate(
        candidate_id=spec.candidate_id,
        target_structure=spec.target_structure,
        domain=spec.domain,
        phi=spec.phi,
        provenance=spec.provenance or "(unspecified)",
        gates=dict(by_gate),
        compression=compression if transfer_passed else None,
        reusable=(by_gate.get(5) == "pass"),
        failure_mode=FAILURE_MODES.get(failed[0]) if failed else None,
        note=(spec.note + (f" | harness: {r.detail}" if (r := next(
            (x for x in results if x.outcome == "fail"), None)) else "")).strip(" |"),
    )


def record(spec: Spec, results: list[GateResult], ledger: Path,
           compression: Optional[dict] = None) -> str:
    """Persist a harness run to the candidate ledger. Returns the candidate id.

    Raises whatever the ledger raises on a bad record -- deliberately not caught,
    because a rejected record is information the caller needs.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from candidates import append_candidate  # noqa: E402

    cand = candidate_from_run(spec, results, compression)
    append_candidate(Path(ledger), cand)
    return cand.candidate_id


def main() -> int:
    ap = argparse.ArgumentParser(description="five-gate validation harness (#29)")
    sub = ap.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="run a spec through the gates")
    p_run.add_argument("spec", help="spec file (path or name under specs/)")
    p_run.add_argument("--json", action="store_true")
    p_run.add_argument("--timeout", type=int, default=600)
    p_run.add_argument("--record", default=None, metavar="LEDGER",
                       help="append the outcome to this ledger (e.g. "
                            "axiom-rewrite/candidates.jsonl). Defaults to not "
                            "recording, so a dry run changes nothing.")
    p_run.set_defaults(func=cmd_run)
    sub.add_parser("list", help="list available specs").set_defaults(func=cmd_list)
    p_batch = sub.add_parser(
        "batch", help="run every spec in a directory/glob and record each (#37)")
    p_batch.add_argument("batch", help="a directory of specs, a glob, or one file")
    p_batch.add_argument("--json", action="store_true")
    p_batch.add_argument("--timeout", type=int, default=600)
    p_batch.add_argument("--record", default=None, metavar="LEDGER",
                         help="append each outcome to this ledger (e.g. "
                              "axiom-rewrite/candidates.jsonl). Defaults to not "
                              "recording, so a dry run changes nothing.")
    p_batch.set_defaults(func=cmd_batch)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())