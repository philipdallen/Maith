#!/usr/bin/env python3
"""Tests for preflight_gate.py (issue #79, split from #76).

`manage.py preflight` writes status/preflight.json (issue #78). This pins the
consumer: the launch path must refuse unless the artifact is *green for the tree
being launched*. The hazard is a recorded hash that is never re-read — a stale
artifact would pass for a fresh one (the class G2-6 exists to prevent). The tests
therefore cover, as separate failures:

  1. a missing artifact blocks
  2. ready=True + matching corpus hash + matching IR version passes
  3. a corpus hash that differs from the tree blocks (stale)
  4. ready=False blocks even when the hashes agree
  5. an IR-version mismatch blocks
  6. the reader's hash agrees with the writer's (manage._sha256_file), so a
     drift cannot make every artifact look stale
  7. the CLI exit code agrees with the decision
  8. end-to-end through `launch_run.py train` (the DoD check): a stale artifact
     makes the launch path exit non-zero naming the mismatch, and a fresh green
     artifact proceeds past the gate

Run: python3 python/test_preflight_gate.py
"""

import argparse
import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "python"))

import manage  # noqa: E402
import preflight_gate  # noqa: E402
import launch_run  # noqa: E402


def _write_tree(td: Path, *, ir_version="2.0.0", corpus_bytes=b"corpus line\n"):
    """Lay out a corpus + stats.json and return (preflight_path, corpus_path)."""
    corpus = td / "Corpus" / "corpus.per_operator.jsonl"
    corpus.parent.mkdir(parents=True, exist_ok=True)
    corpus.write_bytes(corpus_bytes)
    (corpus.parent / "stats.json").write_text(json.dumps({"irVersion": ir_version}))
    return td / "status" / "preflight.json", corpus


def _write_artifact(path: Path, *, ready, corpus_hash, ir_version):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "ready": ready,
        "gates_all_pass": ready,
        "sanity_all_pass": ready,
        "corpus_hash": corpus_hash,
        "ir_version": ir_version,
    }))


def _sha(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def test_missing_artifact_blocks():
    with tempfile.TemporaryDirectory() as td:
        pf, corpus = _write_tree(Path(td))
        ok, reasons, _ = preflight_gate.evaluate(pf, corpus)
        assert ok is False, "a missing artifact must block"
        assert any("no preflight artifact" in r for r in reasons), reasons
    print("PASS: test_missing_artifact_blocks")


def test_ready_and_fresh_passes():
    with tempfile.TemporaryDirectory() as td:
        pf, corpus = _write_tree(Path(td))
        _write_artifact(pf, ready=True, corpus_hash=_sha(corpus), ir_version="2.0.0")
        ok, reasons, observed = preflight_gate.evaluate(pf, corpus)
        assert ok is True, reasons
        assert reasons == [], reasons
        assert observed["actual_corpus_hash"] == _sha(corpus), observed
    print("PASS: test_ready_and_fresh_passes")


def test_stale_corpus_hash_blocks():
    with tempfile.TemporaryDirectory() as td:
        pf, corpus = _write_tree(Path(td))
        # Artifact records a hash for a corpus that is no longer on disk.
        _write_artifact(pf, ready=True, corpus_hash="sha256:" + "0" * 64,
                        ir_version="2.0.0")
        ok, reasons, _ = preflight_gate.evaluate(pf, corpus)
        assert ok is False, "a stale corpus hash must block"
        assert any("hash mismatch" in r for r in reasons), reasons
    print("PASS: test_stale_corpus_hash_blocks")


def test_not_ready_blocks_even_when_hashes_agree():
    with tempfile.TemporaryDirectory() as td:
        pf, corpus = _write_tree(Path(td))
        _write_artifact(pf, ready=False, corpus_hash=_sha(corpus), ir_version="2.0.0")
        ok, reasons, _ = preflight_gate.evaluate(pf, corpus)
        assert ok is False, "ready=False must block"
        assert any("not ready" in r for r in reasons), reasons
    print("PASS: test_not_ready_blocks_even_when_hashes_agree")


def test_ir_version_mismatch_blocks():
    with tempfile.TemporaryDirectory() as td:
        pf, corpus = _write_tree(Path(td), ir_version="2.0.0")
        _write_artifact(pf, ready=True, corpus_hash=_sha(corpus), ir_version="1.4.0")
        ok, reasons, _ = preflight_gate.evaluate(pf, corpus)
        assert ok is False, "an IR-version mismatch must block"
        assert any("IR version mismatch" in r for r in reasons), reasons
    print("PASS: test_ir_version_mismatch_blocks")


def test_reader_and_writer_hash_agree():
    """A drift between the writer (manage) and the reader (preflight_gate) would
    make every artifact look stale — pin them together."""
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "corpus.jsonl"
        f.write_bytes(b"some corpus contents\n" * 100)
        assert preflight_gate.corpus_content_hash(f) == manage._sha256_file(f), \
            "writer/reader hashing drifted"
    print("PASS: test_reader_and_writer_hash_agree")


def test_cli_exit_code_agrees_with_decision():
    with tempfile.TemporaryDirectory() as td:
        pf, corpus = _write_tree(Path(td))
        _write_artifact(pf, ready=True, corpus_hash=_sha(corpus), ir_version="2.0.0")
        r = subprocess.run(
            [sys.executable, str(REPO / "python" / "preflight_gate.py"),
             "--preflight", str(pf), "--corpus", str(corpus)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, f"fresh artifact should exit 0\n{r.stdout}"

        _write_artifact(pf, ready=False, corpus_hash=_sha(corpus), ir_version="2.0.0")
        r = subprocess.run(
            [sys.executable, str(REPO / "python" / "preflight_gate.py"),
             "--preflight", str(pf), "--corpus", str(corpus)],
            capture_output=True, text=True,
        )
        assert r.returncode == 1, f"not-ready artifact should exit 1\n{r.stdout}"
    print("PASS: test_cli_exit_code_agrees_with_decision")


def test_launch_path_blocks_on_stale_and_proceeds_on_fresh():
    """The DoD check: drive the real `launch_run.cmd_train` launch path.

    cmd_train enforces the gate *before* it creates the run dir, so a blocked
    launch leaves no half-started run behind. A fresh green artifact must get
    past the gate — proven by the run dir being created, which is the first
    side-effect that only runs after the gate passes.
    """
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        pf, corpus = _write_tree(td)
        runs_dir = td / "runs"

        def make_args():
            return argparse.Namespace(
                variant="A", epochs=1, dataset_dir=str(td / "datasets"),
                config_tag="pfcheck", lr=None, base_script="train_v2_resume.py",
                skip_preflight_check=False,
            )

        real_runs, real_pf, real_corpus = (
            launch_run.RUNS_DIR, launch_run.DEFAULT_PREFLIGHT_PATH,
            launch_run.DEFAULT_CORPUS_PATH,
        )
        launch_run.RUNS_DIR = runs_dir
        launch_run.DEFAULT_PREFLIGHT_PATH = pf
        launch_run.DEFAULT_CORPUS_PATH = corpus
        try:
            # Stale: artifact records a hash that is not the tree's.
            _write_artifact(pf, ready=True, corpus_hash="sha256:" + "1" * 64,
                            ir_version="2.0.0")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = launch_run.cmd_train(make_args())
            out = buf.getvalue()
            assert rc != 0, f"stale artifact must block, got rc={rc}"
            assert "hash mismatch" in out, out
            assert not any(runs_dir.glob("variant_A_pfcheck*")), \
                "a blocked launch must not create a run dir"

            # Fresh + green: the same launch must proceed past the gate.
            _write_artifact(pf, ready=True, corpus_hash=_sha(corpus),
                            ir_version="2.0.0")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                launch_run.cmd_train(make_args())
            created = list(runs_dir.glob("variant_A_pfcheck*"))
            assert created, (
                "a fresh green artifact should pass the gate and create the run "
                f"dir\n{buf.getvalue()}")
        finally:
            launch_run.RUNS_DIR = real_runs
            launch_run.DEFAULT_PREFLIGHT_PATH = real_pf
            launch_run.DEFAULT_CORPUS_PATH = real_corpus
    print("PASS: test_launch_path_blocks_on_stale_and_proceeds_on_fresh")


def main() -> int:
    tests = [
        test_missing_artifact_blocks,
        test_ready_and_fresh_passes,
        test_stale_corpus_hash_blocks,
        test_not_ready_blocks_even_when_hashes_agree,
        test_ir_version_mismatch_blocks,
        test_reader_and_writer_hash_agree,
        test_cli_exit_code_agrees_with_decision,
        test_launch_path_blocks_on_stale_and_proceeds_on_fresh,
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
