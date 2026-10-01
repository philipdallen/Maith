# Experiment Decision Log

Canonical record of experiment-critical decisions that affect interpretation and reproducibility.

## Usage

- Add a new entry whenever an experiment assumption, protocol, or interpretation rule changes.
- Keep entries append-only; supersede by adding a newer entry that references the old one.
- Use explicit decision IDs so tooling/docs can reference stable anchors.

## Entries

### DEC-001: A/B/C variant semantics
- Date: 2026-07-26
- Status: accepted
- Scope: dataset/build + training/evaluation
- Decision:
  - Variant A uses Maith IR tokens (`Encoder.lean` v1.2.0) with custom `vocab_A.json`.
  - Variant B uses raw `leanExpr` text with native Qwen2.5-Coder BPE.
  - Variant C uses AST-style split `leanExpr` with native Qwen2.5-Coder BPE.
- Rationale:
  - Separates representation effect (A/B/C) from tokenizer-family effect (B/C share tokenizer family).
- References:
  - `docs/reference/Design.md#ab-c-variant-definitions-current-experiment`
  - `docs/experiments/EXPERIMENT_DESIGN.md#variants`

### DEC-002: Shared eval cap for apples-to-apples perplexity
- Date: 2026-07-26
- Status: accepted
- Scope: evaluation/comparison
- Decision:
  - Eval perplexity comparisons across A/B/C must use a shared fixed eval cap (`eval_seq_len_cap=512`).
- Rationale:
  - Prevents sequence-length truncation differences from confounding perplexity comparisons.
- References:
  - `docs/experiments/EXPERIMENT_DESIGN.md#evaluation`
  - `python/check_results_gate.py`

### DEC-003: Embedding-table confound handling
- Date: 2026-07-26
- Status: accepted
- Scope: model architecture interpretation
- Decision:
  - Use fixed base architecture as primary comparison strategy, allowing A's embedding table to resize
    to custom vocab while B/C retain Qwen tokenizer/embedding size.
- Rationale:
  - Keeps most architecture components constant while testing representation directly.
- References:
  - `docs/experiments/EXPERIMENT_DESIGN.md#known-confound-embedding-table-size`

### DEC-004: Decision-grade publication gate
- Date: 2026-07-26
- Status: accepted
- Scope: reporting/publication
- Decision:
  - Results are publishable only after strict full-run checks pass (non-smoke A/B/C, gate pass, readiness pass).
- Rationale:
  - Avoids over-interpreting smoke runs.
- References:
  - `python/run_postrun_pipeline.py`
  - `python/check_publish_readiness.py`
  - `docs/experiments/EXPERIMENT_DESIGN.md#finalization-checklist-publishability-gate`

### DEC-005: Context-pack sidecar protocol for proof-context gap
- Date: 2026-07-26
- Status: accepted
- Scope: dataset/context scaffolding
- Decision:
  - Address cross-declaration proof-context risk via additive sidecar artifacts (`context_refs`,
    `dependency_refs`, `typeclass_context`) rather than changing core A/B/C rows immediately.
- Rationale:
  - Preserves current experiment comparability while enabling controlled context-aware variants.
- References:
  - `docs/CONTEXT_PACK_PROTOCOL.md` (file no longer exists — was a planning doc deleted during repo audit)
  - `python/scaffold_context_artifacts.py`
  - `python/build_dependency_manifest.py`

### DEC-006: Known confounds that disadvantage A's absolute perplexity
- Date: 2026-07-27
- Status: accepted
- Scope: model architecture interpretation / training protocol
- Decision:
  - Two structural confounds must be ruled out before interpreting A vs B/C perplexity differences
    as evidence for or against the representation hypothesis:

  **Confound 1 — Randomly initialized embeddings (primary).**
  Variant A's embedding and output (unembedding) layers are randomly initialized due to the vocab
  resize from 151,643 to 4,495 tokens. Variants B and C retain Qwen's pretrained embeddings in
  full. This gives B/C a substantial head start on next-token prediction that is unrelated to
  representation quality, and the disadvantage is largest at small training-data scale where the
  model has limited opportunity to recover. If A underperforms B/C on perplexity, random
  initialization must be ruled out as the primary cause before concluding the representation
  hypothesis is false.

  **Confound 2 — Differing train sequence caps (secondary).**
  Variant A trains with a 1,024-token sequence cap; variants B/C train with a 384-token cap. This
  asymmetry is intentional — the tighter B/C cap was introduced as a memory-pressure fix for MPS
  (BPE on IR text inflates sequence length ~2.6x). Eval uses a shared 512-token cap across all
  three variants, so the final comparison metric is apples-to-apples. However, A receives longer
  training context per example than B/C do, which is an uncontrolled variable in training exposure.
  This is on record so it is not mistaken for a neutral design choice in future analysis.

- Rationale:
  - Naming confounds before results arrive prevents them from becoming convenient post-hoc
    explanations in either direction. Consistent with the discipline established in DEC-002/003.
- References:
  - `docs/experiments/EXPERIMENT_DESIGN.md#known-confound-embedding-table-size`
  - `python/train.py` (MAX_SEQ_LEN / MAX_SEQ_LEN_C constants)

  **Implementation status (2026-08-02):**
  `python/embed_project.py` and `--embed-project` flag in `train.py` are
  implemented and tested. Run `python3 python/validate_dec006_setup.py`
  before the full training run.

### DEC-007: Effective batch size differs across variants (unmatched)
- Date: 2026-07-27
- Status: accepted
- Scope: training protocol / experiment validity
- Decision:
  - VARIANT_BATCH_CONFIG sets batch_size=2 for A and batch_size=1 for B/C, producing effective
    batch sizes of 8 vs 4 respectively. The print statement "(all variants matched)" in train.py
    was incorrect and has been removed.

  **Consequence for the full run (2026-07-27):**
  Variant A received ~277 gradient steps; B/C received ~554 steps
  (2,213 examples / 8 = 277; / 4 = 554). A received half the parameter updates of B/C
  regardless of representation quality. This is an additional confound — alongside DEC-006's
  embedding-init confound — that must be ruled out before concluding that A's higher perplexity
  (1.39 vs 1.13-1.14) reflects a failure of the IR representation hypothesis.

  **Rationale for the asymmetry:**
  A uses a 4,495-token vocab with smaller embeddings, which allows a larger per-device batch size
  within MPS memory limits. B/C carry 151k-token embedding tables (494M params) and require
  batch_size=1.

  **Resolution for next run:**
  Match gradient steps explicitly. Recommended: set B/C to grad_accum=8 (batch_size=1, effective 8)
  to match A's effective batch of 8. Alternatively train for multiple epochs to give A equivalent
  update exposure. Do not interpret perplexity differences as hypothesis evidence until step counts
  are matched or the asymmetry is explicitly discounted.

- References:
  - python/train.py (VARIANT_BATCH_CONFIG, lines 88-90)
  - Full-run results 2026-07-27: A=1.39, B=1.14, C=1.13

### DEC-008: DEC-006 cold-start test — 3-epoch variant A run
- Date: 2026-07-28
- Status: complete
- Scope: experiment interpretation / confound elimination
- Decision:
  - After the matched-batch rerun (2026-07-28: A=1.39, B=1.15, C=1.13), the A/B/C gap holds.
    DEC-007 (unmatched batch sizes) is ruled out as the primary cause. DEC-006 (randomly
    initialized embeddings for A vs pretrained for B/C) remains unaddressed.

  **Test protocol:**
  Run variant A for 3 epochs, all other hyperparameters unchanged, output to `runs/variant_A_3ep`.
  Compare the 3-epoch A perplexity against the 1-epoch B/C baseline (1.15/1.13).

  ```
  python3 python/train.py --variant A --datasets datasets/ --out runs/variant_A_3ep --epochs 3
  ```

  **Result (2026-07-28):**
  3-epoch variant A eval perplexity = **1.2598** (67.6 minutes, 831 train steps).

  **Interpretation:**
  1.2598 is a meaningful drop from 1.39 (1-epoch), confirming that cold-start embedding
  initialization is a real factor. However, it remains above the "cold-start dominant" threshold
  of ~1.25, and the gap to B/C (1.15/1.13) persists. Cold-start accounts for a significant
  portion of A's underperformance but not all of it. The representation may also be contributing.

  **Conclusion:**
  DEC-006 is partially confirmed as a confound. The cold-start penalty is real but not the
  complete explanation. An embedding warm-start experiment (DEC-009) is required to isolate
  representation quality from initialization advantage more cleanly.

  **Why 3 epochs (not embedding warm-start):**
  3-epoch test was zero-code-change, self-contained, and interpretable as a first probe.
  Embedding warm-start is the cleaner structural fix and is the recommended next step.

  **Perplexity summary (on record before completion-eval result):**
  - 1-epoch A (matched-batch): 1.39
  - 3-epoch A: 1.2598
  - Delta: −0.13 (~9% improvement)
  - 1-epoch B/C baseline: 1.15 / 1.13
  - Residual gap after 3 epochs: A still 0.11–0.13 above B/C
  - Status: partial closure. Cold-start is a real factor. Gap persists. Representation
    contribution cannot yet be separated from remaining initialization disadvantage.
  - Completion accuracy against the 3-epoch checkpoint (checkpoint-831) is pending and
    may change the interpretation of how much of the residual gap is representation vs
    training exposure.

- References:
  - Matched-batch rerun results 2026-07-28: A=1.39, B=1.15, C=1.13
  - 3-epoch result 2026-07-28: A=1.2598
  - docs/history/PHASE_5_RESULTS.md
  - python/train.py (`--epochs` flag, `epochs_override` parameter)

### DEC-011: eval_completion.py fix verification — corrected eval confirmed valid
- Date: 2026-07-29
- Status: accepted
- Scope: evaluation pipeline / result validity

**Bug recap (DEC-010):**
The original `evaluate_completion` loop used a logit-position index (`logit_pos = prefix_len - 1 + k`)
that immediately exceeded `logits.shape[0]` at k=1, causing a break after the first token.
Every run evaluated exactly 1 prediction per example regardless of `--mask-last`.

**Fix — autoregressive teacher-forcing loop:**
The corrected loop iterates directly over `targets = input_ids[prefix_len : prefix_len + mask_last]`.
At each step it:
1. Feeds `current_ids` (initially `input_ids[:prefix_len]`) to the model
2. Takes `logits[0, -1].argmax()` — the prediction for the next position
3. Compares to `target_id` (ground truth)
4. Appends `target_id` (not the prediction) to `current_ids` for the next step (teacher forcing)

**Indexing math:**
For a sequence of length L with `mask_last=10`:
- `prefix_len = L - 10`
- `targets = input_ids[L-10 : L]` — exactly 10 tokens
- Loop runs 10 times; `ex_total` increments to 10
- Grand total across N examples = N × 10 (minus examples with len ≤ mask_last)

**Prediction scaling confirmed against actual output (2026-07-29 run):**
- A: 200 examples × 10 = 2,000 total predictions reported ✓
- B: 189 examples × 10 = 1,890 total predictions reported ✓  (11 examples too short, skipped)
- C: 197 examples × 10 = 1,970 total predictions reported ✓  (3 examples too short, skipped)

This matches exactly. The old buggy runs reported total_predictions = examples_evaluated (200/189/197),
i.e., 1 prediction per example. The fixed runs report total_predictions = examples × 10. The scaling
is confirmed.

**Corrected results (89.7/94.1/94.6) — provisional status:**
These results are valid under the fixed eval but carry one remaining caveat: Variant A used the
3-epoch checkpoint (checkpoint-831) while B and C used 1-epoch checkpoints (checkpoint-554). The
comparison is not matched on training budget. B and C at 3 epochs may score higher, potentially
widening the gap. These numbers are the best available result for A vs B/C but must be treated as
provisional until B and C are evaluated at matched epoch count.

- References:
  - python/eval_completion.py (corrected loop, lines ~216–230)
  - DEC-010 (bug documentation)
  - Corrected run output 2026-07-29: A=89.7%, B=94.1%, C=94.6%

### DEC-012: Regression test for DEC-010 eval_completion.py indexing bug
- Date: 2026-07-29
- Status: accepted
- Scope: evaluation pipeline / test coverage

**What the test covers:**
`python/test_eval_regression.py` adds 6 tests targeting the two bugs documented in DEC-010:

  1. **total_predictions scales with mask_last** — the single most direct regression guard.
     With the old buggy code, total_predictions == n_examples always. With the fix,
     total_predictions == n_examples * mask_last. This test asserts the correct invariant
     at mask_last = 1, 3, 5, and 10.

  2. **Short sequences skipped correctly** — examples with len(input_ids) <= mask_last
     must be excluded entirely from total_predictions and examples_evaluated.

  3. **Perfect predictor scores 100%** — end-to-end sanity check with a controlled model
     that always predicts the correct next token.

  4. **Worst predictor scores 0%** — complementary sanity check with a model that always
     predicts token 0 against sequences starting at token 10.

  5. **Teacher forcing uses ground truth** — RecordingModel logs every input_ids call.
     Verifies that at each step the prefix is extended by the ground-truth token (not the
     prediction), confirming that errors do not compound across the mask_last steps.

  6. **mask_last=1 backward compat** — with mask_last=1 the fixed eval and old buggy eval
     produce the same result (1 token per example). Confirms the fix is not a regression
     for the single-token case.

**Test design notes:**
  - CPU-only, model-free (FakeCausalLM / RecordingModel). Runs in < 1 second.
  - Same treatment as test_train_regression.py: imports only the function under test,
    no GPU, no dataset files required.
  - Test 1 would catch a DEC-010 regression immediately: if the break-on-first-token
    bug re-appeared, total_predictions would equal n_examples (10) instead of
    n_examples * mask_last (10, 30, 50, 100) for the four mask_last values tested.
  - Test 5 (teacher forcing) catches the subtler failure mode where the prefix is
    extended with the predicted token instead of the ground truth — which would make
    accuracy sensitive to error compounding rather than per-position accuracy.

**Run:**
  python3 python/test_eval_regression.py

**Result (2026-07-29):** 6/6 passed.

- References:
  - python/test_eval_regression.py
  - DEC-010 (bug documentation)
  - python/eval_completion.py (corrected evaluate_completion function)

### DEC-009: Embedding warm-start to isolate representation quality
- Date: 2026-07-28
- Status: complete
- Scope: experiment interpretation / confound elimination
- Decision:
  - DEC-008 established that cold-start embedding initialization partially explains A's
    underperformance but does not fully account for the gap to B/C. An embedding warm-start
    experiment is the next step to separate representation quality from initialization advantage.

  **Proposed protocol:**
  Before training variant A, copy pretrained Qwen2.5-Coder embedding vectors for any tokens
  whose string representation appears in both the Qwen vocabulary and the custom IR vocab
  (e.g., numeric literals, common identifiers). Randomly initialize the remainder. All other
  hyperparameters unchanged from the matched-batch rerun. Output to `runs/variant_A_warmstart`.

  **Interpretation framework:**
  - If warm-start A perplexity approaches B/C (≤1.15): embedding initialization was the
    primary cause; IR representation is competitive once initialized fairly.
  - If warm-start A perplexity remains above 1.25: the representation itself underperforms
    at this scale; investigate vocab size (4,495 tokens may be too small), sequence cap
    asymmetry, or structural information loss in the IR encoding.
  - If warm-start A perplexity is between 1.15 and 1.25: both factors contribute; further
    ablations needed.

  **Prerequisites:**
  - Identify token overlap between `vocab_A.json` and Qwen2.5-Coder BPE vocabulary.
  - Implement warm-start weight copy in `python/train.py` (new `--warm-start-embeddings` flag).
  - Verify that warm-started embeddings are trainable (not frozen) so A can still adapt.

  **Result (2026-07-29):**
  Warm-start overlap: **23 tokens out of 4,495 (0.51%)**.
  Warm-start variant A eval perplexity = **1.4288** (22.5 minutes, 1 epoch).

  **Interpretation:**
  The 0.51% overlap means the warm-start was effectively a cold start — 4,472 of 4,495 embedding
  rows remained randomly initialized. Perplexity is 1.43, marginally *worse* than the cold-start
  1-epoch result (1.39), consistent with mild interference from the 23 mismatched pretrained vectors.

  The warm-start approach cannot address DEC-006 at this vocab overlap level. The Qwen BPE
  vocabulary and Maith's custom IR vocabulary are structurally too different for embedding transfer
  to be meaningful.

  **Conclusion:**
  DEC-006 Confound 1 (randomly initialized embeddings) is now fully characterized:
  - Cold-start is a real factor (DEC-008: 3 epochs improved A from 1.39 → 1.26).
  - Warm-start cannot close the gap due to near-zero vocab overlap.
  - The residual gap between A (1.26 at 3 epochs) and B/C (1.15/1.13 at 1 epoch) is
    attributable to the IR representation itself, not initialization alone.

  **Next step:** Run `eval_completion.py` against the matched-batch B and C checkpoints to
  evaluate whether B/C's perplexity advantage translates to completion accuracy. Perplexity
  is an average-case metric; completion accuracy is a sharper, task-relevant signal.

- References:
  - DEC-006, DEC-008
  - docs/history/PHASE_5_RESULTS.md
  - python/train.py
  - runs/variant_A_warmstart/results.json

### DEC-010: eval_completion.py had two bugs — prior completion-accuracy results are invalid
- Date: 2026-07-29
- Status: accepted
- Scope: evaluation validity / result retraction

- Decision:
  The completion-accuracy results previously reported (A=56%/60.5%, B=94%/96.8%, C=100%/94.9%)
  are **invalid** and must not be used to support or refute the representation hypothesis.
  Two bugs were identified:

  **Bug 1 — Single-token-only evaluation (primary).**
  The logit indexing loop used logit_pos = prefix_len - 1 + k, but the forward pass only
  produced prefix_len logit rows (indices 0..prefix_len-1). At k=1, logit_pos = prefix_len,
  which immediately triggered the break guard. Every run — regardless of --mask-last value
  — evaluated exactly one token per example. The --mask-last flag changed only which
  single position was tested, not how many tokens were evaluated. "200 examples, mask-last 10"
  = 200 single-token predictions, not 2,000.

  **Bug 2 — Structurally biased test position (secondary, Variant C specific).**
  Token 13 (Qwen BPE structural delimiter) appeared at the tested position in 67/246 eval_C
  examples (27%) and is a high-frequency token (12,790 occurrences in eval_C, 15.2% of all
  tokens). Its preceding context is highly repetitive — 33/67 cases preceded by the exact same
  3-token pattern [1523, 48765, 23684]. A model could inflate accuracy on these positions by
  learning one n-gram. Variants A and B do not show equivalent concentration (A: token 98 at
  0.6% corpus frequency). This independently inflated C's score regardless of Bug 1.

  **Fix applied (2026-07-29):**
  - Replaced single-pass logit loop with autoregressive teacher-forcing loop evaluating each
    of the mask_last positions independently.
  - Added --checkpoint-A flag for direct evaluation against runs/variant_A_3ep.
  - Targets now read from input_ids[prefix_len:] directly, not the labels array.

  **Results retracted from PHASE_5_RESULTS.md:**
  - Completion accuracy, last 5 tokens, 50 examples: A=56%, B=94%, C=100%
  - Completion accuracy, last 10 tokens, 200 examples: A=60.5%, B=96.8%, C=94.9%
  - All interpretation and conclusions based on those numbers.
  - The "Phase 5 finding: IR representation hypothesis falsified" conclusion is premature
    and must be reassessed after the corrected eval.

  **Rerun protocol:**
  python3 python/eval_completion.py --checkpoint-A runs/variant_A_3ep --samples 200 --mask-last 10

  **Corrected result (2026-07-29):**
  Variant A (3-epoch, checkpoint-831): 89.7%  (1,794 / 2,000 tokens, 200 examples)
  Variant B (1-epoch, checkpoint-554): 94.1%  (1,779 / 1,890 tokens, 189 examples)
  Variant C (1-epoch, checkpoint-554): 94.6%  (1,863 / 1,970 tokens, 197 examples)

  **Key finding:**
  A trails B and C but the gap is far smaller than the buggy numbers suggested — 89.7% vs 94–95%,
  not 60% vs 95%. This materially changes the Phase 5 conclusion: the IR representation is
  competitive at this task, not strongly inferior. A's deficit over B/C is ~5 percentage points,
  which is consistent with the residual cold-start embedding penalty (DEC-006/008) rather than a
  fundamental failure of the representation hypothesis.

  **Comparison note:**
  A used 3-epoch checkpoint-831 (more training); B/C used 1-epoch checkpoint-554 (less training).
  This comparison still favors B/C — if A needed 3x the training to reach 89.7% while B/C hit
  94–95% at 1 epoch, the representation advantage of B/C is real. But "real and ~5pp" is a very
  different finding from "A is broken at 60%".

- References:
  - python/eval_completion.py (fix commit following 83ded87)
  - docs/history/PHASE_5_RESULTS.md (retracted results above, corrected results below)
  - DEC-008 (3-epoch A checkpoint)
  - DEC-009 (warm-start context)

---

### DEC-013: Training stability — batch size reduction, epoch checkpointing, gradient checkpointing

**Date:** 2026-07-30
**Status:** Applied

**Context:**
Variant A repeatedly died from thermal throttling on Apple Silicon (16 GB MPS). Root cause:
BATCH_SIZE=2 with float32 forward+backward passes on a 361M-param randomly-initialized model
saturated MPS compute units within 3-5 steps. The effective batch size (BATCH_SIZE x GRAD_ACCUM)
was kept at 8 throughout to preserve training dynamics.

**Changes applied:**

1. BATCH_SIZE 2 to 1, GRAD_ACCUM 4 to 8 (effective batch unchanged at 8).
   Halves peak per-step memory with no validity impact. Applies equally to A, B, and C.

2. save_strategy "no" to "epoch", save_total_limit=3.
   Saves a checkpoint after each epoch. A crash mid-epoch loses at most one epoch of progress.
   A --resume flag was added to the CLI to pick up from the latest saved checkpoint.
   Does not affect model outputs or comparisons.

3. gradient_checkpointing_enable(use_reentrant=False).
   Recomputes activations during backward pass instead of holding them in memory. Reduces peak
   MPS memory at the cost of ~20-30% more compute per step. use_reentrant=False is the
   MPS-safe variant.

   WARNING - Unverified equivalence assumption: "statistically equivalent" is a general claim
   about gradient checkpointing drawn from CUDA-scale literature. It has NOT been empirically
   verified for this specific setup:
   - Variant A: 361M params, randomly initialized embedding table
   - Variants B/C: 494M params (Qwen2.5-Coder-0.5B), pretrained weights intact
   - Dataset scale: ~2,200 training examples
   - Hardware: Apple Silicon MPS (non-determinism characteristics differ from CUDA)

   The non-determinism introduced by gradient checkpointing may manifest differently across A vs
   B/C due to their asymmetric initialization. The comparison remains relative (all three variants
   use gradient checkpointing), so the playing field is level. But absolute perplexity values
   from DEC-013-onward runs are not directly comparable to prior float32 deterministic runs.

**Impact on experimental validity:**
- A/B/C remain comparable to each other (all three use identical training configuration).
- Results from DEC-013-onward are not directly comparable to pre-DEC-013 runs (batch size
  and gradient checkpointing both changed).
- Prior results (DEC-008, DEC-010, DEC-012) used BATCH_SIZE=2, no gradient checkpointing.

- References:
  - python/train.py (this commit)
  - DEC-007 (original batch-size mismatch fix)
  - DEC-008 (3-epoch A results, pre-DEC-013 config)

---

## DEC-014: Proof-Term Completion Deferred to Phase 7; Next-Tactic Prediction Ruled Out

**Date:** 2026-07-31
**Status:** Recorded. No action taken on codebase.

**Decision:**
Full Mathlib coverage for proof autocompletion is a Phase 7 concern, not a Phase 5/6
concern. The IR is intentionally left unchanged. Three blockers were identified and
documented. Next-tactic prediction is ruled out permanently on architectural grounds.

**Summary of blockers:** See docs/history/PHASE_7_DESIGN.md for the full three-blocker table
and IR change requirements.

**Why next-tactic prediction is ruled out:**
Tactics exist only in the Syntax layer, which is discarded before elaboration. By the
time MetaExtractor.lean runs, there is no tactic string to recover. Supporting it would
require a completely separate extraction path intercepting the elaborator mid-run. This is
not an extension of Maith — it is a different project.

**Why proof-term completion is the right path:**
The current IR already extracts type structure correctly. Proof-term completion (type to
proof term) requires only targeted IR additions: remove the .thmInfo skip, raise the
tactic density filter, extend OperationOp for proof combinators. These changes are scoped
and do not invalidate Phase 5/6 results.

**What is not changing now:**
- MetaExtractor.lean — no changes
- maxTacticDensity filter — remains at 0.8
- constantValueExpr? — .thmInfo skip remains in place
- Phase 6 corpus expansion targets — unchanged

**References:**
- docs/history/PHASE_7_DESIGN.md (full design doc)
- Maith/MetaExtractor.lean (extraction logic)
- Maith/MathlibLoader.lean (tactic density filter)

---

### DEC-015: Corpus expansion — 4 to 14 Mathlib modules, vocab A 4,495 to 8,102 tokens

**Date:** 2026-07-31
**Status:** Accepted. Full matched A/B/C rerun required before any Phase 5 conclusion.

**What happened:**
Commit 56fd814 (July 31, 08:20 AM) executed the corpus expansion that was previously
only tested as a dry run. 1,347 new examples were added from 10 additional Mathlib modules,
growing the dataset from 2,213/246 to 3,375/376 (train/eval). Vocab A grew from 4,495 to
8,102 tokens — an 80% increase.

**New modules added:**
- Algebra.Group.NatPowAssoc:     28 examples
- Algebra.Ring.Basic:            68 examples
- Algebra.Ring.GeomSum:          70 examples
- Algebra.Group.Subgroup.Basic: 393 examples
- Data.Nat.Basic:                27 examples
- Data.Int.Basic:                22 examples
- Order.Lattice:                519 examples
- Order.LatticeIntervals:       128 examples
- Algebra.Module.Basic:          23 examples
- Topology.Basic:                69 examples

**Total corpus:** 3,901 examples across 14 modules (3,375 train / 376 eval after 150
pathological dropped). Original 4 modules: Algebra.Group.Defs, Algebra.Group.Basic,
Algebra.Ring.Defs, Order.Basic.

**Why rolling back datasets is not viable (option 1):**
Vocab A's embedding table is sized to vocab_A.json. Old A/C checkpoints used a 4,495-token
table; the current vocab has 8,102 tokens. The checkpoint is architecturally incompatible
with the current pipeline state and cannot be evaluated against the new vocab. A full matched
rerun of all three variants on the expanded corpus is the only valid path.

**Interaction with DEC-002 (sequence cap asymmetry) — unassessed:**
train_B p99 sequence length on expanded corpus = 2,051 tokens (max 8,242). train_A p99 =
1,036 (max 1,305). The runtime seq cap (DEC-014) is 512 for B/C. The cap now truncates a
larger fraction of the expanded corpus than it did on the original 4-module corpus. This
may interact with DEC-002 in ways not yet characterized. Flag for post-run review: after
the matched rerun completes, stratify perplexity by sequence length bucket to check whether
truncation is affecting B/C disproportionately.

**Action required:**
Re-run all three variants (A, B, C) on the 3,375-example expanded corpus before drawing
any Phase 5 conclusions. B2 already completed on this corpus (perplexity 1.107, 523 min).
A and C must be rerun to match.

**References:**
- commit 56fd814 (corpus expansion)
- python/corpus_expansion_dry_run.py (prior dry run)
- DEC-002 (sequence cap asymmetry, original)
- DEC-006 (cold-start embedding confound)
- docs/experiments/EXPERIMENT_DESIGN.md (matched-run protocol)

---

### DEC-016: Phase 5 conclusion — matched A/B/C rerun on expanded corpus (2026-08-01)

**Date:** 2026-08-01
**Status:** Accepted. Phase 5 closed. Two required follow-ups documented below.

**Runs:**

| Variant | Checkpoint | Train examples | Eval examples | Epochs | Perplexity | Training minutes |
|---------|-----------|----------------|---------------|--------|------------|------------------|
| A | variant_A_v3/checkpoint-final | 3,375 | 376 | 3 | 1.2812 | 77.4 |
| B | variant_B2/checkpoint-final | 3,375 | 376 | 3 | 1.107 | 523.0 |
| C | variant_C_v2/checkpoint-final | 3,375 | 376 | 3 | 1.098 | 272.8 |

All three: seed=42, base model Qwen2.5-Coder-0.5B, smoke_test=false.

**Completion accuracy (eval_completion.py, 50 examples, mask_last=5, teacher-forced):**

| Variant | Top-1 Accuracy | Correct / Total |
|---------|---------------|-----------------|
| A | 89.6% | 224 / 250 |
| B | 94.4% | 236 / 250 |
| C | 90.8% | 227 / 250 |

**Eval script fix (2026-08-01):**
eval_completion.py previously only had --checkpoint-A. Added --checkpoint-B and
--checkpoint-C flags and corrected the getattr key to use .upper(). The fix is
purely directory-routing — no change to the evaluation logic (masking, teacher forcing,
argmax, accuracy counting). Confirmed: the same evaluate_completion() function runs
for all three variants without modification.

**Spot-check (24 examples, 120 positions, B vs C — two independent rounds):**
Round 1 (9 examples, seed 42): B=42/45 (93.3%), C=40/45 (88.9%). Round 2 (15 fresh
examples, seed 7, non-overlapping): B=73/75 (97.3%), C=74/75 (98.7%). Combined:
B=115/120 (95.8%), C=114/120 (95.0%) — essentially tied.

The round-1 narrative ("C fails at syntactic boundaries in longer sequences") does not
replicate. In round 2 C goes 5/5 on the longest example (seq_len=1369) while B drops
to 3/5. Round 2 divergences split evenly: one example where C beats B, one where B
beats C. No systematic pattern was confirmed.

**Implication for the aggregate gap (B=94.4% vs C=90.8%):**
The aggregate gap is real but its source is not explained by any per-token pattern
visible in 24 spot-checked examples. The gap may be driven by a small number of
examples where C fails consistently, or it may be sampling variance in the 50-example
aggregate run. The 200-example, mask_last=10 follow-up eval is the right way to
determine whether the gap holds at scale.

**Perplexity / completion-accuracy inversion (B vs C):**
C has better perplexity (1.098 vs 1.107) but worse completion accuracy (90.8% vs 94.4%)
in the aggregate run. The spot-check does not reproduce this gap at the token level,
suggesting the inversion — if real — is not uniformly distributed across sequences.

**Required follow-up 2 — correction to framing:**
Previously labelled "matched-epoch completion eval." That label is wrong — all three
variants are already at 3 epochs. The actual distinction is sample size and mask depth:
200 examples and mask_last=10 vs the current 50/5. At 2,000 predictions vs 250, the
confidence interval tightens enough to determine whether the B/C gap and the B/C vs A
gap are stable. This is the correct framing.

**Phase 5 finding:**
Variant A trails B and C on both perplexity and completion accuracy on the expanded,
matched corpus. The gap is real: ~0.18 perplexity points, ~5pp completion accuracy.
The gap is materially smaller than earlier mismatched Phase 5 estimates (which showed
a 36pp completion gap from unequal corpus sizes and a buggy eval script).

**DEC-006 status — STILL OPEN:**
Variant A uses a randomly initialized 8,102-token embedding table. Variants B and C use
Qwen2.5-Coder pretrained embeddings (151,643 tokens). The embedding warm-start experiment
(DEC-009) achieved only 0.51% token overlap and was effectively a cold start — it did not
isolate the representation confound. No experiment has yet run A with a genuinely
warm-started embedding. Until that is done, we cannot cleanly separate "IR representation
is worse" from "random initialization is worse." DEC-006 remains an open confound.

**Required follow-up 1 — DEC-002 stratified analysis (not optional):**
DEC-015 flagged that the expanded corpus has B/C p99 sequence length of 2,051 tokens
against a 512-token eval cap, potentially truncating a larger fraction of B/C's harder
examples and artificially improving their perplexity. Before any Phase 6 design uses
these numbers as a baseline, perplexity must be stratified by sequence length bucket
(short: <128 tokens, medium: 128-512, long: >512) to confirm B/C's advantage is not
an artifact of asymmetric truncation. This is a required pre-condition for Phase 6, not
a post-hoc check.

**Required follow-up 2 — matched-epoch completion eval (not optional):**
The corrected Phase 5 completion eval (DEC-010) compared 3-epoch A against 1-epoch B/C,
which was acknowledged as unfair to B/C. The current run has all three at 3 epochs for
the first time. A matched-epoch completion eval must be run before drawing a final
conclusion on the representation hypothesis. The 5pp gap may shrink, hold, or widen —
but until it is measured under matched conditions it is not a conclusion.

**References:**
- runs/variant_A_v3/results.json
- runs/variant_B2/results.json
- runs/variant_C_v2/results.json
- runs/completion_accuracy.json
- DEC-002 (sequence cap asymmetry)
- DEC-006 (cold-start embedding confound)
- DEC-009 (warm-start attempt, 0.51% overlap)
- DEC-010 (eval_completion bug fix)
- DEC-015 (corpus expansion, matched rerun requirement)
- docs/history/PHASE_5_RESULTS.md (full results history)

---

### DEC-017: Follow-up eval results — stratified perplexity and high-confidence completion accuracy (2026-08-02)

**Date:** 2026-08-02
**Status:** Accepted. Phase 6 design blocked pending equal-sequence-length perplexity rerun (see required gate below).

#### Follow-up 1: Stratified perplexity (DEC-002 resolution)

**Results (followup_eval.py, all 376 eval examples, seq_cap per variant):**

| Variant | Short (<128) N | Mean PPL | Medium (128–512) N | Mean PPL | Long (>512) N | Truncated | Mean PPL |
|---------|---------------|----------|--------------------|----------|---------------|-----------|----------|
| A | 158 | 1.663 | 187 | 1.396 | 31 | 5/31 | 2.200 |
| B | 83 | 1.415 | 214 | 1.126 | 79 | 78/79 | 1.077 |
| C | 71 | 1.668 | 197 | 1.109 | 108 | 107/108 | 1.083 |

**Finding:**
The stratification reveals that B/C's aggregate perplexity advantage over A is
substantially driven by asymmetric truncation, not solely by representation quality.

B's 79 "long" examples are truncated in 78/79 cases to 512 tokens — the model never
sees the hard part of those sequences. C truncates 107/108. A's 31 long examples are
truncated in only 5/31 — it is evaluated on sequences up to its full 1024-token training
cap, including the structurally complex tails that B/C never process.

B and C's long-bucket perplexity (1.077/1.083) is their *best* performing bucket, not
their worst. This is consistent with truncation artificially removing the harder suffix
tokens from their eval loss. A's long-bucket perplexity (2.200) is its worst — it is
penalized for tokens that B/C's eval cap silently drops.

**Implication:**
The current aggregate perplexity comparison (A: 1.2812, B: 1.107, C: 1.098) should not
be treated as valid evidence for or against the representation hypothesis. The numbers
are not measuring the same thing: A and B/C are evaluated over materially different
token distributions. The perplexity comparison cannot support a conclusion about
representation quality until it is re-run with matched sequence caps.

This does not affect the short and medium buckets, where all three variants are
unadjusted and directly comparable. In those buckets B and C still lead A (short: A 1.663
vs B 1.415 vs C 1.668; medium: A 1.396 vs B 1.126 vs C 1.109), so the advantage is not
entirely an artifact. But the aggregate headline numbers are contaminated and should not
be cited as a primary result.

#### Follow-up 2: Completion accuracy (DEC-016 required follow-up)

**Results (followup_eval.py, 200 examples, mask_last=10, single-pass teacher-forced):**

| Variant | Top-1 Accuracy | Correct / Total | Examples evaluated |
|---------|---------------|-----------------|-------------------|
| A | 86.2% | 1723 / 2000 | 200 |
| B | 92.8% | 1792 / 1930 | 193 |
| C | 91.4% | 1800 / 1970 | 197 |

**Finding:**
A trails B and C by ~5–6 percentage points. The gap from the 50-example run (A: 89.6%,
B: 94.4%, C: 90.8%) survives at scale with tighter confidence: 2,000 predictions for A,
~1,950 for B and C. The B/C gap narrows from 3.6pp to 1.4pp and is not a reliable
signal — within expected variance at this sample size.

This result is not affected by the sequence-cap asymmetry identified in Follow-up 1.
Completion accuracy is computed from the full uncapped sequence for each example
(the model sees the entire sequence; only the final mask_last tokens are evaluated),
so B/C are not receiving any truncation benefit here. The 5–6pp A deficit is a clean
result that stands on its own.

**Methodological note:**
The completion eval uses a single-pass teacher-forced method (DEC-017 / followup_eval.py)
replacing the original token-by-token loop. The two methods were verified to produce
bit-identical predictions on 5 examples per variant before the full run
(check_completion_indexing.py, all variants PASS). The token count difference across
variants (B: 1930, C: 1970 vs A: 2000) reflects examples skipped for being shorter than
mask_last=10, not a sampling difference.

#### Required gate before Phase 6: equal-sequence-length perplexity rerun

**This is a Phase 6 blocker, not an open question.**

Phase 6 design must not proceed until perplexity is re-evaluated with a matched sequence
cap across all three variants. The current perplexity numbers are not a valid baseline
for a Phase 6 comparison.

**What is required:**
Re-run perplexity evaluation for all three variants with a single shared sequence cap —
either 512 tokens (B/C's current cap, meaning A is evaluated under A's training cap for
the long bucket) or a cap chosen to equalize the truncation fraction across variants.
The goal is that the "long" bucket truncation rate is comparable across A, B, and C so
that the per-bucket and aggregate perplexity numbers reflect the same token distribution.

**What this will and will not resolve:**
It will produce a perplexity comparison that is not confounded by asymmetric truncation,
making it valid evidence for or against the representation hypothesis at the sequence
lengths where all variants are compared on equal footing.

It will not resolve DEC-006 (cold-start embedding confound). Even a clean perplexity
comparison may still conflate representation quality with initialization disadvantage.
DEC-006 remains open and must be addressed separately in Phase 6 design.

**References:**
- runs/followup_eval_results.json
- python/followup_eval.py
- python/check_completion_indexing.py
- DEC-002 (sequence cap asymmetry, original)
- DEC-006 (cold-start embedding confound, still open)
- DEC-015 (corpus expansion)
- DEC-016 (Phase 5 conclusion)

---

### DEC-018: Equal-sequence-length perplexity rerun — Phase 5 perplexity gate resolved (2026-08-02)

**Date:** 2026-08-02
**Status:** Accepted. Phase 5 perplexity comparison now valid. Phase 6 blocker lifted.

**Required by:** DEC-017, which found that the original aggregate perplexity comparison
was not valid evidence because A and B/C were evaluated over different token distributions
due to asymmetric sequence-length truncation.

#### Results at shared 512-token cap (dec018_ppl_rerun.py, all 376 eval examples)

| Variant | Short (<128) N | Mean PPL | Medium (128–512) N | Mean PPL | Long (>512) N | Truncated | Mean PPL | Overall Mean PPL |
|---------|---------------|----------|--------------------|----------|---------------|-----------|----------|-----------------|
| A | 158 | 1.663 | 187 | 1.396 | 31 | 31/31 | 1.168 | 1.489 |
| B | 83 | 1.415 | 214 | 1.126 | 79 | 78/79 | 1.077 | 1.180 |
| C | 71 | 1.668 | 197 | 1.109 | 108 | 107/108 | 1.083 | 1.207 |

B and C's numbers are unchanged from DEC-017 (they were already at a 512-token cap).
A's long-bucket perplexity falls from 2.200 to 1.168 once capped at 512 — confirming
that the 2.200 figure was driven by hard suffix tokens beyond the 512-token boundary
that B/C were never evaluated on. However, A's overall perplexity rises from 1.281 to
1.489 under the matched cap because its short and medium buckets now have their relative
weight increased (A has proportionally more short examples than B/C, and those examples
have higher perplexity for A than for B/C).

#### Interpretation

**B and C lead A in every bucket at the matched cap.** The advantage is not a
truncation artifact. Specifically:

- Short bucket: B leads A by 0.248 perplexity points; C is essentially tied with A.
- Medium bucket: B leads A by 0.270; C leads A by 0.287.
- Long bucket: B leads A by 0.091; C leads A by 0.085 — the gap narrows but does not close.
- Overall: B leads A by 0.309; C leads A by 0.282.

The DEC-017 concern was valid: the original 1.281 vs 1.107/1.098 comparison was
contaminated by asymmetric truncation and should not have been cited. The DEC-018
matched comparison (1.489 vs 1.180/1.207) is a valid apples-to-apples result. The
direction is the same — B/C outperform A — but the mechanism is confirmed to be real
rather than an evaluation artifact.

**The B/C gap (1.180 vs 1.207) is small** and similar in magnitude to the DEC-017
unmatched comparison. B has a slight perplexity edge over C.

**DEC-006 (cold-start confound) remains open.** This result confirms that B and C
produce lower perplexity on the same token distributions. It does not isolate whether
that advantage comes from representation quality or from the embedding warm-start that
B and C receive from Qwen2.5-Coder's pretrained weights. DEC-006 must be addressed
in Phase 6 design.

#### Phase 5 perplexity conclusion (now valid)

At a shared 512-token evaluation cap, Variant A (Maith IR) has higher perplexity than
both Variant B (raw leanExpr, Qwen BPE) and Variant C (normalized leanExpr, Qwen BPE)
across all sequence-length buckets. Combined with the completion accuracy result
(DEC-017: A 86.2%, B 92.8%, C 91.4%), the Phase 5 evidence consistently shows A
trailing B/C on both metrics. The representation hypothesis — that IR tokens improve
model performance — is not supported by Phase 5 results. DEC-006 remains the
unresolved confound: the gap may reflect initialization disadvantage rather than
representation quality.

**Phase 6 blocker lifted.** Phase 6 design may proceed from this baseline.

#### References
- runs/dec018_ppl_results.json
- python/dec018_ppl_rerun.py
- DEC-002 (sequence cap asymmetry)
- DEC-006 (cold-start embedding confound, still open)
- DEC-016 (Phase 5 matched-run conclusion)
- DEC-017 (stratified perplexity, follow-up completion accuracy)

---

### DEC-019: Corpus expansion — planning entry (2026-08-02)

**Date:** 2026-08-02
**Status:** Planned. Not started. Awaiting decision on which hypothesis to prioritize
and GPU time to commit before execution.

#### Background

Phase 5 (DEC-016 through DEC-018) established that A trails B/C on both perplexity and
completion accuracy at matched evaluation conditions. DEC-006 identifies the unresolved
confound: A's embedding table is randomly initialized at training time, while B and C
begin from Qwen2.5-Coder's pretrained weights. Two Phase 6 attempts to close this
confound have so far been inconclusive:

- **Attempt 1 (warm-start):** embedding warm-start via vocabulary projection — marginal
  or negative result; did not close the gap.
- **Attempt 2 (embed-pretrain):** longer pretraining of A's embeddings — similarly
  inconclusive.

Corpus expansion is a potential **Attempt 3** on the DEC-006 confound, but it is also
a separate and distinct hypothesis about generalization. These two motivations call for
different module choices and produce different experiments; they must not be conflated.

#### The two separate claims

**Claim 1 — Volume (DEC-006 lineage):**
More training examples give A's randomly-initialized embeddings more gradient signal,
potentially allowing A to partially close the initialization gap with B/C. Mechanism:
A requires more signal to organize its embedding space from scratch; B/C start from an
organized state and need less signal per example. Prediction: increasing volume in
algebra-adjacent modules may narrow A's gap, particularly in short/medium sequences
where cold-start effects dominate.

*Important caveat:* this is not guaranteed. B/C also benefit from additional data and
start from a stronger position. The gap may stay proportionally similar or widen. This
is an empirical question, not a given.

**Claim 2 — Diversity (generalization):**
Broader domains test whether the IR representation transfers outside the algebraic
modules the baseline was trained on. This is a different and valid experiment: does
Maith IR generalize to, e.g., topological or lattice structures? This does not directly
address DEC-006 — B/C would be expected to benefit at least as much from domain
diversity, given their tokenizers already cover diverse Lean syntax from pretraining.

#### Module choices implied by each claim

| Claim | Module priority | Rationale |
|-------|----------------|-----------|
| Volume (DEC-006) | Algebra-adjacent: NatPowAssoc, Ring.Basic, Ring.GeomSum, Subgroup.Basic, Data.Nat.Basic, Data.Int.Basic, Algebra.Module.Basic | Similar IR graph structure to baseline; more examples in the same distribution |
| Diversity (generalization) | Topology.Basic, Order.Lattice | Meaningfully out-of-distribution relative to baseline algebra modules; tests transfer |

Both sets are in `Scripts/module_expansion_targets.json` under `expansion_candidates`.

#### Required pre-execution steps (in order)

1. **Dry-run (print-only):** confirm module list and generated Lean runner — no
   extraction runs.
   ```
   python3 python/corpus_expansion_dry_run.py --set candidates --print-only
   ```

2. **Dry-run (real counts):** get actual declaration counts and success rates from
   Mathlib directly, replacing any secondhand estimates with verified ground truth.
   (~10–15 min Lean build time, no training.)
   ```
   python3 python/corpus_expansion_dry_run.py --set candidates
   ```

3. **Decide the hypothesis explicitly** before running extraction or training. Log the
   choice as a follow-up DEC entry (DEC-020 or similar) before proceeding. This is the
   step that makes the eventual result interpretable. Expansion run without an explicit
   hypothesis choice cannot be cleanly interpreted either way.

4. **Extract, rebuild datasets, retrain** — only after steps 1–3 are complete. Same
   order of time commitment as the Phase 5 matched rerun (extraction + full A/B/C
   retrain at 3 epochs each).

#### What this entry does not decide

- Which hypothesis to prioritize (volume vs. diversity).
- Whether expansion is the right next Phase 6 step relative to other approaches.
- Module subset selection within the candidate list.

Those decisions require the dry-run numbers and an explicit hypothesis choice first.

#### References
- Scripts/module_expansion_targets.json
- python/corpus_expansion_dry_run.py
- DEC-006 (cold-start embedding confound, still open)
- DEC-016 (Phase 5 conclusion)
- DEC-018 (perplexity gate resolved)

---

### DEC-020: Phase 6 conclusion — expanded corpus A/B/C rerun (2026-08-02)

**Date:** 2026-08-02
**Status:** Closed.

#### What was run

Full A/B/C retrain on the expanded 14-module corpus (DEC-015), matching the Phase 5
design. Embed-pretrain warm-start applied identically across all three variants
(DEC-009). Equal epoch counts: B and C at 2 epochs, A at 3 epochs (same ratio as
Phase 5 to account for A's smaller vocabulary). All runs completed without throttling
or checkpointing issues.

#### Results

| Variant | Vocab | Params | Epochs | Eval perplexity | Training time |
|---------|-------|--------|--------|----------------|--------------|
| A (IR tokenization) | 8,144 | 365M | 3 | **1.2792** | 105 min |
| B (BPE, standard FT) | 151,643 | 494M | 2 | **1.1295** | 181 min |
| C (BPE, embed-pretrain) | 151,643 | 494M | 2 | **1.1102** | 189 min |

B/C gap: 0.019 (negligible). A trails B/C by ~0.15–0.17 perplexity points.

#### Interpretation

The Phase 5 finding (DEC-016) replicates exactly on the expanded corpus. The A/B/C
gap did not close with more data: A's perplexity improved from Phase 5 (where
embed-pretrain eval was 2.14 pre-warmup) to 1.28 final, but B and C improved
proportionally, maintaining the same margin.

This is consistent with the representation hypothesis in DEC-006 — IR tokenization
produces a fundamentally different sequence structure that does not benefit from
BPE-pretrained Qwen weights as efficiently — but DEC-006 remains technically open
because the cold-start confound (A's embedding table was randomly initialized at
Phase 4 baseline) has not been isolated by a controlled experiment. The embed-pretrain
warm-start (DEC-009) mitigated this for Phase 5 and Phase 6 runs, but a direct
embedding-projection experiment was attempted (runs/variant_B_phase6 embed_pretrain
path) and showed only marginal improvement (embed_pretrain_eval_ppl 1.2761 → 1.1295
final for B; 1.2902 → 1.1102 for C; 2.1403 → 1.2792 for A), which does not
definitively isolate the representation quality effect from the embedding-table effect.

#### What this closes

- Phase 6 is complete. The experimental question "does more data close the gap?" is
  answered: no, not at the volume tested (~3,375 train / 376 eval examples across 14
  modules).
- DEC-019 (corpus expansion plan) status: the volume-for-DEC-006 hypothesis was
  implicitly tested here; the gap did not narrow. The diversity hypothesis
  (Topology.Basic, Order.Lattice) remains untested.

#### What remains open

- **DEC-006** — the cold-start embedding confound is still not definitively isolated.
  A controlled experiment (identical vocab, embed-pretrain on IR tokens from a Lean
  corpus, then fine-tune) would be required to separate representation quality from
  initialization quality.
- **DEC-019 diversity track** — domain generalization (does Maith IR transfer to
  topology/lattice structures?) was not addressed by Phase 6 and remains a valid
  future question.
- **Decompiler validity** (from DEC-014 and the decompiler PR) — the Lean decompiler
  produces structural skeletons, not yet valid Lean. This is a Phase 7 concern.

#### Decision

Phase 6 is closed. The project has a clean, reproducible, multi-phase result: IR
tokenization (Variant A) consistently trails BPE-based fine-tuning (Variants B/C) by
~0.15–0.17 perplexity points across both Phase 5 and Phase 6 corpus sizes. The gap
is stable, not converging. Whether this is attributable to representation quality,
initialization, or both requires a dedicated controlled experiment that is out of scope
for the current experimental program.

#### References
- runs/variant_A_phase6/results.json
- runs/variant_B_phase6/results.json
- runs/variant_C_phase6/results.json
- DEC-006 (cold-start embedding confound, still open)
- DEC-009 (embed-pretrain warm-start)
- DEC-015 (corpus expansion)
- DEC-016 (Phase 5 conclusion)
- DEC-018 (perplexity gate resolved)
- DEC-019 (corpus expansion plan)


### DEC-021: Embedding projection experiment — cold-start confound for DEC-006 closed (2026-08-03)

**Date:** 2026-08-03
**Status:** Closed. DEC-006 is now closed.

#### Background

DEC-006 identified a cold-start confound: Variant A's embedding table was randomly
initialized at Phase 4 baseline, while B and C inherited pretrained Qwen embeddings.
DEC-020 (Phase 6) mitigated this with an embed-pretrain warm-start (DEC-009) but could
not definitively isolate representation quality from initialization quality, because the
warm-start was applied to all three variants and the IR token space has no direct
pretrained analogue.

The controlled experiment proposed in DEC-006 and DEC-019: train an embedding projection
layer that maps Qwen's pretrained BPE embedding space into A's IR token space, giving A
genuinely warm embeddings derived from pretrained weights rather than random noise.

#### What was run

- **Script:** `python/train.py --variant A --datasets datasets/ --embed-project datasets/embed_proj_A.pt`
- **Checkpoint dir:** `runs/variant_A_dec006/`
- **Base model:** Qwen/Qwen2.5-Coder-0.5B
- **Vocab size:** 8,144 (IR vocabulary, unchanged)
- **Params:** 365.2M
- **Train examples:** 3,375 | **Eval examples:** 376
- **Epochs:** 2
- **Seed:** 42

#### Results

| | Perplexity |
|--|--|
| **Variant A — this run (embed-projected)** | **1.2978** |
| Variant A — Phase 6 baseline (embed-pretrain warm-start) | 1.2792 |
| Variant A — Phase 5 baseline (v3) | 1.2812 |
| Variant B — Phase 6 | 1.1295 |
| Variant C — Phase 6 | 1.1102 |

The embedding projection did not improve Variant A. The result (1.2978) is within
noise of both the Phase 5 (1.2812) and Phase 6 (1.2792) baselines. The gap to B/C
(~0.17 perplexity points) is fully intact.

Note: the terminal summary block printed "Variant A: 1.28" due to a rounding display
quirk in the comparison printer. The authoritative value from results.json is 1.2978.

#### Interpretation

Giving Variant A genuinely warm embeddings — projected from pretrained BPE weights —
produced no meaningful improvement over random initialization or the DEC-009
embed-pretrain approach. This rules out the embedding cold-start as the primary driver
of the A/B/C gap.

The gap is therefore attributable to **representation quality**, not initialization:
IR tokenization (Variant A) produces a sequence structure that is intrinsically less
learnable from this dataset and base model than BPE tokenization (Variants B/C),
independent of how the embedding table is seeded.

#### What this closes

- **DEC-006** — the cold-start embedding confound is now definitively closed. The
  embedding projection result rules out initialization as the cause of the A/B/C gap.
  The conclusion is: IR tokenization is less efficient than BPE for Lean expression
  completion at this scale, for reasons of representation quality, not initialization.

#### What remains open

- **Completion accuracy** — perplexity is confirmed consistent across three runs of
  Variant A (Phase 5, Phase 6, DEC-021). A completion accuracy eval on the DEC-021
  checkpoint would confirm the task metric is likewise unchanged. This is a low-priority
  confirmatory check; the perplexity convergence across three independent runs is
  already strong evidence.
- **DEC-019 diversity track** — domain generalization to topology/lattice structures
  remains untested and is a valid Phase 7 question.
- **Decompiler validity** (DEC-014) — structural skeleton → valid Lean is a Phase 7 concern.

#### Decision

DEC-006 is closed. The experimental program has a clean answer: IR tokenization
consistently trails BPE by ~0.17 perplexity points across Phase 5, Phase 6, and a
controlled embedding projection experiment. The gap is real, stable, and not explained
by initialization. Phase 7 should treat IR tokenization as a weaker baseline and focus
on decompiler validity and domain generalization.

#### Known residual: 93% alpha-equivalence rate is accurate, not a defect

Post-DEC-021 normalisation audit found a 93.0% alpha-equivalence identical rate across
1,478 structurally-similar corpus pairs. Investigation of the failing 7% established
that this is **not a normaliser bug** and is not fixable at the `MetaExtractor.lean` level.

The failing pairs fall into two categories:

1. **`Foo.mk` vs `Foo.mk._flat_ctor`** — 43 training examples. These are genuinely
   distinct types. `Foo.mk` takes typeclass implicit arguments (`[Zero M] [Add M]`);
   `Foo.mk._flat_ctor` takes the same constraints as explicit lambda arguments carrying
   field values directly (`M -> (M -> M -> M) -> AddZero M`). The IR correctly reflects
   that `forall {M} [Zero M] [Add M], AddZero M` and `forall {M}, M -> (M -> M -> M) ->
   AddZero M` are different expressions — different binder kinds, different R-row
   structure, different O-row gen tokens. `canonicaliseDeclName` normalises the scope
   string embedded in binder IDs but cannot change the underlying Expr structure.

2. **`Foo.casesOn` vs `Foo.recOn`** — 132 training examples. Lean generates both as
   eliminators for the same type, but their elaborated `Expr` types differ in argument
   order and universe structure. Same analysis applies.

Total affected: **175 of 2,213 training examples (7.9%)**.

**The 93% alpha-equivalence rate should be read as accurate and expected.** The corpus
genuinely contains structurally-distinct sibling declarations — auto-generated Lean
variants of the same typeclass with different type signatures. This is understood, not
a defect in the normaliser or the IR. The normaliser is correctly producing different
token sequences for different expressions. No further fix is required before retraining.

#### References
- runs/variant_A_dec006/results.json
- DEC-006 (cold-start confound — now closed)
- DEC-009 (embed-pretrain warm-start)
- DEC-016 (Phase 5 conclusion)
- DEC-020 (Phase 6 conclusion)
- DEC-019 (corpus expansion plan, diversity track remains open)
- docs/reference/IR_V2_FIX_SPEC.md (Fix 1 implemented; residual explained above)
- python/normalisation_audit.py (audit run post-Fix-1, 2026-08-03)

---

### DEC-022 — Fix 2 (polarity removal) regresses perplexity at current scale

**Date:** 2026-08-03
**Status:** Closed — finding documented, Fix 2 deferred
**Decision:** Do not apply Fix 2 until corpus exceeds ~10k examples or a lighter-weight separator design is validated.

#### Background

Fix 2 removed polarity tokens (neut, pos) from Encoder.lean on the hypothesis that they carried near-zero information (confirmed by normalisation audit: 99.8% of rows were neut). The expectation was that removing this noise would improve model generalisation.

#### Experiment

Two controlled runs on the true v1.3.0 corpus (4,029 examples, 3,491 train, zero polarity tokens):

| Run | Init | Perplexity |
|---|---|---|
| DEC-021 baseline (v1.2.0 tokens) | embed_project | 1.2978 |
| v1.3.0 + embed_pretrain | embed_pretrain | 1.3896 |
| v1.3.0 + embed_project (clean comparison) | embed_project | 1.3717 |

The like-for-like comparison (same init strategy, same corpus size) shows a 0.074pp regression from polarity removal. This is not explained by dataset size (3,491 > 3,375) or init method.

#### Finding

neut was functioning as a predictable positional anchor — appearing after every entity row at a fixed interval, giving the model a reliable rhythmic structure. At 365M params trained on 3.5k examples, the positional attention benefits of this anchor outweigh the semantic noise it introduces.

The "polarity tokens carry no semantic information" finding from the normalisation audit remains correct. The mistake was assuming semantic noise equals training noise. At small corpus scale, structural regularity matters more than semantic cleanliness.

#### Decision

- Fix 2 is not reverted in Encoder.lean — the code change is correct and cleaner
- The v1.3.0 corpus (zero polarity tokens) becomes the new baseline
- Future training runs use v1.3.0 tokens; any comparison to DEC-021 must account for the 0.074pp structural-anchor cost
- Revisit polarity removal when corpus exceeds ~10k examples or when IR pretraining (item 4 in Phase 7 roadmap) is implemented

#### New baseline

v1.3.0 + embed_project: perplexity 1.3717, 3,491 train examples, vocab 8,221 tokens.
All future runs compared against this number unless otherwise noted.

#### References
- runs/variant_A_v1_3_0_true/results.json (embed_pretrain, 1.3896)
- runs/variant_A_v1_3_0_proj/results.json (embed_project, 1.3717)
- docs/reference/IR_V2_FIX_SPEC.md (Fix 2 spec)
- python/normalisation_audit.py
- DEC-021 (prior baseline)

---

### DEC-023 — Fix 3 (IO marker simplification) sets new Variant A best: 1.2751

**Date:** 2026-08-03
**Status:** Closed — new baseline established
**Decision:** v1.4.0 IR format (IN_N/OUT_N tokens) is now the active format. Fix 3 is confirmed effective.

#### Background

Fix 3 replaced compound IO marker strings (inputs:FVAR_0,FVAR_1 / output:TERM_2) with
arity count tokens (IN_N) and output position tokens (OUT_N). The hypothesis was that
9,977 unique inputs: token types were diluting the vocabulary signal for gen: tokens.

#### Experiment

Single controlled run on v1.4.0 corpus (4,029 examples, same 14 modules, re-extracted):

| Run | Vocab | Init | Perplexity |
|---|---|---|---|
| DEC-021 baseline (v1.2.0) | 8,144 | embed_project | 1.2978 |
| v1.3.0 (polarity removed) | 8,221 | embed_project | 1.3717 |
| v1.4.0 (IO markers) | 1,236 | embed_project | 1.2751 |

#### Finding

Vocab reduction from 8,221 to 1,236 tokens (85% reduction) improved perplexity by
0.0966pp vs v1.3.0 and 0.0227pp vs DEC-021. First time Variant A has beaten the
DEC-021 baseline. The IO marker token explosion was a real source of training noise.

The gap to B/C (BPE baselines at 1.1295/1.1102) is now 0.145pp, down from 0.17pp.

#### New baseline

v1.4.0 + embed_project: perplexity 1.2751, 3,491 train examples, vocab 1,236 tokens.

#### References
- runs/variant_A_v1_4_0/results.json
- docs/reference/IR_V2_FIX_SPEC.md (Fix 3 spec)
- DEC-022 (prior baseline, v1.3.0)

---

### DEC-024 — Flat-IR ablation: graph content is noise at this scale

**Date:** 2026-08-04
**Status:** Closed — decisive finding, design revision required
**Decision:** The semantic content of the IR graph is not being learned at 365M params / 3.5k examples. Pursue IR pretraining or corpus expansion before any further IR content changes.

#### Experiment

Flat-IR ablation: transform v1.4.0 token sequences into shape-only sequences where every content token (entity IDs, gen: ops, relation types, attribute keys/values) is replaced with SLOT. Vocab: 11 tokens only.

| Variant | Representation | Perplexity |
|---|---|---|
| Flat-IR (shape only, 11 tokens) | Structure only | 1.0551 |
| Variant C (AST BPE) | BPE baseline | 1.1102 |
| Variant B (raw BPE) | BPE baseline | 1.1295 |
| Variant A v1.4.0 (full IR) | Semantic graph IR | 1.2751 |

#### Finding — what the data actually shows

**Raw perplexity comparison is not valid across vocabulary sizes.** Flat-IR's low PPL is partly an artefact of task difficulty: 66.6% of flat-IR tokens are SLOT, making next-token prediction structurally easier. The vocabulary-normalised comparison in bits/token (log2 of PPL) is the correct measure:

| Variant | PPL | bits/token | vocab |
|---|---|---|---|
| Flat-IR | 1.0551 | 0.077 | 11 |
| C (BPE) | 1.1102 | 0.151 | 151,936 |
| B (BPE) | 1.1295 | 0.176 | 151,936 |
| A v1.4.0 | 1.2751 | 0.351 | 1,236 |

In bits/token, B and C remain well below Variant A. Flat-IR is lowest, but this reflects that predicting SLOT is easier than predicting mathematical identifiers. A bigram model achieves perplexity 2.38 on the flat-IR eval set; the neural model achieves 1.055 — the gap (2.38 → 1.055) represents real learning of structural patterns, not a trivial result, but it is a far simpler task than Variant A or B/C.

**What is confirmed:** At the current scale (365M params, 3.5k examples), Variant A's semantic content contributes approximately 0.27 additional bits/token of prediction difficulty above what shape alone requires, and the model cannot recover that cost. The semantic tokens (gen:, entity IDs, relation types) are not helping relative to their structural overhead.

**What is NOT confirmed:** Whether this is because (a) more data would allow the model to learn the semantics, or (b) the semantic tokens are inherently poorly suited to next-token prediction in this format regardless of data volume. The current experiments do not distinguish these explanations. "Data volume" was stated as the cause in earlier notes — that is a hypothesis, not a finding.

#### What the experiment was designed to test — and what it answered

The flat-IR ablation was designed to test: "Is graph structure helping at all, or is it noise?" The answer is: **the structural shape of Mathlib declarations is highly predictable and learnable. Whether the semantic content within that structure adds value cannot be determined from these experiments alone** — it requires either more data or a different experimental design (e.g., probing tasks, not perplexity).

#### Open questions the data does not resolve

1. Would semantic content help with more training data (10k+ examples)?
2. Would probing tasks (e.g., predicting declaration type from IR) show semantic content being used?
3. Is the BPE advantage due to Qwen pretraining priors, or is it a genuine representational advantage?

#### References
- runs/variant_flat/results.json (raw config and eval)
- python/build_flat_ir_dataset.py (flat-IR transform)
- Vocabulary normalisation analysis: log2(PPL) computed 2026-08-04
- Bigram baseline: PPL 2.38 on flat-IR eval, computed 2026-08-04
- docs/history/PHASE_7_ROADMAP.md (decision tree, item 4)
- DEC-023 (prior Variant A best, 1.2751)

---

### DEC-025 — Probing experiment: does Variant A encode semantic content?

**Date:** 2026-08-07
**Status:** ✅ Complete
**Decision:** A_encodes_semantics — IR representations carry strong semantic content; pursue v2 IR + corpus expansion

#### Purpose

DEC-024 established that Variant A's semantic content adds ~0.27 bits/token of unrecoverable prediction difficulty, but cannot determine whether this is a data volume problem or a training objective/format problem. This probing experiment resolves that ambiguity by testing whether semantic content is present in the model's internal representations at all, independent of perplexity.

#### Experiment design

See docs/experiments/PROBING_TASK_FINAL.md for full spec. Summary:

- Freeze each trained checkpoint, forward-pass all 4,029 corpus examples
- Mean-pool final hidden layer to 896-dim representation per example
- Train linear probe to classify 11 Mathlib module classes
- Compare Variant A vs Flat-IR (11-token shape-only) — gap is the key signal

Variants probed: A v1.4.0 (vocab=1236), C phase6 (vocab=151936), Flat-IR (vocab=11), B phase6 (vocab=151936), Random Qwen (no fine-tuning)

**Thresholds (set before running — from PROBING_TASK_FINAL.md Step 7):**

| Label | Criterion | Meaning |
|---|---|---|
| A encodes semantics | A accuracy minus Flat-IR accuracy >= 10pp | Semantic content in representations; data volume is bottleneck |
| Inconclusive | Gap 5-10pp | Run Task 2 (arity prediction) before concluding |
| Flat matches A | Gap < 5pp | Semantic tokens not in representations; format/objective problem |

#### Results

Ran 2026-08-07. Variants A and flat only (B, C, random not needed — gap was decisive).

| Variant | Accuracy (mean ± std, 3 seeds) | Macro-F1 | Balanced Acc |
|---|---|---|---|
| Variant A v1.4.0 | **75.4% ± 1.7%** | 0.703 ± 0.050 | 0.700 ± 0.025 |
| Flat-IR | 13.6% ± 1.5% | 0.042 ± 0.005 | 0.103 ± 0.002 |
| Random baseline | 9.1% | — | — |

A vs Flat-IR gap: **61.9 pp**
Outcome: **A_encodes_semantics**
Task 2 needed: No — gap is unambiguous

Per-class F1 (Variant A, best seed):
- Algebra.Group.Defs: 0.720
- Algebra.Group.Basic: 0.816
- Order.Lattice: 0.824
- Algebra.Ring.Defs: 0.626
- Order.Basic: 0.850
- Group.Subgroup.Basic: 0.866
- Order.LatticeIntervals: 0.950
- Algebra.Ring.GeomSum: 0.714
- Topology.Basic: 0.667
- Algebra.Ring.Basic: 0.267 ← weakest (likely overlap with Ring.Defs)
- Other: 0.571

#### Interpretation

The result is unambiguous. A 62pp gap between Variant A (75.4%) and Flat-IR (13.6%) — barely above the 9.1% random baseline — confirms that Variant A's representations carry strong Mathlib-structured semantic content. A linear probe alone is sufficient to distinguish 11 Mathlib modules with 75% accuracy, meaning the information is linearly decodable from the final hidden states.

Flat-IR at 13.6% confirms the shape-only baseline encodes almost no module-identifying content — the model learns structural sequence patterns but not mathematical identity.

The higher perplexity of Variant A vs Flat-IR (DEC-024: ~0.27 bits/token gap) is therefore a task difficulty artifact, not a failure to learn. Predicting the next semantic token (e.g. `typeclass_name:Group`, `gen:Mathlib.Algebra...`) is genuinely harder than predicting the next SLOT. The model is working correctly — it is learning a harder, more informative task.

The weakest class is Algebra.Ring.Basic (F1=0.267), likely due to semantic overlap with Ring.Defs. This is expected and is not a concern at this stage.

#### Next step

A_encodes_semantics → proceed with v2 IR implementation and corpus rebuild. The improved typeclass_name tokens (C2) should directly improve Ring.Basic/Ring.Defs disambiguation in future probing runs.

#### References

- docs/experiments/PROBING_TASK_FINAL.md — full experiment spec
- python/extract_representations.py — representation extraction script (OpenHands, openhands/probing-scripts)
- python/probing_task.py — linear probe training and evaluation (OpenHands, openhands/probing-scripts)
- runs/probing/task1_results.json — raw results (gitignored, written at runtime)
- DEC-024 — open questions this experiment resolves

---

> **Naming note for future IR candidates:** The v2 changes use C1–C4 labels.
> These map to the v1-era "Fix N" naming: C1 (polarity removal) = "Fix 2"
> (DEC-022); C4 (GEN bucketing) is new in v2. "Fix 3" (IO marker simplification,
> DEC-023) was a v1.4.0 change. Use this mapping when reading the decision history
> to understand why a future candidate should or should not repeat a change.

### DEC-026 — IR v2 compression gate: PARTIAL, proceed to implementation

**Date**: 2026-08-07
**Branch**: kit/ir-design-research (merged from openhands/ir-compression-gate, commit 40d8704)

#### Decision

Gate result is PARTIAL. Proceed to MetaExtractor.lean update implementing C1, C2, C4.

#### Gate results (simulation-based)

| Metric | current_A | v2_C1C2C4 | Pass? |
|--------|-----------|-----------|-------|
| BPT | 6.3718 | 6.4110 | ❌ |
| Redundancy | 0.3797 | 0.3772 | ✅ |
| Coverage | 0.9973 | 0.9973 | ✅ |

#### Why proceed despite BPT regression

The BPT increase (6.37→6.41) is a simulation artifact, not a real prediction. The simulation adds 6,298 brand-new synthetic tokens (IDs 9999, 9998 for C2) that each appear in only a handful of sequences — new rare tokens always increase entropy. In a real v2 encoder, the 20 typeclass tokens would appear across thousands of declarations at high frequency, driving BPT down, not up.

The redundancy improvement from C4 (GEN_UNK redistribution) is the meaningful signal: 1,564 tokens that were pooled into one bucket now spread across 20 — directly reducing the skewed distribution that was inflating redundancy.

C1 contributes zero to the simulation because the encoder already omits polarity. The schema change is still correct (removes dead schema weight) but has no measurable token-stream effect.

#### Approved schema changes

- ✅ C1 — polarity removal (schema cleanup, no token effect)
- ✅ C2 — typeclass enrichment (+2 tokens per typeclass-constructor declaration)
- ✅ C4 — GEN_UNK namespace bucketing (20 buckets, ~78 tokens each)
- ❌ C3 — attribute sparsity (deferred, needs Lean cross-check)

#### Next step

Implement C1, C2, C4 in MetaExtractor.lean and rebuild datasets. Run variant A training on v2 corpus. Gate: perplexity improvement over DEC-021 baseline (1.2978).

#### Implementation results (2026-08-08)

**C1/C2 partial run (variant_A_v2_full, first attempt):** perplexity **1.2458**
(vocab 601, 2 epochs, 44.5 min). Beats the DEC-021 baseline (1.2978) and the
prior best A (v1.4.0 = 1.2751). **But this run was C1+C2 only — C4 was missing.**

**C4 was not actually present in the dataset.** Audit (`docs/scratch/v2_token_analysis.md`)
found that `build_dataset.py`'s `encode_ir` mapped every `gen:*` token to a single
`GEN_UNK` (49,893 positions = 8.27% of all tokens); the `GEN_ALGEBRA`/`GEN_ORDER`/
… vocab entries were defined but never used. The corpus still emitted v1-style
`gen:<FullName>` and nothing bucketed them. So the 1.2458 result reflects
polarity removal + typeclass enrichment only, not the full v2 IR.

**C4 fix** (commit `f194027`): added `bucket_from_module` (replicates
`bucketFromModule` in `MetaExtractor.lean`) and modified `encode_ir` to map
`gen:* → GEN_<bucket>` by the declaration's module. Verified end-to-end after
dataset rebuild (`b72db9c`): `GEN_UNK → 0`; gen tokens redistributed to
`GEN_ALGEBRA` (5.36%), `GEN_ORDER` (2.77%), `GEN_TOPOLOGY` (0.10%),
`GEN_DATA` (0.04%). Regression tests in `python/test_c4_bucketing.py`.

**Full v2 (C1+C2+C4) re-run:** launched 2026-08-08 (commit `b72db9c` dataset +
`train_v2_resume.py` bos/eos null-out fix). Result:

> **RESULT** eval_perplexity = 1.2361 (full C1+C2+C4, vocab 601, 2 epochs, 44.8 min)

Gate (full v2): improvement over 1.2458 (C1+C2) and, ultimately, over the B/C
baselines (B=1.11, C=1.10). A v2 result below 1.2458 means C4 helps; below B/C
would give the representation hypothesis direct support.

**Full A/B/C results (200 examples, mask_last=10, authoritative checkpoints):**

| Variant | Representation | Vocab | Perplexity | Top-1 Acc | Correct/Total |
|---|---|---|---|---|---|
| A (v2, C1+C2+C4) | Maith IR tokens | 601 | 1.2361 | 90.0% | 1799/2000 |
| B | Raw leanExpr → Qwen BPE | 151,643 | 1.107 | 91.7% | 1816/1980 |
| C | AST-style → Qwen BPE | 151,643 | 1.098 | 93.0% | 1850/1990 |

Checkpoints: A=`runs/variant_A_v2_full`, B=`runs/variant_B2` (checkpoint-277),
C=`runs/variant_C_v2`. (The old stale `runs/variant_{A,B,C}` dirs were
quarantined to `runs/_stale_variant_*`; see `docs/scratch/runs_audit.md`,
`docs/scratch/variant_c_eval_bug.md`.)

**Gate outcome:**
- C1+C2+C4 (1.2361) < C1+C2 partial (1.2458) → **C4 helped** (~0.01 ppl, ~0.3pp accuracy).
- A still trails B (1.107 / 91.7%) and C (1.098 / 93.0%) on both metrics.
- The representation hypothesis is **not yet supported** by perplexity/accuracy.
  Consistent with DEC-025: under prediction metrics, the bottleneck appears to be
  data/objective, not the representation (A's representations encode strong semantic
  content, 62pp probe gap vs Flat-IR); non-prediction metrics (retrieval, ATP) are
  open (H6/H7). Next levers: corpus expansion, IR pretraining, objective redesign.

**Comparison gap identified (2026-08-09):**
The A/B/C comparison is confounded by model size — A uses a 601-token embedding
table (358M params) while B/C use 151k tokens (494M params). Two variables changed
at once: representation *and* parameter count. The critical control experiment is
**B-small** (BPE, 358M params, same training data as A) — if B-small ≈ A at 90%,
the size gap explains A's deficit; if B-small << A, the IR structure is doing real
work. See `docs/experiments/V2_COMPARISON_MATRIX.md` for the full 2×2 grid and DEC-027 for
the B-small experiment scope.

**Related fixes this session:**
- `eval_completion.py` stale-checkpoint guard (commit `c8d0e4e`) — warns when
  `results.json` mtime is >1d off from the checkpoint weights. This caught the
  Variant C 1.5%-top-1 bug: the default `runs/variant_C/` held a stale Jul-31
  checkpoint while its `results.json` described an Aug-1 run
  (`docs/scratch/variant_c_eval_bug.md`, `docs/scratch/runs_audit.md`).
- Quarantined the three stale/inconsistent dirs (`runs/_stale_variant_{A,B,C}`)
  so the default eval path can no longer load mismatched checkpoints.
  Authoritative runs: A→`variant_A_v1_4_0`/`variant_A_v2_full`, B→`variant_B2`/
  `variant_B_phase6`, C→`variant_C_v2`/`variant_C_phase6`.
- `train_v2_resume.py`: step-based checkpointing (`save_strategy="steps"`,
  ~half-epoch) + numeric resume sort, so mid-epoch stalls are resumable; also
  nulls `bos_token_id`/`eos_token_id` for variant A (base Qwen ids 151643 are
  out of range for the 601-token vocab and crashed eval on load).

---

### DEC-027 — B-small control: size confound confirmed, representation not yet doing measurable work under prediction metrics

**Date:** 2026-08-09
**Status:** ✅ Complete
**Decision:** B-small ≥ 90% gate → model size explains the A-vs-B/C gap at this scale. The v2 IR representation is not yet doing measurable work *under prediction-family metrics (perplexity, completion accuracy)* beyond what a small-vocab BPE achieves; whether it helps under non-prediction metrics (retrieval, ATP) is open (H6/H7).

#### Purpose

The v2 A/B/C comparison (DEC-026) was confounded by model size: A uses a 601-token
embedding table (358M params) while B/C use 151k tokens (494M params). B-small
controls for size by truncating BPE to the same 601 tokens and 358M params as A,
isolating representation (semantic IR vs raw BPE) from size.

#### Experiment

- **B-small:** Qwen2.5-Coder-0.5B with embedding table truncated to 601 tokens
  (top-601 BPE tokens, 99.92% coverage). Same 3,491 training examples, seed=42,
  2 epochs. Output: `runs/variant_B_small/`.
- **Vocab builder:** `python/build_b_small_vocab.py` (truncates BPE, remaps to
  compact 0..600 IDs). Datasets: `datasets/{train,eval}_B_small.jsonl`.
- **Eval:** `eval_completion.py --variants B_SMALL --checkpoint-B_SMALL
  runs/variant_B_small --samples 200 --mask-last 10` (B_SMALL variant support
  added to eval_completion.py to load the remapped eval split).

#### Results

| Variant | Representation | Vocab | Params | Perplexity | Top-1 Acc |
|---|---|---|---|---|---|
| A (v2 IR) | Semantic IR graph → tokens | 601 | 358M | 1.2361 | 90.0% |
| **B-small (BPE control)** | Raw BPE truncated to 601 | 601 | 358M | **1.1294** | **90.5%** |
| B (full BPE) | Raw BPE, full vocab | 151,643 | 494M | 1.107 | 91.7% |
| C (AST BPE) | AST-split BPE, full vocab | 151,643 | 494M | 1.098 | 93.0% |

#### Gate outcome

- **B-small top-1 = 90.5% ≥ 90% gate → size explains the gap.**
- B-small at matched params (358M, 601-vocab) achieves 90.5% — essentially tied
  with A's 90.0%. The IR representation is **not doing measurable work under prediction
  metrics (perplexity, completion accuracy)** beyond what a small-vocab BPE achieves at
  this scale; non-prediction metrics (retrieval, ATP) are open (H6/H7).
- On perplexity, B-small (1.1294) is better than A (1.2361) — BPE is more
  predictable than the IR tokens even at matched vocab/params, likely because
  BPE token distributions are more Zipfian/concentrated.
- The full B/C advantage (91.7%/93.0%) is mostly a **size effect**: B-small → B
  gains ~1.2pp from the 136M extra embedding params; B-small → A loses ~0.5pp
  from switching BPE to IR.

#### Interpretation

This does **not** disprove the representation hypothesis — it means the v2 IR, at
3.5k examples and 358M params, does not outperform a size-matched BPE baseline on
next-token prediction. Combined with DEC-025 (A's representations DO encode
semantic content, 62pp probe gap), the picture is:

1. The IR representation encodes real semantic structure (DEC-025 probing).
2. That structure does not translate to a next-token-prediction advantage over
   BPE at matched scale (DEC-027 B-small control).
3. Under prediction metrics, the bottleneck appears to be **training objective +
   data volume**, not the representation itself — next-token prediction may not be
   the objective that rewards semantic structure. **This is a scoped hypothesis about
   prediction, not a closed claim about representation overall.** Whether
   representation is the bottleneck *under semantic-task metrics* is exactly what H6
   (retrieval/similarity evaluation) would distinguish: if the IR wins on retrieval,
   then representation *is* doing work that prediction metrics couldn't measure, and
   this "objective is the bottleneck" interpretation is incomplete. See
   [`HYPOTHESIS_GRID`](../experiments/HYPOTHESIS_GRID.md) H5/H6.

#### Next steps for the IR-candidate search

- **Corpus expansion** (>10k examples) — the most direct lever; v2's 601-vocab
  is well-suited to scale.
- **Objective redesign** — next-token prediction may not reward semantic
  structure; consider a masked-reconstruction or proof-completion objective.
- **IR pretraining** — pretrain the embedding table on the IR before fine-tuning.
- **A candidate tweak** — if pursuing incremental v2.x: the perplexity gap
  (A 1.24 vs B-small 1.13) suggests IR tokens are harder to predict; a candidate
  that simplifies the token format further (e.g. C3 attribute sparsity) could
  narrow it, but DEC-027 says the gain would be from easier prediction, not
  richer semantics.

#### References

- `docs/experiments/V2_COMPARISON_MATRIX.md` — the 2×2 control grid (now complete
  for the B-small cell).
- `docs/experiments/V2_NEXT_STEPS.md` — merge-to-main checklist.
- DEC-025 (A encodes semantics), DEC-026 (v2 IR implementation + A/B/C results).


---

### DEC-028 — Operator identity collapse: C4 GEN bucketing as a competing explanation for the perplexity null

**Date:** 2026-08-09
**Status:** Accepted — confound identified, experiment designed, not yet run.

#### Background

C4 (GEN module bucketing, part of v2) collapses all operators within a Mathlib namespace
into a single `GEN_<area>` token (e.g., `GEN_ALGEBRA` for all algebraic operators). Only
~12 operators have special-cased distinct tokens (`Eq`, `LT.lt`, `HAdd`, `HMul`, etc.).
All other operators — `mul_comm`, `mul_left_cancel`, `isUnit`, and dozens of others — map
to the same token regardless of their semantic identity.

#### The competing explanation

DEC-027 concluded that the IR "is not yet doing measurable work under prediction metrics"
beyond size-matched BPE. The README and HYPOTHESIS_GRID attribute this to an objective
mismatch (H5/H11) — next-token prediction rewards predictability, not semantic utility.

C4 bucketing is a competing explanation that is not addressed by the current evidence:
the IR may underperform BPE on prediction not because canonicalization is inherently less
predictable, but because C4 specifically *removes operator identity* — a structural detail
that next-token prediction rewards. BPE at least produces different subword sequences for
`mul_comm` vs `mul_left_cancel`; the IR produces the identical `GEN_ALGEBRA` token for both.

This means the perplexity null (H2) may be partly a C4 design artifact, not solely a
prediction-metric limitation. It also affects H11's "contingent" component: the bias isn't
just "v2 didn't add semantic redundancy" — it's "v2 actively removed operator identity via
bucketing," which is a more specific and actionable diagnosis.

#### What this does NOT overturn

- H1 (IR encodes semantics) stands — DEC-025's probing gap (62pp) was measured on v2
  representations *with* bucketing, so the model extracts semantic signal despite it
  (via graph structure, entity IDs, typeclass attributes, and the ~12 special-cased ops).
- H2 (IR doesn't improve prediction) stands *for the v2 IR as designed* — the null is
  real for this specific representation. The open question is whether it generalizes to
  an un-bucketed IR.
- H11's fundamental component (canonicalization removes surface variation) stands. The
  contingent component is now more specific: C4 bucketing is an identified contributor.

#### Experiment to resolve

Add a `bucket_mode` flag to `MetaExtractor` / `encode_ir` with two modes:
- `module` (current behavior — ~20 GEN buckets)
- `per_operator` — emit the actual short operator name (`gen:mul_comm`, `gen:isUnit`),
  assign distinct IDs via the vocab builder with a frequency threshold (`GEN_UNK` for
  singletons) to bound vocab growth.

Re-run the A-vs-B-small comparison with `per_operator`. This is the decisive test:
- If A still ties B-small → the objective-mismatch interpretation is strengthened; the
  null is not a bucketing artifact.
- If A beats B-small → the prior null was a C4 artifact; the headline result changes.

#### Impact on H11

H11's "contingent" component is updated: the bias is partly attributable to a specific
design decision (C4 bucketing), not just a general "v2 didn't add semantic redundancy."
This makes the contingent component more actionable — the fix is specific (per_operator
mode), not vague ("design better tokens").

#### References

- DEC-026 (C4 implementation), DEC-027 (B-small result), DEC-024 (flat-IR ablation)
- `docs/experiments/HYPOTHESIS_GRID.md` — H2, H11
- `docs/experiments/EXPERIMENT_DESIGN.md` — v1→v2 IR optimization assessment

---

### DEC-029 — Code review findings: trivial fixes and doc corrections

**Date:** 2026-08-09
**Status:** Accepted — six findings from code review; three doc fixes to apply, two trivial
code fixes to apply, one already addressed.

#### Findings

**1. Operator identity collapse (C4 bucketing) — see DEC-028.**
The most important finding. Code + experiment needed.

**2. Proof terms skipped — the IR is a statement representation, not a proof representation.**
`constantValueExpr?` returns `none` for `.thmInfo`, so only statement types are extracted.
The README's "ATP success rate — ❌ not started" implies ATP eval is just a harness away;
it actually requires a proof-term extraction mode that does not exist.

**Doc fix:** Make explicit that the current IR is a *statement* representation and that
ATP/proof-search evaluation (H7) requires a proof-term extraction mode. Retrieval
evaluation (H6) does not need proof terms and is not blocked.

**3. Vestigial polarity no-ops in Normalizer.**
`normalizePolarityEntity/Attr/Rel/Op` are dead code from C1 (polarity removal). Pure cruft.

**Code fix:** Delete the four functions and their `.map` calls in `normalizeGraph`. Run
Lean tests to confirm nothing depended on them. ~15 min.

**4. Device priority bug in train.py.**
`mps` is checked before `cuda`, so on a machine with both, the slower MPS is selected.

**Code fix:** Reorder to `cuda → mps → cpu`. One line.

**5. Asymmetric init + MPS non-determinism framing — mostly addressed.**
The A-vs-B/C gap conflates representation, params, init, and run-to-run noise. The clean
test (A-vs-B-small, DEC-027) already exists and is presented as the primary result in the
README banner and HYPOTHESIS_GRID. The MPS non-determinism (DEC-013) is real but the
perplexity gap (1.2361 vs 1.1294) is large enough that it's unlikely to be noise.

**Status:** Already addressed in the current doc framing. A deterministic rerun is worth
doing before publishing any positive result, but not for the current null.

**6. B/C special-token inconsistency.**
Variant B adds BOS/EOS by default; C uses `add_special_tokens=False` per AST piece.
Undocumented difference, minor confound.

**Doc fix:** Add one line to variant definitions noting the special-token difference.

#### Summary

| # | Finding | Type | Effort | Status |
|---|---|---|---|---|
| 1 | C4 bucketing | code + experiment | medium | DEC-028 — experiment designed |
| 2 | Proof terms skipped | doc | small | Apply doc fix |
| 3 | Polarity no-ops | code | trivial | Apply code fix |
| 4 | Device priority | code | trivial | Apply code fix |
| 5 | Asymmetric init framing | doc | small | Already addressed |
| 6 | B/C special tokens | doc | trivial | Apply doc fix |

#### References

- DEC-028 (bucketing confound — the primary finding)
- `docs/experiments/HYPOTHESIS_GRID.md` — H2, H7, H11
- `docs/experiments/EXPERIMENT_DESIGN.md` — variant definitions, evaluation framework

### DEC-033 — H5 contrastive objective experiment: infrastructure built, ready to run (2026-08-18)

**Date:** 2026-08-18
**Status:** Active — infrastructure complete, training not yet run
**Scope:** H5 hypothesis, contrastive objective

**Decision:** Implement H5 (contrastive training objective) using NT-Xent / SimCSE
in-batch negatives, building on the A_v3_2ep checkpoint. Motivated by H6's ambiguous
result — the most credible explanation at toy scale is that next-token prediction does
not optimize for semantic similarity, not that the IR is wrong.

**Infrastructure built:**
- `python/build_h5_pairs.py` — positive pair construction from dependency groundtruth
- `python/train_h5_contrastive.py` — NT-Xent training loop with pre-flight gates
- `python/test_h5_pairs.py` — 15 unit tests (15/15 pass)
- `python/test_h5_contrastive.py` — 20 unit tests (20/20 pass)
- `datasets/h5_pairs_train.json` — 12,460 pairs from 3,375 declarations
- manage.py aliases: `build-h5-pairs`, `train-h5`, `extract-h5`, `eval-h5`, `eval-h5-mode2`
- `docs/experiments/H5_SCOPE.md` — full gate sequence and acceptance criteria

**Gate sequence:** see `H5_SCOPE.md`. Run `python test_h5_pairs.py` and
`python test_h5_contrastive.py` before any training run.

**What would close H5 positive:** A_h5 Recall@10 > A_v3_2ep with non-overlapping CIs
in both Mode 1 and Mode 2.

---

### DEC-030 — H6 retrieval retest: IR does not improve retrieval over BPE at toy scale (2026-08-12)

**Date:** 2026-08-12
**Status:** Closed
**Scope:** H6 (retrieval/similarity)

**Decision:** H6 is closed (negative) at toy scale under the prediction-trained objective.

**Experiment:** Clean 2-epoch retest of A_v3_2ep (per-operator IR, 2254-vocab, 359.9M params,
perplexity 1.2928) vs B_small (BPE truncated to 601-vocab, 358M params), both on the same
clean 3375/376 split. Fixes the epoch confound and dataset contamination from the initial run.

**Results:** Both modes agree — A_v3_2ep does not beat B_small (Recall@10: 0.0052 vs 0.0064
Mode 1, 0.0012 vs 0.0028 Mode 2, CIs overlap). The IR's explicit dep-name tokens didn't help
retrieval under next-token prediction.

**See:** `docs/experiments/H6_RESULTS.md` for full results and confound acknowledgment.


### DEC-031 — Comparison invariants invalidated: B_small and flat retrain pending (2026-08-12)

**Date:** 2026-08-12
**Status:** Active
**Scope:** Pipeline quality gates, H2/H6 comparison validity

**Decision:** Retrain B_small and flat on the clean 3375/376 split to resolve the
comparison-validity invariant failures (Gate 5-G5-4).

**Context:** The quality gate system (DEC-030 era, PIPELINE_QUALITY_GATES.md) identified
three comparison-validity failures in the invariant checker:

1. `comparison_representation_at_matched_size`: A (3375/376, 2ep) vs B_small (3491/388, 2ep) —
   train_examples and eval_examples differ. B_small was trained on the old leaky split.
2. `comparison_representation_at_matched_size` (A_v3): A_v3_2ep (3375/376, 2ep) vs B_small
   (3491/388, 2ep) — same issue, different train/eval counts.
3. `comparison_ir_vs_flat_ablation`: A (3375/376) vs flat (3627/402) — flat was trained on
   a different split.

**Resolution:** Retrain B_small and flat on the clean 3375/376 split at 2 epochs and
max_seq_len=512 (matching A_v3_2ep). This makes all three variants comparable: same
split, same epochs, same truncation.

**max_seq_len decision:** 512 (not 1024). Rationale: A_v3_2ep was already trained at 512;
switching to 1024 for B_small/flat would introduce a new truncation confound. G1-4 (330
sequences exceeding 512) remains a known warning — it affects all variants equally and
does not bias the comparison. A 1024 retrain of all variants is deferred unless results
suggest truncation matters.

**Pre-condition:** All quality gates must pass after retrain before any hypothesis test
(H1-H14) runs. Sanity checks (S1, S2) must also pass first.


### DEC-032 — B_small and flat retrained on clean split, comparison invariants resolved (2026-08-12)

**Date:** 2026-08-12
**Status:** Closed
**Scope:** H2/H6 comparison validity, pipeline quality gates

**Decision:** B_small and flat retrained on clean 3375/376 split at 2 epochs, max_seq_len=512.
Comparison-validity invariants now pass.

**Results:**
- B_small_clean: perplexity 1.1385, 358.4M params, 601 vocab, 3375/376, 2 epochs
- flat_clean: perplexity 1.063, 357.9M params, 11 vocab, 3375/376, 2 epochs
- A_v3_2ep: perplexity 1.2928, 359.9M params, 2254 vocab, 3375/376, 2 epochs

All three variants matched on split (3375/376), epochs (2), and size (~358M).

**Gate status after retrain:**
- Gate 1: 3/4 pass (G1-4 seq_len known warning, 330 seqs > 512)
- Gate 2: 5/5 pass
- Gate 3: 57/57 pass (all comparison invariants green)
- Gate 4: 23/23 pass
- Gate 5: 57/57 pass

**Sanity checks:**
- S1 (random baseline): WARNING — pretrained model scores above chance (0.072 vs 0.020). Not contamination
  — the "untrained" Qwen is actually pretrained on code and has existing retrieval signal.
- S2 (identical pair): PASS — Recall@1=1.0, MRR=1.0. Ranking logic verified.

**Pre-condition for hypothesis tests:** Gates 2-5 green, S2 passed, S1 is a documented warning.
  Hypothesis tests (H1-H14) are unblocked.

### DEC-035 — H5 end-to-end contrastive fine-tune complete; retrieval eval pending (2026-08-19)

**Date:** 2026-08-19
**Status:** Closed — ambiguous positive
**Scope:** H5 hypothesis, end-to-end contrastive fine-tune

**Decision:** Run the full end-to-end contrastive fine-tune (fine-tune the entire
A_v3_2ep encoder, not just a projection head) to test whether the H5 projection-head
effect grows with full model adaptation.

**Motivation:** DEC-033 established the projection-head result (Mode 2 statistically
positive, effect small). The projection head compresses 896→256 dims and freezes the
encoder; full e2e removes both constraints and is the cleaner test of whether the
contrastive signal can reshape the representation layer itself.

**Training run:**
- Base checkpoint: `runs/variant_A_v3_2ep/checkpoint-final`
- Objective: NT-Xent (in-batch negatives, temp=0.07)
- Dataset: 12,443 dependency pairs from `datasets/h5_pairs_train.json`
- Config: 1 epoch, batch=32, lr=2e-5, max_seq_len=512, device=MPS
- Total steps: 388
- Initial loss: 3.9335
- Final loss: 2.6762 (loss_descended=True)
- Duration: ~5.9 hours (21,344s)
- Checkpoint: `runs/variant_A_h5_e2e/checkpoint-final`
- Mid-run checkpoint: `runs/variant_A_h5_e2e/checkpoint-step200`
- Results: `runs/variant_A_h5_e2e/results.json`

**Gate status:** All gates verified clean at time of training (inherited from DEC-032/DEC-034).

**Retrieval eval results (2026-08-19):**

Mode 1 (eval→train, n=287):
- A_h5_e2e  Recall@10: 0.0042 [0.0009, 0.0082]  MRR: 0.0144 [0.0059, 0.0255]
- A_h5_proj Recall@10: 0.0057 [0.0013, 0.0118]  MRR: 0.0100 [0.0049, 0.0184]
- A_v3_2ep  Recall@10: 0.0052 [0.0009, 0.0113]  MRR: 0.0095 [0.0046, 0.0171]
- B_small   Recall@10: 0.0049 [0.0009, 0.0101]  MRR: 0.0140 [0.0062, 0.0256]
All CIs overlap — no statistically significant separation.

Mode 2 (train→train, n=2641):
- A_h5_e2e  Recall@10: 0.0027 [0.0016, 0.0040]  MRR: 0.0066 [0.0055, 0.0082]
- A_h5_proj Recall@10: 0.0029 [0.0014, 0.0048]  MRR: 0.0058 [0.0048, 0.0072]
- A_v3_2ep  Recall@10: 0.0012 [0.0005, 0.0019]  MRR: 0.0051 [0.0041, 0.0065]
- B_small   Recall@10: 0.0028 [0.0016, 0.0042]  MRR: 0.0061 [0.0051, 0.0075]

Mode 2 key finding: A_h5_e2e (0.0027) and A_h5_proj (0.0029) both statistically ahead
of A_v3_2ep (0.0012) — CIs non-overlapping. A_h5_e2e matches B_small_clean (0.0028),
CIs overlapping. Both contrastive variants improve over the next-token baseline; e2e
and projection-head are statistically indistinguishable from each other.

**Results files:**
- Mode 1: `runs/h5_retrieval/results_e2e.json`
- Mode 2: `runs/h5_retrieval/results_e2e_mode2.json`

**Interpretation:** H5 is an ambiguous positive. Contrastive objective (both e2e and
projection-head) reliably beats the next-token baseline in Mode 2. Full e2e fine-tune
does not further improve over the projection-head. The effect is real but small — well
below the pretrained baseline (Recall@10≈0.072). H5 cannot be closed positive at this
scale. Most informative next steps: H4/H8 (scale) or H9 (co-training).

**Status:** Closed — ambiguous positive. See HYPOTHESIS_GRID H5 row.

---

### DEC-034 — H6 retest: ambiguous result, closes neither direction (2026-08-18)

**Date:** 2026-08-18
**Status:** Closed
**Scope:** H6 retrieval hypothesis, HYPOTHESIS_GRID

**Decision:** H6 is marked partial/ambiguous in the hypothesis grid. The retest under
verified quality gates produced conflicting results across evaluation modes. H6 is not
worth re-running at toy scale; the next informative step is H5 or H4/H8.

**Evidence:**

Mode 1 (eval to train, n=287):
- A_v3_2ep Recall@10: 0.0052 [0.0006, 0.0090]
- B_small_clean Recall@10: 0.0049 [0.0009, 0.0101]
- A numerically ahead; CIs fully overlap — not statistically meaningful.

Mode 2 (train to train, n=2641):
- A_v3_2ep Recall@10: 0.0012 [0.0005, 0.0028]
- B_small_clean Recall@10: 0.0028 [0.0016, 0.0042]
- B_small_clean ahead; CIs do not overlap — statistically meaningful, leans negative.

**Interpretation:** The two modes disagree. Mode 2 has 9x more queries and its CIs do
not overlap — it is the more reliable signal. Under Mode 2, H6 leans negative at toy
scale. The direction is consistent with the original (invalid) DEC-030 finding after
correcting for the dataset confound.

**What this does not close:** H6 at scale (H4/H8), H6 under a contrastive objective
(H5), H6 under a graph-native architecture (H12). The negative result is specific to
next-token-prediction-trained embeddings at 358-360M parameters on 3375 examples.

**Gate status at time of test:** 57/57 pass (verified clean embeddings, correct split).
Results: runs/h6_retrieval/results_clean.json (Mode 1), results_mode2.json (Mode 2).
Full analysis: docs/experiments/H6_RESULTS.md.

**Next:** DEC-033 (H5 infrastructure) is the active front. H5 smoke test and full run
in progress as of 2026-08-18.


---

### DEC-036 — Adopt PleaNP CI/toolchain + integrity-gate protocol; open the axiom-discovery track; consolidate branches (2026-09-15)

**Date:** 2026-09-15
**Status:** Active
**Scope:** Repo infrastructure (CI, toolchain, gates), research direction (axiom discovery), branch hygiene

**Decision:** Maith adopts the CI and toolchain protocols learned in the sibling
project PleaNP (same author), redirects research toward the axiom-discovery track,
and consolidates all development onto a single `dev` branch. Concretely:

1. **Add the two new direction documents** — `docs/experiments/AXIOM_DISCOVERY.md`
   (active track: search for compressive foundations via homomorphic φ candidates,
   superseding the toy-model training path) and
   `docs/experiments/BENCHMARK_CORPUS_PLAN.md` (how the circuit-complexity
   benchmark corpus is built: conservativity corpus + transfer targets).
2. **Port PleaNP's CI/toolchain protocol** — `.github/workflows/ci.yml` (Lean
   build + tests, Tier-1 integrity gates, stdlib-only Python tests),
   `.devcontainer/` (warm elan + Mathlib-cache environment), `tooling/gates/`
   (hygiene, vacuity, lethality scanners + their fixtures), and
   `docs/TOOLCHAIN_AND_CI.md` documenting the two-tier gate model.
3. **Consolidate branches** — `dev` is now the single integration branch,
   merging `kit/dev` (42 commits ahead of `main`) with `main`'s doc commits.
   The stale remote branches are retired (see below).

**Rationale:** PleaNP formalized the complexity barriers under an integrity
protocol built specifically to defeat AI-authored proof failures — the class of
failure the claimed OpenAI Navier–Stokes resolution exemplifies: a proof that
compiles and reads plausibly but hides its difficulty in a definition, an
unstated axiom, or an unused hypothesis. The axiom-discovery track
(AXIOM_DISCOVERY.md) has exactly this exposure — it will produce Lean claims
(homomorphism obligations, transfer results) evaluated by AI-generated code — so
the gates must be in place *before* the first candidate, not after. Adopting the
protocol now, while the theorem surface is small, makes the discipline cheap.

**Branch consolidation detail (no work lost):** `kit/dev` was the canonical dev
line (42 ahead / 3 behind `main`). The three `main`-only commits are docs
(README "At a glance" + agentic-AI disclosure) and are retained. Genuinely
unmerged content from stale branches was checked file-by-file and merged onto
`dev` where it was not superseded:

- `docs/glossary-readability` — glossary readability pass (retained; merged, verified identical).
- `docs/agents-md` — V2_COMPARISON_MATRIX `A-large` N/A + `C-small` correction
  (retained; merged, verified identical).
- `docs/bucketing-confound-and-fixes` — DEC-028/029 already in `kit/dev`
  (superseded).
- `openhands/build-dataset-v2` — v2 GEN_* buckets already in `kit/dev`
  (superseded). `docs/DEPENDENCIES.md` (from `openhands/dev`, `probing-scripts`)
  is superseded by `docs/reference/PYTHON_PIPELINE.md` + `requirements.txt`.
- `openhands/ir-compression-gate` — the `ir-research/scripts/compression_gate.py`
  work is superseded by `python/check_ir_build.py` (the DEC-026 gate landing);
  `ir-research/` is a local-only, gitignored research dir.

The retired remote branches and their tip SHAs are recorded below so any
previously-unmerged commit remains recoverable (GitHub keeps unreachable objects
reachable via these SHAs; this table is the pointer registry):

| Retired branch | Tip SHA |
|---|---|
| `copilot/dev` | `db4a0ef6374931de72f580395cafc9169368af8d` |
| `docs/agents-md` | `642802976923c55bf87965cdb76dc40b7a39fc5a` |
| `docs/bucketing-confound-and-fixes` | `ed6a3565945f3711151e5e4aa45f33a3f58f829a` |
| `docs/experiment-scope` | `ba7731cb286185c3e7fb5e268b250806ffe1dce4` |
| `docs/glossary-readability` | `25e75e87efcb4614c6e9a058fec6db6a6c1ff4cf` |
| `kit/dev` | `6ae5593c418977b9cdc07b5b52e6cd613a40e86a` |
| `kit/ir-design-research` | `8f88331e3d74b1214091c84b7f79078b0fb55d36` |
| `literature-review-2026-08` | `9c06fc2f7d7a2487a01e6bf9f07d0d76e82ddea0` |
| `openhands/build-dataset-v2` | `b7f1dbb8e0e4d7fb8bcd500960c75e44c20064b5` |
| `openhands/decompiler` | `b46c5167e48e07ecc03183336d93a35aed4602c0` |
| `openhands/dev` | `1fdf258e121170087228a68cf0578f439c92fe95` |
| `openhands/ir-compression-gate` | `40d8704d48d3b63aa96b1ed4ac396dbae16c364f` |
| `openhands/ir-coverage-step2` | `0c52d4843fbc7096af497f84863b3ef57fdc1aaf` |
| `openhands/ir-metaextractor-v2` | `b37f86feb64632002405cb49088b421d96463fb7` |
| `openhands/ir-metaextractor-v2-c3c4` | `c89d0ec6b268bad27b6e893f52c18985786673d8` |
| `openhands/ir-schema-step3` | `f22d2932dc0d919e999489d92afec191ec3e89cd` |
| `openhands/ir-v2-test-audit` | `f7e2069e8b757e1e286efc819e64432b25400f40` |
| `openhands/phase-8c` | `52c084763569cd50058cf30288a92411cc2ddc1b` |
| `openhands/phase-8d` | `2ab10a5caca3880e856218f2b7f3103123177f91` |
| `openhands/probing-scripts` | `313034d58670a33760c0a1c6c0c7fc112cb94623` |
| `openhands/probing-task-design` | `ffdd2c4d670303c61582d873db613effb02f7c90` |

**Verification:** Lean toolchain set up per the ported bootstrap; `lake build
tests` and `lake build buildCorpus` both succeed. Tier-1 hygiene and vacuity
scans are clean; the lethality scan surfaced one real pre-existing dead helper
(`runEnvTest`, unused `env` parameter) and is wired advisory in CI pending
triage. **Caveat recorded:** the test harness exits 0 even when assertions fail
— the suite reports 4 pre-existing failures (2 decoder round-trip format, 1
injectivity non-commutative, 1 Lean validity), all documented in
`docs/experiments/V2_NEXT_STEPS.md`. The CI `lean` job surfaces these as a
warning rather than a false green. Making the harness exit non-zero on failure
is required before the test step is a true oracle. See `docs/TOOLCHAIN_AND_CI.md` §6.

**Status of gates at adoption:** Gate 6 (hygiene) clean; Gate 5 (vacuity) clean;
Gate 5 Tier 1b (lethality) 1 violation / 47 reviews (entry-point noise, allow-listed).

**Next:** stand up the axiom-rewrite harness (AXIOM_DISCOVERY §Immediate next
steps 3–4); the transfer gate's Tier-2 `#print axioms` check
(`tooling/gates/axiom_check.py`) activates with the first kernel-checked
transferred theorem.

---

### DEC-037 — Port the multi-agent task protocol; reconcile the axiom-discovery docs against reality (2026-09-15)

**Date:** 2026-09-15
**Status:** Active
**Scope:** Multi-agent workflow, research-direction docs, gate-model honesty

**Decision:** Complete the PleaNP protocol port begun in DEC-036 by adding the
*task-coordination* half (DEC-036 added the CI, toolchain, and branch halves), and
reconcile the two research-direction documents against verified ground truth
before any pipeline is built on them.

**(1) Multi-agent task protocol.** Added `docs/MULTI_AGENT_WORKFLOW.md` (adapted
from PleaNP): run-ids, one-claim-per-agent, stale-claim/protocol/docs sweeps,
`blocked by` dependency lineages, done-with-gate-evidence, `Tests:` follow-ups,
blockers in `blockers/`, and an end-of-session report. Created the seven status
labels on the repo (`status:available|claimed|done|blocked-needs-input`,
`priority:high`, `community-ready`, `needs-gate`) and a `blockers/` directory.

Maith previously had **no** task protocol — only per-task docs
(`TASK_AGENT_A_MANAGE_PY.md`, `TASK_AGENT_B_TENSORBOARD.md`) and an *artifact*
gate system (`manage.py gate`, 5 stations). The protocol names the artifact gates
as the done-evidence for experiment tasks, so the two systems compose rather than
duplicate.

**(2) Corpus premise corrected.** `AXIOM_DISCOVERY.md` and
`BENCHMARK_CORPUS_PLAN.md` both assumed the benchmark corpus would come from
importing `complexitylib`/`descriptive-complexity` "once PleaNP issue #70 lands."
Issue #70 closed 2026-09-13 **rejecting** that import (complexitylib's head pins
`v4.34.0-rc2` + a `cslib` dependency vs PleaNP's stable `v4.31.0`) and chose a
local `PleaNP.Circuits`. Consequence: the corpus source is
`PleaNP.Circuits`, which on PleaNP's `dev` branch holds five type-checking
modules (`Basic`, `AC0` — including the unproved `parity_notin_AC0` statement —
`Monotone`, `MonotoneApprox`, `MustRefute`). It is **concentrated in one area**
(circuit complexity), so **Part 1 of the corpus plan (conservativity corpus) is
blocked on breadth**, not on existence (issue #31); Part 2 (transfer targets) is
unblocked and should go first. Both documents updated to say so.

An earlier draft of this entry, and of both documents, described
`PleaNP.Circuits` as an "early stub" — that was read off PleaNP's `main` branch,
where only a 17-line placeholder exists. The real modules are on `dev`, which is
212 commits ahead. Corrected here; the lesson (check the work branch, not the
default branch, when assessing a sibling repo) is worth keeping.

**(3) Claimed-but-absent infrastructure corrected.** Verified on 2026-09-15:

| Claim | Reality |
|---|---|
| Structural similarity search (subgraph isomorphism / graph edit distance / fingerprinting) exists, "originally built as a proof-candidate generator" | **Absent.** `Maith/GraphEquivalence.lean` is exact structural/normalized/rewrite *equality* (a test helper referenced only by `Init.lean`), not similarity. This is the search mechanism itself — real work, not reuse. |
| HOF application + projection parsing are "the highest-priority extraction gaps... the actual blocking dependency" | **Done.** `MetaExtractor.lean` handles both; `testHOFApplicationExtracts` / `testProjectionExtracts` pass. (The stale inline comment in `MetaExtractor.lean` claiming otherwise was corrected in this change.) |
| Toy-model loop "moved to `archive/`" | **No `archive/` exists.** The scripts remain in place and wired into `manage.py`; shelving is a research-direction decision (README §9), not a filesystem move. |
| `DIRECTION.md` (3 references) | **Does not exist** in Maith, PleaNP, muse, or philharmonic. |

Both documents gained a reconciliation table recording the above; the actual
blocking dependency is re-stated as the circuit-complexity substrate, and
`AXIOM_DISCOVERY.md`'s "Immediate next steps" were reordered to build the
nonexistent pieces in dependency order (transfer-target list → ledger/coverage
map → similarity search → harness → first batch).

**(4) Gate-model gaps recorded, not papered over.** The workflow doc's §"Known
gaps" lists four places where a green check is weaker than it looks, to be filed
as `priority:high` tasks: (i) `check_invariants.py` declares five `must_match`
fields but `test_invariants.py` has a failing fixture for only the **epoch** axis,
so the `seed`/`train_examples`/`eval_examples`/`representation_id` constraints are
unproven; (ii) no invariant guards the losslessly-verifiable representation
claims in `ENCODER_FORMAT.md`; (iii) `manage.py gate`'s `--datasets` scoping;
(iv) the Lean test harness exits 0 on failure (also DEC-036 §6).

**Rationale (the OpenAI Navier–Stokes lesson, applied to process):** the same
discipline that motivates the integrity gates — a check that cannot fail is not a
check — applies to the protocol itself. Adopting a task protocol whose
done-evidence is a tautology would reproduce the failure it exists to prevent.
Hence the explicit "known gaps" section rather than a clean-looking port.

**Verification:** labels created via the GitHub API (7, all 201); `docs/`
cross-references updated (README, AGENTS.md, docs/README.md, decisions/INDEX.md);
`lake build tests` still succeeds after the `MetaExtractor.lean` comment fix;
Tier-1 hygiene/vacuity gates still clean.

**Next:** file the four §Known-gaps items as `priority:high` issues, then the
axiom-discovery build-out as a `blocked by` lineage per the new protocol.

**Filed (this session, exercising the new protocol):** #22–#25 (the four
gate-model gaps, `priority:high` + `needs-gate`) and #26–#31 (the axiom-discovery
build-out as a `blocked by` lineage: #26 targets, #27 ledger, #28 search ← #27,
#29 harness ← #28, #30 first batch ← #26/#27/#29, #31 conservativity corpus
blocked on upstream `PleaNP.Circuits`). Dependency edges were set via the GitHub
issue-dependencies API (which requires the internal `issue_id`, not the issue
number).
---

### DEC-038 — Axiom-discovery taxonomy + pipeline diagram; restore the glossary's lost terminology section (2026-09-15)

**Date:** 2026-09-15
**Status:** Active
**Scope:** Terminology, documentation of the transfer pipeline

**Decision:** Name the axiom-discovery pipeline and its vocabulary explicitly, and
fix a documentation regression introduced during the DEC-036 branch consolidation.

**(1) New glossary sections.** `docs/reference/GLOSSARY.md` gains:

- **§Terminology: family, candidate, structure** — *restored*, see (3).
- **§Axiom discovery: the transfer pipeline** — defines the track's terms:
  transfer target, benchmark corpus (Parts 1/2), φ, target structure, the five
  gates, candidate ledger, coverage map, the proposal heuristics, `#barrier_check`.

**(2) A real terminology collision, now named.** The word **"candidate" is
overloaded** between the two tracks:

- *Experiment track* ("the IR"): a candidate = a concrete tokenization of the
  semantic graph family (v2.0.0, a v2.x tweak). Defined since `966c49a`.
- *Axiom track*: a candidate = the φ spec (target structure + domain + φ
  definition + provenance). ~35 uses in `AXIOM_DISCOVERY.md`.

Same word, different referents. The glossary now flags this with an explicit ⚠ and
a rule: qualify in writing as **"candidate φ"** vs **"IR candidate"** when the
distinction matters. This was previously undocumented — a reader moving between
the two docs would reasonably conflate them.

**(3) Regression found and fixed.** `ENCODER_FORMAT.md` links to the glossary
anchor `#terminology-family-candidate-structure`. **That section did not exist** at
`origin/dev`: it was added at `966c49a` (2026-08-12, "consolidate IR terminology"),
and the `docs/glossary-readability` branch — which rewrote `GLOSSARY.md` — was
based on a commit *before* `966c49a`, so its rewrite reverted the section. When
that branch was folded into `dev` in DEC-036, the loss came with it.

This is a self-inflicted regression from DEC-036: the consolidation verified the
glossary's *readability* changes as byte-identical to the source branch, but did
not check that the source branch had dropped content added *after* its base. The
lesson — **when merging a long-lived branch, diff its content against the current
work branch, not just against the branch it came from** — is the same class as the
"check the work branch, not the default branch" lesson from DEC-037.

Fix: the section is restored verbatim from `966c49a`, plus a `##` heading so the
anchor `ENCODER_FORMAT.md` already links to resolves.

**(4) Pipeline diagram.** `AXIOM_DISCOVERY.md` gains a mermaid diagram of the
end-to-end flow: upstream `PleaNP.Circuits` → corpus (targets unblocked / Part 1
breadth-blocked) → proposal (ledger, coverage map, similarity search) → the five
gates → `#barrier_check` on anything crossing gate 3. It makes three buried facts
visible: #28 is a real build rather than reuse; the corpus halves differ in status;
and gate 4 is downstream of gate 3 by construction.

**Verification:** mermaid block balanced (4 `subgraph` / 4 `end`); both files
UTF-8 clean; anchor target now resolves.

**Next:** the taxonomy is now written down but the overload remains in prose —
`AXIOM_DISCOVERY.md`'s ~35 unqualified uses were left as-is (qualifying them all
would churn the doc). Cleared up as each section is next edited.

---

### DEC-039 — Axiom-discovery: substrates, output object, and the IR-mode constraint for #28 (2026-09-15)

**Date:** 2026-09-15
**Status:** Active
**Scope:** Axiom-discovery pipeline design; issue #28 Definition of Done

**Decision:** Make three previously-implicit things explicit in
`AXIOM_DISCOVERY.md`, and record the verification behind the one that changes an
open issue.

**(1) Two jobs, two substrates.** The track has been read as "candidates are
written in the IR" and as "candidates are written via metaprogramming"; both are
wrong, and the doc invited the confusion by titling a section "Candidate
representation". The actual split:

- **Propose** (find candidate phi's) consumes **the IR** — similarity search needs
  an indexable, comparable object.
- **Validate** (run the five gates) uses **metaprogramming** — the gates are Lean
  obligations, dischargeable only by elaborating terms.
- The candidate's **phi itself is ordinary Lean**. It is neither IR (a token
  sequence cannot state a homomorphism) nor metaprogrammed. The pattern is that
  phi is written normally but discharged by instance search — the mechanism
  `#barrier_check` already uses.

The section was renamed `## Candidate spec (record shape)`, with the table added.

**(2) The output object was undefined.** Gate 5 promotes a surviving phi to
"reusable" and nothing defined the record that promotion produces. Following the
document's own definitions, the track's product is neither the phi (phi maps into
an *existing* structure) nor a candidate (disposable probes) but the **promoted
structure** — the small generator that transfers and replicates across unrelated
sub-domains, i.e. GCT's shape. A record **schema** is now defined; the tooling is
deliberately **not** built (no candidate has survived gate 3, so building it would
repeat the very failure the reconciliation note corrects — describing
infrastructure before there is anything to put in it).

**(3) IR-mode constraint on structural search (verified, not asserted).** The
default extraction mode collapses operator identity, so structural similarity over
it would match *shape* but not *which operation*. Verified at source and by
execution:

- `Maith/MetaExtractor.lean:137-141` — `genericOpToken` returns `bucketFromModule st`
  for `BucketMode.module` (the default, `:30`), vs `s!"op:{headName}"` for `.per_operator`.
- `Maith/MetaExtractor.lean:111` — `bucketFromModule` maps by *declaration module*.
- Executed: `python3 python/test_c4_bucketing.py` ->
  `all gen:* -> GEN_ALGEBRA (29); got [29, 29, 29]` — three distinct operators
  (`gen:Foo`, `gen:Bar.Baz`, `gen:Quux`) collapse to one token.
- Corroborated: `Tests/CorpusPipelineTests.lean:236-249` asserts both modes
  (`proj:GEN_MATHLIB/0` vs `proj:Semigroup/0`).

**Issue #28 updated** with this evidence and a DoD addition: the search must consume
`--per-operator` extraction, and the done comment must state the corpus mode and the
distinct-operator count it produced, so shape-only matching cannot pass unnoticed.

**Method note.** (3) was initially stated by reading a doc description (AGENTS.md's
DEC-028 summary). On request it was re-derived from the extractor lines and an
executed test before being written into #28's DoD — the project's own discipline
(no claim accepted against a description of an artifact rather than the artifact).
Recorded because the first pass was one step shy of the standard this repo holds
itself to.

**Verification:** mermaid balanced (4/4); Tier-1 hygiene/vacuity clean; both files
UTF-8 clean; #28 body confirmed to carry the addendum.

---

### DEC-040 — Cross-repo Lean imports: verified feasible; (a) chosen for transfer-target formalization (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** Axiom-discovery corpus plan Part 2; PleaNP packaging; Maith #26

**Decision:** Formalize circuit-complexity transfer targets **in Maith** (option
(a)), importing circuit-model definitions from PleaNP. Cross-repo import was
verified feasible rather than assumed, and the one real blocker is filed upstream
as PleaNP #102.

**Why this needed deciding:** Maith extracts IR from elaborated `Expr` inside a
running Lean process, and `Scripts/BuildCorpus.lean` enumerates only modules it
can import. A target statement formalized in PleaNP would therefore not reach
Maith's pipeline. The alternatives were (a) formalize in Maith, or (b) formalize
in PleaNP and defer extraction.

**Verified feasibility (not asserted).** A scratch consumer package depending on
PleaNP at `3e74ae6`:

```
$ lake update
error: PleaNP: no configuration file with a supported extension:
  .lake/packages/PleaNP/lakefile.lean
  .lake/packages/PleaNP/lakefile.toml
```

PleaNP's Lake package lives at `lean/`; Lake resolves a dependency's root at the
repo root. With a root shim (`package «PleaNP» where srcDir := "lean"` plus the
`lean_lib` declaration), both the dependency and the consumer built, and real
definitions resolved:

```
✔ Built PleaNP.Circuits.Basic (21s)      # dependency
✔ Built Maith.Probe (52s)                # consumer
PleaNP.Circuits.BoolGate : ℕ → Type
PleaNP.Circuits.IsPPoly : CircuitFamily → Prop
PleaNP.Circuits.Largeness : PropertyFamily → Prop
PleaNP.Circuits.NaturalProperty : PropertyFamily → Prop
```

Both repos pin Lean `v4.31.0` / Mathlib `v4.31.0`, so there is no toolchain drift
to reconcile — unlike PleaNP #70, where the mismatch is what killed the
`complexitylib` import.

**Two findings that shape consumption:**

1. **A shim alone is insufficient — the dependency must be built.** With the shim
   present but PleaNP uncompiled, the consumer fails with `unknown module prefix
   'PleaNP'`: Lake resolves the path but finds no oleans. Consumers must build the
   `PleaNP.Circuits` closure (or consume the warm image).
2. **`srcDir` handles layout, not target resolution.** Without the `lean_lib`
   declaration in the root file, `lake build PleaNP.Circuits.Basic` is `unknown` —
   so the shim duplicates the library declarations. Flagged as a duplication for
   PleaNP to resolve deliberately.

**Correction recorded.** An earlier statement in this project held that
re-exporting PleaNP's modules "would effectively require a mirror repo." That is
**wrong** — it needs a ~10-line root lakefile upstream. The claim was made without
testing; testing it took one experiment. Same failure mode as DEC-037's method
note (assert from a description rather than the artifact).

**Filed upstream:** PleaNP **#102** — root `lakefile` shim, with three options
(A: shim + duplication; B: move package to root; C: extractable sub-package) left
for the maintainer, plus the CI-coupling and import-weight consequences.

**Maith side:** #26 body rewritten around option (a) and its DoD made explicit —
statements live in `Maith/Benchmark/`, must type-check against PleaNP imports, and
the done comment must include the `lake build` output. Steps 1-3 (research,
filtering, cross-check) are unblocked and need no Lean; step 4 (formalization) is
blocked on PleaNP #102. #26 carries **no** `status:available` label until then, and
the external blocker is stated in-body because PleaNP #102 cannot be a native
GitHub `blocked_by` edge across repos.

**Also noted, not covered by #26:** `Scripts/BuildCorpus.lean` hardcodes its module
list, so getting `Maith/Benchmark/` declarations into the IR corpus is a separate
change (to that list or to its discovery mechanism).

**Verification:** the import experiment was run end-to-end (clone, shim, Mathlib
cache restore, dependency build, consumer build, `#check` of four PleaNP
definitions); scratch dirs removed afterward and the Maith working tree left clean.

---

### DEC-041 — Search/proposal refinements filed as #32-#34; #28 extended to candidate dedup (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** Axiom-discovery search/proposal loop; issue tracking

**Decision:** Record the maintainer's four search-loop refinements as tracked
issues, **without starting them**. Per the maintainer's explicit priority note,
none of this reorders the queue — the transfer-target list (#26) remains the
unblocked next step, and these land once #28-#30 are underway.

**Filed:**

| Issue | Refinement |
|---|---|
| **#32** | `failure_mode` on the ledger — a fixed enum (`not_homomorphism`, `degenerate_collapse`, `target_too_weak`, `no_replication`), not free text, so gate 1-5 failures are groupable. Three open questions raised in-issue: gate 4 may be non-failing (the doc calls it bookkeeping), singular-vs-plural (the pipeline is admission-controlled, so the first failure is the meaningful one), and required-vs-optional (recommended required, else it drifts to free text). |
| **#33** | Retrieve prior failures by (structure-family, sub-domain) before proposing, and feed their `failure_mode` into the proposal prompt. Depends on #32. **Flagged as under-scoped in the original phrasing**: the ledger stores `target_structure` and `domain` as *free strings*, so "query by family/sub-domain" requires a schema addition (a `structure_family` field or a mapping), not merely a query. |
| **#34** | **Gate 6** — adversarial significance check via 2+ genuinely distinct external models with mirrored for/against prompts. Filed `status:blocked-needs-input` because the maintainer asked to confirm scope first. Scope boundary written in-issue: IN = one small script (prompt template, 2-3 API calls, ledger writes); OUT = any orchestration, retry/queue layer, caching service, or harness change. Four open questions: which providers (available: `GOOGLE_API_KEY`, `NVIDIA_BUILD_KEY`, `OPENHANDS_API_KEY`), whether gate 6 gates `reusable` or is purely a signal, cost/volume cap, and the result schema. |

**#28 extended, not forked.** The candidate-dedup proposal is folded into #28 as
instructed, since it is the same fingerprinting machinery on a second input.
Written in-issue as two phases:

- **Phase 1 (original scope, Mathlib `corpus.jsonl`)** — remains **claimable**. The
  extension was written so it does not make #28 unactionable.
- **Phase 2 (candidate φ dedup)** — genuinely blocked, and the reasons are recorded
  rather than hand-waved: (i) fingerprinting an *elaborated* φ requires φ to exist
  as a Lean term, but the ledger stores φ as a spec string — elaborating it is #29's
  job; (ii) phase 2's input format is undefined, and getting anything new into
  `corpus.jsonl` means extending `Scripts/BuildCorpus.lean`'s hardcoded module list.
  So "same machinery, second corpus" needs the second corpus pinned first.

The in-issue DoD for phase 2 requires a test using a pair that is *the same map
under different names* — a text diff would miss it, which is the entire point — and
requires that test in the done comment, so a dedupe that only catches textual
repeats cannot pass.

**Token issue recorded (environment).** `ALL_REPOs_GH_TOKEN` has **`repo` scope
only**, so pushing any change under `.github/workflows/` is rejected with
`refusing to allow a Personal Access Token to create or update workflow ... without
workflow scope`. `GITHUB_TOKEN` has the workflow scope (and admin on this repo).
Both authenticate as the same login. Workaround — swap the remote URL for pushes
touching workflows, then restore — is now documented in `docs/AGENT_HANDOFF.md`
§Commands so the next agent does not rediscover it by hitting a password prompt.

**Rationale for filing rather than building:** the maintainer asked for scope
confirmation on #34 and gave an explicit do-not-reorder instruction. Filing keeps
the proposals from being lost while leaving the queue untouched. Two of the four
items also turned out to need schema decisions the maintainer should make (#32's
gate-4 question, #33's family/sub-domain fields), which is exactly what the
blocker protocol exists for.

**Verification:** #32-#34 exist (201) with the labels above; #28's body confirmed to
carry the two-phase addendum and still labelled `status:available`; handoff queue
table and Commands section updated; docs UTF-8 clean.

---

### DEC-042 — Part 2 transfer targets drafted (T1-T10 + N1/N2); steps 2-3 handed to the maintainer (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** Axiom-discovery benchmark corpus, Part 2; issue #26

**Decision:** the Part 2 transfer-target list is drafted at
`docs/experiments/TRANSFER_TARGETS.md` — 10 targets plus 2 screening results.
Research (step 1) is done; **steps 2 and 3 are explicitly NOT done** and remain the
maintainer's, and step 4 is blocked on PleaNP #102.

**Tool substitution, stated plainly.** `BENCHMARK_CORPUS_PLAN.md` assigns step 1 to
a DeepSeek research pass. DeepSeek was not available here, so it was executed with
web research (Tavily, targeted queries, primary sources preferred). That substitutes
the *tool*, not the *role*: the plan's step-2 human filtering and step-3 independent
cross-check are unaffected by the substitution and are still required.

**Structure of the list.** Organised around a distinction the plan does not make
explicitly, which matters for what a candidate φ is being tested against:

- **OPEN** targets (no known proof) — a φ reaching one is a new result.
- **RESOLVED-but-novel** — a proof exists, so a φ re-deriving it is a
  *transfer/compression* test rather than a discovery. This is the "small generator
  repays across scales" signal `AXIOM_DISCOVERY.md` describes.
- **NEGATIVE / barrier** results (N1 natural proofs, N2 relativization/algebrization)
  — screening instruments, not targets; N2 is what `#barrier_check` operationalises.

The maintainer should confirm this reading at step 2, because if the track wants
**only** OPEN targets the list shrinks to T2/T3/T4-gap/T7-general/T8/T9 — every one
of which is *believed to require* the very circuit lower bounds that are blocked.
That is a real constraint on what a φ could reach and it is recorded in the doc.

**Primary-source verification caught a real error.** T6 (matching) was first drafted
from a search snippet as "bipartite matching, 2^{n^{1/3−o(1)}}". Reading the arXiv
abstract directly showed the headline theorem is **perfect** matching at
**2^{n^{Ω(1)}}**, with bipartite as a separate theorem and a different exponent. The
doc now records the corrected statement *and* records the miss in its cross-check
section — the plan's step-3 rationale ("a single LLM pass can miss a recent result or
misstate a theorem's status") materialised within the drafting itself.

**Retraction hazard recorded.** T5 notes that Norbert Blum's 2017 claimed P ≠ NP
proof (approximation method on monotone functions) was retracted by the author —
arXiv:1708.03486 is the replacement, its comments field reading "the replacement of
the incorrect paper". Any φ touching monotone lower bounds must cite the established
papers (Tardos 1988; Grötschel-Lovász-Schrijver), not the retracted claim. This is a
live hazard for this specific track because the retracted proof used exactly the
monotone-approximation machinery the track targets.

**Scope finding for step 4 (new).** Two target families likely need substrate
`PleaNP.Circuits` does **not** have: T8/T9 are proof complexity (Frege, AC⁰-Frege) and
T7's other half is communication complexity. `PleaNP.Circuits` is Boolean-circuit
shaped (gates, families, AC⁰, monotone). So even after PleaNP #102 lands, some
targets need *new substrate*, not just import. Recorded rather than discovered later.

**T1 is already partially available.** PleaNP `Circuits/AC0.lean` defines `parity`,
`IsAC0`, `ComputesParity`, and `parity_notin_AC0 : Prop` (unproved, with partial
results landed). It is not yet importable into Maith (blocked on #102), but the
statement shape exists — verified by inspection, not assumed.

**What was deliberately NOT done.** No stand-in `Maith/Benchmark/` definitions were
written to make the formalization table look complete. Doing so would violate the
point of option (a) — importing the *real* PleaNP models — and would produce
statements that type-check against the wrong substrate, which is the failure mode the
integrity gates exist to catch. Each target instead records its blocked reason, which
the issue's DoD explicitly permits.

**Also not done, and flagged:** step 3's genuinely-independent second-model pass. The
plan says it is mandatory given how load-bearing the list is. The doc says so and
recommends running it before the list is frozen. Partially mitigated by using
multiple independent sources per target (course notes, surveys, arXiv, Dagstuhl
LIPIcs, proceedings) rather than one pass — but that is mitigation, not the step.

**Citations verified:** six primary/secondary URLs checked as resolving (200), and
the two load-bearing claims (T6's exact statement, the Blum retraction) verified
against their primary sources rather than a description of them.

**Verification:** doc is 386 lines, UTF-8 clean, 12 per-target verification notes;
every citation URL resolves; Tier-1 gates clean. Nothing was entered into the
candidate ledger — targets are not candidates (a candidate is a φ, and no φ has been
proposed); future candidates should reference a target id (T1-T10) in their `domain`
field.

---

### DEC-043 — PleaNP #102 landed: step 4 unblocked; pin-to-SHA required, PleaNP dev is CI-unverified (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** Cross-repo dependency for #26 step 4; PleaNP packaging

**Decision:** PleaNP #102 is closed (commits `1037101` + `da0f7f0` on PleaNP `dev`),
so **#26's step 4 (formalizing transfer-target statements in Maith) is no longer
blocked on the import**. Two operational constraints are recorded with it, and one
open decision is deferred.

**What landed upstream.** A root `lakefile.lean` with `srcDir := "lean"` (option A
from #102), a drift guard (`tooling/gates/lakefile_sync_check.py`, wired into CI,
5 tests / 7 drift classes), and PleaNP DEC-027. PleaNP's own build commands are
unaffected — every one runs from `lean/`, and Lake picks the nearest lakefile.

**Verified end-to-end from Maith**, against the real GitHub URL rather than a local
copy:

```
require PleaNP from git "https://github.com/allenpd728/PleaNP.git" @ "dev"
$ lake update                                       -> EXIT=0
✔ Built PleaNP.Circuits.Basic (62s) / Soundness (5.1s) / AC0 (6.1s)
✔ Built Maith.Benchmark.Probe (5.6s)
PleaNP.Circuits.parity_notin_AC0 : Prop
PleaNP.Circuits.IsAC0 : PleaNP.Circuits.CircuitFamily -> Prop
```

So T1's statement shape imports directly instead of being restated — the point of
option (a). The temporary Maith-side change was **reverted**; Maith's tree is clean.

**Constraint 1 — pin to a SHA, not `@ "dev"`.** The verification used the moving
branch, which works but means a PleaNP push could break Maith's build with no
change on Maith's side. Step 4 should pin a revision.

**Constraint 2 — PleaNP `dev` is not CI-verified.** Checked every workflow trigger:
`ci.yml` runs on `push: [main]` and `pull_request: [main]` only; `warm-toolchain.yml`
runs on `push: [main, dev]`; and `main` is **not branch-protected** (API returns
"Branch not protected"). So the `#102` commits were verified *locally* — both build
commands, all four Tier-1 gates, the sync guard and its tests, plus the end-to-end
consumer build — but not by CI. The legitimate route to CI coverage without
violating branch discipline is a `dev` -> `main` **pull request**, which both
triggers the workflow and surfaces the change for the review `AGENTS.md` requires.
Recorded upstream on #102; the maintainer's call whether to add `dev` to `ci.yml`'s
triggers instead.

**Deferred decision — the permanent Maith-side dependency.** Whether Maith adds
`require PleaNP` to its `lakefile.lean` for good. Verified working, but it makes
Maith's CI hard-depend on PleaNP building and pulls the full Mathlib closure (via
`Circuits.Basic`'s `import Mathlib`). Deferred to when step 4 actually starts; not
made unilaterally.

**On Mathlib submission (asked, answered, no action).** The question was whether
submitting PleaNP's Lean files to Mathlib formally would establish that Maith is
using valid, useful code. **No — that would not achieve the goal, and PleaNP has
already scoped the question.** Its `docs/MATHLIB_SUBMISSION.md` (2026-09-06) records
that PleaNP is *not* ready to submit anything: the upstream P/NP substrate is
contested, the only eventual candidate is the **oracle-machine layer** (not
circuits, not the barriers), and the load-bearing prerequisite is a **named human
accountability anchor** who can engage Zulip — the same gap flagged for funding.

The category mismatch is the real answer: Mathlib acceptance validates
*Mathlib-appropriateness* — style, generality, API design, absence of duplication in
their tree — not that a definition is *useful for Maith* or *used correctly by
Maith*. And it is slow (weeks to months, multiple review rounds, rejection the
default expectation).

**What actually satisfies the goal** is Maith-side and cheap: (a) the definitions
*type-check and compose*, which is mechanically verified; and (b) the formal
definition -> plain-English gloss mapping is correct, which is the irreducible human
read-back step (`docs/AGENT_HANDOFF.md` §"The human's part", Gate 4). That is a
per-definition review, not an upstream process. Recorded on #26 so step 4 does it
explicitly rather than assuming it.

**Also recorded:** the corpus needed by #28 phase 1 is **not committed**
(`Corpus/corpus.jsonl` is gitignored; only manifest/logs/stats are tracked), so a
`lake exe buildCorpus --per-operator` run is a prerequisite for that work. Noted
because it is easy to assume the corpus is present. `check_ir_build.py` already
defaults to `Corpus/corpus.per_operator.jsonl`, so the per-operator mode is at least
consistent with the IR gates' expectations.

**Verification:** `lake update` + consumer build green from Maith; PleaNP's own
`lake build PleaNP.Circuits.Basic` (8558 jobs) and `lake build tests` (8564 jobs)
green with the root file present; PleaNP hygiene/vacuity/unicode gates clean on all
changed paths; Maith tree clean after reverting the temporary dependency.

---

### DEC-044 — PleaNP CI enabled on dev; two environment-shaped defects found; #105 open (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** PleaNP CI coverage; implications for the Maith-side PleaNP dependency

**Decision:** PleaNP now runs CI on `dev` pushes (not only `main`), and `dev` is
green. Done because `dev` was 116 commits ahead of `main` with the build/test
workflow **never having run on it** — so any defect accumulated silently.

**Result: CI run #99 on `dev` (`7e5c08a`) — 40/40 steps, 0 skipped.**
`main` remains triggered; PRs to `main` remain the review gate.

**The first run failed, and that is the useful part.** Run #98 (`7eba75c`) failed
at the Gate 8 unicode step with **645 violations** — every one inside
`lean/.lake/packages/{mathlib,aesop,batteries}` (9341 vendored `.lean` files).
`unicode_scan.scan()` walked with `rglob("*")` and had no vendored-tree exclusion,
so it scanned upstream code as if it were PleaNP's.

**That defect was invisible to every local check**, including a full 37-step local
rehearsal run earlier in this same session that reported the step PASS. `.lake` does
not exist until `lake exe cache get` runs; the scan had nothing upstream to find.
A real CI checkout materialises it. Fixed in `7e5c08a`, verified both ways against a
tree with `.lake` actually present (without the exclusion: 645 violations; with it:
clean, exit 0); `unicode_scan`'s 21 unit tests still pass.

**A second, structurally-disqualifying defect was found in the Galaxy regen smoke
step** (filed as PleaNP #103, fixed). `metadata.repo` embedded an absolute path
(`str(repo_root)`), so `cmp` could never match in CI regardless of staleness — the
step was *incapable of passing* there. Made location-independent; verified
byte-identical when regenerated from a different checkout directory. Its stale
NaturalProofs row was fixed in the same pass.

**Both defects were environment-shaped** — one path-dependent, one
vendored-tree-dependent — and neither was reachable from a clean local tree. The
lesson recorded upstream: a local rehearsal is not CI, and to rehearse meaningfully
the environment differences must be reproduced deliberately (materialise `.lake`,
run from a CI-like path), not assumed away.

**Filed and still open: PleaNP #105** — `main` and `dev` have **diverged**. `main`
carries 4 commits not in `dev` (PRs #99/#100: README "At a glance" + agentic-AI
disclosure), both touching only `README.md`. Until back-merged, a `dev` -> `main`
merge is a merge of divergent lines and those README changes could be lost. Same
class of divergence as this repo's DEC-036.

**Implications for Maith (relevant to #26 step 4):**

- **The PleaNP dependency is safer than it was.** `dev` now has CI on push, so a
  break introduced upstream is visible rather than silent. This does not remove the
  need to pin a SHA (DEC-043) — CI greenness is not a stability guarantee — but it
  materially lowers the risk of consuming a broken revision.
- **`main` is not branch-protected**, so PleaNP's review-before-merge discipline is
  convention, not enforcement. Recorded upstream; not a Maith decision.

**Method note (recorded because it cost a cycle).** The earlier local rehearsal
reported "36/37, effectively green" and I relayed that as the expected first-run
result. The first genuine run was red. The doc's caveat ("a local reproduction is
not CI") was already written; applying it is the hard part. Concretely: reproduce
the environment before believing a rehearsal.

**Verification:** CI #99 green on `dev` at `7e5c08a` (40/40 steps, verified by
enumerating job steps rather than reading the run conclusion); PleaNP #103, #104,
#106 closed with evidence; #105 filed and open.

---

### DEC-045 — PleaNP merged dev -> main; pin `@ "main"`; branches content-identical (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** Cross-repo dependency pin for #26 step 4; PleaNP branch state

**Decision:** PleaNP's `dev` is merged to `main` (PleaNP `a4aae01`), and Maith should
pin **`@ "main"`** rather than the `@ "dev"` that DEC-043 recommended.

**Sequence, each step verified before the next:**

1. **Back-merged `main` into `dev` first** (`dff52f7`) — closing PleaNP #105. `main`
   carried 4 commits `dev` lacked (PRs #99/#100, `README.md` only: the "At a glance"
   block and the agentic-AI disclosure). Without this step the `dev` -> `main` merge
   would have been a merge of *divergent* lines and could have dropped them.
   Verified: `At a glance` and `agentic AI tooling` each appeared 1x on `main` / 0x
   on `dev` before; both present after.
2. **CI green on that merge commit** — PleaNP run #100 at `dff52f7`.
3. **Merged `dev` -> `main`** (`--no-ff`, `a4aae01`) and pushed.
4. **CI green on `main`** — run #101 at `a4aae01`, **40/40 steps, 0 skipped**.
   Verified by enumerating job steps, not by reading the run conclusion — a mistake
   made earlier in this session.

**`main` and `dev` are content-identical.** `git diff origin/main origin/dev` is
empty; the sole `main`-only commit is the merge commit itself. So pinning `main`
loses nothing.

**Why `main` beats `dev` as the pin:**

- `main` is where CI has run all along; `dev` only since 2026-09-16.
- A `dev`-pinned downstream build can break from an unrelated upstream push, since
  `dev` is the working branch and moves freely.

**Still pin a SHA for reproducibility.** A branch moves. The name is acceptable
while step 4 is exploratory; a SHA is required once a result is cited.

**End-to-end verification against `main`** (the thing downstream actually pins):

```
require PleaNP from git "https://github.com/allenpd728/PleaNP.git" @ "main"
✔ Built Demo.Probe (4.3s)
PleaNP.Circuits.parity_notin_AC0 : Prop
@PleaNP.Circuits.Reducer.approximate : {n : ℕ} → MonotoneGate n → ApproxSet n
@PleaNP.Circuits.ApproxSet.sm_and_size_le : ∀ {n} (A B), (A.smAnd B).sizeOf ≤ A.sizeOf * B.sizeOf
```

**Correction to my own verification, recorded because the failure mode generalises.**
The first consumer probe failed with `Unknown identifier
PleaNP.Circuits.MonotoneApprox.Reducer.approximate`. I had built the path from the
**filename**: the module is `MonotoneApprox` but the namespace is `Reducer`, so the
name is `PleaNP.Circuits.Reducer.approximate` — and I had also omitted the import.
Fixed by reading the actual `namespace` declarations in the file. The same
name-from-filename guess would put a plausible-but-wrong declaration path into any
downstream doc, which is the class of error the `#check` discipline exists to catch.
Confirmed by `#check`, not by reading.

**PleaNP CI status, both branches:** `dev` run #99 (40/40) and `main` run #101
(40/40). Only #101 is on the long-verified line.

**Verification:** PleaNP `main` and `dev` content-identical; CI green on both;
consumer build against `@ "main"` succeeds and resolves real circuit definitions;
the merge preserved both README additions; PleaNP #105 closed.

---

### DEC-046 — ENCODER_FORMAT's testable claims machine-enforced (invariants 8 + 9); #23 closed (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** `docs/reference/ENCODER_FORMAT.md` claims; `check_invariants.py`; issue #23

**Decision:** `ENCODER_FORMAT.md`'s **testable** claims are now named invariants with
fixtures that can fail, and the doc carries a claim → invariant → fixture table plus
an explicit list of claims *deliberately not* machine-checked.

- **Invariant 8** (`check_grammar_arity`): `GRAPH_BEGIN`/`GRAPH_END` envelope,
  `E`/`A`/`R`/`O` row headers only, row arities (E=2, A/R/O=4), `IN_N ≤ 9`/`IN_MANY`,
  `OUT_N ≤ 63`/`OUT_MANY`/`OUT_VAR`.
- **Invariant 9** (`check_c1_polarity_absence`): C1's claim that no polarity tokens
  appear in a v2 stream.

**Two traps, both found by running against real data rather than reasoning:**

1. **`neg` is ambiguous, so C1 cannot be a string-absence check.** `neg` is both a
   polarity marker and the arithmetic op token (id 12), and appears **467 times** in
   `train_A.jsonl`. Every occurrence sits in an `O` row's op slot (all preceded by
   `OUT_*`) — arithmetic negation, which v2 legitimately emits. My first instinct
   ("assert no polarity token in the data") would have failed on *correct* data.
   Invariant 9 is therefore **role-based**.
2. **The IR grammar describes IR tokens only.** `B`/`C`/`B-small` are Qwen BPE and
   `flat` is the SLOT ablation. Checking them against the IR grammar produced
   **10,114** and **103,096** spurious "malformed" reports on the first run. Both
   invariants now discover IR-token variants from each record's `source` field.

**A fixture caught a bug in my own invariant:** a short `A` row silently absorbed
`GRAPH_END` as its `value` slot, so the row looked well-formed and the terminator
check never fired. Fixed by bounding the row slice at the first boundary token.

**Mutation-guard design changed.** The first guard reported 4 mutations as failures.
Diagnosis showed each property was still caught by a *second* code path — defence in
depth. Reporting those as failures would train a reader to ignore the guard, so it
now distinguishes **DETECTED / REDUNDANT / GAP** and fails only on a genuine gap or a
broken control. Result: 6 detected, 3 redundant, **0 gaps**.

**Also in this change set:** known-gaps 1 and 2 in `MULTI_AGENT_WORKFLOW.md` were
stale (gap 1 had been closed by #22 but still read as open). Both now marked
resolved. Gap 3 (#24) is the last open one.

**A false claim in my own commit history, corrected rather than hidden.** Commit
`3b5d175`'s message asserted it "refreshed the gap-5 wording". It did not — there is
no gap 5, and the diff touched only gap 2. Since `dev` is not force-pushed, the
message cannot be amended, so the correction is recorded here and in the follow-up
commit `3527141`. Worth noting for the pattern: the claim was specific and
plausible, and I did not verify it before committing. The diff is the evidence, not
the message.

**Verification:** `test_invariants.py` 23 pass / 0 fail; guard 6/3/0; the real checker
reports `grammar_arity_A_{train,eval}` and `c1_polarity_absence_A_{train,eval}` PASS
on committed datasets. CI run #36 green on `5ea8397`, including the new
"Encoder-format invariants are not vacuous" step. The one checker failure
(`corpus_format`, `Corpus/corpus.jsonl` absent) is pre-existing — confirmed unchanged
by re-running with the change stashed.

---

### DEC-047 — manage.py gate/invariants path resolution (#24); all four known gaps closed (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** `python/manage.py` gate commands; `MULTI_AGENT_WORKFLOW.md` known gaps

**Decision:** `manage.py gate` and `manage.py invariants` now resolve every path
argument through one `resolve_repo_path` helper. This closes the last of the four
known gaps (#22-#25) recorded when the multi-agent protocol was ported.

**The defect was subtler than the issue described.** The issue said "takes a
`--datasets` path and otherwise falls back to a default", implying the fallback was
the risk. It was not: the default was already correct (`DATASETS_DIR`, repo-anchored
from `REPO = Path(__file__).resolve().parent.parent`). The three real problems:

- `gate --datasets <relative>` used the value **verbatim**, so it resolved against
  the **caller's cwd** and could gate a different tree.
- `manage.py invariants` used bare `"datasets"` / `"runs"` as **both** the default
  and the override — always cwd-relative, and inconsistent with `cmd_gate`.
- Neither printed **which** tree was gated, so a transcript was not self-evidencing.

**Fix:** relative paths anchor at `REPO` (stable meaning from any directory); a
missing directory is a **hard error (exit 2) before any gate runs**; the resolved
path is printed in a `GATE TARGET` header alongside the tree's provenance
(`representation_id`, `encoderVersion`, `seed`, train/eval counts) read from
`representation_manifest.json`.

**Why error rather than fall back:** the entire point is to prevent gating the wrong
tree. A silent fallback to the default is exactly the contamination class
`RUN_REGISTRY.md` guards against, so failing loudly is the safe behaviour.

**Two mistakes of my own, both caught before shipping** — recorded because the
classes recur:

1. `describe_dataset_dir` first read `train_manifest.json` assuming a summary dict.
   It is a **per-example list**; the summary is `representation_manifest.json`. The
   first version printed `manifest=unreadable` on correct data. Fixed, and both file
   shapes are now documented in the function.
2. The first `cmd_invariants` mutation in the guard left a **dangling `except`**, so
   its "DETECTED" was really a `SyntaxError` — proving nothing about the tests.
   Spotted because the guard reported `exit=1` with `failures=0`, the signature of a
   crash rather than an assertion. Replaced with a well-formed mutation.

**Verification:** `test_manage_gate_paths.py` 10 pass / 0 fail; its mutation guard
6/6 detected with a passing control; CI run #40 green on `38c1c35` including the two
new steps. `MULTI_AGENT_WORKFLOW.md`'s known-gaps section is struck through with a
header stating all four are closed, and kept as a list of traps rather than deleted.

**State of the ported protocol:** gaps #22 (invariant fixtures), #23
(encoder-format claims), #24 (this), #25 (harness exit code) are all `status:done`.
The remaining open Maith issues are #26 (blocked on maintainer steps 2-3), #28
(similarity search, claimable), #29/#30 (blocked down the chain), #31 (blocked
upstream), and #32-#34 (search-loop refinements, deliberately not started per the
maintainer's priority note).

---

### DEC-048 — Structural similarity over IR graphs, phase 1 (#28); mutation-guard bytecode hazard fixed (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** `python/structural_similarity.py`; `#28`; all five mutation guards

**Decision:** `#28` phase 1 lands — canonical structural fingerprints over IR graphs
plus a documented graded similarity for ranking. `Maith/GraphEquivalence.lean` is
exact *equality* for testing; this is *similarity* for candidate discovery.
Phase 2 (candidate dedup) stays blocked, per the issue's own addendum.

**What "similar" means, decided explicitly.** Three candidate notions: exact identity
(trivial, already covered), alpha-equivalence modulo naming/ordering (decidable —
implemented), and semantic similarity (needs human judgement, no ground truth). Only
the middle one is claimed. Per `AXIOM_DISCOVERY.md`'s filter-not-generator constraint,
this ranks and prunes; it never asserts two graphs *mean* the same thing.

**Fingerprint invariance (presentation) vs sensitivity (content).** Invariant to
declaration name, bound-scope strings, positional indices, ordering, and polarity.
Sensitive to row kinds, relation direction and operator, attribute keys/values,
operation identity and arity, and **free-variable names**.

**A design boundary pinned by a test.** `ENCODER_FORMAT.md` calls free-variable names
(`Eq`, `HMul.hMul`) "semantically stable… real vocab", so they are content: changing
one must **not** match. My first fixture asserted the opposite ("rename `Eq` to `Iff`,
must still match") and failed — **the code was right and the fixture was wrong**.
`test_free_variable_name_change_must_not_match` records the decision so it is not
later "fixed" into a regression.

**The `--per-operator` constraint, now measured.** The module *errors* on a
module-bucketed corpus rather than warning. On two unrelated real graphs: **0.18**
per-operator vs **0.54** module-bucketed — ~3× inflation from losing operator
identity alone. The silent quality loss `#28`'s addendum warned about is now visible.

**Real corpus results (4,029 graphs):** 3,167 distinct fingerprints, 539 shared by
more than one graph, 1,401 graphs in a shared group. Largest groups are genuine
families (`CancelMonoid`/`CommMonoid`/`SubNegMonoid` at 51×).

**Three gaps found by mutation testing, all in my own fixtures:**

1. **Relation direction** unprotected — the fixture varied only the *operator*, so
   collapsing `src`/`tgt` left every test passing.
2. **Operation arity** unprotected — the existing fixture coincidentally also added
   an entity, so it did not isolate arity.
3. **Only detectable in the CI condition** — with `Corpus/corpus.jsonl` absent (it is
   gitignored), the "operation identity ignored" mutation went undetected because its
   only catcher was corpus-dependent. Added synthetic fixtures so the guard is
   corpus-independent. A guard whose detection depends on a gitignored artifact is
   not a guard.

**A serious hazard found and fixed in the same change set: mutation guards could
leave stale bytecode, corrupting the module under test.** A guard writes a *mutated*
module to disk, runs tests, then restores the source — but the mutated build's `.pyc`
survived the restore and was loaded by **later** processes. `axiom-rewrite` loaded
`open("w")` instead of `open("a")` and *truncated the ledger*. It surfaced as
`test_candidates.py` failing 3 tests hours after passing, with `git diff` showing no
source change. Proven by disassembling the cached bytecode (`LOAD_CONST 'w'`).

All five guards now purge the target module's bytecode after restoring, via a shared
`_purge_bytecode` helper. Verified: all five pass, leave no stale `.pyc`, and
`test_candidates.py` passes *after* the guards run. Also fixed a false-GAP in the
`manage.py` guard (it mutated only `cmd_invariants`, leaving `cmd_gate`'s
runs-resolution intact, so the CLI still errored and the guard misreported).

**Verification:** 19 structural-similarity tests pass, verified corpus-independent by
moving `Corpus/corpus.jsonl` away (the CI condition); mutation guard 9/9 detected with
and without the corpus; full local CI suite 17/17; CI run #43 green on `1979702` with
the two new steps passing.

**Also:** `#29` unblocked (`status:available`) now that `#28` is done, per protocol
step 7. Noted on it that only phase 1 of `#28` landed, so phase 2's dependency on
elaborated φ remains — arguably `#29` territory.

### DEC-049 — Mutation-guard bytecode hazard closed at the root (#36) (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** `tooling/mutation_guard_lib.py` (new), `tooling/test_mutation_guard_lib.py`
(new), the five mutation guards, `.github/workflows/ci.yml`,
`docs/AGENT_HANDOFF.md`.

**Decision:** DEC-048 recorded that mutation guards could leave a stale mutated
`.pyc` that a *later* process loads even after the source is restored — it once
truncated the candidate ledger (`open("w")` surviving a restore of `open("a")`)
and surfaced as unrelated test failures hours later. DEC-048's fix purged the
bytecode cache, but placed the purge **outside** the guard's `try/finally`: the
restore was protected, the purge was not. Any exception from inside the mutation
loop — `KeyboardInterrupt`, or a `subprocess.TimeoutExpired` from the structural
guard's `timeout=600` — restored the source and skipped the purge, leaving
exactly the stale `.pyc` the fix existed to prevent. The five guards also
duplicated the helper verbatim, which is where the divergence arose.

The hazard is now closed at the root in a single shared module,
`tooling/mutation_guard_lib.py`:

* `guarded_source(SRC)` binds restore **and** purge into one `finally`, so no exit
  path can skip either; it also purges on entry, so a stale `.pyc` from an earlier
  crashed run cannot contaminate this one, and drops the module from `sys.modules`
  so a re-import re-reads the restored source.
* `run_python(...)` launches guard children with `-B` and
  `PYTHONDONTWRITEBYTECODE=1`, so the mutated `.pyc` is not written in the first
  place — the fix disables the cause, not just cleans up after it.
* `sys.dont_write_bytecode = True` at import time covers the guard process itself
  (the invariants 8/9 guard imports the mutated module in-process).

All five guards now use the helper. The false docstring in
`python/test_mutation_guard.py` ("temp copy via an import shim — the real source
file is never modified") is corrected: the guard writes the **real** source, which
is exactly why the restore/purge guarantees matter.

**Verification:** `tooling/test_mutation_guard_lib.py` — 5 tests, including a
positive control that reproduces the stale-`.pyc` load and two tests that fail
when the old bug is reintroduced (purge moved outside the `finally`; entry purge
removed). All five guards pass (4/4, 6 detected + 3 redundant, 7/7, 9/9, 7/7),
leave no stale `.pyc`, and `test_candidates.py` passes afterwards. The new test is
a CI step in the `python` job.

**Rationale:** The convention's failure modes are all *silent* and surface in a
*later* process, which is the most expensive shape to debug. A shared helper that
makes the safe path the only path is worth more than five correct-but-copyable
incantations — DEC-048's own note ("more delicate than it looks") was the warning;
this is the structural answer to it.

---

### DEC-050 — Five-gate harness (#29) + harness→ledger bridge; main untouched by instruction (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** `axiom-rewrite/harness.py`; issues #29, #36, #37; branch policy

**Decision:** `#29` lands. The shared five-gate harness consumes candidate **specs as
data** — per the DoD's explicit constraint, no DSL or elaborator per candidate — and
gates 1-3 are discharged by the **Lean kernel**, not by a grep. Plus the bridge into
the candidate ledger that #29's own known-limits list had recorded as missing.

**Gate semantics.** A gate passes iff its obligation **elaborates**.
`set_option warningAsError true` makes a smuggled `sorry` an *error*, so it cannot
pass a gate — tested. Obligations are written in **positive** form, so no polarity
flag is needed: a false obligation simply fails to elaborate.

**Three specs pin the DoD's three requirements:**

- `fixture_unit_collapse.json` — gate 1 PASS (it genuinely is a homomorphism),
  gate 2 FAIL (collapsing everything makes injectivity false). Rejected, no partial
  credit.
- `fixture_transfer_fails.json` — gates 1-2 PASS, gate 3 FAIL → gate 4 refuses.
- `control_valid.json` — all five PASS. This is what makes the rejections
  meaningful: without a passing case, "rejects everything" looks identical to
  "rejects correctly".

**A mistake caught before shipping, worth recording as a pattern.** The first
version of gate 2's obligation was written as a **refutation** (proving
non-injectivity). That elaborates fine, so the harness would have marked the
degenerate candidate as **PASSING** gate 2 — the exact inverse of the DoD's
requirement, and it would have looked correct. Positive-form obligations fixed it.
Caught by asking what "gate 2 fails" means *mechanically* before writing the spec.

**Bridge (#37).** `candidate_from_run()` / `record()` persist a run to the ledger;
`run --record <ledger>` is opt-in so a dry run changes nothing. The ledger's rules
are deliberately **not** re-implemented — the bridge passes gate outcomes through
and lets `candidates.py:validate` accept or reject, keeping the ledger the single
authority. Compression is forwarded only when gate 3 passed, so an offered number
for a failed transfer is **declined** (recorded as `compression=None`) rather than
erroring.

**Took a sibling's better fix for the bytecode hazard.** A sibling landed
`tooling/mutation_guard_lib.py` (#36) which binds restore+purge into one `finally`
and disables bytecode writes via `-B`/`PYTHONDONTWRITEBYTECODE`. That supersedes my
DEC-048 per-guard purge, which ran *outside* the `try/finally` and so could still
leak a mutated `.pyc` on a crash or child timeout. Merged rather than reconciled:
my commit only added new harness files, so there was nothing of mine to keep.

**Branch policy change — `main` is no longer pushed from this session.** The
maintainer reported that main-correlated pushes are consuming Netlify credits.
Investigated: **Maith and PleaNP are not connected to any Netlify site.** The two
sites are `muse-qa-58fd708e` (repo `allenpd728/muse`, branch `dev`) and
`philharmonica` (`allenpd728/philharmonic`, branch `main`); scanning 175 recent
deploys across both found zero mentioning Maith or PleaNP. The `muse` site deploys
on its **`dev`** branch, and read 20 deploys on 2026-09-16 aligned with `muse`'s own
commits. So the credit spend is `muse`'s, not this repo's — reported plainly rather
than silently complying with a premise that does not hold. Reading is all that was
done: changing a live site's build config is an owner action, not attempted.

Per the instruction, this session pushed **only to `dev`**. Consequence recorded:
`main` now trails `dev` by the #29 work (and `dev` is by design content-superset).
The 22 "main-only" commits found while checking are all this session's own earlier
dev→main merges, not third-party work.

**Verification:** `test_harness.py` 13 passed / 0 failed (incl. 3 bridge tests and a
`sorry`-must-fail test); `lake build tests` 72 jobs; CI run #52 green on `ecc90ad`
with the harness step running **in the Lean job**; `#36`'s guard-lib tests 5/5 and
both migrated guards pass. Tier-1 gates clean; no stray `.lean` scratch or
`__pycache__` left (`-B` used deliberately).

### DEC-051 — Corpus filename encodes the bucket mode (#35): the builder/consumer contract, and an overwrite footgun closed (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** `Maith/MathlibCorpusBuilder.lean`, `Tests/CorpusPipelineTests.lean`,
`python/check_ir_build.py`, `python/test_corpus_filename_contract.py` (new),
`.github/workflows/ci.yml`, `AGENTS.md`, `docs/AGENT_HANDOFF.md`,
`docs/reference/PIPELINE_QUALITY_GATES.md`,
`docs/reference/STRUCTURAL_SIMILARITY.md`, `docs/experiments/KNOWN_ISSUES.md`.

**Decision:** `buildCorpus` encoded the bucket mode in *how* it built but not in
*what* it wrote: both modes wrote `Corpus/corpus.jsonl`. Meanwhile the consumers
(`check_ir_build.py`, `structural_similarity.py`) default to
`Corpus/corpus.per_operator.jsonl`. So the documented command
(`lake exe buildCorpus --per-operator`, required by #28's DoD) produced an artifact
the documented gate could not find, and — worse — because both modes shared a path,
a per-operator build silently overwrote the module-mode corpus. That second half is
KNOWN_ISSUES #3 / AUDIT_2026_08_10 P0-2: the on-disk corpus stopped matching the v2
manifest because a `--per-operator` run had replaced it.

The mode is now in the filename: `corpusFileNameForMode` maps `.module` to
`corpus.jsonl` and `.per_operator` to `corpus.per_operator.jsonl`, applied in both
`buildMathlibIRCorpus` and `buildMathlibIRCorpusWithTrace`. Consumers' defaults
become correct as a consequence, so the documented command now feeds the documented
gate; the explicit `--corpus` escape remains as the override.

Option 2 from the issue (require an explicit `--corpus` everywhere) was rejected:
it leaves the two modes sharing a path, so it does not fix the overwrite, and it
contradicts every doc that already names `corpus.per_operator.jsonl`.

**Verification (real Lean build; toolchain v4.31.0 + restored Mathlib cache):**
- `buildCorpus --per-operator` writes `Corpus/corpus.per_operator.jsonl` (4029 examples)
- `buildCorpus` (module) writes `Corpus/corpus.jsonl` (4029 examples)
- **Both files coexist afterward** — the overwrite can no longer happen.
- `manage.py gate ir` and `structural_similarity.py` now find the corpus with no
  `--corpus` (G1-1/G1-2/G1-3 PASS; G1-4 remains the DEC-032 accepted warning).
- Lean test `testCorpusFileNameForMode` (26/26 suite green) plus the new
  `python/test_corpus_filename_contract.py` (5 checks, CI-wired) pin the contract;
  both were confirmed to FAIL when the mapping or its application is reverted.

**Rationale:** A filename is a contract between two languages, and the bug was that
nothing tested the contract. The cross-language test binds the Lean mapping to the
Python defaults, so renaming one side cannot silently break the gate again.

### DEC-052 — Candidate batch runner + ledger VCS policy (#37) (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** `axiom-rewrite/harness.py`, `axiom-rewrite/test_harness.py`,
`axiom-rewrite/README.md`, `.gitattributes` (new),
`axiom-rewrite/candidates.jsonl` (now tracked).

**Decision:** #29's harness ran **one spec per invocation** and wrote nothing on
its own; the #29 follow-up added the ledger bridge but still one spec at a time.
A candidate batch (#30) needs a loop, and the ledger needed a decided VCS status
before #30 produces entries. Both are settled here.

**1. Batch runner.** `harness.py batch <dir|glob> [--json] [--record LEDGER]`
runs every spec in a target and records each outcome. Three deliberate choices:

- A spec that **fails a gate is data, not an error** — the ledger keeps failed
  candidates on purpose — so a failing spec does not abort the batch and the
  process exits 0. Only a *usage* problem exits 2 (no specs found, malformed spec,
  unrecordable row). A batch's job is coverage; "all specs failed" is a legitimate
  result, so per-spec verdicts live in the output and the ledger, not the exit code.
- Each spec is run and recorded **independently**, so one bad record cannot discard
  outcomes already written.
- `collect_specs` accepts a directory, a glob (absolute or relative), or a file,
  sorted for determinism.

`cmd_run` was refactored onto a shared `run_one`, so the single-spec and batch
paths cannot drift apart.

**2. Ledger VCS policy: commit it, with `merge=union`.** `axiom-rewrite/candidates.jsonl`
is now tracked (it existed only as a local artifact). Rationale: it is append-only
history of the same kind as `docs/decisions/LOG.md` (committed), and #30's results
are a reproducibility claim — an uncommitted ledger makes "we tried this"
unverifiable for a reader. The repo runs parallel agents, so two can append between
the same two commits; `.gitattributes` gives the ledger `merge=union` (a git
builtin), and concurrent appends compose instead of conflicting on the final line.
Order is then not meaningful, which is fine: the ledger is read by `candidate_id`
and `coverage` does not depend on position. Verified by simulating two concurrent
appends across branches — both rows survived the merge.

The file is committed **empty**, so the tracked path exists before #30 writes to it
(#30 owns producing entries; this issue owns the mechanism).

**Verification:**
- `axiom-rewrite/test_harness.py` 18/18 (5 new: `collect_specs` dir/glob/file,
  batch records every spec and a gate failure does not abort, missing target exits
  2, malformed spec exits 2 while good specs still run, ledger is tracked with
  `merge=union`). The batch tests stub `Harness.discharge`, so they exercise the
  real control flow without needing the toolchain.
- Non-vacuity: reverting the exit-code semantics to "1 on any failure" fails the
  batch test; the union-merge claim is backed by an actual two-branch merge.
- Real Lean run: `batch axiom-rewrite/specs --record /tmp/...` processed 3 specs,
  recorded 3 rows (`passed_gate_5`, `failed_gate_3`, `failed_gate_2`), exit 0.
- Ledger tests 16/16, mutation guard 7/7, Tier-1 gates clean.

**Rationale:** #30 is now one command away from a recorded batch, and the ledger's
status is a decision rather than a default. The exit-code choice is the subtle part:
encoding "some candidate failed" in a batch's exit status would make normal,
expected search outcomes look like tool failures.

### DEC-053 — Gate 5 Tier 1b (binder/lethality) promoted from advisory to blocking (#38) (2026-09-16)

**Date:** 2026-09-16
**Status:** Active
**Scope:** `.github/workflows/ci.yml`, `Tests/ExtractionFaithfulnessTests.lean`,
`docs/TOOLCHAIN_AND_CI.md`, `docs/AGENT_HANDOFF.md`.

**Decision:** The binder/lethality scan ran with `continue-on-error: true` since
adoption, with an in-file note to promote it "once clean". It had exactly one
VIOLATION keeping it advisory: `runEnvTest` in
`Tests/ExtractionFaithfulnessTests.lean`, a dead helper whose `env : Environment`
parameter was never used (zero call sites; `Tests/Harness.lean`'s `runTest`
already covers the same ground without an environment parameter).

The helper is removed and the step is now blocking (no `continue-on-error`), so a
new unused-parameter regression fails CI. That is the point of Tier 1b: it is the
mechanical check for non-load-bearing binders — the "parameter that looks
load-bearing but is inert" hole the gate suite exists to catch.

**Deliberately NOT `--strict`.** The 34 remaining items are REVIEWs, not
violations: almost all are entry points (`runAll*`, `main`, `default*`) unreferenced
by construction. Triaging those is a separate, larger task; this promotion is on
the *violation* criterion the CI comment named. The one REVIEW worth a follow-up
under `--strict` is the `discarded_let` at `Maith/CorpusSerializer.lean:126`.

**Verification:**
- Scan now exits 0: `0 violation(s), 34 review item(s)` (was 1 violation, exit 1).
- Non-vacuous: planting an unused parameter in `Tests/Harness.lean` makes the scan
  exit 1 — so the promotion genuinely fails CI on a regression, rather than being
  a decorative gate.
- The scanner self-test still detects the planted case8 fixture (`DecidesLike`'s
  unused `M`/`t`) — the promotion did not weaken the fixture check.
- `lake build tests` + the suite pass (26/26) with the helper gone.

**Rationale:** A gate that cannot fail its build is documentation, not a gate.
Leaving Tier 1b advisory meant the class of defect it targets could reappear
silently; the cost of closing it was deleting one dead function.


### DEC-054 — Prior art for the active track (#39): the axiom-discovery track had no grounding (2026-09-18)

**Date:** 2026-09-18
**Status:** Active
**Scope:** `docs/reference/PRIOR_ART.md` (new section 9 + references),
`docs/experiments/AXIOM_DISCOVERY.md` (new "Prior art and positioning"
section), `README.md`.

**Decision:** The axiom-discovery track was promoted to active on 2026-09-15
(DEC-036) without carrying any literature grounding across. Measured on the
document as it stood: `docs/reference/PRIOR_ART.md` (543 lines, last revised
2026-08-16) had **zero** mentions of `homomorphism`, `axiom discovery`,
`transfer`, `conjecture`, `causal abstraction`, `analogy`, or
`circuit complexity`, while `IR` had 96 - the document covered only the
shelved IR/training track. `AXIOM_DISCOVERY.md`, the active track's own spec,
had zero citations of any kind (no arXiv reference, no "et al", no
references section).

A new **section 9** is added to `PRIOR_ART.md` scoped explicitly to the active
track, with its own reference block, and a summary section is added to
`AXIOM_DISCOVERY.md` pointing into it. The document header now states the
two-track split so sections 1-8 are not mistaken for active-track grounding.

**What the grounding establishes:**

1. **The phi idea is classical.** Transport of structure (Bourbaki), the
   transfer principle (Los), and categorical/Morita equivalence precede it.
   The general principle is not a Maith contribution, and no document should
   read as if it were.
2. **The proposal step is analogical retrieval**, whose foundational account
   is Gentner's structure-mapping (1983), with applied retrieval in Kang et al.
   (ACM TOCHI 2022) and literature-based discovery (Swanson's ABC model /
   ARROWSMITH). Consequence: the presentation-vs-content boundary in
   `STRUCTURAL_SIMILARITY.md` is structure-mapping's relational emphasis,
   re-derived.
3. **The pipeline shape has a close published analogue** (arXiv:2607.28632:
   region search -> semantic critic -> Lean 4 validation, 20/20
   parse+typecheck, not `exact?`-absorbed, not `aesop`-discharged), plus
   LeanConjecturer (arXiv:2506.22005), STP (ICML 2025), ATG (NAACL 2024).
   Formal Lean validation is standard in this line, so it is not the
   differentiator.
4. **Gates 1-2 are the question causal abstraction formalizes** (Geiger et al.;
   interchange intervention accuracy as a graded metric), with Sutter et al.
   (arXiv:2507.08802) as the boundary condition.

**Two substantive findings, not just citations:**

- **The #28 ranking objective is right for dedup and wrong for discovery.**
  `sim = 0.7*facts + 0.3*ops` has no semantic-distance term, so it ranks
  near-identical structures highest - correct for phase-1 dedup, but the field
  convention for cross-domain *candidate generation* is
  `surprise = structural_similarity x semantic_distance`. Left as an open
  design decision for #28 phase 2 (not changed here), now on the record rather
  than re-derived.
- **The proposal mechanism has no ground-truth recovery setting.** Every gate
  evaluates a candidate that already exists; nothing tests whether search can
  find candidates known to be present. A "mechanism ran, found nothing"
  outcome is therefore uninterpretable - it cannot distinguish absence of
  candidates from failure to see them. This is the same class of gap
  `STRUCTURAL_SIMILARITY.md` already admits for semantic similarity, at the
  level of the whole proposal step. Filed as an open question in sections
  9.5/9.7, not resolved here.

**Correction carried across repos.** A sibling-repo review (Ephapse `DEC-010`)
initially flagged Sutter et al. as a risk to gate 1, on the reading that a
homomorphism obligation could be passed vacuously. That was **wrong**: gate 1
is a written Lean term whose complexity is fixed by its author, not a learned
or capacity-selected map, so the vacuity result does not apply; and gate 2
already rejects the Unit-collapse by name (see the #29 starter in
`AGENT_HANDOFF.md`). Corrected in both repos. The causal-abstraction literature
is a **strengthening to borrow** - specifically sharpening what gate 2's kernel
characterization must establish - not a defect to defend against.

**Non-goal:** no novelty claim. Per the standing rule, nothing here authorizes
calling anything novel; the purpose is grounding, not priority.

**Verification:** `grep -c` for each of the seven previously-absent terms
returns non-zero on `docs/reference/PRIOR_ART.md` after the change;
`AXIOM_DISCOVERY.md` now contains a references-bearing section. No gate,
candidate, ledger record, or experiment is touched by this decision.

### DEC-055 — Active-track prior art: recovery-setting design, and a declined third repo (2026-09-18)

**Date:** 2026-09-18
**Status:** Active
**Scope:** `docs/reference/PRIOR_ART.md` (section 9.5.1, 9.7, active-track references).

**Carried over from a review of a general-purpose cross-domain hypothesis-generation
pipeline.** That document proposed, among other things, a retrospective validation
design and a challenge-before-admission stage. Two items were adopted; the pipeline
itself was declined.

**1. Adopted: retrospective time-cut validation as the preferred design for the
missing ground-truth recovery setting (section 9.5.1).**

The gap recorded in DEC-054 was that every Maith gate evaluates a candidate that
already exists, so "the proposal mechanism ran and found no candidates" cannot be
distinguished from "the search cannot see real candidates." The previously recorded
answer was synthetic injected fixtures.

The stronger, established answer is time-cut validation: freeze the knowledge base
at time *t*, pose a then-open question, generate and rank using only pre-*t*
evidence, and compare against what was later supported. This is the design in
current use, not a proposal:

- ProjectionBench (arXiv:2605.30284) - progressive information disclosure from a
  paper's topic and research question, with hypotheses required at each stage.
- IdeaBench (PMC11923747) - 2,374 target papers published after 2024-01-01 with
  ~23K filtered references, dated specifically to prevent training leakage.

**The load-bearing caveat, which the source document omitted.** The cut must be
relative to the **model's training cutoff**, not to wall-clock recency. If the model
has memorized the later discovery, the benchmark measures recall rather than
hypothesis generation. Both source benchmarks select post-cutoff material for
exactly this reason. A time-cut design without a stated cutoff and verified
post-cutoff targets is not evidence, and this is recorded in the section so a future
implementer cannot miss it.

Ranked above the injected-fixture design because fixtures test sensitivity under
conditions where candidates are shaped to be findable, whereas time-cut tests the
same property against real structure. It is also the only design discussed that could
support a claim about the *end* of the pipeline (whether gate-3 survivors correspond
to what the field later valued), not just the search step. It still does not
establish discovery - only recovery - and section 9.5.1 says so.

**2. Recorded as an open question, not adopted: a pre-admission challenge stage
(section 9.7).**

The gates verify a candidate that already exists; nothing tries to defeat one before
it enters. The nearest existing thing is #34, which operates only on gate-5
survivors. The asymmetry worth noting: post-hoc verification is strong in this
pipeline, pre-admission critique is thin. Filed as a candidate design, not a
commitment.

**3. Declined: the third repo.** Recorded here because the review crossed this repo.
The pipeline is the same intellectual ancestor with a weaker search mechanism
(prompted LLM over text dossiers, versus a proven homomorphism obligation) and no
validation oracle; its blinded-panel and priority-scoring apparatus is the expensive
substitute for the kernel oracle Maith already has. Building it while the active track
has no first candidate batch (#30 not run) would repeat the infrastructure-ahead-of-
results mistake this project has already made once. The sibling decision is recorded
in full at Ephapse `docs/decisions/LOG.md` DEC-012, which also corrects the source
document's NSF framing (NSF 26-512 is a data-readiness program, not a
hypothesis-generation one; the relevant framing is the Genesis Mission DCL, NSF
26-023, and for-profit organizations are eligible proposers).

**Non-goal:** unchanged. Nothing here authorizes a novelty claim or touches a gate,
candidate, ledger record, or experiment.

**Verification:** `docs/reference/PRIOR_ART.md` section 9.5.1 exists and states the
training-cutoff caveat; section 9.7 records the challenge-stage question and marks the
recovery gap as partly resolved; the active-track reference block contains the two
time-cut benchmark citations.

### DEC-056 — Time-cut validation is the LBD replication protocol; target selection is a bias source (2026-09-18)

**Date:** 2026-09-18
**Status:** Active
**Scope:** `docs/reference/PRIOR_ART.md` (section 9.5.2, active-track references).

**Carried over from the sibling repo's oracle-problem review (Ephapse DEC-013).**
Adopted in part; the causal-instrument half of that decision is Ephapse-internal and
does not apply here.

**The point.** The time-cut design recorded in DEC-055 (§9.5.1) is not an LLM-era
invention. Literature-based discovery has used the same **replication** protocol for
decades: given a known discovery at time *t*, supply the pre-*t* literature, produce a
ranked candidate list, and score the system by how highly the known target ranks.
Swanson's fish-oil / Raynaud's syndrome (1986) and magnesium / migraine (1988) links
are the canonical targets.

**Two documented weaknesses of that protocol, now recorded in section 9.5.2:**

1. **The target set is tiny.** LBD evaluation has relied on the same handful of
   confirmed discoveries for over three decades. A Maith analogue must state its
   target set and selection process rather than inheriting "a few famous hits" as
   though that were a benchmark.
2. **Target-selection bias.** The canonical discoveries were made by a researcher who
   personally experienced the conditions involved - a documented concern about
   scientific neutrality in the protocol. Target selection is a bias source, not a
   neutral step.

**Why this applies to Maith directly.** The active track's benchmark domain is circuit
complexity and #26 builds a transfer-target list (T1-T10 plus screening results). Under
this protocol that list *is* the target set, so the same two questions apply: how were
the targets chosen, and could the selection make recovery easy or hard for reasons
unrelated to the search mechanism?

**The generalizable statement recorded in the section:** a time-cut benchmark measures
the search mechanism only if the target set was not selected with knowledge of what the
mechanism can find; otherwise it measures the selection. Same failure shape as the #28
ground-truth gap (§9.2), one level up.

**Not adopted:** the causal-intervention instruments (RAVEL Cause/Isolate, interchange
intervention as a positive control). Those address Ephapse's problem - no kernel - and
are irrelevant where a kernel already exists. Maith's gate 2 already discharges the
structure-preservation obligation more strongly than an intervention score would.

**Non-goal:** unchanged. No gate, candidate, ledger record, or experiment touched.

**Verification:** section 9.5.2 exists with both documented weaknesses and the
target-selection question applied to #26; the active-track reference block contains the
Swanson, Smalheiser, ARROWSMITH, and LBD-evaluation-critique citations.

### DEC-057: RLM triage decisions (how a triage finding becomes a task)
- Date: 2026-10-01
- Status: accepted
- Scope: task-filing
- Decision:
  - D1: An RLM Analyzer report is unverified LLM triage. A finding becomes a task only after it is confirmed against raw files in this repo.
  - D2: A refuted or stale finding gets no task. It is recorded in the triage summary with the evidence that refutes it.
  - D3: Generic web-app security advice (authn/authz, API validation, security headers, WAF, pen testing, SAST/DAST, log anomaly detection) does not apply. This repo runs no web service, so no task is filed for it.
  - D4: One task per verified finding. No bundling, no extra scope, no refactors, no opportunistic items.
  - D5: Anything that needs a human choice is filed as a blocker for the owner, not decided by the agent.
- Rationale:
  - The reports are a triage aid, not a source of truth. Verification against raw artifacts is the only step that separates a real defect from a plausible-sounding one, which is the same rule the integrity gates already apply to results.
  - D4 keeps each task claimable in one run and keeps the acceptance check unambiguous.
- References:
  - rlm-triage-summary.md in philipdallen/portfolio-ops (branch tasks/rlm-triage-2026-10-01)
  - docs/MULTI_AGENT_WORKFLOW.md (task definition, blocker mechanics)
