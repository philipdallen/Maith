# Pipeline Quality Gates — Implementation Scope

> **Purpose.** Scoping document for implementing the five-station quality gate system
> defined in [`docs/reference/PIPELINE_QUALITY_GATES.md`](../reference/PIPELINE_QUALITY_GATES.md).
> This is the specification for an implementation agent (OpenHands or similar).
>
> **Read first:**
> - [`docs/reference/PIPELINE_QUALITY_GATES.md`](../reference/PIPELINE_QUALITY_GATES.md) — the full design
> - [`docs/reference/EXPERIMENT_MEASUREMENT.md`](../reference/EXPERIMENT_MEASUREMENT.md) — the measurement
>   validity gaps each gate is designed to catch (see the "Automated Prevention" section)
> - [`docs/experiments/PIPELINE_HARDENING_SCOPE.md`](PIPELINE_HARDENING_SCOPE.md) — prior hardening work this builds on
> - [`python/check_invariants.py`](../../python/check_invariants.py) — the existing invariant checker to extend, not replace

---

## What this work is

The project has checks, but they fire too late and cover the wrong stages. The invariant
checker only runs at train time. There are no gates on the IR build or corpus build. The
most important invariant (comparison validity — Invariant 5) is defined but never called.

This work adds gates at every station so a defect is caught at the station that produced
it, not two stations later when it's already contaminated downstream output.

---

## What already exists — do not rebuild

| File | What it does | Role in the new system |
|---|---|---|
| `python/check_invariants.py` | 7 invariants, CLI + `run_all_checks()` | Gate 3 and Gate 4 source — extend, don't replace |
| `python/launch_run.py` | Experiment launcher with invariant preflight | Wire new gate calls here |
| `python/manage.py` | Control layer, aliases, status | Add `gate` subcommand here |
| `python/manifest.py` | Manifest read/write, provenance hashing | Use for provenance checks in Gates 2 and 3 |
| `validate_roundtrip.py` | 4029/4029 round-trip check | Gate 1-G1-1 — call it, don't rewrite it |
| `Corpus/stats.json` | IR build output stats | Gate 1-G1-2 source |
| `Corpus/representation_manifest.json` | Provenance record | Gate 2-G2-4 source |

---

## Scope: exactly what to build

### Task 1 — Wire Invariant 5 into `run_all_checks()` (30 minutes)

`check_comparison_validity()` is fully implemented in `check_invariants.py` but is never
called from `run_all_checks()`. It is the most important unwired invariant — it would
have caught the epoch confound that invalidated the original H6 run.

**Change:** In `run_all_checks()`, after the block that checks A vs flat, add:

```python
# Check A_v3_2ep vs B_small (the H6 clean comparison) if both exist
# Note: results.json has "variant": "A" (not "A_v3_2ep"), so we must match
# by run directory name, not by the variant field. Scan runs/ for directories
# containing "v3" in the name.
import glob
a_v3_dirs = glob.glob(os.path.join(str(runs_dir), "variant_A_v3*"))
if a_v3_dirs and "variant_B_small" in [str(p) for p in runs_dir.iterdir()]:
    a_v3_results = json.load(open(Path(a_v3_dirs[0]) / "results.json"))
    b_small_results = json.load(open(runs_dir / "variant_B_small" / "results.json"))
    manifests = [a_v3_results, b_small_results]
    all_results.extend(check_comparison_validity(
        manifests, "representation_at_matched_size"
    ))
```

This matches by run *directory name* (`variant_A_v3*`), not by the `variant` field in
`results.json` (which is `"A"` for A_v3_2ep, not `"A_v3_2ep"`). This is more robust than
scanning `results_by_variant` keys.

**Acceptance:** `python3 python/check_invariants.py` includes a comparison_validity
result in its output when both A_v3 and B_small runs exist in `runs/`.

---

### Task 2 — Add `check_ir_build.py` (Gate 1)

New script: `python/check_ir_build.py`

Reads `Corpus/corpus.per_operator.jsonl` (or whichever corpus path is passed) and
`Corpus/stats.json`, runs the four checks below, and exits non-zero on failure.

```
python3 python/check_ir_build.py [--corpus Corpus/corpus.per_operator.jsonl]
                                  [--stats Corpus/stats.json]
                                  [--max-seq-len 1024]
```

**Checks to implement:**

| ID | Check | Implementation |
|---|---|---|
| G1-1 | Round-trip passes | Call `validate_roundtrip.py` as subprocess; pass if exit code 0 |
| G1-2 | Yield is 100% | Read `stats.json`; assert `successfulExamples == totalDeclarations` and all `failureStats` values are 0 |
| G1-3 | Format consistency | Sample first 200 records from corpus JSONL; count `gen:FullName` tokens vs `GEN_<BUCKET>` tokens; fail if both > 0 (mixed = corrupt). Report the detected format. |
| G1-4 | No overlength sequences | Read all records; collect `seq_len` values (or compute `len(tokens)` if `seq_len` absent); fail if any exceed `--max-seq-len` (default 1024), report count and worst offender |

**Output format:** Same `PASS/FAIL/SKIP` style as `check_invariants.py`.

**Do not** re-implement the round-trip logic — call `validate_roundtrip.py` as a
subprocess and propagate its exit code.

---

### Task 3 — Add `check_corpus.py` (Gate 2)

New script: `python/check_corpus.py`

Reads the corpus JSONL and `Corpus/representation_manifest.json`, runs the checks below.

```
python3 python/check_corpus.py [--corpus Corpus/corpus.per_operator.jsonl]
                                [--manifest Corpus/representation_manifest.json]
```

**Checks to implement:**

| ID | Check | Implementation |
|---|---|---|
| G2-1 | Declaration count plausible | `stats.json` `totalDeclarations` is between 3500 and 6000 (the known range for 14 Mathlib modules; adjust bounds if modules change). Fail outside range with actual count. |
| G2-2 | Module coverage | Load `Scripts/BuildCorpus.lean` or the module list from `scripts/module_expansion_targets.json` to get expected modules; verify each module has ≥1 declaration in the corpus. Report any missing module. |
| G2-3 | No duplicate example IDs | Stream corpus JSONL, collect all `name` fields (use `module::name` as the key); fail if any appear more than once. Report duplicates. |
| G2-4 | Representation ID stamped | `Corpus/representation_manifest.json` exists and has a non-empty `representation_id` field. |
| G2-5 | Version strings current | Read `encoderVersion` from `Corpus/stats.json`; compare against the version string in `Maith/Encoder.lean` (grep for `version :=` or similar). Warn (not fail) if they differ — this is advisory since the Lean toolchain may not be present. |

**Note on G2-5:** If the Lean toolchain is absent (no `lean` on PATH), skip G2-5 and
emit SKIP with explanation. Do not fail the gate for a missing toolchain.

---

### Task 4 — Add post-training gate to `launch_run.py` (Gate 4 completion)

After training completes in `cmd_train()`, add a validation block before the final
manifest write. The existing post-train code writes `results.json` and the manifest;
add checks before that point.

**Checks to add in `cmd_train()`, after the training subprocess exits 0:**

```python
def _validate_training_output(run_dir: Path, variant: str) -> list[str]:
    """Returns list of failure strings. Empty = all pass."""
    errors = []

    # G4-1: checkpoint exists (already checked by Invariant 2 — assert here for fast fail)
    ckpt = run_dir / "checkpoint-final"
    if not ckpt.exists():
        errors.append("G4-1: checkpoint-final/ not found")
        return errors  # can't proceed with other checks

    # G4-2: results.json has required fields
    rp = run_dir / "results.json"
    if rp.exists():
        r = json.load(open(rp))
        required = ["eval_perplexity", "epochs", "train_examples", "n_params_M",
                    "vocab_size", "learning_rate", "effective_batch_size", "max_seq_len"]
        missing = [f for f in required if f not in r]
        if missing:
            errors.append(f"G4-2: results.json missing fields: {missing}")

        # G4-4: perplexity plausible
        ppl = r.get("eval_perplexity")
        vocab = r.get("vocab_size", 151643)
        if ppl is not None:
            if not (1.0 < ppl < vocab):
                errors.append(f"G4-4: eval_perplexity={ppl} not in (1.0, {vocab})")
    else:
        errors.append("G4-2: results.json not written")

    # G4-3: loss descended (from loss_curve.json)
    lc = run_dir / "loss_curve.json"
    if lc.exists():
        curve = json.load(open(lc))
        train = curve.get("train", [])
        if len(train) >= 2:
            initial = train[0]["loss"]
            final = train[-1]["loss"]
            # Design spec: ≥50% reduction (PIPELINE_QUALITY_GATES.md G4-3)
            if final >= initial * 0.5:  # less than 50% reduction = no meaningful progress
                errors.append(f"G4-3: loss did not descend sufficiently: {initial:.3f} → {final:.3f} "
                               f"({(1 - final/initial)*100:.0f}% reduction, need ≥50%)")
    else:
        errors.append("G4-3: loss_curve.json not written — cannot verify loss descent")

    return errors
```

Call `_validate_training_output()` after the training subprocess exits and before
`write_results_manifest()`. If errors are non-empty, print them and exit non-zero.

---

### Task 5 — Wire Gate 3 at dataset-build time

Currently Gate 3 (the invariant checker) runs at `launch_run.py train` time, before
training. It should also run immediately after `build_dataset.py` writes the datasets,
so a corrupt dataset is caught before it is ever used.

**Current `build_dataset.py` invocation:** `build_dataset.py` is a standalone script
that reads `Corpus/corpus.per_operator.jsonl` (or `corpus.jsonl`) and writes to a
dataset directory (e.g., `datasets_perop/` or `datasets/`). It takes `--corpus`,
`--out-dir`, and variant-specific flags. It is not currently wired through
`launch_run.py` — it is run directly.

**Change:** In `launch_run.py`, add a `build-dataset` subcommand that:

1. Calls `build_dataset.py` with the appropriate flags (passing `--corpus`,
   `--out-dir`, and any variant-specific flags like `--per-operator`)
2. Immediately after `build_dataset.py` exits 0, calls `check_invariants.py` with:
   - `--datasets <out-dir>` (the newly written directory)
   - `--runs runs/` (for cross-checks against existing checkpoints)
3. Exits non-zero if any invariant fails, with a message pointing back to the corpus

```python
# In launch_run.py, add:
def cmd_build_dataset(args):
    """Build datasets and run Gate 3 immediately after."""
    script = REPO / "python" / "build_dataset.py"
    cmd = [sys.executable, str(script),
           "--corpus", str(args.corpus),
           "--out-dir", str(args.dataset_dir)]
    # ... (pass through any variant/flags)

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("Dataset build failed.")
        return 1

    # Gate 3: run invariant checker on the freshly built datasets
    print("Running Gate 3 — Dataset Quality Check ...")
    inv_result = subprocess.run(
        [sys.executable, str(REPO / "python" / "check_invariants.py"),
         "--datasets", str(args.dataset_dir), "--runs", str(RUNS_DIR)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    print(inv_result.stdout)
    if inv_result.returncode != 0:
        print("GATE 3 FAILED — datasets may be corrupt. Do not proceed to training.")
        return 1
    print("Gate 3 passed — datasets are valid.")
    return 0
```

This ensures the production line is: corpus passes Gate 1+2 → dataset built → Gate 3
passes → training may proceed.

---

### Task 6 — Add `manage.py gate <station>` command

Add a subcommand to `manage.py` so any gate can be run manually:

```
python3 python/manage.py gate ir       # Gate 1: check_ir_build.py
python3 python/manage.py gate corpus   # Gate 2: check_corpus.py
python3 python/manage.py gate dataset  # Gate 3: check_invariants.py split+vocab
python3 python/manage.py gate train    # Gate 4: check_invariants.py ckpt + loss check
python3 python/manage.py gate eval     # Gate 5: Invariant 5 + embedding match
python3 python/manage.py gate all      # Run all gates in sequence, stop on first failure
```

This lets Kit or a human run any gate in isolation to diagnose a specific station
without triggering a full experiment.

**Implementation:** Wire each `gate <station>` to call the appropriate script via
`subprocess.run()`, following the same pattern as `run_invariant_check()` already
uses in `manage.py`.

---

## Acceptance Criteria

The implementation is complete when:

1. `python3 python/check_invariants.py` includes a `comparison_validity` result in
   output (Task 1)
2. `python3 python/check_ir_build.py --corpus Corpus/corpus.per_operator.jsonl` exits 0
   on the current corpus, reports all four checks, and exits 1 with a clear message
   if any fail (Task 2)
3. `python3 python/check_corpus.py --corpus Corpus/corpus.per_operator.jsonl` exits 0
   on the current corpus, reports all five checks (Task 3)
4. Running `python3 python/launch_run.py train --variant A --epochs 2 ...` on a
   successful training run prints Gate 4 results before registering the run (Task 4)
5. `python3 python/manage.py gate all` runs all gates and reports pass/fail per station
   (Task 6)

**Regression test:** After completing Tasks 1–6, run `python3 -m pytest python/tests/`
— all existing tests must still pass. No existing behavior should change.

---

## Out of scope for this task

- **CI/GitHub Actions integration** — that is P3 in the design doc; this is P0–P1
- **Rewriting `check_invariants.py`** — extend it, don't replace it
- **G1-5 (lake build tests)** — requires Lean toolchain; skip if `lean` not on PATH
- **G2-5 version string check** — advisory warn only, not a hard gate failure
- **G5 (evaluation gates)** — the full suite for gate 5 is separate scope after P0–P1 is stable
- **Any changes to `train_v2_resume.py` or `build_dataset.py`** — the gate scripts read
  their output; they do not modify the scripts that produce it

---

## File map — what gets created or changed

| File | Action | Notes |
|---|---|---|
| `python/check_invariants.py` | Modify | Task 1: wire Invariant 5 into `run_all_checks()` |
| `python/check_ir_build.py` | Create | Task 2: Gate 1 script |
| `python/check_corpus.py` | Create | Task 3: Gate 2 script |
| `python/launch_run.py` | Modify | Task 4: post-train validation; Task 5: dataset gate call |
| `python/manage.py` | Modify | Task 6: `gate` subcommand |
| python/tests/test_quality_gates.py | Create | Tests for the new gate scripts |

---

## Test cases to include in test_quality_gates.py

| Test | What it verifies |
|---|---|
| `test_gate1_passes_on_valid_corpus` | `check_ir_build.py` exits 0 on a synthetic valid corpus JSONL |
| `test_gate1_fails_on_mixed_format` | Corpus with both `gen:FullName` and `GEN_BUCKET` tokens fails G1-3 |
| `test_gate1_fails_on_overlength` | Corpus with a sequence exceeding `max-seq-len` fails G1-4 |
| `test_gate2_fails_on_duplicate_ids` | Corpus with two records sharing the same `name` fails G2-3 |
| `test_gate4_fails_on_no_loss_descent` | `_validate_training_output()` returns an error when initial and final loss are equal |
| `test_gate4_fails_on_implausible_ppl` | `_validate_training_output()` fails when `eval_perplexity < 1.0` or `> vocab_size` |
| `test_invariant5_wired` | `run_all_checks()` includes a `comparison_` key in results when A and B_small runs exist |
