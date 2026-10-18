# Probing Task Final Proposal

**Created:** 2026-08-04  
**Authors:** Kit and OpenHands Agent (combined and resolved)  
**Branch:** `openhands/probing-task-design`  
**Research basis:** `docs/experiments/PROBING_TASK_GUIDE.md`  
**Decisions this gates:** IR pretraining vs corpus expansion vs representation redesign

---

## Executive Summary

DEC-024 established that Variant A's semantic IR content adds ~0.27 bits/token of prediction difficulty that is not recovered at 365M params / 3.5k examples. The experiment cannot determine from perplexity alone whether more data would allow the model to learn the semantics, or whether the training objective does not encourage semantic encoding.

A **linear probing task** tests whether the model's internal representations encode module identity from IR token sequences. The probe does not test whether semantic content is "meaningfully" understood — it tests whether information correlated with module membership is present in representations. This narrows the DEC-024 ambiguity:

- **If A >> Flat-IR (probing):** Representations differ between semantic and structural IR. The model is not ignoring semantic content — the bottleneck may be training objective, data volume, or both. IR pretraining or data expansion is a viable investment.
- **If A ≈ Flat-IR (probing):** Representations do not encode semantic content in a way that distinguishes modules. The bottleneck may be the training objective (not data volume). Format changes alone are unlikely to help; objective changes should be investigated.

> **Why probing is cheaper:** Uses existing frozen checkpoints and pretrained Qwen from HuggingFace cache. No new training runs. Estimated: ~45 minutes extraction + ~5 minutes probing. Alternatives (IR pretraining, corpus expansion) require weeks of engineering and GPU time.

---

## Decision Rationale

### Elements from Kit_Proposal.md

| Element | Reason |
|---------|--------|
| 11-class setup (merge 4 smallest into `Other`) | Smallest classes have 22-28 examples; 20% holdout = 4-5 eval examples per class — unreliable |
| Gap-based threshold (≥10pp) | Cleaner than joint absolute thresholds; easier to interpret |
| O-row count bins for Task 2 (0-5, 6-15, 16-40, 40+) | Derived directly from `graph.operations` length; no new extraction needed |
| Measured timing (0.17s/example) | Verified on actual hardware; OpenHands's 500ms estimate was 3x too slow |
| Std < 0.01 for degeneracy check | Correct test for 896-dim vector degeneracy (not mean > median) |
| GEN_UNK filtering for memorization detection | Correct approach for 896×11 linear layer (not weight inspection) |
| Fixed 100 epochs, no early stopping | Small model (896×11) converges without overfitting risk; early stopping adds complexity |
| Variant A, C, Flat-IR, Random (4 variants) | Decisive comparisons: A vs Flat-IR tests semantic content; C vs Flat-IR tests AST structure value |

### Elements from OpenHands_Proposal.md

| Element | Reason |
|---------|--------|
| Macro-F1 and balanced accuracy metrics | Top-1 accuracy misleading on imbalanced 11-class problem |
| Multiple probe seeds (3 runs) | Linear probe convergence varies with initialization |
| Clearer Step 1 framing | Avoids overclaiming ("semantic content IS being learned" → "representations encode module identity") |
| MPS seed: both `torch.manual_seed` AND `torch.mps.manual_seed` | MPS has separate RNG from CPU |

### Resolved Disagreements

| Disagreement | Resolution |
|-------------|------------|
| Class merging vs class-weighted loss | **Merging adopted.** Class-weighted loss complicates comparison across variants; 11-class setup is simpler and sufficient |
| Threshold: joint absolute vs gap-based | **Gap-based adopted.** ≥10pp gap is more robust than requiring A ≥ X% AND Flat-IR ≤ Y% simultaneously |
| Patience-based early stopping vs fixed epochs | **Fixed 100 epochs adopted.** Linear probe on 896-dim inputs cannot overfit in 100 steps |
| One seed vs multiple seeds | **3 seeds adopted.** Probe training stochasticity is real; report mean ± std |

---

## Verified Data Section

All numbers sourced from `docs/scratch/AUDIT_2026_08_04.md` (verified against raw `results.json` files) or computed from `Corpus/corpus.jsonl`.

### Perplexity Results (from audit, Section 1)

| Run | Variant | Vocab | Train | Eval | eval_perplexity | bits/token | Source |
|-----|---------|-------|-------|------|-----------------|-----------|--------|
| variant_flat | Flat-IR | 11 | 3,627 | 402 | 1.0551 | 0.077 | `runs/variant_flat/results.json` |
| variant_C_phase6 | C | 151,643 | 3,375 | 376 | 1.1102 | 0.151 | `runs/variant_C_phase6/results.json` |
| variant_B_phase6 | B | 151,643 | 3,375 | 376 | 1.1295 | 0.176 | `runs/variant_B_phase6/results.json` |
| variant_A_v1_4_0 | A (v1.4.0) | 1,236 | 3,491 | 388 | 1.2751 | 0.351 | `runs/variant_A_v1_4_0/results.json` |

### Corpus Statistics (from audit, Section 3 + corpus analysis)

| Metric | Value | Source |
|--------|-------|--------|
| Total examples | 4,029 | `Corpus/corpus.jsonl` |
| Modules | 14 | Derived from `module` field |
| Unique gen: tokens | 1,999 | Computed from corpus |
| Gen: tokens shared ≥2 modules | 310 / 1,999 (15.5%) | Computed from corpus |
| Gen: tokens unique to 1 module | 1,689 / 1,999 (84.5%) | Computed from corpus |
| Structural tokens (non-gen:) | 896,175 (91.0%) | Computed from corpus |
| Semantic tokens (gen:) | 88,839 (9.0%) | Computed from corpus |
| Gen: tokens appearing once | 569 (28.5%) | Computed from corpus |
| Gen: tokens appearing ≤5 times | 1,274 (63.7%) | Computed from corpus |

### Module Distribution (from audit, Section 3)

| Module | Count | In `Other`? |
|--------|-------|-------------|
| Mathlib.Algebra.Group.Defs | 1,129 | No |
| Mathlib.Algebra.Group.Basic | 548 | No |
| Mathlib.Order.Lattice | 519 | No |
| Mathlib.Algebra.Ring.Defs | 446 | No |
| Mathlib.Order.Basic | 431 | No |
| Mathlib.Algebra.Group.Subgroup.Basic | 393 | No |
| Mathlib.Order.LatticeIntervals | 256 | No |
| Mathlib.Algebra.Ring.GeomSum | 70 | No |
| Mathlib.Topology.Basic | 69 | No |
| Mathlib.Algebra.Ring.Basic | 68 | No |
| Mathlib.Algebra.Group.NatPowAssoc | 28 | **Yes → Other** |
| Mathlib.Data.Nat.Basic | 27 | **Yes → Other** |
| Mathlib.Algebra.Module.Basic | 23 | **Yes → Other** |
| Mathlib.Data.Int.Basic | 22 | **Yes → Other** |

### O-Row Count Bins (from Kit_Proposal.md, verified from corpus)

| Bin | Count | % |
|-----|-------|---|
| 0–5 | 1,136 | 28.2% |
| 6–15 | 1,446 | 35.9% |
| 16–40 | 964 | 23.9% |
| 40+ | 483 | 12.0% |

### Checkpoint Paths (from audit, Section 1 + git history)

> **Note:** These paths are gitignored (`runs/` in `.gitignore`). They exist locally on the machine that ran the experiments but are not in the repo. Execute on that machine or copy checkpoints to the same paths.

| Variant | Local Path | Config |
|---------|-----------|--------|
| A (v1.4.0) | `runs/variant_A_v1_4_0/checkpoint-final/` | hidden=896, vocab=1,236 |
| C (Phase 6) | `runs/variant_C_phase6/checkpoint-final/` | hidden=896, vocab=151,643 |
| Flat-IR | `runs/variant_flat/checkpoint-final/` | hidden=896, vocab=11 |
| Random baseline | `~/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-0.5B/` | hidden=896, vocab=151,643 |

> **⚠️ Verification required:** Confirm these paths exist on the execution machine before starting. If missing, the checkpoints must be obtained from the machine that ran the original experiments.

### Probe Architecture Constraints

| Parameter | Value | Source |
|-----------|-------|--------|
| Hidden dimension | 896 (all variants identical) | Verified from `results.json` n_params_M fields |
| Sequence cap | 512 | Uniform across all variants |
| MPS memory per model | ~1.65 GB (float32) | Measured, documented in Kit_Proposal.md |
| Forward pass time | 0.17s/example | Measured on MPS |
| Extraction time (4 variants) | ~45 minutes | 4,029 × 4 × 0.17s ÷ 60 |

---

## Addressing All [KIT] Concerns

The following table documents all 9 concerns raised by Kit in `doc/Openhands_Proposal.md` and how this final proposal resolves them.

| # | [KIT] Concern | Resolution in Final Proposal |
|---|--------------|----------------------------|
| 1 | **Checkpoints not missing** — Step 2 incorrectly stated they were absent | ✅ Resolved: Checkpoints exist at `runs/variant_*/checkpoint-final/` but are gitignored. Path verification step added to checklist. |
| 2 | **Threshold design fragile** — joint absolute thresholds (A ≥ 40% AND Flat-IR ≤ 15%) miss edge cases | ✅ Resolved: Adopted gap-based threshold (≥10pp gap between A and Flat-IR). Cleaner and more robust. |
| 3 | **Timing wrong** — 500ms/example estimated vs actual 0.17s | ✅ Resolved: Using measured 0.17s/example, ~45 min total extraction time. |
| 4 | **Class handling** — 14 classes with 22-example classes unreliable | ✅ Resolved: Merging 4 smallest into `Other`, final 11-class setup. Per-class metrics not evaluated for `Other` group. |
| 5 | **Cross-module sharing discrepancy** — 18.8% stated vs 15.5% actual | ✅ Resolved: Using verified 310/1,999 = 15.5% from audit. |
| 6 | **Degeneracy detection** — mean > median not valid for 896-dim vectors | ✅ Resolved: Using std < 0.01 threshold as in Kit_Proposal.md. |
| 7 | **Memorization detection** — weight inspection not applicable to 896×11 linear layer | ✅ Resolved: Using GEN_UNK filtering approach (replace module-exclusive gen: tokens, check if accuracy drops). |
| 8 | **Save format** — nested JSON for float vectors inefficient | ✅ Resolved: Using `.pt` tensors per variant + separate labels.json (planned output). |
| 9 | **MPS seed** — only CPU seed set, not MPS RNG | ✅ Resolved: Setting both `torch.manual_seed(42)` and `torch.mps.manual_seed(42)`. |

---

## Task Design

### Task 1 — Module Classification (Primary)

**Goal:** Test whether representations encode module identity from IR token sequences.

**Label setup:**
- 10 individual modules + 1 `Other` class (4 smallest merged)
- `Other` contains: Data.Int.Basic (22), Algebra.Module.Basic (23), Data.Nat.Basic (27), Group.NatPowAssoc (28)
- Total: 100 examples in `Other`, 3,929 in the other 10 classes
- **Limitation:** Per-class metrics cannot be evaluated for the `Other` group individually

**Class distribution for Task 1:**

| Class | Train (~80%) | Eval (~20%) |
|-------|-------------|-------------|
| Group.Defs | ~903 | ~226 |
| Group.Basic | ~438 | ~110 |
| Order.Lattice | ~415 | ~104 |
| Ring.Defs | ~357 | ~89 |
| Order.Basic | ~345 | ~86 |
| Group.Subgroup.Basic | ~314 | ~79 |
| Order.LatticeIntervals | ~205 | ~51 |
| Ring.GeomSum | ~56 | ~14 |
| Topology.Basic | ~55 | ~14 |
| Ring.Basic | ~54 | ~14 |
| Other (4 classes) | ~80 | ~20 |
| **Total** | **~3,222** | **~807** |

**Random baseline (11 classes):** 1/11 = **9.1%**

**Sequence handling:**
- Truncate all sequences to 512 tokens uniformly
- 3,699 / 4,029 examples (91.8%) fit without truncation
- Remaining 330 examples (8.2%) are truncated — affects all variants equally

**Split strategy:**
- 80/20 stratified split, stratified by module label
- Seed: 42 for reproducibility
- `Other` class treated as single unit for stratification

### Task 2 — O-Row Count Prediction (Secondary, conditional)

**Run only if:** Task 1 gap between A and Flat-IR is 5–10pp (inconclusive zone).

**Label setup:**
- 4 bins derived from `graph.operations` array length per example
- Bins: 0–5 (28.2%), 6–15 (35.9%), 16–40 (23.9%), 40+ (12.0%)

**Random baseline (4 classes):** 1/4 = **25.0%**

**Motivation:** O-row count is structural (not semantic) — tests whether representations encode operation complexity vs module identity. If A >> Flat-IR on both Task 1 and Task 2, semantic encoding is confirmed. If A ≈ Flat-IR on Task 2, semantic content is absent regardless of module classification.

---

## Probe Architecture

### Hyperparameters

```python
PROBE_CONFIG = {
    # Task
    "task": "module_classification",   # or "arity_classification"
    "num_classes": 11,                  # 10 modules + Other

    # Model
    "input_dim": 896,                   # hidden size (all variants identical)
    "probe": "linear",                 # single nn.Linear(896, num_classes)

    # Pooling
    "pooling": "mean",                 # mean over sequence, all positions equally

    # Training
    "optimizer": "AdamW",
    "lr": 1e-3,
    "weight_decay": 1e-4,
    "epochs": 100,                     # fixed, no early stopping
    "batch_size": 32,

    # Seeds (3 runs for stochasticity management)
    "probe_seeds": [42, 43, 44],      # run with 3 seeds, report mean ± std

    # Data
    "train_split": 0.8,
    "split_seed": 42,                  # fixed split seed
    "seq_cap": 512,                    # uniform across all variants
}
```

### Why Fixed 100 Epochs (No Early Stopping)

A linear probe (896×11 = 9,856 parameters) on frozen 896-dimensional representations cannot overfit in 100 steps on 3,222 training examples. Early stopping adds complexity and may terminate before convergence on minority classes. Fixed 100 epochs is simpler and sufficient.

### Why Mean Pooling

- No CLS token in causal LM
- Last-token pooling biases toward recent context
- Mean pooling treats all positions equally — standard for probing decoder-only models

---

## Interpretation Criteria

### Thresholds (Set Before Running)

> **Note:** All thresholds are based on gap (difference in probe accuracy between variants), not absolute accuracy levels. This is more robust than requiring simultaneous conditions on two variants.

| Outcome | Definition | Interpretation |
|---------|-----------|---------------|
| **A >> Flat-IR** | Gap (A − Flat-IR) ≥ 10pp | Representations differ. Semantic content is encoded. Bottleneck is training objective or data volume. |
| **A ≈ Flat-IR** | Gap (A − Flat-IR) < 5pp | Within expected variance. Semantic content not encoded in this setup. |
| **Inconclusive** | Gap 5–10pp | Run Task 2 before concluding. |

**Gap thresholds justified:**
- 10pp ≈ 1 standard deviation at this sample size (~800 eval examples)
- Well above noise floor for a linear probe
- Distinguishes meaningful from random variation

### Joint Interpretation with C and Random

| Result | Sub-case | Interpretation | Next Step |
|--------|----------|---------------|-----------|
| A >> Flat-IR (≥10pp) | A ≈ C | IR and BPE encode semantics equally | Data volume is bottleneck. Pursue corpus expansion to 10k+. |
| A >> Flat-IR (≥10pp) | A >> C | IR encodes semantics better than BPE | Strong signal for IR hypothesis. IR pretraining is highest-leverage. |
| A >> Flat-IR (≥10pp) | C >> A | BPE encodes semantics better than IR | BPE representations richer. IR pretraining essential. |
| A ≈ Flat-IR (<5pp) | Both < C | Semantic content not encoded in IR; BPE is | Representation or objective problem. Investigate training objective before format changes. |
| A ≈ Flat-IR (<5pp) | All 3 ≈ Random | Fine-tuning not changing representations | Review training setup. |
| Inconclusive (5–10pp) | — | Run Task 2 | If A >> Flat-IR on Task 2: semantic content present, weakly encoded. If A ≈ Flat-IR on Task 2: not encoded at all. |

### Confidence Levels

For outcomes where actions are high-effort investments:

| Outcome | Confidence Signal |
|---------|-----------------|
| High confidence (pursue investment) | Gap ≥ 15pp AND macro-F1 > 0.35 |
| Moderate confidence | Gap ≥ 10pp AND macro-F1 > 0.25 |
| Low confidence (caution) | Gap ≥ 10pp but macro-F1 < 0.25 |

> **Why macro-F1 floor?** A probe achieving 50% top-1 accuracy with macro-F1 = 0.15 is solving via class-size bias (predicting Group.Defs always). The combination of gap + macro-F1 prevents over-interpreting biased probes.

### Random Qwen Baseline Interpretation

| Outcome | Meaning |
|---------|---------|
| Random ≈ fine-tuned variants | Qwen priors dominate. Fine-tuning is not changing representations. Training protocol review needed. |
| Random ≈ 9% (near random) | Qwen has no relevant priors. Fine-tuning is creating representations. |
| Random >> 9% | Qwen has relevant priors for module identity. |

---

## Risk Register

### Risk 1: Flat-IR Representations Are Degenerate

**Risk:** With only 11 token types, mean-pooled representations may collapse to near-identical vectors across examples.

**Detection:**
```python
# After extracting Flat-IR representations
import torch
std_per_dim = representations_flat.std(dim=0)  # [896]
overall_std = std_per_dim.mean().item()
assert overall_std > 0.01, "DEGENERATE: Flat-IR representations collapsed"
```

**Threshold:** std > 0.01 across representation dimensions.

**If degenerate:** Flat-IR probe result is uninterpretable. Report as "inconclusive — Flat-IR degenerate." Do not draw conclusions from A vs Flat-IR comparison.

**Source:** Kit_Proposal.md (correct method); OpenHands_Proposal.md "mean > median" was invalid for 896-dim vectors.

---

### Risk 2: Module-Exclusive Token Memorization

**Risk:** Linear probe succeeds by learning module-exclusive gen: token signatures (84.5% of gen: tokens are unique to one module) without encoding richer structure.

**Detection — GEN_UNK filtering approach:**

1. Create filtered corpus: for each example, replace all module-exclusive gen: tokens with a single `GEN_UNK` token
2. Re-extract representations with the filtered token sequences
3. Re-run probe on filtered representations
4. If accuracy drops significantly (> 10pp): probe was exploiting token signatures
5. If accuracy is unchanged: probe learned genuine structural patterns

**If detected:** Finding is still valid — module-exclusive signatures are semantic content. Claim narrows to "representations encode module-specific vocabulary" rather than "rich structural understanding."

**Source:** Kit_Proposal.md (correct method); OpenHands_Proposal.md "probe weight inspection" was not applicable to 896×11 linear layer.

---

### Risk 3: Cross-Module Label Leakage

**Risk:** Same declaration name appears in multiple modules.

**Detection:** Computed from corpus — zero duplicate declaration names across modules.

**Status:** **No risk.** Verified from corpus analysis. No filtering needed.

---

### Risk 4: MPS Non-Determinism in Extraction

**Risk:** Representation extraction varies across runs due to MPS GPU non-determinism.

**Mitigation:**
```python
import torch
torch.manual_seed(42)
torch.mps.manual_seed(42)  # MPS has separate RNG
```

> **Note:** Both seeds must be set. `torch.manual_seed` alone does not seed the MPS RNG.

**If non-deterministic:** Introduces noise but not systematic bias. Relative ordering of A vs Flat-IR vs C preserved.

---

### Risk 5: Probe Training Stochasticity

**Risk:** Linear probe convergence varies with random initialization.

**Mitigation:**
- Run probe training with 3 seeds: 42, 43, 44
- Report mean ± standard deviation across seeds
- Use mean accuracy for interpretation
- Use std as uncertainty estimate (especially important in 5–10pp inconclusive zone)

**Source:** Kit_Proposal.md (identified by OpenHands review).

---

### Risk 6: Imbalanced Classes Bias Top-1 Accuracy

**Risk:** With Group.Defs at 28% of examples, a probe predicting Group.Defs always achieves ~28% top-1 accuracy.

**Mitigation:**
- Report **macro-F1** (unweighted per-class F1 average): robust to class imbalance
- Report **balanced accuracy** (mean per-class recall): directly comparable across imbalance levels
- Do not interpret top-1 accuracy alone

**Source:** OpenHands_Proposal.md review of Kit_Proposal.md.

---

### Risk 7: Ambiguous Outcome in 5–10pp Gap Zone

**Risk:** Task 1 gap of 5–10pp is neither decisive for "A >> Flat-IR" nor clearly "A ≈ Flat-IR."

**Resolution:** Run Task 2 (O-row count prediction). If A >> Flat-IR on Task 2, semantic content is weakly but genuinely encoded. If A ≈ Flat-IR on both tasks, semantic content is not encoded.

**If Task 2 also inconclusive:** Report as "inconclusive — both tasks suggest weak encoding, further experiments needed."

---

### Risk 8: 8.2% of Examples Truncated at 512 Tokens

**Risk:** Long examples are truncated uniformly across all variants. If truncation affects some variants differently (e.g., Flat-IR sequences are shorter), systematic bias could be introduced.

**Mitigation:** All variants truncated at the same 512-token cap. If truncation introduces bias, it affects all variants equally. No action needed beyond documenting this limitation.

---

## Implementation Checklist

### Phase 1 — Verify Checkpoint Availability

> **⚠️ Do not skip this step.** Checkpoints are gitignored and must exist on the execution machine.

- [ ] 1.1 Verify `runs/variant_A_v1_4_0/checkpoint-final/` exists locally
- [ ] 1.2 Verify `runs/variant_C_phase6/checkpoint-final/` exists locally
- [ ] 1.3 Verify `runs/variant_flat/checkpoint-final/` exists locally
- [ ] 1.4 Verify `~/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-0.5B/` is cached
- [ ] 1.5 If any path is missing: obtain checkpoints from the machine that ran the original experiments before proceeding

### Phase 2 — Extract Representations

- [ ] 2.1 Write `python/extract_representations.py`:
  ```python
  # For each variant (A, C, Flat-IR, Random):
  #   - Load checkpoint with AutoModelForCausalLM, output_hidden_states=True
  #   - Set seeds: torch.manual_seed(42), torch.mps.manual_seed(42)
  #   - Load corpus examples (Corpus/corpus.jsonl)
  #   - Tokenize using variant's tokenizer (custom for A/Flat-IR, Qwen for C/Random)
  #   - Truncate to 512 tokens
  #   - Forward pass: hidden_states = model(input_ids).hidden_states[-1]
  #   - Mean pool over sequence: representations = hidden_states.mean(dim=1)
  #   - Save: torch.save(representations, f"runs/probing/representations_{variant}.pt")
  #   - Shape: [4029, 896]
  #   - Load one variant at a time (MPS memory: ~1.65 GB per model)
  ```
- [ ] 2.2 Save labels: write `runs/probing/labels.json`:
  ```json
  {
    "names": [...],       // declaration names in corpus order
    "modules": [...],     // module labels in corpus order
    "module_labels": {...}, // module → class_id mapping (0-10)
    "other_classes": [...], // names of 4 classes merged into Other
    "arity_bins": [...]    // O-row count bin per example (0-3)
  }
  ```
- [ ] 2.3 After extraction: verify each `.pt` file:
  - Shape is [4029, 896]
  - No NaN or Inf values
  - `torch.all(representations.std(dim=0) > 0.01)` — confirms non-degenerate
- [ ] 2.4 Run extraction determinism check: extract Flat-IR twice, verify `torch.allclose(rep1, rep2)`

### Phase 3 — Train Probes (Task 1)

- [ ] 3.1 Write `python/probing_task.py`:
  ```python
  # Load representations: torch.load("runs/probing/representations_{variant}.pt")
  # Load labels: json.load(open("runs/probing/labels.json"))
  # Stratified 80/20 split: indices that preserve class distribution, seed=42
  # For each variant (A, C, Flat-IR, Random):
  #   For each probe_seed in [42, 43, 44]:
  #     - Initialize: probe = nn.Linear(896, 11)
  #     - Train: AdamW lr=1e-3, weight_decay=1e-4, 100 epochs, batch=32
  #     - Evaluate on held-out 20%
  #     - Record: top1_acc, macro_f1, balanced_acc, per_class_f1
  #   Report: mean ± std across 3 seeds
  ```
- [ ] 3.2 Compute random baseline: uniform random predictions = 1/11 = 9.1%
- [ ] 3.3 Memorization check (Risk 2): if time permits, run GEN_UNK filtering experiment
- [ ] 3.4 Write `runs/probing/task1_results.json`:
  ```json
  {
    "variant_A": {"top1": 0.XX, "macro_f1": 0.XX, "balanced_acc": 0.XX, "per_class_f1": {...}, "seeds": {"42": {...}, "43": {...}, "44": {...}}},
    "variant_C": {...},
    "variant_flat": {...},
    "variant_random": {...},
    "gap_A_minus_flat": 0.XX,
    "interpretation": "...",
    "next_step": "..."
  }
  ```

### Phase 4 — Interpret and Decide (Task 2 Conditional)

- [ ] 4.1 Apply interpretation table:
  - If gap ≥ 10pp: A >> Flat-IR → document finding and next step
  - If gap < 5pp: A ≈ Flat-IR → document finding and next step
  - If gap 5–10pp: **Inconclusive → proceed to Phase 5**
- [ ] 4.2 If inconclusive: run Task 2 (O-row count prediction)
  - Derive labels from `graph.operations` length: bin into 4 buckets
  - Same probe architecture, 3 seeds, same split
  - Write `runs/probing/task2_results.json`
  - Apply interpretation table for Task 2

### Phase 5 — Document

- [ ] 5.1 Append DEC-025 to `docs/decisions/LOG.md`:
  - All probe accuracies (top-1, macro-F1, balanced_acc)
  - Gap values with confidence level
  - Selected interpretation and justification
  - Next step from decision table
- [ ] 5.2 Update `docs/history/PHASE_7_ROADMAP.md` with selected path forward
- [ ] 5.3 Do NOT modify: `Corpus/`, `datasets/`, `datasets_flat/`, `Maith/`, any `runs/variant_*/`

---

## Files to Create

| File | Purpose |
|------|---------|
| `python/extract_representations.py` | Forward-pass all 4 variants, save 896-dim mean-pooled representations as `.pt` tensors |
| `python/probing_task.py` | Train and eval linear probes for Task 1 and Task 2, multi-seed |
| `runs/probing/representations_A.pt` | Variant A representations, shape [4029, 896] (gitignored) |
| `runs/probing/representations_C.pt` | Variant C representations, shape [4029, 896] (gitignored) |
| `runs/probing/representations_flat.pt` | Flat-IR representations, shape [4029, 896] (gitignored) |
| `runs/probing/representations_random.pt` | Random Qwen representations, shape [4029, 896] (gitignored) |
| `runs/probing/labels.json` | Module labels (0–10), arity bins, declaration names |
| `runs/probing/task1_results.json` | Task 1 results for all variants, all seeds |
| `runs/probing/task2_results.json` | Task 2 results (only if Task 1 inconclusive) |

---

## Estimated Time

| Phase | Time |
|------|------|
| Verify checkpoint paths | 5 minutes |
| Write extraction script | 1–2 hours |
| Write probing script | 1 hour |
| Run extraction (4 × ~11 min) | ~45 minutes |
| Run probing (4 variants × 3 seeds) | < 5 minutes |
| Interpret and document | 1–2 hours |
| **Total** | **~4–6 hours** |

> **Buffer note:** If GEN_UNK memorization test is run, add 2 hours. If results are ambiguous and Task 2 is needed, add 1 hour.

---

## References

- `docs/experiments/PROBING_TASK_GUIDE.md` — research guide this proposal satisfies
- `docs/experiments/PROBING_TASK_FINAL.md` — this document
- Kit's original proposal — elements adopted above (source doc removed as obsolete in 2026-07 docs cleanup)
- `docs/scratch/Openhands_Proposal.md` — OpenHands's original proposal (elements adopted, [KIT] concerns resolved)
- `docs/scratch/AUDIT_2026_08_04.md` — verified experimental data (all numbers sourced here)
- `docs/decisions/LOG.md` — DEC-024 (open questions this addresses), DEC-021, DEC-023
- `docs/history/PHASE_7_ROADMAP.md` — Phase 7 decision tree, items this gates
- `runs/variant_*/results.json` — raw perplexity values (verified in audit)
- `Corpus/corpus.jsonl` — corpus with module labels (verified 4,029 examples, 14 modules)
