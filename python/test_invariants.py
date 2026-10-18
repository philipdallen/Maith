#!/usr/bin/env python3
"""
test_invariants.py — Tests for check_invariants.py.

Confirms the invariant checker passes on valid fixtures and fails on
intentionally-broken ones. Each test corresponds to a real bug class.

Run: python3 python/test_invariants.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO = Path(__file__).resolve().parent.parent
from check_invariants import (
    check_split_integrity,
    check_variant_input_consistency,
    check_vocab_range,
    check_checkpoint_results_consistency,
    check_comparison_validity,
    check_provenance_hash,
    check_grammar_arity,
    check_c1_polarity_absence,
    COMPARISON_CLAIMS,
)
from manifest import (
    write_dataset_manifest, write_results_manifest, write_checkpoint_manifest,
    verify_manifest, expected_source_for_variant,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_dataset(path: Path, variant: str, n_train: int = 10, n_eval: int = 5):
    """Create a valid dataset JSONL with correct source field.

    example_id is the SAME across variants (the invariant: all variants evaluate
    the same declarations) — only source and input_ids differ per variant.
    """
    def _row(i, split):
        return {
            "source": variant,
            "representation_id": "semantic_graph_ir_v2_0_0",
            "example_id": f"Test.Mod::DECL_{split}_{i}",  # same across variants
            "name": f"DECL_{split}_{i}",
            "module": f"Test.Mod",
            "input_ids": [i % 100, (i + 1) % 100, (i + 2) % 100],
            "labels": [0, 1, 2],
            "seq_len": 3,
        }
    with open(path / f"train_{variant}.jsonl", "w") as f:
        for i in range(n_train):
            f.write(json.dumps(_row(i, "train")) + "\n")
    with open(path / f"eval_{variant}.jsonl", "w") as f:
        for i in range(n_eval):
            f.write(json.dumps(_row(i, "eval")) + "\n")


def _make_broken_source_dataset(path: Path, variant: str):
    """Create a dataset where the source field doesn't match the variant."""
    with open(path / f"train_{variant}.jsonl", "w") as f:
        for i in range(3):
            f.write(json.dumps({
                "source": "WRONG_VARIANT",
                "representation_id": "semantic_graph_ir_v2_0_0",
                "example_id": f"Test.Mod::{variant}_train_{i}",
                "name": f"{variant}_train_{i}",
                "module": "Test.Mod",
                "input_ids": [1, 2, 3],
                "labels": [0, 1, 2],
                "seq_len": 3,
            }) + "\n")


def _make_overlap_dataset(path: Path, variant: str):
    """Create a dataset where train and eval overlap by example_id."""
    shared_id = f"Test.Mod::SHARED_DECL"
    for split, n in [("train", 10), ("eval", 5)]:
        with open(path / f"{split}_{variant}.jsonl", "w") as f:
            # First row is shared
            f.write(json.dumps({
                "source": variant,
                "representation_id": "semantic_graph_ir_v2_0_0",
                "example_id": shared_id,
                "name": "SHARED_DECL",
                "module": "Test.Mod",
                "input_ids": [1, 2, 3],
                "labels": [0, 1, 2],
                "seq_len": 3,
            }) + "\n")
            for i in range(n - 1):
                f.write(json.dumps({
                    "source": variant,
                    "representation_id": "semantic_graph_ir_v2_0_0",
                    "example_id": f"Test.Mod::{variant}_{split}_{i}",
                    "name": f"{variant}_{split}_{i}",
                    "module": "Test.Mod",
                    "input_ids": [1, 2, 3],
                    "labels": [0, 1, 2],
                    "seq_len": 3,
                }) + "\n")


def _make_out_of_vocab_dataset(path: Path, variant: str, vocab_size: int):
    """Create a dataset with input_ids exceeding vocab_size."""
    with open(path / f"train_{variant}.jsonl", "w") as f:
        for i in range(3):
            f.write(json.dumps({
                "source": variant,
                "representation_id": "semantic_graph_ir_v2_0_0",
                "example_id": f"Test.Mod::{variant}_train_{i}",
                "name": f"{variant}_train_{i}",
                "module": "Test.Mod",
                "input_ids": [vocab_size + 100],  # out of range
                "labels": [0],
                "seq_len": 1,
            }) + "\n")
    with open(path / f"eval_{variant}.jsonl", "w") as f:
        for i in range(2):
            f.write(json.dumps({
                "source": variant,
                "representation_id": "semantic_graph_ir_v2_0_0",
                "example_id": f"Test.Mod::{variant}_eval_{i}",
                "name": f"{variant}_eval_{i}",
                "module": "Test.Mod",
                "input_ids": [1, 2],
                "labels": [0, 1],
                "seq_len": 2,
            }) + "\n")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_split_integrity_passes():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _make_dataset(tmp, "A")
        _make_dataset(tmp, "B")
        results = check_split_integrity(tmp, ["A", "B"])
        failures = [r for r in results if r["passed"] is False]
        assert not failures, f"Expected pass, got failures: {failures}"
    print("PASS: test_split_integrity_passes")


def test_split_integrity_catches_overlap():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _make_overlap_dataset(tmp, "A")
        results = check_split_integrity(tmp, ["A"])
        overlap_checks = [r for r in results if "disjoint" in r["name"]]
        failures = [r for r in overlap_checks if r["passed"] is False]
        assert failures, "Expected failure on overlapping split, but all passed"
    print("PASS: test_split_integrity_catches_overlap")


def test_variant_input_passes():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _make_dataset(tmp, "A")
        results = check_variant_input_consistency(tmp, "A")
        failures = [r for r in results if r["passed"] is False]
        assert not failures, f"Expected pass, got failures: {failures}"
    print("PASS: test_variant_input_passes")


def test_variant_input_catches_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _make_broken_source_dataset(tmp, "A")
        # need eval file too
        with open(tmp / "eval_A.jsonl", "w") as f:
            for i in range(2):
                f.write(json.dumps({
                    "source": "WRONG_VARIANT",
                    "representation_id": "semantic_graph_ir_v2_0_0",
                    "example_id": f"Test.Mod::A_eval_{i}",
                    "name": f"A_eval_{i}",
                    "module": "Test.Mod",
                    "input_ids": [1, 2],
                    "labels": [0, 1],
                    "seq_len": 2,
                }) + "\n")
        results = check_variant_input_consistency(tmp, "A")
        failures = [r for r in results if r["passed"] is False]
        assert failures, "Expected failure on source mismatch, but all passed"
    print("PASS: test_variant_input_catches_mismatch")


def test_vocab_range_passes():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _make_dataset(tmp, "A")
        # input_ids are [i%100, (i+1)%100, (i+2)%100] — all < 101
        results = check_vocab_range(tmp, "A", vocab_size=101)
        failures = [r for r in results if r["passed"] is False]
        assert not failures, f"Expected pass, got failures: {failures}"
    print("PASS: test_vocab_range_passes")


def test_vocab_range_catches_out_of_range():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _make_out_of_vocab_dataset(tmp, "A", vocab_size=100)
        results = check_vocab_range(tmp, "A", vocab_size=100)
        failures = [r for r in results if r["passed"] is False]
        assert failures, "Expected failure on out-of-range ids, but all passed"
    print("PASS: test_vocab_range_catches_out_of_range")


def test_comparison_validity_matched_size():
    m_a = {
        "artifact_type": "results", "variant": "A",
        "representation_id": "semantic_graph_ir_v2_0_0",
        "source_input": "ir_tokens", "seed": 42, "epochs": 2,
        "train_examples": 3491, "eval_examples": 388,
    }
    m_bsmall = {
        "artifact_type": "results", "variant": "B_small",
        "representation_id": "semantic_graph_ir_v2_0_0",
        "source_input": "bpe_601", "seed": 42, "epochs": 2,
        "train_examples": 3491, "eval_examples": 388,
    }
    results = check_comparison_validity([m_a, m_bsmall], "representation_at_matched_size")
    failures = [r for r in results if r["passed"] is False]
    assert not failures, f"Expected pass for matched-size comparison, got: {failures}"
    print("PASS: test_comparison_validity_matched_size")


def test_comparison_validity_catches_epoch_mismatch():
    m_a = {
        "artifact_type": "results", "variant": "A",
        "representation_id": "semantic_graph_ir_v2_0_0",
        "source_input": "ir_tokens", "seed": 42, "epochs": 2,
        "train_examples": 3491, "eval_examples": 388,
    }
    m_b = {
        "artifact_type": "results", "variant": "B",
        "representation_id": "semantic_graph_ir_v2_0_0",
        "source_input": "bpe_full", "seed": 42, "epochs": 3,  # EPOCH MISMATCH
        "train_examples": 3491, "eval_examples": 388,
    }
    results = check_comparison_validity([m_a, m_b], "representation_at_matched_size")
    failures = [r for r in results if r["passed"] is False]
    assert failures, "Expected failure on epoch mismatch (2 vs 3), but comparison passed"
    print("PASS: test_comparison_validity_catches_epoch_mismatch")


# ---------------------------------------------------------------------------
# Invariant 5 fixtures — one per declared comparison constraint
# ---------------------------------------------------------------------------
#
# Issue #22: the checker declares five `must_match` fields but only the `epochs`
# axis had a failing fixture, so four constraints (and both `must_differ`
# directions) were asserted by code nobody had proven *can* fail. These fixtures
# close that.
#
# _MISMATCH holds a differing value per field. The per-claim test mutates one
# field at a time and asserts the checker fires AND names the field — with an
# unmutated control so a fixture cannot pass vacuously.

_MISMATCH = {
    "representation_id": "semantic_graph_ir_v9_9_9",
    "seed": 7,
    "train_examples": 3000,
    "eval_examples": 100,
    "epochs": 3,
}


def _base_result(variant, source_input, **overrides):
    """A results manifest with the project's real values (datasets/representation_manifest.json)."""
    m = {
        "artifact_type": "results", "variant": variant,
        "representation_id": "semantic_graph_ir_v2_1_1",
        "source_input": source_input, "seed": 42, "epochs": 2,
        "train_examples": 3375, "eval_examples": 376,
    }
    m.update(overrides)
    return m


def _valid_pair(claim):
    """Two manifests that satisfy `claim` — the control pair for mutation."""
    spec = COMPARISON_CLAIMS[claim]
    a = _base_result("A", "ir_tokens")
    b_source = "bpe_601" if "source_input" in spec["must_differ"] else "ir_tokens"
    b = _base_result("B_small", b_source)
    return a, b


def test_comparison_validity_catches_each_must_match_field():
    """One fixture per must_match field, per claim — and the control passes."""
    for claim in COMPARISON_CLAIMS:
        a, b = _valid_pair(claim)
        control = [r for r in check_comparison_validity([a, b], claim) if r["passed"] is False]
        assert not control, f"{claim}: control pair should PASS, got {control}"

        for field in COMPARISON_CLAIMS[claim]["must_match"]:
            am, bm = _valid_pair(claim)
            bm[field] = _MISMATCH[field]
            failures = [r for r in check_comparison_validity([am, bm], claim)
                        if r["passed"] is False]
            assert failures, f"{claim}: {field} mismatch was NOT caught"
            assert any(field in r["detail"] for r in failures), \
                f"{claim}: {field} mismatch caught but not named: {failures}"
    print("PASS: test_comparison_validity_catches_each_must_match_field")


def test_comparison_validity_catches_must_differ_violation():
    """`must_differ` must fire when the field is identical across manifests."""
    checked = 0
    for claim in COMPARISON_CLAIMS:
        for field in COMPARISON_CLAIMS[claim]["must_differ"]:
            a, b = _valid_pair(claim)
            b[field] = a[field]  # collapse the required difference
            failures = [r for r in check_comparison_validity([a, b], claim)
                        if r["passed"] is False]
            assert failures, f"{claim}: identical {field} was NOT caught"
            checked += 1
    assert checked, "no must_differ fields to check — fixture is vacuous"
    print("PASS: test_comparison_validity_catches_must_differ_violation")


def test_comparison_validity_missing_field_is_lenient():
    """A field absent from one manifest is ignored (deliberate leniency for older
    results.json files). Pinned so the leniency is not 'fixed' away."""
    a, b = _valid_pair("representation_at_matched_size")
    b["seed"] = None
    res = check_comparison_validity([a, b], "representation_at_matched_size")
    failures = [r for r in res if r["passed"] is False]
    assert not failures, f"one-sided None should be lenient, got {failures}"
    print("PASS: test_comparison_validity_missing_field_is_lenient")


def test_comparison_validity_catches_heterogeneous_mismatch():
    """[42, 7, None]: None present AND >=2 distinct non-None values -> fail."""
    a, b = _valid_pair("representation_at_matched_size")
    b["seed"] = 7
    c = _base_result("C", "ast_split", seed=None)
    failures = [r for r in check_comparison_validity([a, b, c], "representation_at_matched_size")
                if r["passed"] is False]
    assert failures, "heterogeneous [42, 7, None] seed was NOT caught"
    print("PASS: test_comparison_validity_catches_heterogeneous_mismatch")


def test_comparison_claims_all_constraints_exercised():
    """Every declared constraint has a fixture, pinned PER CLAIM in both directions.

    Mutation-tested: pinning only the *union* of constraints lets a field be
    silently dropped from one claim while surviving in another. The per-claim pin
    below catches that. It fails if a constraint is added (no fixture) or removed
    (fixture orphaned) for any claim — so the contract cannot change silently.

    This matters because COMPARISON_CLAIMS is exactly what someone would edit to
    make a failing comparison "pass". Weakening an invariant now fails loudly here
    instead of silently accepting a confounded comparison.
    """
    expected = {
        "representation_at_matched_size": (
            ["representation_id", "seed", "train_examples", "eval_examples", "epochs"],
            ["source_input"],
        ),
        "representation_vs_full_bpe": (
            ["representation_id", "seed", "train_examples", "eval_examples"],
            ["source_input"],
        ),
        "ir_vs_flat_ablation": (
            ["representation_id", "seed", "train_examples", "eval_examples", "epochs"],
            [],
        ),
    }

    got = {k: (v["must_match"], v["must_differ"]) for k, v in COMPARISON_CLAIMS.items()}
    assert got == expected, (
        "COMPARISON_CLAIMS changed. If intentional, update this pin AND add the "
        f"matching fixture in _MISMATCH.\n  expected: {expected}\n  got:      {got}"
    )

    # Every pinned must_match field needs a mutation value in _MISMATCH.
    # (must_differ fields are exercised by collapsing them, not by a value table,
    # so they are covered by test_comparison_validity_catches_must_differ_violation.)
    needed = {f for mm, _md in got.values() for f in mm}
    missing = needed - set(_MISMATCH)
    assert not missing, f"pinned must_match constraints with no fixture value: {sorted(missing)}"

    # And every must_differ field must actually be declared somewhere, so the
    # collapse fixture is not vacuous.
    differ_fields = {f for _mm, md in got.values() for f in md}
    assert differ_fields, "no must_differ constraints declared — collapse fixture is vacuous"
    print("PASS: test_comparison_claims_all_constraints_exercised")



# ---------------------------------------------------------------------------
# Invariants 8 + 9 fixtures (issue #23)
# ---------------------------------------------------------------------------
# ENCODER_FORMAT.md states the token grammar and C1 (polarity absence) in prose.
# These fixtures prove the invariant checks can FAIL, not merely pass.

def _write_ir_dataset(tmp: Path, tokens: list[str], variant: str = "A",
                      vocab: dict | None = None):
    """Write a minimal IR dataset whose input_ids decode to `tokens`."""
    if vocab is None:
        base = sorted(set(tokens))
        vocab = {tok: i for i, tok in enumerate(base)}
    ids = [vocab[t] for t in tokens]
    (tmp / f"vocab_{variant}.json").write_text(json.dumps(vocab))
    for split in ("train", "eval"):
        (tmp / f"{split}_{variant}.jsonl").write_text(
            json.dumps({
                "source": "A", "representation_id": "semantic_graph_ir_v2_0_0",
                "example_id": f"{split}_0", "name": "t", "module": "M",
                "input_ids": ids, "labels": ids, "seq_len": len(ids),
            }) + "\n"
        )
    return vocab


_VALID_GRAPH = ["GRAPH_BEGIN", "E", "FVAR_0", "R", "FVAR_0", "TERM_0", "eq",
                "O", "IN_1", "OUT_0", "neg", "GRAPH_END"]


def test_grammar_arity_passes_on_valid_graph():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_ir_dataset(tmp, _VALID_GRAPH)
        res = check_grammar_arity(tmp)
        assert res, "no results produced"
        bad = [r for r in res if r["passed"] is False]
        assert not bad, f"valid graph rejected: {bad}"
    print("PASS: test_grammar_arity_passes_on_valid_graph")


def test_grammar_arity_catches_each_break():
    """One fixture per grammar break the doc specifies."""
    cases = {
        "missing GRAPH_BEGIN": ["E", "FVAR_0", "GRAPH_END"],
        "missing GRAPH_END": ["GRAPH_BEGIN", "E", "FVAR_0"],
        "bad row header": ["GRAPH_BEGIN", "X", "FVAR_0", "GRAPH_END"],
        "A-row wrong arity": ["GRAPH_BEGIN", "A", "FVAR_0", "typeclass", "GRAPH_END"],
        "R-row wrong arity": ["GRAPH_BEGIN", "R", "FVAR_0", "GRAPH_END"],
        "O-row bad arity token": ["GRAPH_BEGIN", "O", "TWO", "OUT_0", "neg", "GRAPH_END"],
        "O-row arity over cap": ["GRAPH_BEGIN", "O", "IN_10", "OUT_0", "neg", "GRAPH_END"],
        "O-row bad output token": ["GRAPH_BEGIN", "O", "IN_1", "OUTPUT_0", "neg", "GRAPH_END"],
        "O-row output over cap": ["GRAPH_BEGIN", "O", "IN_1", "OUT_64", "neg", "GRAPH_END"],
    }
    for label, toks in cases.items():
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _write_ir_dataset(tmp, toks)
            res = check_grammar_arity(tmp)
            bad = [r for r in res if r["passed"] is False]
            assert bad, f"grammar break NOT caught: {label}"
    print(f"PASS: test_grammar_arity_catches_each_break ({len(cases)} breaks)")


def test_grammar_arity_ignores_non_ir_variants():
    """B_small (BPE) and flat (SLOT) must NOT be checked against the IR grammar.

    Regression guard for the category error found when these invariants were first
    run: they reported 10114 and 103096 spurious 'malformed' graphs.
    """
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_ir_dataset(tmp, _VALID_GRAPH, variant="A")
        # A BPE-ish dataset that is NOT IR: no GRAPH_BEGIN, arbitrary ids.
        (tmp / "vocab_B_small.json").write_text(json.dumps({"x": 0}))
        for split in ("train", "eval"):
            (tmp / f"{split}_B_small.jsonl").write_text(
                json.dumps({"source": "B_small", "example_id": f"{split}_0",
                            "input_ids": [0, 0, 0]}) + "\n")
        res = check_grammar_arity(tmp)
        names = [r["name"] for r in res]
        assert not any("B_small" in n for n in names),             f"non-IR variant was checked against the IR grammar: {names}"
    print("PASS: test_grammar_arity_ignores_non_ir_variants")


def test_c1_polarity_passes_with_arithmetic_neg():
    """The trap: `neg` as an ARITHMETIC op in an O row is legitimate under C1."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write_ir_dataset(tmp, _VALID_GRAPH)   # contains O ... neg
        res = check_c1_polarity_absence(tmp)
        bad = [r for r in res if r["passed"] is False]
        assert not bad, f"arithmetic 'neg' wrongly flagged as polarity: {bad}"
    print("PASS: test_c1_polarity_passes_with_arithmetic_neg")


def test_c1_polarity_catches_real_polarity_placement():
    """Polarity tokens in a row body (where v2 has no slot) must fail."""
    cases = {
        "pos in E-row body": ["GRAPH_BEGIN", "E", "pos", "GRAPH_END"],
        "neut in R-row body": ["GRAPH_BEGIN", "R", "FVAR_0", "neut", "GRAPH_END"],
        "neg in A-row body": ["GRAPH_BEGIN", "A", "FVAR_0", "neg", "value", "GRAPH_END"],
        "pos in O-row arity slot": ["GRAPH_BEGIN", "O", "pos", "OUT_0", "add", "GRAPH_END"],
        "neut in O-row output slot": ["GRAPH_BEGIN", "O", "IN_1", "neut", "add", "GRAPH_END"],
    }
    for label, toks in cases.items():
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _write_ir_dataset(tmp, toks)
            res = check_c1_polarity_absence(tmp)
            bad = [r for r in res if r["passed"] is False]
            assert bad, f"C1 violation NOT caught: {label}"
    print(f"PASS: test_c1_polarity_catches_real_polarity_placement ({len(cases)} cases)")


def test_c1_polarity_on_real_datasets():
    """The committed datasets must satisfy C1 today.

    The datasets are untracked build artifacts (#84), so a fresh clone and CI
    have none on disk. Skip cleanly there; when the files are present the check
    must still be non-vacuous.
    """
    if not any((REPO / "datasets").glob("*.jsonl")):
        print("  SKIP  test_c1_polarity_on_real_datasets (no datasets on disk)")
        return
    res = check_c1_polarity_absence(REPO / "datasets")
    bad = [r for r in res if r["passed"] is False]
    assert not bad, f"committed datasets violate C1: {bad}"
    assert res, "no IR datasets found -- fixture is vacuous"
    print(f"PASS: test_c1_polarity_on_real_datasets ({len(res)} checks)")


def test_grammar_arity_on_real_datasets():
    """The committed datasets must satisfy the grammar today.

    Datasets are untracked build artifacts (#84); skip when absent (CI), and
    stay non-vacuous when present.
    """
    if not any((REPO / "datasets").glob("*.jsonl")):
        print("  SKIP  test_grammar_arity_on_real_datasets (no datasets on disk)")
        return
    res = check_grammar_arity(REPO / "datasets")
    bad = [r for r in res if r["passed"] is False]
    assert not bad, f"committed datasets violate the grammar: {bad}"
    assert res, "no IR datasets found -- fixture is vacuous"
    print(f"PASS: test_grammar_arity_on_real_datasets ({len(res)} checks)")


def test_manifest_verify_catches_missing_fields():
    bad_manifest = {"artifact_type": "results", "variant": "A"}
    errors = verify_manifest(bad_manifest)
    assert len(errors) > 0, "Expected errors for missing fields"
    assert any("missing field" in e for e in errors)
    print("PASS: test_manifest_verify_catches_missing_fields")


def test_manifest_verify_catches_invalid_values():
    bad_manifest = {
        "artifact_type": "WRONG", "variant": "ALSO_WRONG",
        "representation_id": "x", "source_input": "nope",
        "seed": 42, "epochs": 2, "train_examples": 1, "eval_examples": 1,
        "created_at": "x", "created_by_commit": "x",
        "pipeline_version": "x", "provenance_hash": "x",
    }
    errors = verify_manifest(bad_manifest)
    assert any("invalid artifact_type" in e for e in errors), f"Expected artifact_type error: {errors}"
    assert any("invalid variant" in e for e in errors), f"Expected variant error: {errors}"
    assert any("invalid source_input" in e for e in errors), f"Expected source_input error: {errors}"
    print("PASS: test_manifest_verify_catches_invalid_values")


def test_expected_source_mapping():
    assert expected_source_for_variant("A") == "ir_tokens"
    assert expected_source_for_variant("B") == "bpe_full"
    assert expected_source_for_variant("C") == "ast_split"
    assert expected_source_for_variant("B_small") == "bpe_601"
    print("PASS: test_expected_source_mapping")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    tests = [
        test_split_integrity_passes,
        test_split_integrity_catches_overlap,
        test_variant_input_passes,
        test_variant_input_catches_mismatch,
        test_vocab_range_passes,
        test_vocab_range_catches_out_of_range,
        test_comparison_validity_matched_size,
        test_comparison_validity_catches_epoch_mismatch,
        test_grammar_arity_passes_on_valid_graph,
        test_grammar_arity_catches_each_break,
        test_grammar_arity_ignores_non_ir_variants,
        test_c1_polarity_passes_with_arithmetic_neg,
        test_c1_polarity_catches_real_polarity_placement,
        test_grammar_arity_on_real_datasets,
        test_c1_polarity_on_real_datasets,
        test_comparison_validity_catches_each_must_match_field,
        test_comparison_validity_catches_must_differ_violation,
        test_comparison_validity_missing_field_is_lenient,
        test_comparison_validity_catches_heterogeneous_mismatch,
        test_comparison_claims_all_constraints_exercised,
        test_manifest_verify_catches_missing_fields,
        test_manifest_verify_catches_invalid_values,
        test_expected_source_mapping,
    ]
    passed = 0
    failed = 0
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
    print(f"{'='*40}")
    print(f"Tests: {passed} passed, {failed} failed")
    print(f"{'='*40}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
