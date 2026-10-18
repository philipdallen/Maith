# Experiment Process — Operational Guide

> **Purpose.** How to run experiments using the structured process. This is the
> operational manual for `launch_run.py`, the enforced preconditions, and the run
> registry. Read this before running any experiment.

---

## The process in one paragraph

Every experiment goes through three enforced gates: (1) the invariant checker
must pass on the datasets, (2) embedding shapes must match datasets, (3) the run
must be recorded in the registry with its config. The `launch_run.py` script
automates all three. You can bypass it by running scripts directly, but the
scripts themselves now have wired preconditions that block on invariant failures
and shape mismatches. The process is enforced by code, not by convention.

---

## Commands

All commands run from the repo root on the M4:
```bash
cd /Users/openhands-demo/maith-repo
```

### Show the comparison grid

```bash
python3 python/launch_run.py grid
```

Shows every checkpoint's config (variant, epochs, vocab, train count, perplexity),
groups them into valid comparison sets (matching epochs + vocab + train_n), and
lists what's needed to fill empty cells. **Run this first** to see the current
state before starting any new experiment.

### Launch a training run

```bash
python3 python/launch_run.py train \
    --variant A \
    --epochs 2 \
    --dataset-dir datasets_perop \
    --config-tag v3_2ep \
    --base-script train_v2_resume.py
```

What it does:
1. Runs the invariant checker on `--dataset-dir` — blocks if any invariant fails
2. Records the run in `RUN_REGISTRY.md` with a run ID and config
3. Creates a versioned run directory: `runs/variant_A_v3_2ep_{timestamp}/`
4. Launches the training script with the right args
5. Writes a manifest (`manifest.json (run-time artifact)`) after completion

The `--config-tag` is a short label for the run (e.g. `v3_2ep`, `b_small_3ep`).
It's part of the run ID and directory name, so make it descriptive.

### Launch embedding extraction

```bash
python3 python/launch_run.py extract \
    --variants A_v3_2ep,B_small \
    --embeddings-dir runs/retrieval_embeddings_v3
```

What it does:
1. Runs the invariant checker — blocks if it fails
2. Verifies dataset files exist for every variant
3. Records the extraction in the registry
4. Launches `extract_retrieval_embeddings.py` (which itself runs the invariant
   checker as a precondition — double-gated)
5. Verifies all embedding shapes match dataset sizes after completion

Use `--force` to overwrite an existing embeddings directory (not recommended;
prefer a new versioned directory name).

### Launch retrieval eval

```bash
python3 python/launch_run.py eval \
    --variants A_v3_2ep,B_small \
    --embeddings-dir runs/retrieval_embeddings_v3 \
    --mode eval_to_train \
    --out runs/h6_retrieval/results_v3.json
```

What it does:
1. Verifies all embedding shapes match current datasets — blocks if mismatch
   (prevents the exact bug that invalidated the first H6 run)
2. Records the eval in the registry
3. Launches `retrieval_eval.py` (which also checks shapes — double-gated)
4. Saves results to `--out`

For triangulation, run Mode 2 after Mode 1:
```bash
python3 python/launch_run.py eval \
    --variants A_v3_2ep,B_small \
    --embeddings-dir runs/retrieval_embeddings_v3 \
    --mode train_to_train \
    --out runs/h6_retrieval/results_v3_mode2.json
```

---

## End-to-end workflow for a new experiment

Here's the full sequence for running a new comparison from scratch, using the
A v3 2-epoch retrain as the example:

### Step 0: Check the grid
```bash
python3 python/launch_run.py grid
```
Confirm what exists and what's needed.

### Step 1: Verify datasets are clean
```bash
python3 python/check_invariants.py --datasets datasets --runs runs
```
Must report: `Total: 50 passed, 0 failed, 0 skipped`.

### Step 2: Build any needed datasets (to a versioned dir, never overwrite)
```bash
# Example: per-operator dataset for A v3
python3 python/build_perop_dataset.py   # writes to datasets_perop/
```

### Step 3: Train
```bash
python3 python/launch_run.py train \
    --variant A \
    --epochs 2 \
    --dataset-dir datasets_perop \
    --config-tag v3_2ep \
    --base-script train_v2_resume.py
```
This takes ~1-2 hours on the M4 (MPS, 3375 examples, 2 epochs).

### Step 4: Extract embeddings
```bash
python3 python/launch_run.py extract \
    --variants A_v3_2ep,B_small \
    --embeddings-dir runs/retrieval_embeddings_v3
```
This takes ~4 minutes per variant on MPS.

### Step 5: Build dependency ground truth (if corpus changed)
```bash
python3 python/build_dependency_groundtruth.py
```

### Step 6: Run retrieval eval (Mode 1)
```bash
python3 python/launch_run.py eval \
    --variants A_v3_2ep,B_small \
    --embeddings-dir runs/retrieval_embeddings_v3 \
    --mode eval_to_train \
    --out runs/h6_retrieval/results_v3.json
```

### Step 7: Triangulate (Mode 2)
```bash
python3 python/launch_run.py eval \
    --variants A_v3_2ep,B_small \
    --embeddings-dir runs/retrieval_embeddings_v3 \
    --mode train_to_train \
    --out runs/h6_retrieval/results_v3_mode2.json
```

### Step 8: Check the grid
```bash
python3 python/launch_run.py grid
```
Confirm the new comparison cell is filled and the configs match.

---

## What the enforced preconditions check

### Invariant checker (runs before extraction and eval)

Checks (see `check_invariants.py` for the full list):
1. **Split integrity:** train/eval disjoint by example_id, no intra-file duplicates,
   eval identity identical across variants
2. **Checkpoint-results consistency:** results.json mtime matches checkpoint mtime
3. **Variant-input consistency:** dataset source field matches variant
4. **Vocab-range consistency:** all input_ids within vocab range
5. **Comparison validity:** compared runs have matching configs (epochs, seed, etc.)
6. **Provenance hash consistency:** datasets compared have matching corpus provenance

If any check fails: the script prints `INVARIANT VIOLATION — experiment blocked.`
and exits with code 1. You must fix the violation before proceeding.

### Embedding shape verification (runs before eval)

For every variant in the eval, checks:
- `embeddings_{variant}_train.pt` shape[0] == `datasets/train_{variant}.jsonl` line count
- `embeddings_{variant}_eval.pt` shape[0] == `datasets/eval_{variant}.jsonl` line count

If any mismatch: the script prints `EMBEDDING/DATASET MISMATCH — eval blocked.`
and exits. You must re-extract embeddings from the current datasets.

---

## Contamination prevention rules

These are enforced by the launcher and documented in `RUN_REGISTRY.md`:

1. **Never overwrite `datasets/`.** New builds go to `datasets_{mode}/` or
   `datasets_v{N}/`. The `datasets/` dir is the current canonical version.
2. **Never overwrite embeddings dirs.** Each extraction round gets a versioned dir
   (`runs/retrieval_embeddings_v{N}/`).
3. **Every new training run gets a new directory.** `runs/variant_{V}_{config}_{ts}/`,
   not overwriting an existing one. The launcher refuses to overwrite.
4. **Run the invariant checker before every extraction and eval.** Enforced in code.
5. **Record the run in the registry before starting.** The launcher does this
   automatically. If running scripts directly, add a row to `RUN_REGISTRY.md` first.
6. **Manifests are written by the launcher after training.** If running scripts
   directly, manually create a manifest using `python/manifest.py`.

---

## Bypassing the process (for emergencies only)

Both `extract_retrieval_embeddings.py` and `retrieval_eval.py` accept
`--skip-invariant-check` to bypass the preconditions. This exists for debugging
(e.g., testing code on intentionally-broken fixtures). **Do not use it for real
experiments.** Any result produced with `--skip-invariant-check` should be
marked as unverified in the registry.

---

## File reference

| File | Role |
|---|---|
| `python/launch_run.py` | Structured experiment launcher (train, extract, eval, grid) |
| `python/check_invariants.py` | The gate — 6 invariants, hard-fails on violation |
| `python/manifest.py` | Provenance manifest system (write/load/verify) |
| `python/test_invariants.py` | Unit tests for the invariant checker (23 tests) |
| `docs/experiments/RUN_REGISTRY.md` | Checkpoint provenance reference + comparison matrix |
| `docs/experiments/PIPELINE_HARDENING_SCOPE.md` | Design doc for the harness |
| `docs/experiments/KNOWN_ISSUES.md` | Known bugs and their status |
| `docs/experiments/H6_RETRIEVAL_SCOPE.md` | H6 experiment spec |
| `docs/experiments/H6_RETEST_PLAN.md` | H6 retest plan (triangulated verification) |
| `docs/experiments/EXPERIMENT_PROCESS.md` | This document |
| `python/manage.py` | Self-service control layer — status, results, aliases, dashboard |
| `docs/experiments/MANAGE_PY_TENSORBOARD_SCOPE.md` | Design doc for manage.py + TensorBoard |

---

## `manage.py` — self-service control layer

`launch_run.py` is the structured launcher; `manage.py` wraps it with a
one-command, no-flags interface so the user can check status, see results, and
trigger experiments without memorizing flag combinations. See
[`MANAGE_PY_TENSORBOARD_SCOPE.md`](MANAGE_PY_TENSORBOARD_SCOPE.md) for the full
spec.

### Commands

| Command | What it does |
|---|---|
| `manage.py status` | Show grid + running processes + latest results + what's needed |
| `manage.py results` | Show H6 retrieval (both modes) + probing vs retrieval, with 95% CIs |
| `manage.py grid` | Show the comparison matrix (valid vs confounded) |
| `manage.py invariants` | Run the invariant checker (formatted pass/fail report) |
| `manage.py logs <run_id>` | Tail a specific run's training.log (`--tail N` for one-shot) |
| `manage.py train-av3-2ep` | Launch A v3 2-epoch retrain (pre-configured, guarded) |
| `manage.py extract [variants]` | Extract embeddings (default: all) |
| `manage.py eval [variants] [mode]` | Run H6 retrieval eval |
| `manage.py watch` | Generate auto-refreshing HTML dashboard (`--once` for single snapshot) |
| `manage.py watch --stop` | Stop the watch loop |

### Guards on experiment aliases

Every `train-*` alias enforces three preconditions before launching:

1. **Audit precondition check** — verifies that required audit items (listed in
   `AUDIT_PRECONDITIONS` inside `manage.py`) are marked `[RESOLVED <sha>]` in
   `AUDIT_2026_08_10.md`. Blocks with a clear message if not resolved. Override
   with `--skip-audit-check` (not recommended).
2. **Corpus-provenance check** — verifies the dataset directory's
   `representation_manifest.json` is consistent with the corpus format on disk
   (guards against the corpus-overwrite bug). Override with
   `--skip-provenance-check` (not recommended).
3. **Invariant check** — runs `check_invariants.py` as a preflight. Blocks if
   any invariant fails.

### TensorBoard

Training runs log `train/loss` and `eval/perplexity` to TensorBoard event files
in `runs/{run_id}/tb/`. To visualize:

```bash
tensorboard --logdir runs/ --port 6006
```

Then open `http://localhost:6006` in a browser. For remote access, tunnel:
```bash
ssh -L 6006:localhost:6006 -i <key> -p <port> <user>@<host>
```
