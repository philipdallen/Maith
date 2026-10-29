#!/usr/bin/env python3
"""Tests for phase-2 candidate dedup over elaborated phi terms (#97).

The DoD is one observable check: two candidate specs whose phi *text* differs but
which elaborate to structurally identical terms are reported as duplicates, and a
third genuinely different phi is reported as distinct. The first two tests are that
check; the rest cover the fixture-loading contract and the mode/invariance the
dedup inherits from phase 1.

Run: python3 python/test_structural_similarity_dedup.py
"""

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "python"))
sys.path.insert(0, str(REPO / "axiom-rewrite"))

import structural_similarity_dedup as dd  # noqa: E402

FIXTURES = REPO / "axiom-rewrite" / "fixtures" / "dedup"

_results = []


def check(name, cond, detail=""):
    _results.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" -- {detail}" if detail else ""))


def _load_all():
    return [dd.load_spec(p) for p in dd.collect_fixtures(FIXTURES)]


def test_duplicate_text_different_elaboration_is_caught():
    """DoD (a): two textually different phi's with the same elaborated term = dup."""
    specs = _load_all()
    a = next(s for s in specs if s.candidate_id == "C-DEDUP-A")
    b = next(s for s in specs if s.candidate_id == "C-DEDUP-B")
    check("duplicate phi text differs", a.phi != b.phi, f"{a.phi!r} vs {b.phi!r}")
    check("duplicate elaborated fingerprint matches",
          a.fingerprint().key() == b.fingerprint().key())
    dups = dd.duplicates(dd.dedup(specs))
    check("duplicate group reported",
          ["C-DEDUP-A", "C-DEDUP-B"] in dups, f"dups={dups}")


def test_genuinely_different_phi_is_distinct():
    """DoD (b): a genuinely different phi is NOT reported as a duplicate."""
    specs = _load_all()
    groups = dd.dedup(specs)
    dups = dd.duplicates(groups)
    check("distinct phi not in any duplicate group",
          all("C-DEDUP-DISTINCT" not in g for g in dups))
    check("distinct phi listed as distinct",
          "C-DEDUP-DISTINCT" in dd.distinct(groups))


def test_positional_index_and_binder_name_do_not_create_a_difference():
    """The duplicate pair differs in binder name, positional index and polarity."""
    specs = _load_all()
    a = next(s for s in specs if s.candidate_id == "C-DEDUP-A")
    b = next(s for s in specs if s.candidate_id == "C-DEDUP-B")
    # A's bound scope is "n", B's is "x"; A's term index is 0, B's is 3; B adds polarity.
    check("fingerprints equal despite naming/index/polarity differences",
          a.fingerprint() == b.fingerprint())


def test_operation_identity_change_breaks_the_duplicate():
    """Mutating the op identity of one duplicate must make it distinct.

    This is the mutation guard's in-process counterpart: the dedup is sensitive to
    the one axis that matters (which operation the phi applies).
    """
    specs = _load_all()
    b = next(s for s in specs if s.candidate_id == "C-DEDUP-B")
    mutated_graph = copy.deepcopy(b.phi_graph)
    mutated_graph["operations"][0]["op"] = "op:succ"
    mutated = dd.CandidatePhi(record=b.record, phi_graph=mutated_graph)
    a = next(s for s in specs if s.candidate_id == "C-DEDUP-A")
    check("changed op identity is no longer a duplicate",
          a.fingerprint().key() != mutated.fingerprint().key())


def test_fixture_must_be_a_candidate_record():
    """A fixture missing candidate fields is rejected, not silently accepted."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "bad.json"
        p.write_text(json.dumps({"candidate_id": "C-X", "phi_graph": {"entities": []}}))
        try:
            dd.load_spec(p)
            check("incomplete record rejected", False, "no FixtureError raised")
        except dd.FixtureError:
            check("incomplete record rejected", True)


def test_fixture_must_carry_phi_graph():
    """A fixture without `phi_graph` is rejected (phase 2 needs the elaborated term)."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "nograph.json"
        p.write_text(json.dumps({
            "candidate_id": "C-Y", "target_structure": "T", "domain": "D",
            "phi": "def phi := id", "provenance": "test",
        }))
        try:
            dd.load_spec(p)
            check("missing phi_graph rejected", False, "no FixtureError raised")
        except dd.FixtureError:
            check("missing phi_graph rejected", True)


def test_dedup_run_records_ledger_with_coverage():
    """DoD (#114): a synthetic dedup run is recorded in the ledger with coverage.

    The dedup verdict must become ledger state readable back through
    `candidates.py` -- not just fixture output. Recording twice is refused, because
    the ledger is append-only.
    """
    import tempfile
    import candidates as cand_mod
    with tempfile.TemporaryDirectory() as td:
        led = Path(td) / "candidates.jsonl"
        specs = _load_all()
        groups = dd.dedup(specs)
        written = dd.record_dedup(specs, groups, led)
        check("all fixtures recorded", written == len(specs), f"wrote {written}")

        recs = {c.candidate_id: c for c in cand_mod.read_ledger(led)}
        check("ledger holds every fixture",
              set(recs) == {"C-DEDUP-A", "C-DEDUP-B", "C-DEDUP-DISTINCT"})
        check("duplicate verdict recorded on both members",
              "duplicate group C-DEDUP-A = C-DEDUP-B" in recs["C-DEDUP-A"].note
              and "duplicate group C-DEDUP-A = C-DEDUP-B" in recs["C-DEDUP-B"].note)
        check("distinct verdict recorded",
              "dedup: distinct" in recs["C-DEDUP-DISTINCT"].note)

        rows = cand_mod.coverage(led)
        check("coverage map derives one domain row",
              len(rows) == 1 and rows[0]["attempts"] == 3, f"rows={rows}")

        try:
            dd.record_dedup(specs, groups, led)
            check("re-recording refused (append-only)", False, "no LedgerError raised")
        except cand_mod.LedgerError:
            check("re-recording refused (append-only)", True)


def main() -> int:
    test_duplicate_text_different_elaboration_is_caught()
    test_genuinely_different_phi_is_distinct()
    test_positional_index_and_binder_name_do_not_create_a_difference()
    test_operation_identity_change_breaks_the_duplicate()
    test_fixture_must_be_a_candidate_record()
    test_fixture_must_carry_phi_graph()
    test_dedup_run_records_ledger_with_coverage()
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = len(_results) - passed
    print("\n" + "=" * 40)
    print(f"Tests: {passed} passed, {failed} failed")
    print("=" * 40)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
