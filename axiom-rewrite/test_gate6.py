#!/usr/bin/env python3
"""Tests for gate 6 — the adversarial significance signal (issue #34).

Covers the Definition of Done: mirrored for/against prompts, per-model verdicts,
an agreement value, the prompt-template version, and the signal-ledger write.

Only the network is faked: `evaluate_candidate` takes a `transport` callable, and
every test passes a real in-process one. Parsing, verdict collapse, agreement,
signal mapping, validation, and ledger I/O are the real code paths.

Run: python3 axiom-rewrite/test_gate6.py
"""

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gate6  # noqa: E402
from gate6 import (  # noqa: E402
    Gate6Error, Signal, agreement, append_signal, build_prompt,
    evaluate_candidate, gate5_survivors, model_verdict, parse_labels,
    read_signals, signal_for, GATE6_TEMPLATE_VERSION,
)

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"ok   {name}")
    else:
        print(f"FAIL {name} {detail}")
        FAILS.append(name)


CAND = {
    "candidate_id": "C-001",
    "target_structure": "Group",
    "domain": "decl_a",
    "phi": "def phi := id",
    "provenance": "seed",
}


def fake_transport(labels_by_provider):
    """Build a transport returning a fixed FOR/AGAINST pair per provider."""
    def _t(spec, prompt):
        f, a = labels_by_provider[spec["provider"]]
        return f"FOR: {f}\nAGAINST: {a}\n"
    return _t


# --- prompt template -------------------------------------------------------

def test_prompt_is_mirrored():
    p = build_prompt(CAND)
    check("prompt asks FOR", "FOR:" in p and "AGAINST:" in p)
    check("prompt names candidate", "C-001" in p and "Group" in p and "decl_a" in p)
    check("prompt names phi", "def phi := id" in p)


def test_prompt_does_not_leak_gate_output():
    # The two models must judge independently: no prior verdict, no gate result.
    p = build_prompt(CAND)
    for leak in ("verdict", "gate 5 passed", "agreement"):
        check(f"prompt has no {leak!r}", leak.lower() not in p.lower())


# --- parsing ---------------------------------------------------------------

def test_parse_labels():
    f, a = parse_labels("blah\nFOR: significant\nAGAINST: unremarkable\nmore")
    check("parse both labels", (f, a) == ("significant", "unremarkable"))
    f, a = parse_labels("FOR: Unremarkable\nAGAINST: UNCLEAR")
    check("parse is case-insensitive", (f, a) == ("unremarkable", "unclear"))
    f, a = parse_labels("no labels here")
    check("missing labels -> None", (f, a) == (None, None))
    f, a = parse_labels("FOR: maybe\nAGAINST: unremarkable")
    check("off-enum label -> None", f is None and a == "unremarkable")


# --- per-model verdict -----------------------------------------------------

def test_model_verdict():
    check("agree unremarkable", model_verdict("unremarkable", "unremarkable") == "unremarkable")
    check("agree significant", model_verdict("significant", "significant") == "significant")
    check("mirror flip -> split", model_verdict("significant", "unremarkable") == "split")
    check("unclear agrees", model_verdict("unclear", "unclear") == "unclear")
    check("missing label -> error", model_verdict(None, "unremarkable") == "error")


# --- agreement + signal ----------------------------------------------------

def test_agreement():
    check("both unremarkable", agreement(["unremarkable", "unremarkable"]) == "unremarkable")
    check("both significant", agreement(["significant", "significant"]) == "significant")
    check("split vs unremarkable -> disagreement",
          agreement(["split", "unremarkable"]) == "disagreement")
    check("any error -> incomplete", agreement(["unremarkable", "error"]) == "incomplete")
    check("empty -> incomplete", agreement([]) == "incomplete")
    # Regression (found in live smoke test): convergent `unclear` is a valid
    # verdict but must not read as a disagreement or a triage signal.
    check("convergent unclear -> incomplete", agreement(["unclear", "unclear"]) == "incomplete")
    check("unclear vs unremarkable -> disagreement",
          agreement(["unclear", "unremarkable"]) == "disagreement")


def test_evaluate_convergent_unclear_does_not_crash():
    t = fake_transport({"google": ("unclear", "unclear"),
                        "nvidia": ("unclear", "unclear")})
    sig = evaluate_candidate(CAND, transport=t)
    check("unclear verdict is storable", sig.models[0]["verdict"] == "unclear")
    check("convergent unclear -> incomplete", sig.agreement == "incomplete")
    check("convergent unclear -> incomplete signal", sig.signal == "incomplete")


def test_signal_mapping():
    check("unremarkable -> early_reject", signal_for("unremarkable") == "early_reject")
    check("significant -> attention", signal_for("significant") == "attention")
    check("disagreement -> attention", signal_for("disagreement") == "attention")
    check("incomplete -> incomplete", signal_for("incomplete") == "incomplete")


# --- evaluate: the whole path ---------------------------------------------

def test_evaluate_convergent_unremarkable():
    t = fake_transport({"google": ("unremarkable", "unremarkable"),
                        "nvidia": ("unremarkable", "unremarkable")})
    sig = evaluate_candidate(CAND, transport=t, run_id="20261026-0206-9221")
    check("convergent unremarkable agreement", sig.agreement == "unremarkable")
    check("convergent unremarkable -> early_reject", sig.signal == "early_reject")
    check("two distinct providers", {m["provider"] for m in sig.models} == {"google", "nvidia"})
    check("template version stored", sig.template_version == GATE6_TEMPLATE_VERSION)
    check("run id stored", sig.run_id == "20261026-0206-9221")


def test_evaluate_disagreement_earns_attention():
    t = fake_transport({"google": ("significant", "significant"),
                        "nvidia": ("unremarkable", "unremarkable")})
    sig = evaluate_candidate(CAND, transport=t)
    check("disagreement", sig.agreement == "disagreement")
    check("disagreement -> attention", sig.signal == "attention")


def test_evaluate_split_earns_attention():
    t = fake_transport({"google": ("significant", "unremarkable"),
                        "nvidia": ("significant", "significant")})
    sig = evaluate_candidate(CAND, transport=t)
    check("split recorded for google", sig.models[0]["verdict"] == "split")
    check("split -> attention", sig.signal == "attention")


def test_evaluate_model_failure_is_data():
    def broken(spec, prompt):
        if spec["provider"] == "nvidia":
            raise RuntimeError("connection reset")
        return "FOR: unremarkable\nAGAINST: unremarkable\n"
    sig = evaluate_candidate(CAND, transport=broken)
    check("failed model -> error verdict", sig.models[1]["verdict"] == "error")
    check("failure -> incomplete agreement", sig.agreement == "incomplete")
    check("failure -> incomplete signal", sig.signal == "incomplete")
    check("no raw error text stored", "error" not in sig.models[1])


# --- retention rule --------------------------------------------------------

def test_retention_rejects_raw_payloads():
    s = Signal(candidate_id="C-001", template_version=GATE6_TEMPLATE_VERSION,
               models=[{"provider": "google", "model": "m", "for_label": "x",
                        "against_label": "y", "verdict": "unremarkable",
                        "raw_response": "the full text"}],
               agreement="unremarkable", signal="early_reject")
    try:
        s.validate()
        check("retention rule rejects raw_response", False)
    except Gate6Error:
        check("retention rule rejects raw_response", True)


# --- ledger ----------------------------------------------------------------

def test_append_and_read_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "gate6_signals.jsonl"
        t = fake_transport({"google": ("unremarkable", "unremarkable"),
                            "nvidia": ("unremarkable", "unremarkable")})
        sig = evaluate_candidate(CAND, transport=t)
        append_signal(path, sig)
        append_signal(path, sig)
        rows = read_signals(path)
        check("two signals appended", len(rows) == 2)
        check("roundtrip agreement", rows[0]["agreement"] == "unremarkable")
        check("roundtrip keeps template version",
              rows[0]["template_version"] == GATE6_TEMPLATE_VERSION)
        # Append-only: the second write did not rewrite the first.
        lines = path.read_text().strip().splitlines()
        check("append-only, one line each", len(lines) == 2)


def test_gate5_survivors_filter():
    with tempfile.TemporaryDirectory() as td:
        led = Path(td) / "candidates.jsonl"
        recs = [
            {"candidate_id": "C-001", "gates": {"3": "pass", "5": "pass"}},
            {"candidate_id": "C-002", "gates": {"3": "pass"}},
            {"candidate_id": "C-003", "gates": {"5": "fail"}},
        ]
        led.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
        survivors = gate5_survivors(led)
        check("only gate-5 pass survives", [c["candidate_id"] for c in survivors] == ["C-001"])


def test_candidates_ledger_schema_untouched():
    # The carve-out: gate 6 is NOT in the candidate schema, so it cannot become a
    # gate or trip the ordered-gate validation.
    import candidates
    check("6 not a valid gate", 6 not in candidates.VALID_GATES)
    check("candidates.jsonl default is separate",
          candidates.DEFAULT_LEDGER != gate6.DEFAULT_SIGNALS)


def main():
    for fn in [test_prompt_is_mirrored, test_prompt_does_not_leak_gate_output,
               test_parse_labels, test_model_verdict, test_agreement,
               test_evaluate_convergent_unclear_does_not_crash,
               test_signal_mapping, test_evaluate_convergent_unremarkable,
               test_evaluate_disagreement_earns_attention,
               test_evaluate_split_earns_attention,
               test_evaluate_model_failure_is_data,
               test_retention_rejects_raw_payloads,
               test_append_and_read_roundtrip, test_gate5_survivors_filter,
               test_candidates_ledger_schema_untouched]:
        fn()
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILED: {FAILS}")
        return 1
    print("all gate-6 tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
