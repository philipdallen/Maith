# Probing Task Proposal: Does Variant A Learn Semantic IR Content?

**Author:** OpenHands Agent (via `kit/dev` branch)  
**Date:** 2026-08-04  
**Based on:** PROBING_TASK_GUIDE.md, DEC-024, DECISION_LOG.md, corpus analysis  
**Reviewed by:** Kit — inline comments added 2026-08-04

---

## Executive Summary

DEC-024 established that semantic content in Variant A's IR adds ~0.27 bits/token of prediction difficulty that is not recovered at 365M params / 3.5k examples. However, perplexity alone cannot distinguish two explanations:

1. **Data-scale hypothesis:** More data (10k+ examples) would allow the model to learn the semantic tokens.
2. **Format-hypothesis hypothesis:** The IR format is inherently poorly suited to next-token prediction regardless of data volume.

A **linear probing task** can distinguish these: if the model's internal representations encode module membership, arity patterns, or declaration structure, then the semantic content IS being learned — just not captured by perplexity. If probing accuracy is near-random, the semantic content is noise.

> **[KIT]** The executive summary is clear and correctly frames the ambiguity. One gap: it conflates two different claims — "semantic content IS being learned" and "semantic content IS encoded in representations." These are not the same. The model could encode module identity by learning module-exclusive gen: token signatures without understanding what those tokens mean mathematically. The claim "semantic content is being learned" is too strong for what the probe actually tests. Suggest softening to "the model's representations encode information correlated with module membership" — which is what the probe actually measures.

---

## Step 1 — Understand the Question

### What DEC-024 Left Open

**Ambiguity:** Whether the 0.27 bits/token gap between A and Flat-IR represents:
- (a) learnable semantic content that just needs more data, or
- (b) irreducible format mismatch regardless of scale.

### Probing Task Interpretations

| Result | Meaning |
|--------|---------|
| **A >> Flat-IR** (probing) | Semantic IR content IS encoded in representations. The perplexity gap is a training-dynamics problem (needs more data or pretraining), not a representation problem. |
| **A ≈ Flat-IR** (probing) | Representations do not encode semantic content. The perplexity gap is real signal that the format is not being learned. Recommend: simplify IR format or pursue IR pretraining. |

> **[KIT]** The interpretation table is clean but the "A >> Flat-IR → needs more data" conclusion is an overreach. The probe only shows that representations differ between A and Flat-IR — it does not prove that training-dynamics (data volume) is the cause. A could have richer representations than Flat-IR without that richness translating to better perplexity at any data volume. The correct conclusion for "A >> Flat-IR" is: semantic content is encoded in representations, so the model is not ignoring it entirely — the bottleneck may be data volume OR the training objective OR both. Do not present this as definitively ruling out the format-mismatch hypothesis.

### Why Probing Is Cheaper

| Alternative | Cost | Probing |
|-------------|------|---------|
| IR pretraining | 50k-100k declarations, weeks of GPU time | Single forward pass extraction, linear classifier training |
| Corpus expansion | Months of extraction, validation, rerun | Same corpus, no new data needed |

> **[KIT]** "Months of extraction" overstates corpus expansion cost. The current 14-module corpus took hours to extract, not months. This table is making probing look more decisive than it is relative to alternatives. The honest framing: probing is cheaper AND faster to run, but its conclusions are narrower. It answers "are representations different?" not "would more data help?"

---

## Step 2 — Checkpoint Audit

### Available Artifacts

| Artifact | Location | Status |
|----------|----------|--------|
| Embedding projection (v1.4.0) | `datasets/embed_proj_A_v140.pt` | ✅ 4.4 MB |
| Embedding projection (v1.3.0) | `datasets/embed_proj_A_v130.pt` | ✅ 29.5 MB |
| Embedding projection (phase6) | `datasets/embed_proj_A.pt` | ✅ 29.2 MB |
| Flat-IR embeddings | `datasets_flat/embed_proj_flat.pt` | ✅ 41.1 MB |
| Trained model checkpoints | `runs/*/checkpoint-final/` | ❌ Not present in repo |

### Checkpoint Gap

The repo contains embedding projection weights but **no trained model checkpoints** (`runs/*/checkpoint-final/`). The DEC-024 results reference runs that were executed on a separate machine.

> **[KIT — CRITICAL]** This finding is **incorrect**. The trained checkpoints ARE present on disk — they are gitignored (runs/ is in .gitignore) but they exist locally. OpenHands would have seen this if it had checked the filesystem rather than the git index. The three checkpoints needed for this experiment have been verified to exist:
> - `runs/variant_A_v1_4_0/checkpoint-final/model.safetensors` ✅
> - `runs/variant_C_phase6/checkpoint-final/model.safetensors` ✅
> - `runs/variant_flat/checkpoint-final/model.safetensors` ✅
> - Pretrained Qwen2.5-Coder-0.5B is in `~/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-0.5B` ✅
>
> The "Required: Either re-run training or obtain checkpoints from another machine" block below this is therefore **not required**. This is the most significant error in the proposal — it would cause unnecessary re-training if followed literally.

**Required:** Either:
1. Access to the trained checkpoints from the previous experiment runs, OR
2. Re-run training for 4 variants (A v1.4.0, A v1.4.0 continued, C Phase 6, Flat-IR)

> **[KIT]** Remove this block entirely. See note above — checkpoints are present locally, just gitignored.

### Model Configuration (Qwen2.5-Coder-0.5B)

| Parameter | Value |
|-----------|-------|
| Hidden size | 896 |
| Vocab size (base) | 151,643 |
| Num hidden layers | 24 |
| Intermediate size | 4,864 |
| Total parameters | ~494M |

For Variant A v1.4.0: vocab resized to 1,236 tokens with embedding projection.

> **[KIT]** The ~494M parameter count is for the base Qwen model with full BPE vocabulary. Variant A v1.4.0 has a resized embedding table (1,236 tokens) giving ~359M params — confirmed in `runs/variant_A_v1_4_0/results.json` (n_params_M: 359.0). This matters for the random baseline comparison: if you load pretrained Qwen (494M) as the "random baseline," its embedding table is a different size than Variant A. The hidden states are all 896-dim regardless, so the probe still works — but the parameter count difference should be noted.

---

## Step 3 — Corpus Labels Audit

### Corpus Statistics

| Metric | Value |
|--------|-------|
| Total examples | 4,029 |
| Train split | 3,491 |
| Eval split | 388 |
| Modules | 14 |

### Module Distribution

| Module | Count | % of Corpus |
|--------|-------|-------------|
| Mathlib.Algebra.Group.Defs | 1,129 | 28.0% |
| Mathlib.Algebra.Group.Basic | 548 | 13.6% |
| Mathlib.Order.Lattice | 519 | 12.9% |
| Mathlib.Algebra.Ring.Defs | 446 | 11.1% |
| Mathlib.Order.Basic | 431 | 10.7% |
| Mathlib.Algebra.Group.Subgroup.Basic | 393 | 9.8% |
| Mathlib.Order.LatticeIntervals | 256 | 6.4% |
| Mathlib.Algebra.Ring.GeomSum | 70 | 1.7% |
| Mathlib.Topology.Basic | 69 | 1.7% |
| Mathlib.Algebra.Ring.Basic | 68 | 1.7% |
| Mathlib.Algebra.Group.NatPowAssoc | 28 | 0.7% |
| Mathlib.Data.Nat.Basic | 27 | 0.7% |
| Mathlib.Algebra.Module.Basic | 23 | 0.6% |
| Mathlib.Data.Int.Basic | 22 | 0.5% |

> **[KIT]** The four smallest classes (22–28 examples) are too small for reliable per-class evaluation in a stratified split. With 20% held out, Data.Int.Basic contributes ~4 eval examples — a single misclassification swings accuracy by 25%. The proposal should specify merging these into an `Other` class or excluding them, rather than running 14-class classification and accepting unreliable per-class metrics for the small classes.

### Available Label Fields

| Field | Type | Available as Probe Target? |
|-------|------|---------------------------|
| `module` | string (14 values) | ✅ Yes — primary task |
| `tokens` | list of strings | ✅ Yes — extract sequence |
| `graph.entities` | list | ✅ Yes — count, kinds |
| `graph.operations` | list | ✅ Yes — arity extraction |
| `leanExpr` | string | ⚠️ Partial — can extract arity |
| `graph.attributes` | list | ⚠️ Yes — typeclass presence |

> **[KIT]** The `leanExpr` field is raw Lean elaborated expression text. Using it as a probe target label source is fine, but it should not be used as a model input — the probe receives the IR token sequence, not the Lean text. This table mixes "available as label source" with "available as input" in a potentially confusing way. The only input to the probe is the mean-pooled hidden state from the IR token sequence.

---

## Step 4 — Semantic Content Characterisation

### Gen: Token Statistics

| Metric | Value |
|--------|-------|
| Unique gen: tokens | 1,999 |
| Total gen: occurrences | 88,839 |
| Occurrences per unique token | 44.4 (median ~15) |
| Tokens appearing only once | ~30% |
| Tokens shared across 2+ modules | 376 (18.8%) |

> **[KIT — DISCREPANCY]** The "tokens shared across 2+ modules" figure here is 376 (18.8%), but the actual count computed from the corpus is **310 (15.5%)**. Similarly "tokens appearing only once" is stated as ~30% but the actual figure is 569/1,999 = **28.5%**. These are small differences but the proposal should use the exact numbers. The discrepancy in cross-module sharing (18.8% vs 15.5%) may affect the confound risk assessment in Step 8.

### Top 15 Most Frequent Gen: Tokens

| Token | Count | Modules |
|-------|-------|---------|
| gen:hof | 6,073 | All |
| gen:OfNat.ofNat | 4,711 | All |
| gen:instOfNatNat | 2,009 | All |
| gen:instHPow | 1,702 | All |
| gen:HPow.hPow | 1,702 | All |
| gen:AddMonoid.toAddZeroClass | 1,656 | Group.Defs |
| gen:Monoid.toMulOneClass | 1,512 | Group.Defs |
| gen:Zero.toOfNat0 | 1,483 | All |
| gen:DivInvMonoid.toMonoid | 1,423 | Group.Defs |
| gen:AddZeroClass.toAddZero | 1,407 | Group.Defs |
| gen:SubNegMonoid.toAddMonoid | 1,395 | Group.Defs |
| gen:MulOneClass.toMulOne | 1,332 | Group.Defs |
| gen:Group.toDivInvMonoid | 1,306 | Group.Defs |
| gen:AddGroup.toSubNegMonoid | 1,276 | Group.Defs |
| gen:Monoid.toPow | 1,256 | Group.Defs |

> **[KIT]** The "Modules" column labels gen:AddMonoid.toAddZeroClass and similar as "Group.Defs" but these tokens appear in multiple modules — verified cross-module sharing shows 3 modules for gen:AddMonoid.toAddZeroClass. Labelling them as a single module is misleading. Suggest replacing the "All" / single-module labels with actual module counts (e.g. "3 modules", "4 modules") as was done in Kit_Proposal.md.

### Token Type Distribution

| Category | Tokens | % of Corpus |
|----------|--------|-------------|
| Structural (E, A, R, O, IN_N, OUT_N, etc.) | 711,156 | 72.2% |
| Semantic (gen:) | 88,839 | 9.0% |
| Other (identifiers, literals) | 185,019 | 18.8% |
| **Total** | **985,014** | 100% |

> **[KIT]** The "Other (identifiers, literals)" category is unexplained. In the v1.4.0 corpus, tokens are either structural (E, A, R, O, IN_N, OUT_N, FVAR_N, BVAR_N, TERM_N, GRAPH_BEGIN/END, rel ops, attr keys) or semantic (gen:). There is no separate "identifiers, literals" category in the v1.4.0 format — FVAR_N/BVAR_N/TERM_N are structural positional references, not identifiers. The 18.8% "Other" category needs to be defined or this table is misleading. Verified total corpus tokens = 985,014 which matches stats.json, but the 72.2% / 9.0% / 18.8% split requires clarification of what falls in "Other."

---

## Step 5 — Task Feasibility Assessment

### Module Classification

| Metric | Value |
|--------|-------|
| Classes | 14 |
| Largest class (Group.Defs) | 1,129 examples |
| Smallest class (Data.Int.Basic) | 22 examples |
| Random baseline accuracy | 1/14 = **7.14%** |
| Class imbalance ratio | 51:1 (1,129 : 22) |

**Feasibility:** Linear probe on top of pretrained representations should achieve **30-70% accuracy** depending on how much module structure is encoded. Near-random (7%) would indicate no encoding. Above 50% would indicate meaningful semantic encoding.

> **[KIT]** The "30-70% accuracy" prediction is stated without justification. This is presented as a prior but there is no basis given for why 30-70% is the expected range. It should either be justified (e.g. "based on cross-module gen: token exclusivity of 84.5%") or removed. More importantly: the thresholds in Step 7 (A ≥ 40% for "A >> Flat-IR") should be consistent with this feasibility statement — if 30-70% is the expected range, then 40% as a threshold for "meaningful" sits in the lower end of the expected range, which is a low bar.

### Token Length Distribution

| Metric | Value |
|--------|-------|
| Min tokens | 10 |
| Max tokens | 12,188 |
| Mean tokens | 244.5 |
| Median tokens | 122.0 |
| P90 tokens | 454.0 |
| Examples ≤ 512 tokens | 3,699 (91.8%) |

### Arity Binning Alternative

If module classification is too imbalanced, arity binning provides a more balanced task:
- Arity-1 (unary ops): ~30% of operations
- Arity-2 (binary ops): ~50% of operations
- Arity-3+ (ternary+ ops): ~20% of operations

> **[KIT]** The arity binning described here ("unary/binary/ternary") refers to individual operation arity, not sequence-level operation count bins. This is a different task from what Kit_Proposal.md defines as the secondary task (binning total O-row count per sequence into 0-5, 6-15, 16-40, 40+). Clarify which arity property is being binned. The per-operation arity task is harder to implement (requires parsing individual operation inputs) and the class distribution figures given (~30%/50%/20%) are estimates without a source. Actual O-row count distribution from the corpus: 0-5 (28.2%), 6-15 (35.9%), 16-40 (23.9%), 40+ (12.0%) — four roughly balanced classes that are easier to derive.

---

## Step 6 — Probe Architecture Constraints

### Hidden Dimensions

| Checkpoint | Hidden Size | Notes |
|------------|-------------|-------|
| Qwen2.5-Coder-0.5B base | 896 | All variants same base |
| Variant A v1.4.0 | 896 | After embedding projection |
| Variant C Phase 6 | 896 | Native BPE |
| Flat-IR | 896 | After embedding projection |

### Pooling Strategy

**Recommended: Mean pooling over all non-padding tokens**

### Timing Estimate (MPS)

Assumptions:
- Qwen2.5-Coder-0.5B on MPS (Apple Silicon)
- Forward pass: ~500ms per example (batch=1)
- 4,029 examples × 4 variants = 16,116 forward passes
- Total extraction time: ~2.2 hours

> **[KIT — TIMING IS WRONG]** The ~500ms per example estimate is 3x too slow. Measured actual forward pass time on this machine (MPS, seq_len=512, Variant A checkpoint): **0.17 seconds per example**. Total estimated extraction time: 4,029 × 4 × 0.17s ÷ 60 = **~45 minutes**, not 2.2 hours. The overestimate could cause the proposal to be deprioritised on cost grounds when it is actually fast. The 500ms figure may come from CPU inference or a different model size — it should be replaced with the measured value.

### GPU Memory

- Single model in memory: ~2 GB (float32) or ~1 GB (float16)
- Four models simultaneously: ~8 GB (float32) or ~4 GB (float16)
- MPS typically has 16-64 GB available
- **Recommendation:** Load one variant at a time to be safe.

> **[KIT]** Measured MPS memory for Variant A at float32: **1.65 GB**. The ~2 GB estimate is reasonable. However "MPS typically has 16-64 GB available" is misleading — MPS shares unified memory with the CPU. On a 16 GB MacBook, loading one 1.65 GB model leaves the rest for OS and other processes. 16-64 GB implies much more headroom than actually exists on most machines. The load-one-at-a-time recommendation is correct.

---

## Step 7 — Interpretation Criteria

### Thresholds (Defined Before Running)

| Outcome | Definition | Interpretation |
|---------|------------|----------------|
| **A >> Flat-IR** | Module acc: A ≥ 40%, Flat-IR ≤ 15% | Semantic content IS encoded. Gap is a training-dynamics problem. |
| **A ≈ Flat-IR** | Module acc: both within 10% of each other | Semantic content is noise at this scale. |
| **Flat-IR >> A** | Module acc: Flat-IR ≥ 40%, A ≤ 15% | Unexpected. Would indicate structural pattern memorization in A. |
| **C >> A** | Module acc: C ≥ 40%, A ≤ 25% | Qwen pretraining priors are the primary driver, not IR structure. |
| **Random ≈ All** | All accuracies within 5% of 7.14% | Representations encode nothing useful. |

> **[KIT — THRESHOLD DESIGN ISSUE]** The "A >> Flat-IR" threshold (A ≥ 40%, Flat-IR ≤ 15%) requires both conditions simultaneously, but these are defined independently. What if A = 38% and Flat-IR = 14%? Or A = 55% and Flat-IR = 20%? The joint threshold misses cases where there is a meaningful gap but neither condition is individually met. A simpler and more robust definition: "A >> Flat-IR means the gap between A and Flat-IR probe accuracy exceeds Xpp" — where X is set before running. Kit_Proposal.md uses ≥10pp gap as the threshold. That approach is cleaner than requiring both an absolute floor for A and an absolute ceiling for Flat-IR.
>
> Additionally: the "A ≈ Flat-IR → semantic content is noise" interpretation understates certainty. The probe operates on the existing checkpoints trained with a specific objective — if the training objective doesn't encourage semantic encoding, the probe will fail even if the representations could in principle encode semantics. "A ≈ Flat-IR" means the semantic content is not encoded in representations given this training setup, not that it is fundamentally noise.

### Decision Tree Based on Results

| Result | Next Step |
|--------|-----------|
| A >> Flat-IR (module acc: A ≥ 40%, Flat-IR ≤ 15%) | Pursue IR pretraining or corpus expansion. Semantic encoding confirmed. |
| A ≈ Flat-IR (acc difference < 10%) | IR format changes unlikely to help. Simplify IR or pursue pretraining. |
| C >> A (C ≥ 40%, A ≤ 25%) | Qwen priors dominate. IR pretraining is essential. |
| All near random | Representations not useful for this task. Reconsider extraction strategy. |

> **[KIT]** "A ≈ Flat-IR → IR format changes unlikely to help" conflates two things. If A ≈ Flat-IR, it means changing the IR format probably won't help the representations — but it says nothing about whether IR pretraining would help. IR pretraining directly addresses the training objective, not the format. The decision tree should distinguish: (a) format changes (which the probe addresses), (b) training objective changes (which the probe partially addresses), and (c) data volume (which the probe does not address).

### Ambiguous Case

**Case:** A > Flat-IR but both are low (A=25%, Flat-IR=12%)

**Follow-up:** Train probe on arity prediction instead. If A >> Flat-IR on arity, the semantic content encodes operation structure but not module membership.

> **[KIT]** This is a good fallback. Recommend also specifying a gap threshold for the ambiguous case — "A=25%, Flat-IR=12%" is a 13pp gap, which by Kit_Proposal.md's ≥10pp threshold would already count as A >> Flat-IR. The ambiguous zone needs a specific numeric range, not just an example.

---

## Step 8 — Risks and Mitigations

### Risk 1: Degenerate Flat-IR Representations

**Detection:** Check representation variance. If mean > median across all examples, representations are likely collapsed.

> **[KIT]** "If mean > median" is not a valid test for representation degeneracy — mean > median describes a right-skewed distribution of scalar values, but representations are 896-dimensional vectors. The correct check is: compute the standard deviation of the representations across examples (std across the N=4029 dimension), and check whether it is near zero. A value of std < 0.01 would indicate degeneracy. Kit_Proposal.md uses this formulation.

### Risk 2: Module-Exclusive Token Memorization

**Detection:** After training, compute probe weights. If high weights on module-exclusive tokens, this is likely.

> **[KIT]** The probe is a linear classifier over 896-dim hidden states — it doesn't have direct access to token-level weights. "Compute probe weights" describes something that doesn't quite work this way. The weight matrix is 896×11 (hidden_dim × num_classes), not token_vocab×11. You cannot directly read off which tokens drove the decision from the probe weights. The correct detection method: run the probe on a filtered version of the corpus where module-exclusive gen: tokens have been replaced with GEN_UNK, and check whether accuracy drops significantly. If it does, the probe was exploiting module-exclusive tokens.

### Risk 3: Label Leakage (Duplicate Declarations)

**Detection:** Count duplicate declaration names across modules.

**Mitigation:** Filter training examples to unique declaration names before probing.

> **[KIT]** Verified: zero duplicate declaration names across modules (confirmed from corpus). No filtering needed. This risk can be closed.

### Risk 4: MPS Non-Determinism

**Mitigation:** Set `torch.manual_seed(42)` before extraction.

> **[KIT]** MPS non-determinism also requires `torch.mps.manual_seed(42)` in addition to `torch.manual_seed(42)` — the latter sets the CPU seed but MPS has its own RNG. Both should be set for reproducibility.

---

## Implementation Checklist

### Phase 1: Representation Extraction

- [ ] 1.1 Obtain trained checkpoints (A v1.4.0, C Phase 6, Flat-IR, B Phase 6) or re-run training

> **[KIT — CRITICAL]** See Step 2 critique — checkpoints are present locally in `runs/`. This step is not needed. Remove "or re-run training." Also: B Phase 6 is not needed for the probing task as designed — the decisive comparison is A vs Flat-IR, with C as the hypothesis comparison. Including B adds a fourth variant with marginal value. If included, document why.

- [ ] 1.2 Implement representation extraction script (`python/extract_representations.py`)
  - Load each checkpoint
  - Set seed: `torch.manual_seed(42)`
  - For each example: forward pass, mean-pool hidden states
  - Save: `{example_name: {checkpoint_name: hidden_vector}}`

> **[KIT]** The save format `{example_name: {checkpoint_name: hidden_vector}}` is JSON-shaped but 896-dim float vectors do not belong in JSON — they should be saved as tensors in `.pt` files (one per variant), with a separate labels.json for the metadata (planned output). Saving as nested JSON would be extremely slow and memory-inefficient at 4,029 × 4 × 896 floats.

- [ ] 1.3 Verify extraction determinism (run twice, compare hashes)
- [ ] 1.4 Check representation variance (sanity check)
- [ ] 1.5 Extract representations for all 4,029 examples × 4 variants

### Phase 2: Probe Training

- [ ] 2.1 Split corpus: 80% train, 20% eval (module-stratified)
- [ ] 2.2 Train linear probe on module classification
  - Optimizer: AdamW, lr=1e-3
  - Epochs: 100 (early stopping on eval loss)
  - Regularization: weight decay=1e-4

> **[KIT]** Adding weight_decay=1e-4 is reasonable regularisation. However early stopping on eval loss adds complexity and may terminate the probe before it converges on minority classes. With 100 epochs and a small linear model, early stopping is unnecessary — 100 epochs will converge without overfitting. Keep it simple: fixed 100 epochs, report final eval accuracy.

- [ ] 2.3 Train linear probe on arity classification (secondary task)
- [ ] 2.4 Compute accuracy for each (checkpoint, task) pair
- [ ] 2.5 Compute probe weight analysis (sanity check for memorization)

> **[KIT]** See Risk 2 critique — "probe weight analysis" doesn't directly reveal token-level memorization in a 896×11 linear layer. Replace with the filtering approach described in Step 8.

### Phase 3: Analysis and Reporting

- [ ] 3.1 Fill interpretation table with results
- [ ] 3.2 Write findings summary
- [ ] 3.3 Update DECISION_LOG.md with results
- [ ] 3.4 If A >> Flat-IR: draft IR pretraining proposal
- [ ] 3.5 If A ≈ Flat-IR: draft IR simplification proposal

> **[KIT]** "Draft IR simplification proposal" for the A ≈ Flat-IR case is premature. If semantic content is not being encoded, the right response is to understand why — is it the training objective? the IR format? the scale? — before proposing simplification. Simplification means removing content; if the content is not being encoded it may still be worth keeping for future use with a better objective. Suggest replacing 3.5 with: "If A ≈ Flat-IR: document findings and propose objective-function experiment before any IR changes."

---

## Appendix: Probe Configuration

```python
# Recommended probe hyperparameters
PROBE_CONFIG = {
    "task": "module_classification",  # or "arity_classification"
    "num_classes": 14,               # modules
    "pooling": "mean",               # mean over sequence
    "optimizer": "AdamW",
    "lr": 1e-3,
    "weight_decay": 1e-4,
    "epochs": 100,
    "patience": 10,                  # early stopping
    "batch_size": 32,
    "seed": 42,
    "train_split": 0.8,
}
```

> **[KIT]** `num_classes: 14` should be 11 if small classes are merged into `Other` as recommended. Also `patience: 10` for early stopping is inconsistent with the recommendation to remove early stopping above — pick one approach and be consistent. Suggest removing `patience` and keeping fixed 100 epochs. Finally: `torch.mps.manual_seed(42)` should be set alongside `seed: 42` during extraction (see Risk 4 note).

---

## References

- DEC-024: Flat-IR ablation results
- PHASE_7_ROADMAP.md: Item 4 (IR pretraining) and decision tree
- PROBING_TASK_GUIDE.md: This proposal's methodology source
- docs/scratch/AUDIT_2026_08_04.md: Verified experimental results

---

## Summary of Kit's Concerns (Priority Order)

1. **[CRITICAL] Checkpoints are present locally** — Step 2 incorrectly states they are missing. No re-training needed. Fix before acting on this proposal.
2. **[HIGH] Threshold design in Step 7** — joint absolute thresholds (A ≥ 40% AND Flat-IR ≤ 15%) are fragile. Replace with gap-based threshold (≥10pp difference).
3. **[HIGH] Timing estimate** — 2.2 hours should be ~45 minutes based on measured 0.17s/example on this machine.
4. **[MEDIUM] Small class handling** — 14-class setup with 22-example classes will produce unreliable per-class metrics. Merge bottom 4 into `Other` for 11 classes.
5. **[MEDIUM] Cross-module gen: sharing discrepancy** — 18.8% stated vs 15.5% measured. Use verified figures.
6. **[MEDIUM] Risk 1 degeneracy detection** — "mean > median" is not a valid test for 896-dim vector degeneracy. Use std < 0.01 threshold instead.
7. **[MEDIUM] Risk 2 memorization detection** — probe weight inspection does not work for 896-dim hidden states. Use GEN_UNK filtering approach instead.
8. **[LOW] Save format** — nested JSON for 896-dim vectors will be slow. Use `.pt` tensors.
9. **[LOW] MPS seed** — add `torch.mps.manual_seed(42)` alongside `torch.manual_seed(42)`.
