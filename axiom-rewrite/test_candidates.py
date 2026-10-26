#!/usr/bin/env python3
"""Tests for the axiom-discovery candidate ledger + coverage map (issue #27).

Covers the DoD explicitly: append-only semantics, round-trip, CLI. Plus the two
gate rules from AXIOM_DISCOVERY.md §Validation pipeline, which are the reason this
module validates rather than merely stores.

Run: python3 axiom-rewrite/test_candidates.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from candidates import (  # noqa: E402
    Candidate, LedgerError, append_candidate, read_ledger, next_candidate_id,
    coverage, DEFAULT_LEDGER, FAILURE_MODES, VALID_FAILURE_MODES,
)

REPO = HERE.parent
SCRIPT = HERE / "candidates.py"


def _mk(cid="C-001", gates=None, compression=None, reusable=False, domain="decl_a",
        failure_mode="derive"):
    """Build a candidate, deriving `failure_mode` from the first failed gate.

    `failure_mode="derive"` (the default) mirrors what the CLI does, so tests that
    predate #32 keep working. Pass an explicit value (including `None`) to test
    the failure_mode rules themselves.
    """
    gates = gates or {}
    if failure_mode == "derive":
        failed = sorted(g for g, o in gates.items() if o == "fail")
        failure_mode = FAILURE_MODES.get(failed[0]) if failed else None
    return Candidate(
        candidate_id=cid,
        target_structure="Group",
        domain=domain,
        phi="def phi := ...",
        provenance="homomorphic-first heuristic",
        gates=gates,
        compression=compression,
        reusable=reusable,
        failure_mode=failure_mode,
    )


# ---------------------------------------------------------------------------
# Round-trip + append-only
# ---------------------------------------------------------------------------

def test_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "candidates.jsonl"
        c = _mk(gates={1: "pass", 2: "pass", 3: "pass"},
                compression={"nodes_before": 10, "nodes_after": 7})
        append_candidate(p, c)
        back = read_ledger(p)
        assert len(back) == 1, f"expected 1 record, got {len(back)}"
        r = back[0]
        assert r.candidate_id == "C-001"
        assert r.gates == {1: "pass", 2: "pass", 3: "pass"}, r.gates
        assert r.compression == {"nodes_before": 10, "nodes_after": 7}
        assert r.status == "passed_gate_3", r.status
    print("PASS: test_round_trip")


def test_append_only_preserves_prior_lines():
    """Appending must not rewrite earlier records — byte-for-byte."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "candidates.jsonl"
        append_candidate(p, _mk("C-001", gates={1: "pass"}))
        first = p.read_bytes()
        append_candidate(p, _mk("C-002", gates={1: "pass", 2: "fail"}))
        after = p.read_bytes()
        assert after.startswith(first), "earlier bytes were modified"
        assert len(read_ledger(p)) == 2
    print("PASS: test_append_only_preserves_prior_lines")


def test_failed_candidates_are_kept():
    """A failed candidate stays in the ledger — the search history is data."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "candidates.jsonl"
        append_candidate(p, _mk("C-001", gates={1: "fail"}))
        append_candidate(p, _mk("C-002", gates={1: "pass", 2: "fail"}))
        recs = read_ledger(p)
        assert len(recs) == 2, "failed candidates must not be dropped"
        assert {r.candidate_id for r in recs} == {"C-001", "C-002"}
    print("PASS: test_failed_candidates_are_kept")


def test_duplicate_id_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "candidates.jsonl"
        append_candidate(p, _mk("C-001"))
        try:
            append_candidate(p, _mk("C-001"))
        except LedgerError:
            print("PASS: test_duplicate_id_rejected")
            return
        raise AssertionError("duplicate id was accepted")


def test_next_candidate_id_sequential():
    a = _mk("C-001")
    b = _mk("C-002")
    assert next_candidate_id([a, b]) == "C-003"
    assert next_candidate_id([]) == "C-001"
    print("PASS: test_next_candidate_id_sequential")


# ---------------------------------------------------------------------------
# Gate rules (the load-bearing validation)
# ---------------------------------------------------------------------------

def test_compression_requires_gate3():
    """Compression recorded without passing the transfer gate must be REJECTED."""
    try:
        _mk(gates={1: "pass", 2: "pass", 3: "fail"},
            compression={"nodes_before": 10, "nodes_after": 7}).validate()
    except LedgerError:
        print("PASS: test_compression_requires_gate3")
        return
    raise AssertionError("compression accepted for a candidate that failed gate 3")


def test_compression_allowed_after_gate3():
    _mk(gates={1: "pass", 2: "pass", 3: "pass"},
        compression={"nodes_before": 10, "nodes_after": 7}).validate()
    print("PASS: test_compression_allowed_after_gate3")


def test_reusable_requires_gate5():
    """`reusable` without the breadth check must be REJECTED."""
    try:
        _mk(gates={1: "pass", 2: "pass", 3: "pass"}, reusable=True).validate()
    except LedgerError:
        print("PASS: test_reusable_requires_gate5")
        return
    raise AssertionError("reusable accepted without gate 5")


def test_reusable_allowed_after_gate5():
    _mk(gates={1: "pass", 2: "pass", 3: "pass", 5: "pass"}, reusable=True).validate()
    print("PASS: test_reusable_allowed_after_gate5")


def test_ordered_pipeline_enforced():
    """Cannot pass a later gate while an earlier one failed."""
    try:
        _mk(gates={1: "fail", 3: "pass"}).validate()
    except LedgerError:
        print("PASS: test_ordered_pipeline_enforced")
        return
    raise AssertionError("out-of-order gates accepted")


def test_invalid_gate_and_outcome_rejected():
    for bad in ({6: "pass"}, {1: "maybe"}):
        try:
            _mk(gates=bad).validate()
        except LedgerError:
            continue
        raise AssertionError(f"invalid gates accepted: {bad}")
    print("PASS: test_invalid_gate_and_outcome_rejected")


# ---------------------------------------------------------------------------
# failure_mode enum (issue #32)
# ---------------------------------------------------------------------------

def test_failure_mode_required_on_failure():
    """A failed gate with no failure_mode must be REJECTED (else it drifts to
    free text / omission, which is the whole reason the field is an enum)."""
    try:
        _mk(gates={1: "fail"}, failure_mode=None).validate()
    except LedgerError:
        print("PASS: test_failure_mode_required_on_failure")
        return
    raise AssertionError("a failed candidate was accepted with no failure_mode")


def test_failure_mode_keyed_to_first_failed_gate():
    """The mode names the FIRST failure: the pipeline is admission-controlled."""
    assert _mk(gates={2: "fail"}, failure_mode=None).expected_failure_mode == \
        "degenerate_collapse"
    assert _mk(gates={3: "fail"}, failure_mode=None).expected_failure_mode == \
        "target_too_weak"
    assert _mk(gates={5: "fail"}, failure_mode=None).expected_failure_mode == \
        "no_replication"
    assert _mk(gates={1: "fail"}, failure_mode=None).expected_failure_mode == \
        "not_homomorphism"
    print("PASS: test_failure_mode_keyed_to_first_failed_gate")


def test_failure_mode_mismatch_rejected():
    """A mode that disagrees with the first failed gate must be REJECTED."""
    try:
        _mk(gates={3: "fail"}, failure_mode="not_homomorphism").validate()
    except LedgerError:
        print("PASS: test_failure_mode_mismatch_rejected")
        return
    raise AssertionError("a failure_mode inconsistent with the failed gate was accepted")


def test_failure_mode_forbidden_without_failure():
    """A passing candidate must NOT carry a failure_mode."""
    try:
        _mk(gates={1: "pass", 2: "pass", 3: "pass"},
            failure_mode="target_too_weak").validate()
    except LedgerError:
        print("PASS: test_failure_mode_forbidden_without_failure")
        return
    raise AssertionError("failure_mode accepted on a candidate with no failed gate")


def test_failure_mode_free_text_rejected():
    """Only the fixed enum values are allowed — free text defeats groupability."""
    try:
        _mk(gates={2: "fail"}, failure_mode="it just didn't work").validate()
    except LedgerError:
        print("PASS: test_failure_mode_free_text_rejected")
        return
    raise AssertionError("free-text failure_mode was accepted")


def test_gate4_is_non_failing():
    """Gate 4 is bookkeeping and must never be recorded as `fail` (#32)."""
    try:
        _mk(gates={1: "pass", 2: "pass", 3: "pass", 4: "fail"}).validate()
    except LedgerError:
        print("PASS: test_gate4_is_non_failing")
        return
    raise AssertionError("gate 4 accepted as `fail` despite being non-failing")


def test_failure_mode_round_trips():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "candidates.jsonl"
        append_candidate(p, _mk("C-001", gates={1: "pass", 2: "fail"}))
        back = read_ledger(p)
        assert back[0].failure_mode == "degenerate_collapse", back[0].failure_mode
    print("PASS: test_failure_mode_round_trips")


def test_cli_derives_failure_mode_on_failure():
    """The CLI records the mode without the caller naming it (it is derivable),
    and stats groups by it — the observable payoff of the enum."""
    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "c.jsonl"

        def run(*args):
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--ledger", str(ledger), *args],
                capture_output=True, text=True, cwd=str(REPO),
            )

        r = run("add", "--target-structure", "Group", "--domain", "d", "--phi", "p",
                "--provenance", "prov", "--gate", "1=pass", "--gate", "2=fail")
        assert r.returncode == 0, r.stderr
        rec = json.loads(ledger.read_text().strip())
        assert rec["failure_mode"] == "degenerate_collapse", rec

        r = run("list")
        assert "degenerate_collapse" in r.stdout, r.stdout

        r = run("stats")
        assert r.returncode == 0 and "degenerate_collapse: 1" in r.stdout, r.stdout

        # An explicit mode that contradicts the failed gate is rejected.
        r = run("add", "--target-structure", "Group", "--domain", "d", "--phi", "p",
                "--provenance", "prov", "--gate", "3=fail",
                "--failure-mode", "not_homomorphism")
        assert r.returncode != 0 and "REJECTED" in r.stderr, (r.returncode, r.stderr)
    print("PASS: test_cli_derives_failure_mode_on_failure")


def test_required_fields():
    for missing in ("target_structure", "domain", "phi", "provenance"):
        c = _mk()
        setattr(c, missing, "")
        try:
            c.validate()
        except LedgerError:
            continue
        raise AssertionError(f"empty {missing} accepted")
    print("PASS: test_required_fields")


def test_failed_rejected_by_cli_nonzero():
    """The CLI must exit nonzero rather than write a violating record."""
    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "c.jsonl"
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--ledger", str(ledger), "add",
             "--target-structure", "Group", "--domain", "d", "--phi", "p",
             "--provenance", "prov",
             "--gate", "3=fail",
             "--compression", '{"nodes_before":1,"nodes_after":1}'],
            capture_output=True, text=True, cwd=str(REPO),
        )
        assert r.returncode != 0, "CLI accepted a violating record"
        assert "REJECTED" in r.stderr, r.stderr
        assert not ledger.exists() or ledger.read_text().strip() == "", \
            "violating record was written"
    print("PASS: test_failed_rejected_by_cli_nonzero")


# ---------------------------------------------------------------------------
# Coverage map
# ---------------------------------------------------------------------------

def test_coverage_counts_and_unattempted():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "candidates.jsonl"
        append_candidate(p, _mk("C-001", domain="decl_a", gates={1: "pass", 2: "pass", 3: "pass"}))
        append_candidate(p, _mk("C-002", domain="decl_a", gates={1: "pass", 2: "fail"}))
        append_candidate(p, _mk("C-003", domain="decl_b", gates={1: "fail"}))
        rows = coverage(p, domains=["decl_a", "decl_b", "decl_unattempted"])
        by = {r["domain"]: r for r in rows}
        assert by["decl_a"]["attempts"] == 2, by["decl_a"]
        assert by["decl_a"]["passed_gate3"] == 1
        assert by["decl_a"]["failed"] == 1
        assert by["decl_b"]["attempts"] == 1
        assert by["decl_unattempted"]["attempts"] == 0, \
            "declaration with no attempts must appear (that is the point of the map)"
        # Sorted least-attempted first so under-explored work surfaces.
        assert rows[0]["domain"] == "decl_unattempted", rows
    print("PASS: test_coverage_counts_and_unattempted")


def test_coverage_gate5_survivors():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "candidates.jsonl"
        append_candidate(p, _mk("C-001", gates={1: "pass", 2: "pass", 3: "pass", 5: "pass"},
                                reusable=True))
        rows = coverage(p)
        assert rows[0]["passed_gate5"] == 1, rows
    print("PASS: test_coverage_gate5_survivors")


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------

def test_cli_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "c.jsonl"
        doms = Path(tmp) / "domains.txt"
        doms.write_text("decl_a\ndecl_b\n")

        def run(*args):
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--ledger", str(ledger), *args],
                capture_output=True, text=True, cwd=str(REPO),
            )

        r = run("add", "--target-structure", "Lattice", "--domain", "decl_a",
                "--phi", "def phi := ...", "--provenance", "recursive bias",
                "--gate", "1=pass", "--gate", "2=pass", "--gate", "3=pass",
                "--compression", '{"nodes_before":9,"nodes_after":6}')
        assert r.returncode == 0, r.stderr
        assert "C-001" in r.stdout, r.stdout

        r = run("list")
        assert r.returncode == 0 and "Lattice" in r.stdout, r.stdout
        assert "passed_gate_3" in r.stdout, r.stdout

        r = run("list", "--json")
        assert r.returncode == 0
        assert json.loads(r.stdout)[0]["candidate_id"] == "C-001"

        r = run("coverage", "--domains", str(doms))
        assert r.returncode == 0, r.stderr
        assert "decl_b" in r.stdout, "unattempted declaration missing from output"
        assert "no attempts" in r.stdout, r.stdout

        r = run("stats")
        assert r.returncode == 0 and "candidates: 1" in r.stdout, r.stdout

        # Empty-ledger paths must not crash.
        ledger2 = Path(tmp) / "empty.jsonl"
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--ledger", str(ledger2), "list"],
            capture_output=True, text=True, cwd=str(REPO))
        assert r.returncode == 0 and "empty" in r.stdout, r.stdout
    print("PASS: test_cli_end_to_end")


def main():
    tests = [
        test_round_trip,
        test_append_only_preserves_prior_lines,
        test_failed_candidates_are_kept,
        test_duplicate_id_rejected,
        test_next_candidate_id_sequential,
        test_compression_requires_gate3,
        test_compression_allowed_after_gate3,
        test_reusable_requires_gate5,
        test_reusable_allowed_after_gate5,
        test_ordered_pipeline_enforced,
        test_invalid_gate_and_outcome_rejected,
        test_failure_mode_required_on_failure,
        test_failure_mode_keyed_to_first_failed_gate,
        test_failure_mode_mismatch_rejected,
        test_failure_mode_forbidden_without_failure,
        test_failure_mode_free_text_rejected,
        test_gate4_is_non_failing,
        test_failure_mode_round_trips,
        test_cli_derives_failure_mode_on_failure,
        test_required_fields,
        test_failed_rejected_by_cli_nonzero,
        test_coverage_counts_and_unattempted,
        test_coverage_gate5_survivors,
        test_cli_end_to_end,
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
    print("=" * 40)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())