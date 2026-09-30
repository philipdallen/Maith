#!/usr/bin/env python3
"""
launch_run.py — Structured experiment launcher.

Enforces the process rules from RUN_REGISTRY.md:
1. Assigns a run ID and records it in the registry before starting
2. Runs the invariant checker on the datasets (blocks if it fails)
3. Creates a versioned run directory (never overwrites existing runs)
4. Launches the training/extraction/eval script
5. Writes a manifest after completion

Usage:
    # Launch a training run
    python3 python/launch_run.py train --variant A_v3_2ep --epochs 2 \\
        --dataset-dir datasets_perop --base-script train_v2_resume.py

    # Launch an embedding extraction
    python3 python/launch_run.py extract --variant A_v3_2ep \\
        --checkpoint-dir runs/variant_A_v3_2ep/checkpoint-final

    # Launch a retrieval eval
    python3 python/launch_run.py eval --variants A_v3_2ep,B_small \\
        --embeddings-dir runs/retrieval_embeddings_v2

    # Show the comparison grid status
    python3 python/launch_run.py grid
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "python"))

from manifest import write_results_manifest, write_checkpoint_manifest, \
    write_embeddings_manifest, expected_source_for_variant
from preflight_gate import enforce_preflight, DEFAULT_PREFLIGHT_PATH, \
    DEFAULT_CORPUS_PATH

REGISTRY_PATH = REPO / "docs" / "experiments" / "RUN_REGISTRY.md"
RUNS_DIR = REPO / "runs"
DATASETS_DIR = REPO / "datasets"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_id_for(variant, config_tag):
    """Generate a unique run ID."""
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    return f"{variant}_{config_tag}_{ts}"


def check_invariants(datasets_dir=DATASETS_DIR, runs_dir=RUNS_DIR):
    """Run the invariant checker. Returns True if all pass."""
    print("=" * 60)
    print("PRECONDITION: INVARIANT CHECKER")
    print("=" * 60)
    result = subprocess.run(
        [sys.executable, str(REPO / "python" / "check_invariants.py"),
         "--datasets", str(datasets_dir), "--runs", str(runs_dir)],
        capture_output=False,
    )
    if result.returncode != 0:
        print()
        print("INVARIANT CHECK FAILED — experiment blocked.")
        print("Fix the invariant violations before proceeding.")
        return False
    print()
    return True


def append_to_registry(run_id, kind, config):
    """Append a run record to the registry markdown."""
    entry = f"\n| {run_id} | {kind} | {now_iso()} | {json.dumps(config, sort_keys=True)} | pending |\n"
    # Append to the "Run log" section at the end of the registry
    with open(REGISTRY_PATH, "a") as f:
        f.write(entry)
    print(f"Recorded in registry: {run_id}")


def _validate_training_output(run_dir: Path, variant: str) -> list[str]:
    """Gate 4: validate training output. Returns list of failure strings (empty = all pass)."""
    errors = []

    # G4-1: checkpoint exists
    ckpt = run_dir / "checkpoint-final"
    if not ckpt.exists():
        errors.append("G4-1: checkpoint-final/ not found")
        return errors

    # G4-2: results.json has required fields
    rp = run_dir / "results.json"
    if not rp.exists():
        errors.append("G4-2: results.json not written")
        return errors

    with open(rp) as f:
        r = json.load(f)
    required = ["eval_perplexity", "epochs", "train_examples", "n_params_M", "vocab_size"]
    missing = [f for f in required if f not in r]
    if missing:
        errors.append(f"G4-2: results.json missing fields: {missing}")

    # G4-4: perplexity plausible
    ppl = r.get("eval_perplexity")
    vocab = r.get("vocab_size", 151643)
    if ppl is not None and not (1.0 < ppl < vocab):
        errors.append(f"G4-4: eval_perplexity={ppl} not in (1.0, {vocab})")

    # G4-3: loss descended (from loss_curve.json)
    lc = run_dir / "loss_curve.json"
    if lc.exists():
        curve = json.load(open(lc))
        train = curve.get("train", [])
        if len(train) >= 2:
            initial = train[0]["loss"]
            final = train[-1]["loss"]
            if final >= initial * 0.5:
                errors.append(f"G4-3: loss did not descend sufficiently: {initial:.3f} → {final:.3f} "
                               f"({(1 - final/initial)*100:.0f}% reduction, need ≥50%)")
    else:
        errors.append("G4-3: loss_curve.json not written — cannot verify loss descent")

    return errors


def cmd_train(args):
    """Launch a training run with enforced process."""
    variant = args.variant
    epochs = args.epochs
    dataset_dir = Path(args.dataset_dir)
    config_tag = args.config_tag or f"{epochs}ep"

    run_id = run_id_for(variant, config_tag)
    run_dir = RUNS_DIR / f"variant_{run_id}"

    if run_dir.exists():
        print(f"ERROR: run dir {run_dir} already exists — refusing to overwrite.")
        return 1

    # Step 0: enforce the preflight pre-condition (#79). Done before the run dir
    # is created, so a stale/missing artifact cannot leave a half-started run.
    if getattr(args, "skip_preflight_check", False):
        print("WARNING: --skip-preflight-check given — preflight pre-condition NOT enforced.")
    elif not enforce_preflight(DEFAULT_PREFLIGHT_PATH, DEFAULT_CORPUS_PATH):
        return 1

    # Create run dir and log file
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "training.log"

    # Step 1: invariant check (log to file + stdout)
    print("=" * 60)
    print(f"RUN ID: {run_id}")
    print(f"Run dir: {run_dir}")
    print(f"Log file: {log_path}")
    print("=" * 60)

    with open(log_path, "a") as logf:
        logf.write(f"=== RUN {run_id} started at {now_iso()} ===\n")
        logf.write(f"Config: variant={variant} epochs={epochs} dataset={dataset_dir}\n\n")
        logf.write("=== INVARIANT CHECK ===\n")

    print("Running invariant check...")
    inv_result = subprocess.run(
        [sys.executable, str(REPO / "python" / "check_invariants.py"),
         "--datasets", str(dataset_dir), "--runs", str(RUNS_DIR)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    inv_output = inv_result.stdout
    print(inv_output)
    with open(log_path, "a") as logf:
        logf.write(inv_output)
        if inv_result.returncode != 0:
            logf.write("\nINVARIANT CHECK FAILED — experiment blocked.\n")
            logf.write(f"=== RUN {run_id} ABORTED at {now_iso()} ===\n")
    if inv_result.returncode != 0:
        print("INVARIANT CHECK FAILED — experiment blocked.")
        return 1

    # Step 2: record in registry
    config = {
        "variant": variant,
        "epochs": epochs,
        "dataset_dir": str(dataset_dir),
        "lr": args.lr,
        "base_script": args.base_script,
    }
    append_to_registry(run_id, "train", config)

    # Step 3: launch training (tee output to log file)
    script = REPO / "python" / args.base_script
    cmd = [sys.executable, str(script),
           "--variant", variant,
           "--out", str(run_dir),
           "--epochs", str(epochs),
           "--datasets", str(dataset_dir)]
    if args.lr:
        cmd.extend(["--lr", args.lr])

    print(f"Launching training: {' '.join(cmd)}")
    with open(log_path, "a") as logf:
        logf.write(f"\n=== TRAINING STARTED at {now_iso()} ===\n")
        logf.write(f"Command: {' '.join(cmd)}\n\n")
        # Run with output going to both stdout and log file
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end="")
            logf.write(line)
        process.wait()
        train_result = process.returncode

    # Step 4: Gate 4 — validate training output before registering
    if train_result == 0:
        gate4_errors = _validate_training_output(run_dir, variant)
        if gate4_errors:
            print("\nGATE 4 FAILED — training output validation:")
            for e in gate4_errors:
                print(f"  {e}")
            print("Run registered but may have quality issues. Review before using results.")
            with open(log_path, "a") as logf:
                logf.write("\n=== GATE 4 VALIDATION FAILED ===\n")
                for e in gate4_errors:
                    logf.write(f"  {e}\n")

    # Step 5: write manifest if successful
    if train_result == 0:
        results_path = run_dir / "results.json"
        if results_path.exists():
            with open(results_path) as f:
                r = json.load(f)
            write_results_manifest(
                results_path,
                variant=variant,
                representation_id=r.get("representation_id", "unknown"),
                seed=r.get("seed", 42),
                epochs=epochs,
                train_examples=r.get("train_examples", 0),
                eval_examples=r.get("eval_examples", 0),
                checkpoint_path=str(run_dir / "checkpoint-final"),
                actual_learning_rate=float(args.lr) if args.lr else r.get("actual_learning_rate"),
                vocab_size=r.get("vocab_size"),
                n_params_M=r.get("n_params_M"),
                eval_perplexity=r.get("eval_perplexity"),
                repo_root=str(REPO),
            )
            print(f"Manifest written for {run_id}")
        with open(log_path, "a") as logf:
            logf.write(f"\n=== TRAINING COMPLETE at {now_iso()} ===\n")
            logf.write(f"Results: {run_dir / 'results.json'}\n")
        print(f"\nTraining complete: {run_id}")
        print(f"Results: {run_dir}")
        print(f"Log: {log_path}")
    else:
        with open(log_path, "a") as logf:
            logf.write(f"\n=== TRAINING FAILED at {now_iso()} (exit {train_result}) ===\n")
        print(f"\nTraining FAILED: {run_id}")
        print(f"Log: {log_path}")

    return train_result


def cmd_extract(args):
    """Launch embedding extraction with enforced process."""
    variants = args.variants.split(",")
    embeddings_dir = Path(args.embeddings_dir or RUNS_DIR / "retrieval_embeddings_v2")

    if embeddings_dir.exists() and not args.force:
        print(f"ERROR: embeddings dir {embeddings_dir} already exists.")
        print("Use --force to overwrite, or specify a different --embeddings-dir.")
        return 1

    # Create log file
    log_path = RUNS_DIR / f"extraction_{datetime.now().strftime('%Y%m%d_%H%M')}.log"
    run_id = run_id_for("extract", "emb")

    print("=" * 60)
    print(f"RUN ID: {run_id}")
    print(f"Embeddings dir: {embeddings_dir}")
    print(f"Log file: {log_path}")
    print("=" * 60)

    with open(log_path, "a") as logf:
        logf.write(f"=== EXTRACTION {run_id} started at {now_iso()} ===\n")
        logf.write(f"Variants: {variants}\n")
        logf.write(f"Output: {embeddings_dir}\n\n")

    # Step 1: invariant check
    print("Running invariant check...")
    inv_result = subprocess.run(
        [sys.executable, str(REPO / "python" / "check_invariants.py"),
         "--datasets", str(DATASETS_DIR), "--runs", str(RUNS_DIR)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    print(inv_result.stdout)
    with open(log_path, "a") as logf:
        logf.write("=== INVARIANT CHECK ===\n")
        logf.write(inv_result.stdout)
        if inv_result.returncode != 0:
            logf.write("\nINVARIANT CHECK FAILED — extraction blocked.\n")
    if inv_result.returncode != 0:
        print("INVARIANT CHECK FAILED — extraction blocked.")
        return 1

    # Step 2: verify datasets exist
    for v in variants:
        for split in ["train", "eval"]:
            ds_path = DATASETS_DIR / f"{split}_{v}.jsonl"
            if not ds_path.exists() and v != "random":
                print(f"ERROR: {ds_path} not found for variant {v}")
                return 1

    # Step 3: record in registry
    config = {
        "variants": variants,
        "embeddings_dir": str(embeddings_dir),
    }
    append_to_registry(run_id, "extract", config)

    # Step 4: launch extraction
    script = REPO / "python" / "extract_retrieval_embeddings.py"
    cmd = [sys.executable, str(script),
           "--variants", args.variants,
           "--out", str(embeddings_dir)]

    print(f"Launching extraction: {' '.join(cmd)}")
    with open(log_path, "a") as logf:
        logf.write(f"\n=== EXTRACTION STARTED at {now_iso()} ===\n")
        logf.write(f"Command: {' '.join(cmd)}\n\n")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end="")
            logf.write(line)
        process.wait()
        extract_result = process.returncode

    # Step 5: verify shapes match
    if extract_result == 0:
        all_ok = True
        import torch
        for v in variants:
            for split in ["train", "eval"]:
                emb_path = embeddings_dir / f"embeddings_{v}_{split}.pt"
                ds_path = DATASETS_DIR / f"{split}_{v}.jsonl"
                if emb_path.exists() and ds_path.exists():
                    emb = torch.load(emb_path, weights_only=True)
                    with open(ds_path) as f:
                        ds_n = sum(1 for _ in f)
                    if emb.shape[0] != ds_n:
                        print(f"SHAPE MISMATCH: {v}/{split} emb={emb.shape[0]} ds={ds_n}")
                        all_ok = False
        if all_ok:
            print("All embedding shapes match datasets.")
        else:
            print("SHAPE MISMATCH DETECTED — results may be invalid.")
        with open(log_path, "a") as logf:
            logf.write(f"\n=== EXTRACTION COMPLETE at {now_iso()} (exit {extract_result}) ===\n")
            logf.write(f"Shape verification: {'OK' if all_ok else 'MISMATCH'}\n")
    print(f"Log: {log_path}")
    return extract_result


def cmd_eval(args):
    """Launch retrieval eval with enforced process."""
    # Step 1: invariant check
    if not check_invariants():
        return 1

    embeddings_dir = Path(args.embeddings_dir)
    out_path = Path(args.out)

    # Step 2: verify all variants have embeddings
    variants = args.variants.split(",")
    for v in variants:
        for split in ["train", "eval"]:
            emb_path = embeddings_dir / f"embeddings_{v}_{split}.pt"
            if not emb_path.exists():
                print(f"ERROR: {emb_path} not found")
                return 1

    # Step 3: record in registry
    config = {
        "variants": variants,
        "embeddings_dir": str(embeddings_dir),
        "mode": args.mode,
    }
    run_id = run_id_for("eval", args.mode)
    append_to_registry(run_id, "eval", config)

    # Step 4: launch eval
    script = REPO / "python" / "retrieval_eval.py"
    cmd = [sys.executable, str(script),
           "--embeddings-dir", str(embeddings_dir),
           "--groundtruth", args.groundtruth,
           "--out", str(out_path),
           "--variants", args.variants,
           "--mode", args.mode]

    print(f"Launching eval: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


def cmd_grid(args):
    """Show the current state of the comparison grid."""
    print("=" * 70)
    print("COMPARISON GRID STATUS")
    print("=" * 70)
    print()

    # Read all results.json files and tabulate
    print(f"{'Run ID':<30} {'Variant':<10} {'Epochs':<8} {'Vocab':<10} {'Train n':<10} {'PPL':<10}")
    print("-" * 80)

    for d in sorted(RUNS_DIR.iterdir()):
        if not d.is_dir() or not d.name.startswith("variant_"):
            continue
        rp = d / "results.json"
        if not rp.exists():
            continue
        with open(rp) as f:
            r = json.load(f)
        name = d.name
        variant = r.get("variant", "?")
        epochs = r.get("epochs", "?")
        vocab = r.get("vocab_size", "?")
        train_n = r.get("train_examples", "?")
        ppl = r.get("eval_perplexity", "?")
        if isinstance(ppl, float):
            ppl = f"{ppl:.4f}"
        print(f"{name:<30} {variant:<10} {epochs:<8} {vocab:<10} {train_n:<10} {ppl:<10}")

    print()
    print("VALID COMPARISONS (matching epochs + vocab + train_n):")
    print()

    # Group by (epochs, vocab, train_n) to find valid comparison sets
    groups = {}
    for d in sorted(RUNS_DIR.iterdir()):
        if not d.is_dir() or not d.name.startswith("variant_"):
            continue
        rp = d / "results.json"
        if not rp.exists():
            continue
        with open(rp) as f:
            r = json.load(f)
        key = (r.get("epochs"), r.get("vocab_size"), r.get("train_examples"))
        groups.setdefault(key, []).append((d.name, r.get("variant")))

    for key, runs in sorted(groups.items()):
        if len(runs) >= 2:
            epochs, vocab, train_n = key
            print(f"  Epochs={epochs}, Vocab={vocab}, Train={train_n}:")
            for name, variant in runs:
                print(f"    - {name} ({variant})")
            print()

    # H6 retrieval results
    h6_path = RUNS_DIR / "h6_retrieval" / "results.json"
    if h6_path.exists():
        print()
        print("H6 RETRIEVAL RESULTS (latest):")
        with open(h6_path) as f:
            h6 = json.load(f)
        for v, r in h6.get("variants", {}).items():
            r10 = r.get("recall@10", {}).get("mean", "?")
            if isinstance(r10, float):
                r10 = f"{r10:.4f}"
            print(f"  {v}: Recall@10 = {r10}")

    # What's needed
    print()
    print("NEEDED TO FILL THE GRID:")
    print("  1. A_v3_2ep (2-epoch per-op retrain) for clean A-v3 vs B-small comparison")
    print("  2. Flat retrained on dedup'd split (3375/376) for valid flat comparisons")
    print("  3. H6 retrieval on A_v3_2ep embeddings vs B-small")


def main():
    parser = argparse.ArgumentParser(description="Structured experiment launcher")
    sub = parser.add_subparsers(dest="command")

    # train
    p_train = sub.add_parser("train", help="Launch a training run")
    p_train.add_argument("--variant", required=True)
    p_train.add_argument("--epochs", type=int, required=True)
    p_train.add_argument("--dataset-dir", default="datasets")
    p_train.add_argument("--lr", default=None)
    p_train.add_argument("--base-script", default="train_v2_resume.py")
    p_train.add_argument("--config-tag", default=None)
    p_train.add_argument("--skip-preflight-check", action="store_true",
                         help="Override the status/preflight.json pre-condition (NOT RECOMMENDED)")

    # extract
    p_extract = sub.add_parser("extract", help="Launch embedding extraction")
    p_extract.add_argument("--variants", required=True)
    p_extract.add_argument("--embeddings-dir", default=None)
    p_extract.add_argument("--force", action="store_true")

    # eval
    p_eval = sub.add_parser("eval", help="Launch retrieval eval")
    p_eval.add_argument("--variants", required=True)
    p_eval.add_argument("--embeddings-dir", default="runs/retrieval_embeddings")
    p_eval.add_argument("--groundtruth", default="datasets/dependency_groundtruth_eval_to_train.json")
    p_eval.add_argument("--out", default="runs/h6_retrieval/results.json")
    p_eval.add_argument("--mode", default="eval_to_train")

    # grid
    sub.add_parser("grid", help="Show comparison grid status")

    args = parser.parse_args()

    if args.command == "train":
        return cmd_train(args)
    elif args.command == "extract":
        return cmd_extract(args)
    elif args.command == "eval":
        return cmd_eval(args)
    elif args.command == "grid":
        return cmd_grid(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
