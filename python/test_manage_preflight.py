#!/usr/bin/env python3
"""Tests for `manage.py preflight` (issue #78, split from #76).

The hazard this closes: the pre-condition for running an H-test ("G1-G5 and
S1/S2 must pass") lived only in prose, so nothing stopped a test running before
it held. `preflight` records it as a machine-readable artifact. The tests pin:

  1. the artifact records exactly the G1-G5 gates, in order
  2. a corpus whose hash does not match corpus_manifest.json is flagged stale
     (hash_matches=False) -- a recorded hash that is never re-read is the failure
     mode G2-6 exists to prevent
  3. the CLI writes status/preflight.json and its exit code agrees with `ready`

Run: python3 python/test_manage_preflight.py
"""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANAGE = REPO / "python" / "manage.py"
PREFLIGHT_PATH = REPO / "status" / "preflight.json"
sys.path.insert(0, str(REPO / "python"))

import manage  # noqa: E402


def _sha256(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# _gate_commands -- the artifact must record the gates the operator runs
# ---------------------------------------------------------------------------

def test_gate_commands_all_is_g1_through_g5_in_order():
    gates = manage._gate_commands("all", ds="/d", runs="/r", corpus="/c",
                                  skip_roundtrip=True)
    keys = [k for k, _n, _c in gates]
    assert keys == ["G1_ir_build", "G2_corpus", "G3_dataset", "G4_train", "G5_eval"], keys
    # skip_roundtrip must thread through to G1
    g1 = gates[0][2]
    assert "--skip-roundtrip" in g1, g1
    print("PASS: test_gate_commands_all_is_g1_through_g5_in_order")


def test_gate_commands_single_station_returns_one_gate():
    gates = manage._gate_commands("dataset", ds="/d", runs="/r", corpus="/c",
                                  skip_roundtrip=False)
    assert [k for k, _n, _c in gates] == ["G3_dataset"], gates
    print("PASS: test_gate_commands_single_station_returns_one_gate")


# ---------------------------------------------------------------------------
# _corpus_provenance -- stale detection is the whole point
# ---------------------------------------------------------------------------

def test_provenance_matches_when_hash_agrees():
    with tempfile.TemporaryDirectory() as td:
        corpus = Path(td) / "corpus.jsonl"
        corpus.write_text("{}\n")
        manifest = Path(td) / "corpus_manifest.json"
        manifest.write_text(json.dumps({"content_hash": _sha256(corpus)}))
        prov = manage._corpus_provenance(corpus, manifest)
        assert prov["exists"] is True, prov
        assert prov["hash_matches"] is True, prov
        assert prov["content_hash"] == prov["manifest_content_hash"], prov
    print("PASS: test_provenance_matches_when_hash_agrees")


def test_provenance_flags_stale_when_hash_differs():
    with tempfile.TemporaryDirectory() as td:
        corpus = Path(td) / "corpus.jsonl"
        corpus.write_text("{}\n")
        manifest = Path(td) / "corpus_manifest.json"
        manifest.write_text(json.dumps({"content_hash": "sha256:deadbeef"}))
        prov = manage._corpus_provenance(corpus, manifest)
        assert prov["hash_matches"] is False, prov
        assert prov["content_hash"] != prov["manifest_content_hash"], prov
    print("PASS: test_provenance_flags_stale_when_hash_differs")


def test_provenance_absent_corpus_never_matches():
    with tempfile.TemporaryDirectory() as td:
        missing = Path(td) / "nope.jsonl"
        manifest = Path(td) / "corpus_manifest.json"
        manifest.write_text(json.dumps({"content_hash": "sha256:abc"}))
        prov = manage._corpus_provenance(missing, manifest)
        assert prov["exists"] is False, prov
        assert prov["hash_matches"] is False, prov
        assert prov["content_hash"] is None, prov
    print("PASS: test_provenance_absent_corpus_never_matches")


def test_provenance_missing_manifest_is_not_a_match():
    with tempfile.TemporaryDirectory() as td:
        corpus = Path(td) / "corpus.jsonl"
        corpus.write_text("{}\n")
        prov = manage._corpus_provenance(corpus, Path(td) / "absent_manifest.json")
        assert prov["manifest_content_hash"] is None, prov
        assert prov["hash_matches"] is False, prov
    print("PASS: test_provenance_missing_manifest_is_not_a_match")


# ---------------------------------------------------------------------------
# CLI -- the artifact is written and the exit code agrees with `ready`
# ---------------------------------------------------------------------------

def test_cli_writes_artifact_and_exit_code_agrees_with_ready():
    r = subprocess.run(
        [sys.executable, str(MANAGE), "preflight", "--skip-roundtrip",
         "--s1", "unknown", "--s2", "unknown"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert PREFLIGHT_PATH.exists(), "preflight did not write status/preflight.json"
    art = json.loads(PREFLIGHT_PATH.read_text())
    for key in ("generated_at", "ready", "gates_all_pass", "sanity_all_pass",
                "corpus_hash", "ir_version", "corpus", "versions", "gates", "sanity"):
        assert key in art, f"artifact missing {key!r}: {art}"
    assert set(art["gates"]) == {"G1_ir_build", "G2_corpus", "G3_dataset",
                                 "G4_train", "G5_eval"}, art["gates"]
    # unknown S1/S2 => sanity_all_pass False => not ready
    assert art["sanity_all_pass"] is False, art
    assert art["ready"] is False, art
    expected = 0 if art["ready"] else 1
    assert r.returncode == expected, (
        f"exit {r.returncode} disagrees with ready={art['ready']}\n{r.stdout[-400:]}")
    print("PASS: test_cli_writes_artifact_and_exit_code_agrees_with_ready")


def main() -> int:
    tests = [
        test_gate_commands_all_is_g1_through_g5_in_order,
        test_gate_commands_single_station_returns_one_gate,
        test_provenance_matches_when_hash_agrees,
        test_provenance_flags_stale_when_hash_differs,
        test_provenance_absent_corpus_never_matches,
        test_provenance_missing_manifest_is_not_a_match,
        test_cli_writes_artifact_and_exit_code_agrees_with_ready,
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
