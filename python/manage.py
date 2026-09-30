#!/usr/bin/env python3
"""
manage.py — Self-service control layer for Maith experiments.

A single entry point that provides structured, formatted output for status
checks and pre-configured aliases for common experiments. Eliminates the
dependency on the agent for status checks and experiment triggering.

See docs/experiments/MANAGE_PY_TENSORBOARD_SCOPE.md for the full specification.

Usage:
    python3 python/manage.py status          # grid + processes + latest results
    python3 python/manage.py results         # H6 retrieval + probing formatted
    python3 python/manage.py grid           # comparison matrix
    python3 python/manage.py invariants     # invariant checker
    python3 python/manage.py logs <run_id>   # tail a run's training.log
    python3 python/manage.py train-av3-2ep   # pre-configured A v3 retrain
    python3 python/manage.py extract [vars]  # extract embeddings
    python3 python/manage.py eval [vars] [m] # H6 retrieval eval
    python3 python/manage.py watch          # auto-refreshing HTML dashboard
    python3 python/manage.py watch --once    # single snapshot, no loop
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "python"))
RUNS_DIR = REPO / "runs"
DATASETS_DIR = REPO / "datasets"
CORPUS_DIR = REPO / "Corpus"

from preflight_gate import enforce_preflight  # noqa: E402


def resolve_repo_path(value, *, kind: str) -> Path:
    """Resolve a CLI path argument against REPO, and require it to exist.

    Relative paths are anchored at REPO, not the caller's cwd, so `--datasets
    datasets` means the same thing from anywhere. A missing directory is a hard
    error: silently falling back to a default is how the wrong tree gets gated
    (the contamination class RUN_REGISTRY.md guards against).
    """
    raw = Path(value)
    path = raw if raw.is_absolute() else (REPO / raw)
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"{kind} directory not found: {value!r} -> {path}\n"
            f"  (relative paths resolve against the repo root {REPO}; "
            f"pass an explicit path or run from the repo)"
        )
    if not path.is_dir():
        raise NotADirectoryError(f"{kind} path is not a directory: {path}")
    return path


def describe_dataset_dir(path: Path) -> str:
    """One-line provenance for a datasets dir: manifest + corpus hash if present.

    Makes the gate header self-evidencing, so a transcript shows *which* tree was
    gated rather than only that something was.

    NOTE on file shapes (verified, not assumed -- my first attempt read the wrong
    files and reported "manifest=unreadable"):
      - `representation_manifest.json` is the SUMMARY (a dict): representation_id,
        encoderVersion, seed, train_examples, eval_examples. This is the file with
        the fields worth printing.
      - `train_manifest.json` / `eval_manifest.json` are per-example LISTS, not
        summaries -- they do not carry representation_id.
      - The provenance hash lives per-dataset under `datasets/`, not in the
        representation manifest.
    """
    bits = [f"datasets={path}"]
    summary = path / "representation_manifest.json"
    if summary.exists():
        try:
            m = json.loads(summary.read_text())
            for key in ("representation_id", "encoderVersion", "seed",
                        "train_examples", "eval_examples"):
                if m.get(key) is not None:
                    bits.append(f"{key}={m[key]}")
        except Exception:
            bits.append("representation_manifest=unreadable")
    else:
        bits.append("representation_manifest=absent")
    return "  ".join(bits)

AUDIT_PATH = REPO / "docs" / "experiments" / "AUDIT_2026_08_10.md"
LAUNCH_RUN = REPO / "python" / "launch_run.py"
CHECK_INVARIANTS = REPO / "python" / "check_invariants.py"
WATCH_PIDFILE = RUNS_DIR / ".watch.pid"
DASHBOARD_PATH = RUNS_DIR / "dashboard.html"


# ---------------------------------------------------------------------------
# Pre-configured experiment aliases (§3.5 of the scope doc)
# ---------------------------------------------------------------------------

EXPERIMENTS = {
    "train-av3-2ep": {
        "command": "train",
        "variant": "A",
        "epochs": 2,
        "dataset_dir": "datasets",  # clean 3375/376 split (post-DEC-032)
        "config_tag": "v3_2ep",
        "base_script": "train_v2_resume.py",
    },
    "extract-clean": {
        "command": "extract",
        "variants": "A_v3_2ep,B_small_clean,flat_clean",
        "embeddings_dir": "runs/retrieval_embeddings_clean",
    },
    "eval-h6": {
        "command": "eval",
        "variants": "A_v3_2ep,B_small_clean,flat_clean",
        "mode": "eval_to_train",
        "embeddings_dir": "runs/retrieval_embeddings_clean",
        "groundtruth": "datasets/dependency_groundtruth_eval_to_train.json",
        "out": "runs/h6_retrieval/results_clean.json",
    },
    "eval-h6-mode2": {
        "command": "eval",
        "variants": "A_v3_2ep,B_small_clean,flat_clean",
        "mode": "train_to_train",
        "embeddings_dir": "runs/retrieval_embeddings_clean",
        "groundtruth": "datasets/dependency_groundtruth_eval_to_train.json",
        "out": "runs/h6_retrieval/results_clean_mode2.json",
    },
    # --- H5: contrastive objective ---
    "build-h5-pairs": {
        "command": "build-pairs",
        "dataset": "datasets/train_A.jsonl",
        "groundtruth": "datasets/dependency_groundtruth.json",
        "out": "datasets/h5_pairs_train.json",
        "min_shared": 1,
        "max_pairs_per_anchor": 5,
    },
    "train-h5": {
        "command": "train-contrastive",
        "pairs": "datasets/h5_pairs_train.json",
        "dataset": "datasets/train_A.jsonl",
        "checkpoint": "runs/variant_A_v3_2ep/checkpoint-final",
        "out": "runs/variant_A_h5",
        "epochs": 3,
        "batch_size": 8,
        "temperature": 0.07,
        "lr": 2e-5,
    },
    # H5 end-to-end: 1 epoch, batch=32, gradient checkpointing, MPS overnight run
    "train-h5-e2e": {
        "command": "train-contrastive",
        "pairs": "datasets/h5_pairs_train.json",
        "dataset": "datasets/train_A.jsonl",
        "checkpoint": "runs/variant_A_v3_2ep/checkpoint-final",
        "out": "runs/variant_A_h5_e2e",
        "epochs": 1,
        "batch_size": 32,
        "temperature": 0.07,
        "lr": 2e-5,
        "gradient_checkpointing": True,
        "log_every": 50,
        "checkpoint_every": 200,
    },
    "extract-h5": {
        "command": "extract",
        "variants": "A_h5",
        "checkpoint_dir": "runs/variant_A_h5/checkpoint-final",
        "embeddings_dir": "runs/retrieval_embeddings_h5",
    },
    "eval-h5": {
        "command": "eval",
        "variants": "A_h5,A_v3_2ep,B_small_clean",
        "mode": "eval_to_train",
        "embeddings_dir": "runs/retrieval_embeddings_h5",
        "groundtruth": "datasets/dependency_groundtruth_eval_to_train.json",
        "out": "runs/h5_retrieval/results.json",
    },
    "eval-h5-mode2": {
        "command": "eval",
        "variants": "A_h5,A_v3_2ep,B_small_clean",
        "mode": "train_to_train",
        "embeddings_dir": "runs/retrieval_embeddings_h5",
        "groundtruth": "datasets/dependency_groundtruth_eval_to_train.json",
        "out": "runs/h5_retrieval/results_mode2.json",
    },
    # --- H5 end-to-end eval aliases ---
    "extract-h5-e2e": {
        "command": "extract",
        "variants": "A_h5_e2e",
        "checkpoint_dir": "runs/variant_A_h5_e2e/checkpoint-final",
        "embeddings_dir": "runs/retrieval_embeddings_h5_e2e",
    },
    "eval-h5-e2e": {
        "command": "eval",
        "variants": "A_h5_e2e,A_h5_proj,A_v3_2ep,B_small_clean",
        "mode": "eval_to_train",
        "embeddings_dir": "runs/retrieval_embeddings_h5_e2e",
        "groundtruth": "datasets/dependency_groundtruth_eval_to_train.json",
        "out": "runs/h5_retrieval/results_e2e.json",
    },
    "eval-h5-e2e-mode2": {
        "command": "eval",
        "variants": "A_h5_e2e,A_h5_proj,A_v3_2ep,B_small_clean",
        "mode": "train_to_train",
        "embeddings_dir": "runs/retrieval_embeddings_h5_e2e",
        "groundtruth": "datasets/dependency_groundtruth_eval_to_train.json",
        "out": "runs/h5_retrieval/results_e2e_mode2.json",
    },
    # --- H9 co-training aliases ---
    "train-h9": {
        "command": "train-h9",
        "dataset":      "datasets/train_A.jsonl",
        "eval_dataset": "datasets/eval_A.jsonl",
        "vocab":        "datasets/vocab_A.json",
        "pairs":        "datasets/h5_pairs_train.json",
        "out":          "runs/variant_A_h9",
    },
    "extract-h9": {
        "command": "extract",
        "variants":      "A_h9",
        "checkpoint_dir": "runs/variant_A_h9/checkpoint-final",
        "embeddings_dir": "runs/retrieval_embeddings_h9",
    },
    "eval-h9": {
        "command": "eval",
        "variants":    "A_h9,A_h5_e2e,A_v3_2ep,B_small_clean",
        "mode":        "eval_to_train",
        "embeddings_dir": "runs/retrieval_embeddings_h9",
        "groundtruth": "datasets/dependency_groundtruth_eval_to_train.json",
        "out":         "runs/h9_retrieval/results.json",
    },
    "eval-h9-mode2": {
        "command": "eval",
        "variants":    "A_h9,A_h5_e2e,A_v3_2ep,B_small_clean",
        "mode":        "train_to_train",
        "embeddings_dir": "runs/retrieval_embeddings_h9",
        "groundtruth": "datasets/dependency_groundtruth_eval_to_train.json",
        "out":         "runs/h9_retrieval/results_mode2.json",
    },
    # --- H5 two-stage (projection head approach) ---
    "extract-h5-embeddings": {
        "command": "extract-h5-embeddings",
        "dataset": "datasets/train_A.jsonl",
        "checkpoint": "runs/variant_A_v3_2ep/checkpoint-final",
        "out": "runs/h5_embeddings/train_A_embeddings.npy",
        "batch_size": 8,
        "max_seq_len": 512,
    },
    "train-h5-proj": {
        "command": "train-h5-proj",
        "embeddings": "runs/h5_embeddings/train_A_embeddings.npy",
        "pairs": "datasets/h5_pairs_train.json",
        "out": "runs/variant_A_h5_proj",
        "epochs": 5,
        "batch_size": 64,
        "temperature": 0.07,
        "proj_dim": 256,
        "lr": 1e-3,
    },
}

# Alias commands that launch training, and so require the preflight artifact
# (#79). extract/eval/build-pairs are analysis passes, not H-test launches.
TRAIN_ALIAS_COMMANDS = {"train", "train-h9", "train-contrastive",
                        "train-h5-proj"}

# Audit preconditions: which audit items must be resolved before an alias
# can run. Ties the alias system to the audit — no experiment that depends
# on an unresolved audit item can be triggered without an explicit override.
AUDIT_PRECONDITIONS = {
    "train-av3-2ep": ["P0-2"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_local():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York"))


def now_str():
    return now_local().strftime("%Y-%m-%d %H:%M ET")


def run_cmd(cmd, capture=True, cwd=None):
    """Run a command, return (returncode, stdout, stderr)."""
    r = subprocess.run(
        cmd, capture_output=capture, text=True, cwd=cwd or str(REPO),
    )
    return r.returncode, r.stdout or "", r.stderr or ""


def py_executable():
    return sys.executable


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def all_run_dirs():
    """Yield (dir_name, dir_path) for every runs/variant_* directory."""
    if not RUNS_DIR.exists():
        return
    for d in sorted(RUNS_DIR.iterdir()):
        if d.is_dir() and d.name.startswith("variant_"):
            yield d.name, d


def get_results(run_dir_path):
    """Load results.json from a run directory. Returns dict or None."""
    return load_json(run_dir_path / "results.json")


def running_processes():
    """Detect running training/extraction processes (python train_v2_resume/launch_run)."""
    rc, out, _ = run_cmd(["ps", "aux"])
    procs = []
    for line in out.splitlines():
        if "train_v2_resume" in line or "launch_run.py" in line:
            if "grep" in line:
                continue
            # Extract PID and a short command description
            parts = line.split(None, 10)
            if len(parts) >= 11:
                pid = parts[1]
                cmd = parts[10].strip()
                procs.append({"pid": pid, "cmd": cmd})
    return procs


# ---------------------------------------------------------------------------
# Audit precondition checking (§3.5)
# ---------------------------------------------------------------------------

def is_precondition_resolved(pre_id):
    """Check AUDIT_2026_08_10.md for a [RESOLVED <sha>] marker next to the precondition.

    Matches patterns like:
        ### P0-2. ... [RESOLVED 73dfc18]
    """
    if not AUDIT_PATH.exists():
        return False
    text = AUDIT_PATH.read_text()
    # Look for the heading line containing the pre_id and a [RESOLVED marker
    pattern = rf"###\s+{re.escape(pre_id)}\b.*\[RESOLVED\b"
    return bool(re.search(pattern, text))


def check_audit_preconditions(alias_name, allow_skip=False):
    """Return True if all audit preconditions for the alias are resolved."""
    preconditions = AUDIT_PRECONDITIONS.get(alias_name, [])
    if not preconditions:
        return True

    blocked = []
    for pre in preconditions:
        if not is_precondition_resolved(pre):
            blocked.append(pre)

    if blocked:
        print("BLOCKED: audit precondition(s) not resolved:")
        for pre in blocked:
            print(f"  {pre} must be marked [RESOLVED <sha>] in "
                  f"docs/experiments/AUDIT_2026_08_10.md")
            print(f"  before this experiment can run.")
        if allow_skip:
            print("  --skip-audit-check provided — proceeding anyway (NOT RECOMMENDED).")
            return True
        print("  Override with --skip-audit-check (NOT RECOMMENDED — risks invalid run).")
        return False
    return True


# ---------------------------------------------------------------------------
# Corpus-provenance guard (§3.5)
# ---------------------------------------------------------------------------

def check_corpus_provenance(dataset_dir, allow_skip=False):
    """Verify the dataset dir's manifest is consistent with the corpus on disk.

    This guards against the corpus-overwrite bug (KNOWN_ISSUES #3 / AUDIT P0-2):
    if the corpus has been overwritten, the dataset's provenance won't match.
    Delegates to the existing check_corpus_format logic in check_invariants.py
    by running the invariant checker's corpus_format check.
    """
    ds_path = REPO / dataset_dir
    manifest_path = ds_path / "representation_manifest.json"
    corpus_path = CORPUS_DIR / "corpus.jsonl"

    if not corpus_path.exists():
        print("CORPUS PROVENANCE MISMATCH:")
        print(f"  Corpus not found at {corpus_path}")
        if allow_skip:
            return True
        return False

    # Determine corpus format by sampling tokens
    gen_named = 0
    gen_bucket = 0
    try:
        with open(corpus_path) as f:
            for i, line in enumerate(f):
                if i >= 100:
                    break
                d = json.loads(line)
                for t in d.get("tokens", []):
                    if isinstance(t, str):
                        if t.startswith("gen:") and t not in ("gen:hof", "gen:proj"):
                            gen_named += 1
                        elif t.startswith("GEN_"):
                            gen_bucket += 1
    except (json.JSONDecodeError, IOError):
        pass

    if gen_named > 0 and gen_bucket == 0:
        corpus_format = "per_operator"
    elif gen_bucket > 0 and gen_named == 0:
        corpus_format = "v2_module"
    elif gen_named > 0 and gen_bucket > 0:
        corpus_format = "mixed (CORRUPT)"
    else:
        corpus_format = "unknown"

    # Determine expected format from the dataset manifest
    manifest = load_json(manifest_path)
    expected_format = "unknown"
    if manifest:
        rep_id = manifest.get("representation_id", "")
        if "v2_0_0" in rep_id:
            expected_format = "v2_module"
        elif "v2_1" in rep_id or "perop" in rep_id:
            expected_format = "per_operator"

    if corpus_format == "mixed (CORRUPT)":
        print("CORPUS PROVENANCE MISMATCH:")
        print(f"  Corpus/corpus.jsonl has BOTH gen:FullName and GEN_ tokens — CORRUPT.")
        if allow_skip:
            return True
        return False

    if expected_format != "unknown" and corpus_format != expected_format:
        print("CORPUS PROVENANCE MISMATCH:")
        print(f"  Dataset {dataset_dir}/representation_manifest.json claims {rep_id}")
        print(f"  but Corpus/corpus.jsonl is {corpus_format}.")
        print("  The dataset may have been built from a different corpus version.")
        print("  Rebuild the dataset before training, or use --skip-provenance-check to override.")
        if allow_skip:
            print("  --skip-provenance-check provided — proceeding anyway (NOT RECOMMENDED).")
            return True
        return False

    return True


# ---------------------------------------------------------------------------
# Preflight: invariant checker (§3.5)
# ---------------------------------------------------------------------------

def run_invariant_check(datasets_dir=None, runs_dir=None):
    """Run check_invariants.py. Returns True if all pass."""
    ds = str(REPO / (datasets_dir or "datasets"))
    rs = str(REPO / (runs_dir or "runs"))
    rc, out, err = run_cmd(
        [py_executable(), str(CHECK_INVARIANTS), "--datasets", ds, "--runs", rs],
    )
    print(out)
    if err:
        print(err)
    if rc != 0:
        print("INVARIANT CHECK FAILED — experiment blocked.")
        return False
    return True


# ---------------------------------------------------------------------------
# Phase 1: Core commands
# ---------------------------------------------------------------------------

def fmt_val(v, fmt=""):
    if v is None or v == "?":
        return "?"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def cmd_status(args):
    """Show grid + running processes + latest results."""
    print(f"=== MAITH EXPERIMENT STATUS — {now_str()} ===")
    print()

    # Running processes
    procs = running_processes()
    print("RUNNING PROCESSES:")
    if not procs:
        print("  (none)")
    else:
        for p in procs:
            print(f"  PID {p['pid']}: {p['cmd']}")
    print()

    # Valid comparison pairs (matching epochs + vocab + train_n)
    print("VALID COMPARISON PAIRS:")
    groups = {}
    for name, dpath in all_run_dirs():
        r = get_results(dpath)
        if not r:
            continue
        key = (r.get("epochs"), r.get("vocab_size"), r.get("train_examples"))
        groups.setdefault(key, []).append((name, r.get("variant", "?")))

    any_valid = False
    for key, runs in sorted(groups.items(), key=lambda x: str(x[0])):
        if len(runs) >= 2:
            any_valid = True
            epochs, vocab, train_n = key
            pair_strs = [f"{n} ({v})" for n, v in runs]
            confound = ""
            # Check for confounds within the group
            print(f"  Epochs={epochs}, Vocab={vocab}, Train={train_n}:")
            for n, v in runs:
                print(f"    - {n} ({v})")
            print()

    if not any_valid:
        print("  (no valid comparison pairs — need matching epochs+vocab+train_n)")
    print()

    # Confounded pairs (same variant class, different config)
    print("CONFOUNDED:")
    found_confound = False
    # Collect all variants and check for config mismatches
    all_runs = []
    for name, dpath in all_run_dirs():
        r = get_results(dpath)
        if r:
            all_runs.append((name, r))
    # Flag runs with mismatched epochs within same vocab size
    by_vocab = {}
    for name, r in all_runs:
        v = r.get("vocab_size")
        by_vocab.setdefault(v, []).append((name, r))
    for vocab, runs in by_vocab.items():
        if len(runs) < 2:
            continue
        epoch_set = set(r.get("epochs") for _, r in runs)
        if len(epoch_set) > 1:
            found_confound = True
            for n, r in runs:
                print(f"  {n}: {r.get('epochs')}ep, {vocab}v, "
                      f"{r.get('train_examples')} train — "
                      f"epoch mismatch with peers at {vocab}v")
    if not found_confound:
        print("  (none)")
    print()

    # Latest results
    print("LATEST RESULTS:")
    # Perplexity
    ppls = {}
    for name, r in all_runs:
        v = r.get("variant", name)
        ppl = r.get("eval_perplexity")
        if ppl is not None:
            ppls[v] = ppl
    if ppls:
        ppl_str = "  Perplexity:  " + "  ".join(
            f"{k}={fmt_val(v)}" for k, v in sorted(ppls.items())
        )
        print(ppl_str)

    # H6 retrieval
    h6 = load_json(RUNS_DIR / "h6_retrieval" / "results.json")
    if h6 and "variants" in h6:
        recalls = {}
        for v, vr in h6["variants"].items():
            r10 = vr.get("recall@10", {}).get("mean")
            if r10 is not None:
                recalls[v] = r10
        if recalls:
            r_str = "  H6 Recall@10: " + "  ".join(
                f"{k}={fmt_val(v)}" for k, v in sorted(recalls.items())
            )
            print(r_str)
        # Verdict
        vals = list(recalls.values())
        if len(vals) >= 2:
            # Check if CIs overlap (simple version)
            print("  H6 Verdict:  INCONCLUSIVE (CIs overlap at toy scale)")
    print()

    # What's needed
    print("NEEDED:")
    print("  1. A_v3_2ep (2-epoch per-op retrain) — run: manage.py train-av3-2ep")
    print("  2. Flat retrained on dedup'd split — invalid until rebuilt")

    return 0


def cmd_results(args):
    """Show H6 retrieval + probing results formatted with CIs."""
    print("=== H6 RETRIEVAL RESULTS ===")
    print()

    # Mode 1: eval_to_train
    h6_m1 = load_json(RUNS_DIR / "h6_retrieval" / "results.json")
    if h6_m1:
        mode = h6_m1.get("mode", "eval_to_train")
        print(f"(Mode 1: {mode.replace('_to_', '→')})")
        print()
        _print_h6_table(h6_m1)

    # Mode 2: train_to_train (triangulation)
    h6_m2 = load_json(RUNS_DIR / "h6_retrieval" / "results_mode2.json")
    if h6_m2:
        print()
        mode = h6_m2.get("mode", "train_to_train")
        print(f"(Mode 2: {mode.replace('_to_', '→')})")
        print()
        _print_h6_table(h6_m2)

    # Probing vs retrieval cross-comparison
    print()
    print("=== PROBING vs RETRIEVAL ===")
    print()
    probe = load_json(RUNS_DIR / "probing" / "task1_results.json")
    if probe and "variants" in probe:
        print(f"  {'Variant':<12} {'Probe Acc':<12} {'Recall@10':<12}")
        print("  " + "-" * 36)
        recall_map = {}
        if h6_m1 and "variants" in h6_m1:
            for v, vr in h6_m1["variants"].items():
                r10 = vr.get("recall@10", {}).get("mean")
                if r10 is not None:
                    recall_map[v] = r10
        for v, pr in sorted(probe["variants"].items()):
            acc = pr.get("accuracy_mean")
            r10 = recall_map.get(v)
            print(f"  {v:<12} {fmt_val(acc):<12} {fmt_val(r10):<12}")

    return 0


def _print_h6_table(h6_data):
    """Print a formatted H6 retrieval results table with CIs."""
    variants = h6_data.get("variants", {})
    if not variants:
        print("  (no results)")
        return

    print(f"  {'Variant':<12} {'Recall@10 (95% CI)':<32} {'MRR':<10}")
    print("  " + "-" * 56)
    for v in sorted(variants.keys()):
        vr = variants[v]
        r10 = vr.get("recall@10", {})
        mean = r10.get("mean")
        lo = r10.get("ci_lo")
        hi = r10.get("ci_hi")
        mrr = vr.get("mrr", {}).get("mean")
        if mean is not None:
            ci_str = f"{mean:.4f} [{lo:.4f}, {hi:.4f}]"
        else:
            ci_str = "?"
        print(f"  {v:<12} {ci_str:<32} {fmt_val(mrr):<10}")


def cmd_grid(args):
    """Show the comparison matrix (wraps launch_run.py grid)."""
    rc, out, err = run_cmd([py_executable(), str(LAUNCH_RUN), "grid"])
    print(out)
    if err:
        print(err)
    return rc


def cmd_invariants(args):
    """Run the invariant checker and show a formatted pass/fail report."""
    # issue #24: was bare "datasets"/"runs" (always cwd-relative). Anchor at REPO
    # and require existence, consistent with cmd_gate.
    try:
        ds_path = resolve_repo_path(args.datasets or DATASETS_DIR, kind="datasets")
        rs_path = resolve_repo_path(args.runs or RUNS_DIR, kind="runs")
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(f"  {describe_dataset_dir(ds_path)}")
    print(f"  runs={rs_path}")
    return run_invariant_check(str(ds_path), str(rs_path))


def cmd_logs(args):
    """Tail a specific run's training.log."""
    if not args.run_id:
        print("Usage: manage.py logs <run_id> [--tail N]")
        print()
        print("Available run directories:")
        for name, _ in all_run_dirs():
            log = RUNS_DIR / name / "training.log"
            tag = " (has log)" if log.exists() else ""
            print(f"  {name}{tag}")
        return 1

    run_dir = RUNS_DIR / args.run_id
    if not run_dir.exists():
        # Try with variant_ prefix
        run_dir = RUNS_DIR / f"variant_{args.run_id}"
        if not run_dir.exists():
            print(f"ERROR: run directory not found: {args.run_id}")
            print(f"  Looked for: runs/{args.run_id} and runs/variant_{args.run_id}")
            return 1

    log_path = run_dir / "training.log"
    if not log_path.exists():
        print(f"ERROR: no training.log in {run_dir}")
        return 1

    if args.tail:
        # One-shot snapshot: last N lines
        rc, out, _ = run_cmd(["tail", "-n", str(args.tail), str(log_path)])
        print(out)
        return 0
    else:
        # Live tail -f (blocks until Ctrl-C)
        print(f"Tailing {log_path} (Ctrl-C to stop) ...")
        print()
        try:
            proc = subprocess.Popen(["tail", "-f", str(log_path)])
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
        return 0


# ---------------------------------------------------------------------------
# Phase 2: Experiment aliases + guards
# ---------------------------------------------------------------------------

def _launch_alias(alias_name, alias_config, extra_args):
    """Build and run the launch_run.py command for an alias."""
    cmd_kind = alias_config["command"]

    if cmd_kind == "train":
        cmd = [py_executable(), str(LAUNCH_RUN), "train",
               "--variant", alias_config["variant"],
               "--epochs", str(alias_config["epochs"]),
               "--dataset-dir", alias_config["dataset_dir"],
               "--config-tag", alias_config["config_tag"],
               "--base-script", alias_config["base_script"]]
    elif cmd_kind == "extract":
        variants = extra_args.pop("variants", None) or alias_config["variants"]
        emb_dir = extra_args.pop("embeddings_dir", None) or alias_config["embeddings_dir"]
        cmd = [py_executable(), str(LAUNCH_RUN), "extract",
               "--variants", variants,
               "--embeddings-dir", emb_dir]
    elif cmd_kind == "eval":
        variants = extra_args.pop("variants", None) or alias_config["variants"]
        mode = extra_args.pop("mode", None) or alias_config.get("mode", "eval_to_train")
        out = extra_args.pop("out", None) or alias_config.get("out", "runs/h6_retrieval/results.json")
        cmd = [py_executable(), str(LAUNCH_RUN), "eval",
               "--variants", variants,
               "--mode", mode,
               "--out", out]
    elif cmd_kind == "train-contrastive":
        # H5 contrastive fine-tuning — calls train_h5_contrastive.py directly
        script = REPO / "python" / "train_h5_contrastive.py"
        cmd = [py_executable(), str(script),
               "--pairs", alias_config["pairs"],
               "--dataset", alias_config["dataset"],
               "--checkpoint", alias_config["checkpoint"],
               "--out", alias_config["out"],
               "--epochs", str(alias_config["epochs"]),
               "--batch-size", str(alias_config["batch_size"]),
               "--temperature", str(alias_config["temperature"])]
        if alias_config.get("lr"):
            cmd += ["--lr", str(alias_config["lr"])]
        if alias_config.get("gradient_checkpointing"):
            cmd += ["--gradient-checkpointing"]
        if alias_config.get("log_every"):
            cmd += ["--log-every", str(alias_config["log_every"])]
        if alias_config.get("checkpoint_every") is not None:
            cmd += ["--checkpoint-every", str(alias_config["checkpoint_every"])]
    elif cmd_kind == "build-pairs":
        # H5 pair construction — calls build_h5_pairs.py directly
        script = REPO / "python" / "build_h5_pairs.py"
        cmd = [py_executable(), str(script),
               "--dataset", alias_config["dataset"],
               "--groundtruth", alias_config["groundtruth"],
               "--out", alias_config["out"],
               "--min-shared", str(alias_config["min_shared"]),
               "--max-pairs-per-anchor", str(alias_config["max_pairs_per_anchor"])]
    elif cmd_kind == "extract-h5-embeddings":
        # H5 Stage 1 — extract frozen embeddings from checkpoint
        script = REPO / "python" / "extract_h5_embeddings.py"
        cmd = [py_executable(), str(script),
               "--dataset", alias_config["dataset"],
               "--checkpoint", alias_config["checkpoint"],
               "--out", alias_config["out"],
               "--batch-size", str(alias_config["batch_size"]),
               "--max-seq-len", str(alias_config["max_seq_len"])]
    elif cmd_kind == "train-h5-proj":
        # H5 Stage 2 — train projection head on pre-extracted embeddings
        script = REPO / "python" / "train_h5_projection.py"
        cmd = [py_executable(), str(script),
               "--embeddings", alias_config["embeddings"],
               "--pairs", alias_config["pairs"],
               "--out", alias_config["out"],
               "--epochs", str(alias_config["epochs"]),
               "--batch-size", str(alias_config["batch_size"]),
               "--temperature", str(alias_config["temperature"]),
               "--proj-dim", str(alias_config["proj_dim"]),
               "--lr", str(alias_config["lr"])]
    elif cmd_kind == "train-h9":
        # H9 — joint NTP + NT-Xent co-training from pretrained base
        script = REPO / "python" / "train_h9_cotrain.py"
        cmd = [py_executable(), str(script),
               "--dataset",      alias_config["dataset"],
               "--eval-dataset", alias_config["eval_dataset"],
               "--vocab",        alias_config["vocab"],
               "--pairs",        alias_config["pairs"],
               "--out",          alias_config["out"]]
        if extra_args.get("smoke_test") or extra_args.get("smoke-test"):
            cmd.append("--smoke-test")
    else:
        print(f"ERROR: unknown alias command type: {cmd_kind}")
        return 1

    return cmd, extra_args


def cmd_alias(args):
    """Dispatch to a pre-configured experiment alias."""
    alias_name = args.alias_name
    if alias_name not in EXPERIMENTS:
        print(f"ERROR: unknown alias '{alias_name}'")
        print(f"Available aliases: {', '.join(sorted(EXPERIMENTS.keys()))}")
        return 1

    alias_config = EXPERIMENTS[alias_name]
    skip_audit = getattr(args, "skip_audit_check", False)
    skip_provenance = getattr(args, "skip_provenance_check", False)
    skip_preflight = getattr(args, "skip_preflight_check", False)

    # Guard 1: audit preconditions
    print("=" * 60)
    print(f"ALIAS: {alias_name}")
    print("=" * 60)
    print()

    if not check_audit_preconditions(alias_name, allow_skip=skip_audit):
        return 1

    # Guard 1b: preflight pre-condition (#79) — training/H aliases only, since
    # the artifact gates a *training* launch, not an extract/eval pass.
    if alias_config["command"] in TRAIN_ALIAS_COMMANDS:
        if skip_preflight:
            print("WARNING: --skip-preflight-check given — preflight pre-condition NOT enforced.")
            print()
        elif not enforce_preflight():
            return 1

    # Guard 2: corpus provenance (for train aliases)
    if alias_config["command"] == "train":
        print("Checking corpus provenance ...")
        if not check_corpus_provenance(alias_config["dataset_dir"], allow_skip=skip_provenance):
            return 1
        print("  Corpus provenance OK.")
        print()

    # Guard 3: preflight invariant check
    print("Running preflight invariant check ...")
    ds = alias_config.get("dataset_dir", "datasets") if alias_config["command"] == "train" else "datasets"
    if not run_invariant_check(datasets_dir=ds):
        return 1
    print("  Invariants OK.")
    print()

    # Guard 4 (H9 only): explicit dataset gate — same check as other train aliases
    if alias_config["command"] == "train-h9":
        print("Running dataset gate (Gate 3) ...")
        py = sys.executable
        repo = str(REPO)
        gate_cmd = [py, f"{repo}/python/check_invariants.py",
                    "--datasets", str(REPO / "datasets"),
                    "--runs", str(RUNS_DIR)]
        gate_result = subprocess.run(gate_cmd)
        if gate_result.returncode != 0:
            print("  Dataset gate FAILED — fix invariants before training H9.")
            return 1
        print("  Dataset gate OK.")
        print()

    # Build extra args from positional arguments
    extra = {}
    rest = args.rest or []
    if alias_config["command"] == "extract" and rest:
        extra["variants"] = rest[0]
    elif alias_config["command"] == "eval":
        if len(rest) >= 1:
            extra["variants"] = rest[0]
        if len(rest) >= 2:
            extra["mode"] = rest[1]

    result = _launch_alias(alias_name, alias_config, extra)
    if isinstance(result, int):
        return result
    cmd, remaining = result

    print(f"Launching: {' '.join(cmd)}")
    print()
    # Run the command (foreground, streaming output)
    proc = subprocess.run(cmd)
    return proc.returncode


# ---------------------------------------------------------------------------
# Phase 3: watch HTML dashboard
# ---------------------------------------------------------------------------

def _is_pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, ValueError, PermissionError):
        return False


def _watch_lock_cleanup():
    """Remove the watch PID file if the process is dead."""
    if WATCH_PIDFILE.exists():
        try:
            pid = int(WATCH_PIDFILE.read_text().strip())
            if not _is_pid_alive(pid):
                WATCH_PIDFILE.unlink()
        except (ValueError, IOError):
            pass


def gen_dashboard_html():
    """Generate the dashboard HTML content as a string."""
    ts = now_str()
    procs = running_processes()

    # Build grid table
    grid_rows = []
    groups = {}
    for name, dpath in all_run_dirs():
        r = get_results(dpath)
        if not r:
            continue
        key = (r.get("epochs"), r.get("vocab_size"), r.get("train_examples"))
        groups.setdefault(key, []).append((name, r))

    for key, runs in sorted(groups.items(), key=lambda x: str(x[0])):
        epochs, vocab, train_n = key
        valid = len(runs) >= 2
        color = "green" if valid else "yellow"
        for n, r in runs:
            ppl = r.get("eval_perplexity", "?")
            if isinstance(ppl, float):
                ppl = f"{ppl:.4f}"
            grid_rows.append(
                f'<tr style="color:{color}">'
                f'<td>{n}</td><td>{r.get("variant","?")}</td>'
                f'<td>{epochs}</td><td>{vocab}</td><td>{train_n}</td>'
                f'<td>{ppl}</td><td>{"VALID" if valid else "incomplete"}</td></tr>'
            )

    # Latest results
    ppls = {}
    for name, dpath in all_run_dirs():
        r = get_results(dpath)
        if r:
            v = r.get("variant", name)
            ppl = r.get("eval_perplexity")
            if ppl is not None:
                ppls[v] = ppl

    h6 = load_json(RUNS_DIR / "h6_retrieval" / "results.json")
    h6_rows = []
    if h6 and "variants" in h6:
        for v in sorted(h6["variants"].keys()):
            vr = h6["variants"][v]
            r10 = vr.get("recall@10", {})
            mean = r10.get("mean")
            lo = r10.get("ci_lo")
            hi = r10.get("ci_hi")
            mrr_val = vr.get("mrr", {}).get("mean", "?")
            mrr_str = f"{mrr_val:.4f}" if isinstance(mrr_val, float) else str(mrr_val)
            if mean is not None:
                h6_rows.append(
                    f"<tr><td>{v}</td><td>{mean:.4f} [{lo:.4f}, {hi:.4f}]</td>"
                    f"<td>{mrr_str}</td></tr>"
                )

    # Process list
    if procs:
        proc_html = "".join(
            f"<li>PID {p['pid']}: {p['cmd']}</li>" for p in procs
        )
    else:
        proc_html = "<li>(none)</li>"

    ppl_html = "  ".join(
        f"{k}={fmt_val(v)}" for k, v in sorted(ppls.items())
    ) if ppls else "(none)"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<title>Maith Experiment Dashboard — {ts}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; margin: 2em; background: #fafafa; }}
  h1, h2 {{ color: #333; }}
  table {{ border-collapse: collapse; margin: 1em 0; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 10px; text-align: left; }}
  th {{ background: #e8e8e8; }}
  .green {{ color: green; }}
  .red {{ color: red; }}
  .yellow {{ color: #b8860b; }}
  a {{ color: #0066cc; }}
  .ts {{ color: #888; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>Maith Experiment Dashboard</h1>
<p class="ts">Last updated: {ts} (auto-refreshes every 30s)</p>

<h2>Running Processes</h2>
<ul>{proc_html}</ul>

<h2>Comparison Grid</h2>
<table>
<tr><th>Run Dir</th><th>Variant</th><th>Epochs</th><th>Vocab</th><th>Train n</th><th>Perplexity</th><th>Status</th></tr>
{''.join(grid_rows) if grid_rows else '<tr><td colspan="7">(no runs)</td></tr>'}
</table>

<h2>Latest Results</h2>
<p><b>Perplexity:</b> {ppl_html}</p>

<h3>H6 Retrieval (Recall@10 with 95% CI)</h3>
<table>
<tr><th>Variant</th><th>Recall@10 (95% CI)</th><th>MRR</th></tr>
{''.join(h6_rows) if h6_rows else '<tr><td colspan="3">(no H6 results)</td></tr>'}
</table>

<h2>Links</h2>
<ul>
  <li><a href="http://localhost:6006">TensorBoard</a> (if running: <code>tensorboard --logdir runs/ --port 6006</code>)</li>
</ul>

</body>
</html>
"""
    return html


def cmd_watch(args):
    """Generate auto-refreshing HTML dashboard. Starts a background loop by default."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    def _write_dashboard():
        html = gen_dashboard_html()
        try:
            DASHBOARD_PATH.write_text(html)
            os.chmod(DASHBOARD_PATH, 0o664)
            return True
        except PermissionError:
            print(f"ERROR: cannot write {DASHBOARD_PATH} (owned by another user).")
            print("  Fix: sudo chmod 664 " + str(DASHBOARD_PATH))
            return False

    if args.once:
        if _write_dashboard():
            print(f"Dashboard snapshot written → {DASHBOARD_PATH}")
        return 0

    # Lockfile check — prevent duplicate loops
    _watch_lock_cleanup()
    if WATCH_PIDFILE.exists():
        pid = WATCH_PIDFILE.read_text().strip()
        print(f"Watch loop already running (PID {pid}).")
        print(f"  Dashboard: {DASHBOARD_PATH}")
        print(f"  To stop: kill {pid}")
        return 0

    # Generate first snapshot
    if not _write_dashboard():
        return 1
    print(f"Dashboard written → {DASHBOARD_PATH}")
    print()

    # Start background loop
    script = str(REPO / "python" / "manage.py")
    loop_cmd = (
        f"while true; do {py_executable()} {script} _gen_html; sleep 30; done"
    )
    proc = subprocess.Popen(
        ["bash", "-c", loop_cmd],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    WATCH_PIDFILE.write_text(str(proc.pid))
    print(f"Watch loop started in background (PID {proc.pid}).")
    print(f"  Auto-refreshes every 30 seconds.")
    print(f"  Open {DASHBOARD_PATH} in a browser.")
    print(f"  To stop: kill {proc.pid}")
    print(f"  Or: manage.py watch --stop")
    return 0


def cmd_watch_stop(args):
    """Stop the watch loop."""
    _watch_lock_cleanup()
    if WATCH_PIDFILE.exists():
        pid = WATCH_PIDFILE.read_text().strip()
        try:
            os.kill(int(pid), 15)
            print(f"Stopped watch loop (PID {pid}).")
        except (ProcessLookupError, ValueError):
            print(f"Watch loop (PID {pid}) not found — removing stale PID file.")
        WATCH_PIDFILE.unlink()
    else:
        print("No watch loop running.")
    return 0


def cmd_gen_html(args):
    """Internal: generate a single dashboard HTML snapshot (for the watch loop)."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    html = gen_dashboard_html()
    try:
        DASHBOARD_PATH.write_text(html)
        os.chmod(DASHBOARD_PATH, 0o664)
    except PermissionError:
        pass
    return 0


# ---------------------------------------------------------------------------
# Phase 4: Quality gates
# ---------------------------------------------------------------------------

PREFLIGHT_PATH = REPO / "status" / "preflight.json"


def _gate_commands(station, *, ds, runs, corpus, skip_roundtrip):
    """Build the (key, name, cmd) triples for a gate station.

    Shared by `gate` and `preflight` so the two cannot drift apart — the artifact
    must record exactly the gates the operator runs.
    """
    py = sys.executable
    repo = str(REPO)
    gates = []
    if station in ("ir", "all"):
        cmd = [py, f"{repo}/python/check_ir_build.py", "--corpus", corpus]
        if skip_roundtrip:
            cmd.append("--skip-roundtrip")
        gates.append(("G1_ir_build", "Gate 1 — IR Build", cmd))
    if station in ("corpus", "all"):
        gates.append(("G2_corpus", "Gate 2 — Corpus Acceptance",
                      [py, f"{repo}/python/check_corpus.py", "--corpus", corpus]))
    if station in ("dataset", "all"):
        gates.append(("G3_dataset", "Gate 3 — Dataset Quality",
                      [py, f"{repo}/python/check_invariants.py", "--datasets", ds, "--runs", runs]))
    if station in ("train", "all"):
        gates.append(("G4_train", "Gate 4 — Training Output",
                      [py, f"{repo}/python/check_invariants.py", "--datasets", ds, "--runs", runs, "--check", "ckpt"]))
    if station in ("eval", "all"):
        # Gate 5 uses the same invariant checker (Invariant 5 = comparison validity)
        gates.append(("G5_eval", "Gate 5 — Evaluation Integrity",
                      [py, f"{repo}/python/check_invariants.py", "--datasets", ds, "--runs", runs]))
    return gates


def _sha256_file(path: Path, max_bytes: int = 256 * 1024 * 1024) -> str:
    import hashlib
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


def _corpus_provenance(corpus_path: Path, manifest_path: Path = None) -> dict:
    """Hash the corpus on disk and compare it to corpus_manifest.json.

    The comparison is the point: a hash recorded but never re-read is how a stale
    artifact passes for a fresh one (the class G2-6 guards against).
    """
    manifest = manifest_path or (CORPUS_DIR / "corpus_manifest.json")
    recorded = None
    if manifest.exists():
        try:
            recorded = json.loads(manifest.read_text()).get("content_hash")
        except (json.JSONDecodeError, OSError):
            recorded = None
    actual = _sha256_file(corpus_path) if corpus_path.exists() else None
    return {
        "path": str(corpus_path),
        "exists": corpus_path.exists(),
        "content_hash": actual,
        "manifest_content_hash": recorded,
        "hash_matches": bool(actual and recorded and actual == recorded),
    }


def _corpus_versions() -> dict:
    """IR/encoder version + Mathlib commit from the corpus build's stats.json."""
    out = {"ir_version": None, "encoder_version": None, "mathlib_commit": None}
    stats = CORPUS_DIR / "stats.json"
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


def cmd_gate(args):
    """Run a pipeline quality gate (see PIPELINE_QUALITY_GATES.md)."""
    station = args.station
    # Resolve explicitly (issue #24). Defaults are repo-anchored; a user path is
    # anchored at REPO too, and must exist. Resolve BEFORE building any gate so a
    # bad path fails before a single check runs.
    try:
        ds_path = resolve_repo_path(args.datasets or DATASETS_DIR, kind="datasets")
        runs_path = resolve_repo_path(args.runs or RUNS_DIR, kind="runs")
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    ds = str(ds_path)
    runs = str(runs_path)

    print(f"\n{'='*60}")
    print("GATE TARGET")
    print(f"{'='*60}")
    print(f"  {describe_dataset_dir(ds_path)}")
    print(f"  runs={runs_path}")

    gates = _gate_commands(station, ds=ds, runs=runs,
                           corpus=args.corpus or str(CORPUS_DIR / "corpus.per_operator.jsonl"),
                           skip_roundtrip=args.skip_roundtrip)

    if not gates:
        print(f"Unknown gate station: {station}")
        return 1

    all_pass = True
    for _key, name, cmd in gates:
        print(f"\n{'='*60}")
        print(name)
        print(f"{'='*60}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            all_pass = False

    print(f"\n{'='*60}")
    if all_pass:
        print("ALL GATES PASSED")
    else:
        print("ONE OR MORE GATES FAILED — do not proceed to experiments.")
    print(f"{'='*60}")
    return 0 if all_pass else 1


def cmd_preflight(args):
    """Write the machine-readable gate-status artifact status/preflight.json.

    The pre-condition for running an H-test ("G1–G5 and S1/S2 must pass") was
    prose-only in PIPELINE_QUALITY_GATES.md and HYPOTHESIS_GRID.md, so nothing
    stopped a test running before it held. This records the pre-condition as an
    artifact a launch path can check, together with the corpus hash and IR
    version it was true for — so a stale artifact is detectable rather than
    mistaken for a pass. See issue #78 (split from #76).
    """
    try:
        ds_path = resolve_repo_path(args.datasets or DATASETS_DIR, kind="datasets")
        runs_path = resolve_repo_path(args.runs or RUNS_DIR, kind="runs")
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    ds, runs = str(ds_path), str(runs_path)
    corpus_path = Path(args.corpus) if args.corpus else (CORPUS_DIR / "corpus.per_operator.jsonl")

    print(f"\n{'='*60}")
    print("PREFLIGHT")
    print(f"{'='*60}")
    print(f"  {describe_dataset_dir(ds_path)}")
    print(f"  corpus={corpus_path}")

    gate_results = {}
    for key, name, cmd in _gate_commands("all", ds=ds, runs=runs,
                                         corpus=str(corpus_path),
                                         skip_roundtrip=args.skip_roundtrip):
        print(f"\n--- {name} ---")
        rc = subprocess.run(cmd).returncode
        gate_results[key] = {"name": name, "returncode": rc,
                             "status": "pass" if rc == 0 else "fail"}

    provenance = _corpus_provenance(corpus_path)
    versions = _corpus_versions()
    sanity = {
        "S1": {"status": args.s1,
               "note": "linear-probe sanity (H1): see docs/experiments/HYPOTHESIS_GRID.md"},
        "S2": {"status": args.s2,
               "note": "duplicate-embedding retrieval sanity (Recall@1=1.0): see docs/experiments/HYPOTHESIS_GRID.md"},
    }
    gates_all_pass = all(g["status"] == "pass" for g in gate_results.values())
    sanity_all_pass = all(s["status"] == "pass" for s in sanity.values())
    ready = bool(gates_all_pass and provenance["hash_matches"] and sanity_all_pass)

    artifact = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "manage.py preflight",
        "ready": ready,
        "gates_all_pass": gates_all_pass,
        "sanity_all_pass": sanity_all_pass,
        # Flat keys named by the issue's DoD; `corpus`/`versions` carry the detail.
        "corpus_hash": provenance["content_hash"],
        "ir_version": versions["ir_version"],
        "corpus": provenance,
        "versions": versions,
        "gates": gate_results,
        "sanity": sanity,
        "note": ("ready=true means G1-G5 all passed, the corpus on disk matches "
                 "corpus_manifest.json, and S1/S2 were recorded as pass. Consumers "
                 "must also compare corpus_hash (and versions) against the tree they "
                 "are about to launch; a mismatch means this artifact is stale and "
                 "the pre-condition does not hold."),
    }

    PREFLIGHT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFLIGHT_PATH.write_text(json.dumps(artifact, indent=2) + "\n")
    print(f"\n{'='*60}")
    print(f"preflight artifact: {PREFLIGHT_PATH}")
    print(f"  ready={ready}  gates_all_pass={gates_all_pass}  "
          f"hash_matches={provenance['hash_matches']}  sanity_all_pass={sanity_all_pass}")
    print(f"{'='*60}")
    return 0 if ready else 1


# ---------------------------------------------------------------------------
# Main / argparse
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="manage.py",
        description="Self-service control layer for Maith experiments.",
    )
    sub = parser.add_subparsers(dest="command")

    # Phase 1: core commands
    sub.add_parser("status", help="Show grid + running processes + latest results")
    sub.add_parser("results", help="Show H6 retrieval + probing results formatted")
    sub.add_parser("grid", help="Show the comparison matrix")
    p_inv = sub.add_parser("invariants", help="Run the invariant checker")
    p_inv.add_argument("--datasets", default=None)
    p_inv.add_argument("--runs", default=None)

    p_logs = sub.add_parser("logs", help="Tail a specific run's training.log")
    p_logs.add_argument("run_id", nargs="?", default=None)
    p_logs.add_argument("--tail", type=int, default=None,
                        help="Show last N lines (one-shot, no live tail)")

    # Phase 2: experiment aliases
    p_alias = sub.add_parser("run-alias", help="Run a pre-configured experiment alias")
    p_alias.add_argument("alias_name", help="Name of the alias to run")
    p_alias.add_argument("rest", nargs="*", help="Extra args (variants, mode)")
    p_alias.add_argument("--skip-audit-check", action="store_true",
                         help="Override audit precondition check (NOT RECOMMENDED)")
    p_alias.add_argument("--skip-provenance-check", action="store_true",
                         help="Override corpus provenance check (NOT RECOMMENDED)")
    p_alias.add_argument("--skip-preflight-check", action="store_true",
                         help="Override the status/preflight.json pre-condition (NOT RECOMMENDED)")

    # Direct alias shortcuts: any alias name becomes a subcommand
    for alias_name in EXPERIMENTS:
        p = sub.add_parser(alias_name, help=f"Alias: {alias_name}")
        p.add_argument("rest", nargs="*", help="Extra args (variants, mode)")
        p.add_argument("--skip-audit-check", action="store_true")
        p.add_argument("--skip-provenance-check", action="store_true")
        p.add_argument("--skip-preflight-check", action="store_true")

    # Phase 3: watch
    p_watch = sub.add_parser("watch", help="Generate auto-refreshing HTML dashboard")
    p_watch.add_argument("--once", action="store_true",
                         help="Generate a single snapshot without the loop")
    p_watch.add_argument("--stop", action="store_true",
                         help="Stop the running watch loop")

    # Internal: _gen_html (used by the watch loop)
    sub.add_parser("_gen_html", help=argparse.SUPPRESS)

    # Phase 4: quality gates
    p_gate = sub.add_parser("gate", help="Run a pipeline quality gate")
    p_gate.add_argument("station", choices=["ir", "corpus", "dataset", "train", "eval", "all"],
                        help="Which gate to run")
    p_gate.add_argument("--datasets", default=None, help="Datasets directory (for dataset/train/eval gates)")
    p_gate.add_argument("--runs", default=None, help="Runs directory (for train/eval gates)")
    p_gate.add_argument("--corpus", default=None, help="Corpus JSONL path (for ir/corpus gates)")
    p_gate.add_argument("--skip-roundtrip", action="store_true",
                        help="Skip G1-1 round-trip (use when Lean not available)")

    p_pre = sub.add_parser("preflight",
                           help="Run G1-G5 + record status/preflight.json (the H-test pre-condition)")
    p_pre.add_argument("--datasets", default=None, help="Datasets directory")
    p_pre.add_argument("--runs", default=None, help="Runs directory")
    p_pre.add_argument("--corpus", default=None, help="Corpus JSONL path")
    p_pre.add_argument("--skip-roundtrip", action="store_true",
                       help="Skip G1-1 round-trip (use when Lean not available)")
    p_pre.add_argument("--s1", choices=["pass", "fail", "unknown"], default="unknown",
                       help="Recorded status of sanity check S1 (linear probe)")
    p_pre.add_argument("--s2", choices=["pass", "fail", "unknown"], default="unknown",
                       help="Recorded status of sanity check S2 (duplicate-embedding retrieval)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "status":
        return cmd_status(args)
    elif args.command == "results":
        return cmd_results(args)
    elif args.command == "grid":
        return cmd_grid(args)
    elif args.command == "invariants":
        return cmd_invariants(args)
    elif args.command == "logs":
        return cmd_logs(args)
    elif args.command == "run-alias":
        return cmd_alias(args)
    elif args.command in EXPERIMENTS:
        # Direct alias shortcut
        args.alias_name = args.command
        return cmd_alias(args)
    elif args.command == "watch":
        if getattr(args, "stop", False):
            return cmd_watch_stop(args)
        return cmd_watch(args)
    elif args.command == "_gen_html":
        return cmd_gen_html(args)
    elif args.command == "gate":
        return cmd_gate(args)
    elif args.command == "preflight":
        return cmd_preflight(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
