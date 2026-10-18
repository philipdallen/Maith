# Pipeline Quality Gates

> **STATUS: PROPOSAL — drafted by Kit 2026-08-12, not yet reviewed or implemented.**
> This document defines the design. Implementation is a separate step.
>
> **Companion:** [`EXPERIMENT_MEASUREMENT.md`](EXPERIMENT_MEASUREMENT.md) documents the
> validity gaps these gates are designed to catch. Each gate traces to a specific
> measurement concern documented there.

---

## The Production Line Metaphor

A physical production line has **stations** and **quality gates**. A part moves from
station to station. At each gate a inspector checks specific properties before the part
is allowed to continue. If the gate fails, the part goes back — it does not continue
downstream. Nothing at station 4 can be contaminated by a defect that should have been
caught at station 2.

Maith currently has some checks (Lean unit tests, the Python invariant checker) but
they are not organized this way. A failed IR build can still produce a corpus. A
corrupt corpus can still produce datasets. Datasets built from the wrong corpus can
still feed a training run. The invariant checker only fires at experiment time — by
then the damage is upstream.

This document defines the production line for Maith: the stations, what each one
produces, and what the gate checks before anything moves forward.

---

## The Five Stations

```
Station 1         Station 2         Station 3         Station 4         Station 5
IR Build    →     Corpus Build  →   Dataset Build →   Training     →   Evaluation
(Lean)            (Lean→JSONL)      (JSONL→splits)    (train_v2)       (perplexity,
                                                                         retrieval,
                                                                         probing)
```

Each arrow is a **gate**. The gate must pass before the next station can start.

---

## Station 1 — IR Build

**What it does:** The Lean pipeline (`Scripts/BuildCorpus.lean`) runs
`MetaExtractor → Normalizer → Encoder` on every declaration and writes
`Corpus/stats.json` plus a corpus whose name encodes the bucket mode (#35):
`Corpus/corpus.per_operator.jsonl` under `--per-operator`, else
`Corpus/corpus.jsonl`.

**Inputs:** Lean source files, `Maith/*.lean`

**Output:** `Corpus/corpus.per_operator.jsonl` (canonical per-operator build),
`Corpus/stats.json`

### Gate 1 — IR Build Quality Check

Run before corpus output is accepted as valid.

| Check | Pass condition | Failure means |
|---|---|---|
| **G1-1 Round-trip** | `validate_roundtrip.py` passes all N declarations (currently 4,029/4,029) | Encoder or Decoder has a regression; output is not lossless |
| **G1-2 Yield** | `stats.json` `successfulExamples == totalDeclarations` and `failureStats` all zero | Some declarations failed extraction silently |
| **G1-3 Format consistency** | All tokens are either `gen:FullName` style (per-operator) or `GEN_<BUCKET>` style (module-mode), never both | Mixed-format corpus — data is corrupt |
| **G1-4 Sequence length** | `maxLength <= 2048` (or the configured context window); no pathological sequences | Long sequences that will OOM or get silently truncated during training |
| **G1-5 Lean build** | `lake build tests` exits 0 | Unit tests fail — Lean pipeline has a regression |

**Script to add:** `python3 python/check_ir_build.py` — reads `Corpus/stats.json`
and `Corpus/corpus.per_operator.jsonl`, runs checks G1-1 through G1-4. G1-5 requires
the Lean toolchain and runs separately (or in CI).

**Current status:**
- G1-1: `validate_roundtrip.py` exists and passes ✅
- G1-2: `stats.json` exists and is checked manually ⚠️ (not automated)
- G1-3: checked by Invariant 7 in `check_invariants.py` but only at train time ⚠️
- G1-4: not checked anywhere ❌
- G1-5: `lake build tests` exists but not wired into any gate ⚠️

---

## Station 2 — Corpus Build

**What it does:** Validates the raw corpus JSONL, assigns a stable `representation_id`,
and writes `Corpus/representation_manifest.json` to record the corpus provenance.

This station is currently implicit — the corpus is written by Station 1 and consumed
directly by Station 3 with no intermediate validation step.

**Inputs:** `Corpus/corpus.per_operator.jsonl`, `Corpus/stats.json`

**Output:** `Corpus/representation_manifest.json` (provenance record, already exists),
`Corpus/corpus.per_operator.jsonl` (unchanged, now stamped as validated)

### Gate 2 — Corpus Acceptance Check

| Check | Pass condition | Failure means |
|---|---|---|
| **G2-1 Declaration count** | Count matches the expected module list × average yield | Declarations were silently dropped or duplicated |
| **G2-2 Module coverage** | All 14 expected modules present with ≥1 declaration each | A module failed to load (silent Lean import failure) |
| **G2-3 No duplicate IDs** | All `example_id` values unique across the corpus | Duplicate declarations — would inflate training metrics |
| **G2-4 Representation ID stamped** | `representation_manifest.json` present and `representation_id` matches corpus token format | Provenance not recorded; next build could silently overwrite |
| **G2-5 Version strings** | `encoderVersion` and `irVersion` in `stats.json` match the versions in `Maith/Encoder.lean` and `ENCODER_FORMAT.md` | F2 from the Lean audit — stale version strings cause provenance confusion downstream |

**Script to add:** `python3 python/check_corpus.py` — reads the corpus JSONL and
manifest, runs G2-1 through G2-5.

**Current status:**
- G2-1: counted in `stats.json` but not gate-checked ⚠️
- G2-2: not checked ❌
- G2-3: not checked ❌
- G2-4: manifest exists ✅, not verified against corpus format ⚠️
- G2-5: fixed by F2 in the Lean audit ✅ (but not re-verified automatically)

---

## Station 3 — Dataset Build

**What it does:** `build_dataset.py` reads `Corpus/corpus.per_operator.jsonl`, splits
into train/eval (stratified by module), maps tokens to integer IDs, and writes
`datasets_perop/train_A.jsonl`, `eval_A.jsonl`, `vocab_A_perop.json`, etc.

**Inputs:** `Corpus/corpus.per_operator.jsonl`, `Corpus/representation_manifest.json`

**Output:** `datasets_perop/train_*.jsonl`, `eval_*.jsonl`, `vocab_*.json`,
`datasets_perop/representation_manifest.json`

### Gate 3 — Dataset Quality Check

| Check | Pass condition | Failure means |
|---|---|---|
| **G3-1 Split integrity** | Train/eval disjoint by `example_id`; eval sets identical across variants | Invariant 1 — data leakage into eval |
| **G3-2 Vocab range** | All `input_ids` within `[0, vocab_size)` | Invariant 4 — OOM or embedding crash at train time |
| **G3-3 Variant-input match** | `source` field matches expected source for each variant | Invariant 3 — wrong corpus fed to wrong variant |
| **G3-4 Provenance hash** | All variants built from the same corpus commit hash | Invariants built from different corpus versions can't be compared |
| **G3-5 Count consistency** | Train count and eval count match across variants (for variants drawn from the same corpus) | Some variants have more data than others — confounds comparison |
| **G3-6 No zero-length sequences** | All examples have `seq_len > 0`; no empty `input_ids` | Silent training failures |

**Script:** `python3 python/check_invariants.py --check split` already covers G3-1,
G3-3, G3-4. G3-2 covered by `--check vocab`. G3-5 and G3-6 are new.

**Current status:**
- G3-1, G3-2, G3-3, G3-4: covered by `check_invariants.py` ✅ (but only at train time, not at dataset-build time)
- G3-5: partially covered (train count uniform check in Invariant 1) ⚠️
- G3-6: not checked ❌

---

## Station 4 — Training

**What it does:** `train_v2_resume.py` fine-tunes Qwen2.5-Coder-0.5B on a variant's
training split and writes `runs/variant_*/checkpoint-final/` and `results.json`.

**Inputs:** `datasets_perop/train_*.jsonl`, `datasets_perop/vocab_*.json`

**Output:** `runs/variant_A_v3_2ep/checkpoint-final/`, `runs/variant_A_v3_2ep/results.json`,
`runs/variant_A_v3_2ep/loss_curve.json`

### Gate 4 — Training Output Quality Check

| Check | Pass condition | Failure means |
|---|---|---|
| **G4-1 Checkpoint exists** | `checkpoint-final/` present and non-empty | Training crashed without a checkpoint |
| **G4-2 Results complete** | `results.json` has `eval_perplexity`, `epochs`, `train_examples`, `n_params_M`, `vocab_size`, `learning_rate`, `effective_batch_size`, `max_seq_len` | Incomplete run — metrics can't be compared. **Note:** pre-2026-08-11 checkpoints (B_small, B, C, flat) lack `learning_rate`/`effective_batch_size`/`max_seq_len`. The gate should grandfather these legacy checkpoints or warn, not fail. |
| **G4-3 Loss descended** | `loss_curve.json (run-time artifact)` final train loss < initial train loss by ≥50% | Training diverged or made no progress |
| **G4-4 Perplexity plausible** | `eval_perplexity` in `(1.0, vocab_size)` — not NaN, not >100 | Training collapse or eval bug |
| **G4-5 Checkpoint-results consistency** | `results.json` mtime within 7 days of checkpoint mtime | Invariant 2 — stale results.json from a previous run |
| **G4-6 Config recorded** | `results.json` includes `learning_rate`, `effective_batch_size`, `max_seq_len` | Can't reproduce the run or compare configs |

**Script:** `python3 python/check_invariants.py --check ckpt` covers G4-1, G4-5.
G4-2, G4-3, G4-4, G4-6 are new additions.

**Current status:**
- G4-1, G4-5: covered ✅
- G4-2: partially — `eval_perplexity` and `epochs` present in recent runs ⚠️ (`learning_rate` etc. missing from B_small)
- G4-3: not checked ❌
- G4-4: not checked ❌
- G4-6: partially — `learning_rate` added by recent `--lr` flag work ⚠️

---

## Station 5 — Evaluation

**What it does:** Three distinct evaluation types, each with its own gate:

- **5a Perplexity** — already computed during training (end of each epoch eval)
- **5b Retrieval** — `extract_retrieval_embeddings.py` + `retrieval_eval.py`
- **5c Probing** — `probing_task.py`

**Inputs:** Checkpoints from Station 4, datasets from Station 3, ground truth from
`build_dependency_groundtruth.py`

**Output:** `runs/h6_retrieval/results_*.json`, `runs/probing/task*_results.json`

### Gate 5 — Evaluation Integrity Check

| Check | Pass condition | Failure means |
|---|---|---|
| **G5-1 Embedding-checkpoint match** | Embedding files were extracted from the checkpoint they claim (variant, epoch, vocab_size match) | Invariant 3 (extraction bug) — embeddings from wrong model |
| **G5-2 Ground truth coverage** | ≥50% of eval queries have ≥1 dep in train pool | Ground truth is too sparse to be meaningful |
| **G5-3 Retrieval CI non-degenerate** | Bootstrap CIs are finite and `ci_hi - ci_lo > 0` | Degenerate eval — all scores identical |
| **G5-4 Comparison validity** | Compared variants match on `epochs`, `seed`, `train_examples` | Invariant 5 — epoch confound (the DEC-030 issue). **This is the single most important unwired check** — it would have caught the epoch confound that invalidated the original H6 run. Wiring it is P0 priority (see [`QUALITY_GATES_SCOPE`](../experiments/QUALITY_GATES_SCOPE.md) Task 1). |
| **G5-5 Probe accuracy above baseline** | Linear probe accuracy > 1/n_classes (random baseline) | Probe is not learning anything; representations are random |

**Current status:**
- G5-1: caught by Invariant 3, but only if datasets_dir is passed correctly ⚠️
- G5-2: not checked ❌
- G5-3: not checked ❌
- G5-4: Invariant 5 exists in `check_invariants.py` but **is never called** (dead code — the most important unwired invariant) ❌
- G5-5: not checked ❌

---

## The Gate Summary

| Gate | When it runs | Script | Status |
|---|---|---|---|
| **Gate 1** — IR Build | After `lake build` / `BuildCorpus.lean` | `check_ir_build.py` (new) | ❌ not implemented |
| **Gate 2** — Corpus Accept | After corpus JSONL written | `check_corpus.py` (new) | ❌ not implemented |
| **Gate 3** — Dataset Build | After `build_dataset.py` | `check_invariants.py --check split/vocab` | ⚠️ partial, only called at train time |
| **Gate 4** — Training Output | After training completes | `check_invariants.py --check ckpt` + new checks | ⚠️ partial |
| **Gate 5** — Evaluation | After extraction/retrieval/probing | Invariant 5 (unwired) + new checks | ❌ mostly missing |

---

## Implementation Plan

The goal is to wire gates into `launch_run.py` (and a new `manage.py` entry point)
so that each stage automatically runs its gate before writing output to the next
station. Failures block forward progress with a clear error message.

### Priority order

**P0 — Wire what already exists to earlier in the pipeline (1 day):**
1. Run `check_invariants.py` at dataset-build time, not just at train time
2. Wire Invariant 5 (comparison validity) into `run_all_checks()` — it's dead code today
3. Add `manage.py gate <station>` command to run any gate manually

**P1 — Fill the missing checks in existing scripts (2 days):**
4. Add G4-3 (loss descended) and G4-4 (perplexity plausible) to `launch_run.py` post-train validation
5. Add G3-6 (no zero-length sequences) to dataset build validation
6. Add G5-1 (embedding-checkpoint match) to `extract_retrieval_embeddings.py`

**P2 — New gate scripts (3 days):**
7. `python3 python/check_ir_build.py` — Gate 1 (reads corpus JSONL and stats.json)
8. `python3 python/check_corpus.py` — Gate 2 (module coverage, duplicate IDs, version strings)

**P3 — CI integration (after P0–P2 stable):**
9. GitHub Actions workflow: on push to `kit/dev`, run Gate 3 (dataset checks) against
   `datasets_perop/` and `datasets/`, and `lake build tests` for Gate 1-G1-5

---

## How It Changes `launch_run.py`

Currently `launch_run.py` runs the invariant checker once at the start of every
command. Under this design it runs the appropriate gate at each transition:

```
launch_run.py train
  → Gate 3 (dataset quality) — before training starts
  → [training runs]
  → Gate 4 (training output) — before results.json is written
  → PASS: run registered, output accepted

launch_run.py extract
  → Gate 4 (checkpoint exists, results complete) — before extraction starts
  → [extraction runs]
  → Gate 5-G5-1 (embedding-checkpoint match) — before embeddings accepted

launch_run.py eval
  → Gate 5-G5-4 (comparison validity) — before retrieval eval starts
  → [retrieval eval runs]
  → Gate 5-G5-2/G5-3 (ground truth coverage, CI non-degenerate) — after

launch_run.py build-dataset (new command)
  → Gate 1 (IR build) — verify corpus is valid before building datasets
  → [build_dataset.py runs]
  → Gate 3 (dataset quality) — immediately after
```

---

## One Concrete Example

What this looks like for the next planned run — A_v3_2ep retrain on the clean split:

```
$ python3 python/launch_run.py build-dataset --variant A --dataset-dir datasets_perop

Gate 1 — IR Build
  PASS  G1-1 round_trip: 4029/4029 declarations pass
  PASS  G1-2 yield: 4029 successful, 0 failures
  PASS  G1-3 format: per_operator (gen:FullName=1247, GEN_=0 in 100 samples)
  FAIL  G1-4 seq_len: 3 sequences exceed max_len=512 (max=12188)
  → BLOCKED: resolve G1-4 before dataset build proceeds

$ python3 python/launch_run.py train --variant A --epochs 2 --dataset-dir datasets_perop

Gate 3 — Dataset Quality
  PASS  G3-1 split_A_disjoint: train=3375 eval=376
  PASS  G3-2 vocab_range_A_train: all in [0, 2254)
  PASS  G3-3 variant_input_A_train: all 3375 records source=perop
  PASS  G3-5 split_train_count_uniform: all=3375
  PASS  G3-6 no_zero_length: all examples seq_len>0
  All gates pass — training proceeding.

  [training runs — 43 minutes]

Gate 4 — Training Output
  PASS  G4-1 checkpoint_exists: checkpoint-final/ present
  PASS  G4-2 results_complete: perplexity=1.2928, epochs=2, params=359.9M
  PASS  G4-3 loss_descended: 3.14 → 0.23 (93% reduction)
  PASS  G4-4 perplexity_plausible: 1.2928 in (1.0, 2254)
  PASS  G4-5 checkpoint_results_mtime: diff=0.01d
  PASS  G4-6 config_recorded: lr=2e-4, batch=8, max_seq_len=1024
  All gates pass — run registered, results accepted.
```

The agent (or OpenHands) sees a clear, station-by-station pass/fail output. A failure
at any gate is an explicit stop with the specific check that failed, not a silent
corruption that surfaces three steps later.
