#!/usr/bin/env python3
"""
preflight_gate.py — Enforce the H-test pre-condition (issue #79, split from #76).

`manage.py preflight` records the pre-condition as `status/preflight.json`. This
module is the consumer: it refuses to let a launch proceed unless the artifact
records a *green* pre-condition **for the tree being launched**. A recorded hash
that is never re-read is how a stale artifact passes for a fresh one (the class
G2-6 guards against), so the artifact's `corpus_hash` and `ir_version` are
re-computed from the tree on disk and compared, not trusted.

The two consumers are `launch_run.py train` and the training/H aliases in
`manage.py`; both call `enforce_preflight`. See PIPELINE_QUALITY_GATES.md.

Usage:
    from preflight_gate import enforce_preflight
    if not enforce_preflight(preflight_path, corpus_path):
        return 1
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PREFLIGHT_PATH = REPO / "status" / "preflight.json"
DEFAULT_CORPUS_PATH = REPO / "Corpus" / "corpus.per_operator.jsonl"

PREFLIGHT_FILENAME = "status/preflight.json"


def corpus_content_hash(path, max_bytes: int = 256 * 1024 * 1024) -> str | None:
    """sha256 of a corpus file (first max_bytes), or None if it is absent.

    Matches manage.py's hashing exactly — a drift between the writer and the
    reader would make every artifact look stale. test_preflight_gate.py pins the
    two agree.
    """
    path = Path(path)
    if not path.exists():
        return None
    h = hashlib.sha256()
    read = 0
    with open(path, "rb") as f:
        while read < max_bytes:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
            read += len(chunk)
    return f"sha256:{h.hexdigest()}"


def corpus_versions(corpus_path) -> dict:
    """IR/encoder version + Mathlib commit from stats.json beside the corpus."""
    out = {"ir_version": None, "encoder_version": None, "mathlib_commit": None}
    stats = Path(corpus_path).parent / "stats.json"
    if not stats.exists():
        return out
    try:
        data = json.loads(stats.read_text())
    except (json.JSONDecodeError, OSError):
        return out
    out["ir_version"] = data.get("irVersion")
    out["encoder_version"] = data.get("encoderVersion")
    out["mathlib_commit"] = data.get("mathlibCommitHash")
    return out


def evaluate(preflight_path, corpus_path) -> tuple[bool, list[str], dict]:
    """Evaluate the artifact against the tree.

    Returns (ok, reasons, observed). `reasons` is empty iff ok. `observed` carries
    the numbers the decision was made on, so a caller can print them without
    re-deriving (the whole point of the issue: show the mismatch, do not assume).
    """
    preflight_path = Path(preflight_path)
    corpus_path = Path(corpus_path)
    reasons: list[str] = []

    actual_hash = corpus_content_hash(corpus_path)
    versions = corpus_versions(corpus_path)
    actual_ir = versions["ir_version"]
    observed = {
        "preflight_path": str(preflight_path),
        "corpus_path": str(corpus_path),
        "actual_corpus_hash": actual_hash,
        "actual_ir_version": actual_ir,
    }

    if not preflight_path.exists():
        reasons.append(
            f"no preflight artifact at {preflight_path} — run `manage.py preflight` "
            f"and commit status/preflight.json before launching an H-test"
        )
        return False, reasons, observed

    try:
        art = json.loads(preflight_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        reasons.append(f"preflight artifact {preflight_path} is unreadable: {e}")
        return False, reasons, observed

    observed["artifact_corpus_hash"] = art.get("corpus_hash")
    observed["artifact_ir_version"] = art.get("ir_version")
    observed["artifact_ready"] = art.get("ready")
    observed["artifact_generated_at"] = art.get("generated_at")

    if art.get("ready") is not True:
        reasons.append(
            f"artifact not ready (ready={art.get('ready')!r}, "
            f"gates_all_pass={art.get('gates_all_pass')!r}, "
            f"sanity_all_pass={art.get('sanity_all_pass')!r}) — the pre-condition "
            f"G1-G5 + S1/S2 does not hold"
        )

    if actual_hash is None:
        reasons.append(f"corpus not found at {corpus_path} — cannot verify freshness")
    elif art.get("corpus_hash") != actual_hash:
        reasons.append(
            f"corpus hash mismatch: artifact records {art.get('corpus_hash')}, "
            f"tree has {actual_hash} — the artifact is stale"
        )

    if actual_ir is None:
        reasons.append(
            f"IR version unknown: no readable stats.json at {corpus_path.parent / 'stats.json'}"
        )
    elif art.get("ir_version") != actual_ir:
        reasons.append(
            f"IR version mismatch: artifact records {art.get('ir_version')!r}, "
            f"tree has {actual_ir!r} — the artifact is stale"
        )

    return (not reasons), reasons, observed


def enforce_preflight(preflight_path=DEFAULT_PREFLIGHT_PATH,
                      corpus_path=DEFAULT_CORPUS_PATH, *, quiet=False) -> bool:
    """Print the preflight decision and return True iff the launch may proceed."""
    ok, reasons, observed = evaluate(preflight_path, corpus_path)
    if quiet:
        return ok
    print("=" * 60)
    print("PRECONDITION: PREFLIGHT ARTIFACT")
    print("=" * 60)
    print(f"  artifact: {observed['preflight_path']}")
    print(f"  corpus:   {observed['corpus_path']}")
    if ok:
        print(f"  ready=true; corpus hash and IR version match the tree "
              f"(ir_version={observed['actual_ir_version']})")
        print()
        return True
    print("PREFLIGHT CHECK FAILED — experiment blocked.")
    for r in reasons:
        print(f"  - {r}")
    print()
    return False


def main() -> int:
    p = argparse.ArgumentParser(description="Check status/preflight.json against the tree")
    p.add_argument("--preflight", default=str(DEFAULT_PREFLIGHT_PATH))
    p.add_argument("--corpus", default=str(DEFAULT_CORPUS_PATH))
    args = p.parse_args()
    return 0 if enforce_preflight(args.preflight, args.corpus) else 1


if __name__ == "__main__":
    sys.exit(main())
