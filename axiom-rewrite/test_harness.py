#!/usr/bin/env python3
"""Tests for the five-gate harness (#29).

The DoD's three requirements, each pinned:

  (a) the harness runs a spec end-to-end and emits a verdict per gate with the Lean
      obligation it discharged;
  (b) a fixture candidate that passes gate 1 and fails gate 2 (Unit-collapse) is
      correctly rejected with no partial credit;
  (c) gate 4 refuses to emit a compression number for a candidate that failed
      gate 3.

Plus the control that makes (b) meaningful: without a candidate that PASSES, a
harness that rejects everything would look identical to one that rejects correctly.

These tests need the Lean toolchain. They SKIP cleanly when `lake` is unavailable
(the sandbox loses it between sessions) rather than failing -- same pattern as the
corpus-dependent tests in #28.

Run: python3 axiom-rewrite/test_harness.py
"""

import json
import shutil
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

SPECS = HERE / "specs"
LEAN_AVAILABLE = shutil.which("lake") is not None


def _run(spec_name):
    spec = H.Spec.load(SPECS / spec_name)
    h = H.Harness(timeout=600)
    try:
        return spec, h.run(spec)
    finally:
        h.cleanup()


def _by_gate(results):
    return {r.gate: r.outcome for r in results}


# ---------------------------------------------------------------------------
# (a) verdict per gate, with the obligation recorded
# ---------------------------------------------------------------------------

def test_spec_loads_and_reports_every_gate():
    spec = H.Spec.load(SPECS / "fixture_unit_collapse.json")
    assert spec.candidate_id, "spec must carry an id"
    assert spec.prelude, "spec must carry a prelude (the Lean source)"
    assert 1 in spec.obligations and 2 in spec.obligations, spec.obligations
    print("PASS: test_spec_loads_and_reports_every_gate")


def test_every_gate_gets_a_verdict_and_obligation():
    if not LEAN_AVAILABLE:
        print("SKIP: test_every_gate_gets_a_verdict_and_obligation (no lake)")
        return
    _spec, results = _run("fixture_unit_collapse.json")
    gates = [r.gate for r in results]
    assert gates == [1, 2, 3, 4, 5], f"expected all five gates, got {gates}"
    for r in results:
        assert r.outcome in ("pass", "fail", "skip"), r.outcome
        assert r.obligation, f"gate {r.gate} recorded no obligation"
    print("PASS: test_every_gate_gets_a_verdict_and_obligation")


# ---------------------------------------------------------------------------
# (b) the DoD fixture: gate 1 pass, gate 2 fail, no partial credit
# ---------------------------------------------------------------------------

def test_unit_collapse_passes_gate1_fails_gate2():
    if not LEAN_AVAILABLE:
        print("SKIP: test_unit_collapse_passes_gate1_fails_gate2 (no lake)")
        return
    _spec, results = _run("fixture_unit_collapse.json")
    g = _by_gate(results)
    assert g[1] == "pass", f"gate 1 must PASS (it genuinely is a homomorphism): {g}"
    assert g[2] == "fail", f"gate 2 must FAIL (collapses everything): {g}"
    assert g[3] != "pass", "no partial credit: a gate-2 failure must not let gate 3 pass"
    print("PASS: test_unit_collapse_passes_gate1_fails_gate2")


def test_unit_collapse_is_rejected_overall():
    if not LEAN_AVAILABLE:
        print("SKIP: test_unit_collapse_is_rejected_overall (no lake)")
        return
    _spec, results = _run("fixture_unit_collapse.json")
    s = H.Harness.summary(results)
    assert s["all_passed"] is False, "the degenerate candidate must be rejected"
    assert s["highest_gate_passed"] == 1, s
    print("PASS: test_unit_collapse_is_rejected_overall")


# ---------------------------------------------------------------------------
# (c) gate 4 refuses compression when gate 3 failed
# ---------------------------------------------------------------------------

def test_gate4_refuses_when_gate3_fails():
    if not LEAN_AVAILABLE:
        print("SKIP: test_gate4_refuses_when_gate3_fails (no lake)")
        return
    _spec, results = _run("fixture_transfer_fails.json")
    g = _by_gate(results)
    assert g[1] == "pass" and g[2] == "pass", f"this fixture must reach gate 3: {g}"
    assert g[3] == "fail", f"gate 3 is deliberately false here: {g}"
    gate4 = next(r for r in results if r.gate == 4)
    # Gate 4 is non-failing (#32): it withholds a compression number, it does not
    # reject the candidate. The candidate is rejected by gate 3.
    assert gate4.outcome == "skip", gate4
    assert "refused" in gate4.obligation, gate4.obligation
    assert "no number emitted" in gate4.obligation, (
        "the refusal must be OBSERVABLE, not implied: " + gate4.obligation)
    print("PASS: test_gate4_refuses_when_gate3_fails")


def test_gate4_refuses_when_gate3_absent():
    """Gate 3 skipped (not failed) must also refuse: absence is not a pass."""
    unit = H.Harness._gate4(
        H.Spec.load(SPECS / "fixture_unit_collapse.json"),
        [H.GateResult(1, "pass", "x"), H.GateResult(2, "fail", "y")],
    )
    assert unit.outcome == "skip", unit
    assert "refused" in unit.obligation, unit.obligation
    print("PASS: test_gate4_refuses_when_gate3_absent")


# ---------------------------------------------------------------------------
# Control: the harness can PASS things
# ---------------------------------------------------------------------------

def test_control_passes_all_gates():
    if not LEAN_AVAILABLE:
        print("SKIP: test_control_passes_all_gates (no lake)")
        return
    _spec, results = _run("control_valid.json")
    g = _by_gate(results)
    assert g == {1: "pass", 2: "pass", 3: "pass", 4: "pass", 5: "pass"}, g
    assert H.Harness.summary(results)["all_passed"] is True
    print("PASS: test_control_passes_all_gates")


def test_gate4_permits_after_gate3_passes():
    spec = H.Spec.load(SPECS / "control_valid.json")
    r = H.Harness._gate4(spec, [H.GateResult(3, "pass", "x")])
    assert r.outcome == "pass", r
    assert "permitted" in r.obligation, r.obligation
    print("PASS: test_gate4_permits_after_gate3_passes")


# ---------------------------------------------------------------------------
# The oracle is the kernel, not a grep
# ---------------------------------------------------------------------------

def test_sorry_does_not_pass_a_gate():
    """A smuggled `sorry` must fail: `warningAsError` makes it an error.

    This is the harness's own integrity property -- if `sorry` counted as success,
    every gate would be trivially passable.
    """
    if not LEAN_AVAILABLE:
        print("SKIP: test_sorry_does_not_pass_a_gate (no lake)")
        return
    h = H.Harness(timeout=300)
    try:
        ok, detail = h.discharge("theorem smuggled : (0 : Nat) = 1 := by sorry",
                                 "sorry probe")
    finally:
        h.cleanup()
    assert ok is False, f"a `sorry` proof PASSED a gate (detail: {detail})"
    print("PASS: test_sorry_does_not_pass_a_gate")


def test_true_also_does_not_pass_when_obligation_is_false():
    """Sanity: a genuinely false obligation fails, so gates are not vacuous."""
    if not LEAN_AVAILABLE:
        print("SKIP: test_true_also_does_not_pass_when_obligation_is_false (no lake)")
        return
    h = H.Harness(timeout=300)
    try:
        ok, _ = h.discharge("theorem bogus : (0 : Nat) = 1 := rfl", "false probe")
    finally:
        h.cleanup()
    assert ok is False, "a false obligation PASSED -- gates would be vacuous"
    print("PASS: test_true_also_does_not_pass_when_obligation_is_false")


def test_run_records_to_ledger_with_the_ledgers_own_rules():
    """The harness -> ledger bridge (the gap left when #29 first closed).

    Records the DoD fixture and asserts the ledger's rules held: no compression for
    a candidate that did not pass gate 3, and not reusable without gate 5.
    """
    if not LEAN_AVAILABLE:
        print("SKIP: test_run_records_to_ledger_with_the_ledgers_own_rules (no lake)")
        return
    import tempfile, json as _json
    sys.path.insert(0, str(HERE))
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "candidates.jsonl"
        spec = H.Spec.load(SPECS / "fixture_unit_collapse.json")
        h = H.Harness(timeout=600)
        try:
            results = h.run(spec)
        finally:
            h.cleanup()
        H.record(spec, results, ledger)

        rec = _json.loads(ledger.read_text().strip())
        assert rec["gates"]["2"] == "fail", rec["gates"]
        assert rec["compression"] is None, \
            f"compression recorded for a candidate that failed gate 3: {rec['compression']}"
        assert rec["reusable"] is False, "marked reusable without gate 5"
        assert rec["status"] == "failed_gate_2", rec["status"]
        # The bridge must populate the fixed failure enum (#32), not leave it null.
        assert rec["failure_mode"] == "degenerate_collapse", rec["failure_mode"]
    print("PASS: test_run_records_to_ledger_with_the_ledgers_own_rules")


def test_control_records_as_reusable():
    if not LEAN_AVAILABLE:
        print("SKIP: test_control_records_as_reusable (no lake)")
        return
    import tempfile, json as _json
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "candidates.jsonl"
        spec = H.Spec.load(SPECS / "control_valid.json")
        h = H.Harness(timeout=600)
        try:
            results = h.run(spec)
        finally:
            h.cleanup()
        H.record(spec, results, ledger)
        rec = _json.loads(ledger.read_text().strip())
        assert rec["reusable"] is True, \
            "a gate-5 survivor should be marked reusable"
        assert rec["status"] == "passed_gate_5", rec["status"]
    print("PASS: test_control_records_as_reusable")


def test_recording_declines_compression_for_a_failed_transfer():
    """A candidate that failed gate 3 cannot carry compression, even if offered."""
    if not LEAN_AVAILABLE:
        print("SKIP: test_recording_declines_compression_for_a_failed_transfer (no lake)")
        return
    import tempfile, json as _json
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "candidates.jsonl"
        spec = H.Spec.load(SPECS / "fixture_transfer_fails.json")
        h = H.Harness(timeout=600)
        try:
            results = h.run(spec)
        finally:
            h.cleanup()
        # Offer a compression number the caller should not get to record.
        H.record(spec, results, ledger, compression={"nodes_before": 10, "nodes_after": 3})
        rec = _json.loads(ledger.read_text().strip())
        assert rec["compression"] is None, (
            "compression was recorded despite gate 3 failing -- the bridge must "
            f"not forward it: {rec['compression']}")
    print("PASS: test_recording_declines_compression_for_a_failed_transfer")


# ---------------------------------------------------------------------------
# (#37) the batch runner
# ---------------------------------------------------------------------------

def _stub_discharge(monkeypatch_pass: bool, monkeypatch_ok: list):
    """Replace Harness.discharge so batch tests need no Lean toolchain.

    Records each label it was asked for in `monkeypatch_ok`, returns a fixed
    verdict. Keeps the batch tests independent of the toolchain while still
    exercising the real `run`/`run_one`/`cmd_batch` control flow.
    """
    def _fake(self, source, label):
        monkeypatch_ok.append(label)
        return monkeypatch_pass, "stub"
    return _fake


def _batch(target: str, ledger: str | None = None, as_json: bool = False) -> int:
    """Invoke the real `cmd_batch` with a parsed-args stand-in."""
    return H.cmd_batch(Namespace(batch=target, record=ledger, timeout=600,
                                 json=as_json))


def test_collect_specs_dir_glob_and_file():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "a.json").write_text("{}")
        (d / "b.json").write_text("{}")
        (d / "note.txt").write_text("x")
        names = [p.name for p in H.collect_specs(str(d))]
        assert names == ["a.json", "b.json"], names
        assert [p.name for p in H.collect_specs(str(d / "a.json"))] == ["a.json"]
        assert [p.name for p in H.collect_specs(str(d / "*.json"))] == ["a.json", "b.json"]
        assert H.collect_specs(str(d / "nope")) == [], "missing target must be empty"
    print("PASS: test_collect_specs_dir_glob_and_file")


def test_batch_records_every_spec_and_a_failure_does_not_abort():
    """A spec that FAILS a gate is data, not an error: batch continues, exit 0."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        ledger = d / "candidates.jsonl"
        # one passing spec, one failing spec -- both must be recorded.
        shutil.copy(SPECS / "control_valid.json", d / "control.json")
        shutil.copy(SPECS / "fixture_unit_collapse.json", d / "collapse.json")
        calls = []
        orig = H.Harness.discharge
        H.Harness.discharge = _stub_discharge(True, calls)
        try:
            rc = _batch(str(d), str(ledger))
        finally:
            H.Harness.discharge = orig
        assert rc == 0, f"batch exit code should be 0 even with a failing spec, got {rc}"
        rows = [json.loads(l) for l in ledger.read_text().splitlines()]
        ids = {r["candidate_id"] for r in rows}
        assert ids == {"C-CONTROL-VALID", "C-FIXTURE-UNIT-COLLAPSE"}, ids
        # The control spec has gates 1-3 plus a gate-5 obligation (4 Lean
        # discharges); the collapse fixture has gates 1-2 only (2). Total 6.
        assert len(calls) == 6, f"expected 6 Lean discharges, got {len(calls)}"
    print("PASS: test_batch_records_every_spec_and_a_failure_does_not_abort")


def test_batch_missing_target_is_a_usage_error():
    with tempfile.TemporaryDirectory() as td:
        rc = _batch(str(Path(td) / "no_such_dir"), None)
        assert rc == 2, f"a missing batch target must exit 2, got {rc}"
    print("PASS: test_batch_missing_target_is_a_usage_error")


def test_batch_malformed_spec_is_a_usage_error_but_others_still_run():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "broken.json").write_text("{ not json")
        shutil.copy(SPECS / "control_valid.json", d / "good.json")
        calls = []
        orig = H.Harness.discharge
        H.Harness.discharge = _stub_discharge(True, calls)
        try:
            rc = _batch(str(d), None)
        finally:
            H.Harness.discharge = orig
        assert rc == 2, f"a malformed spec must exit 2, got {rc}"
        assert calls, "the good spec must still have been run"
    print("PASS: test_batch_malformed_spec_is_a_usage_error_but_others_still_run")


def test_ledger_is_tracked_with_union_merge():
    """#37's VCS policy: the ledger is committed and appends are union-merged.

    The policy decision is that `axiom-rewrite/candidates.jsonl` is version-
    controlled (like `docs/decisions/LOG.md`), and `.gitattributes` gives it
    `merge=union` so two agents appending between the same commits compose instead
    of conflicting. This pins both halves, plus that the CLI's default ledger is
    that same path — a policy that named a different file would be no policy.
    """
    ga = REPO / ".gitattributes"
    assert ga.exists(), ".gitattributes must exist to carry the merge policy"
    rule = [l for l in ga.read_text().splitlines()
            if l.split("#")[0].strip().startswith("axiom-rewrite/candidates.jsonl")]
    assert rule, ".gitattributes must map the ledger"
    assert "merge=union" in rule[0], f"ledger must be merge=union: {rule[0]!r}"

    import candidates as C
    assert C.DEFAULT_LEDGER == HERE / "candidates.jsonl", C.DEFAULT_LEDGER
    # Committed, not gitignored: the reader must be able to verify "we tried this".
    assert C.DEFAULT_LEDGER.exists(), \
        "the ledger path must exist in the repo (tracked), not be generated"
    print("PASS: test_ledger_is_tracked_with_union_merge")


def main() -> int:
    tests = [
        test_spec_loads_and_reports_every_gate,
        test_every_gate_gets_a_verdict_and_obligation,
        test_unit_collapse_passes_gate1_fails_gate2,
        test_unit_collapse_is_rejected_overall,
        test_gate4_refuses_when_gate3_fails,
        test_gate4_refuses_when_gate3_absent,
        test_control_passes_all_gates,
        test_gate4_permits_after_gate3_passes,
        test_sorry_does_not_pass_a_gate,
        test_true_also_does_not_pass_when_obligation_is_false,
        test_run_records_to_ledger_with_the_ledgers_own_rules,
        test_control_records_as_reusable,
        test_recording_declines_compression_for_a_failed_transfer,
        # #37: the batch runner
        test_collect_specs_dir_glob_and_file,
        test_batch_records_every_spec_and_a_failure_does_not_abort,
        test_batch_missing_target_is_a_usage_error,
        test_batch_malformed_spec_is_a_usage_error_but_others_still_run,
        test_ledger_is_tracked_with_union_merge,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print()
    print("=" * 40)
    print(f"Tests: {passed} passed, {failed} failed")
    if not LEAN_AVAILABLE:
        print("(Lean unavailable -- gate-executing tests skipped)")
    print("=" * 40)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())