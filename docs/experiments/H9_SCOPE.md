# H9 Experiment Scope — Co-Training (IR + Contrastive Joint Objective)

> **Hypothesis:** Co-training (IR token prediction alongside a contrastive auxiliary
> loss) recovers gains where post-hoc contrastive fine-tuning alone did not. The
> contrastive signal reshapes the representation layer more effectively when applied
> during next-token learning than as a separate stage on top of an already-converged
> model.

> **Status:** Infrastructure pending. Scope defined 2026-08-19.

---

## Motivation

H5 established that a contrastive objective (NT-Xent) reliably improves retrieval over
the next-token baseline in Mode 2 — both projection-head and end-to-end variants beat
A_v3_2ep (Recall@10: 0.0027–0.0029 vs 0.0012, CIs non-overlapping). But the effect is
small, and full e2e fine-tuning didn't improve over the frozen projection-head. This
suggests the encoder's representation has already converged to a local optimum under
next-token loss, and a post-hoc contrastive pass can't fully escape it.

H9 tests whether applying the contrastive signal *during* next-token learning —
co-training from the base checkpoint — produces a better representation than either
objective alone. The key difference from H5: the model never fully converges on
next-token prediction before seeing the contrastive signal.

---

## Design

**Base model:** `Qwen/Qwen2.5-Coder-0.5B` (pretrained, no IR fine-tuning)
We train from the pretrained base, not from `A_v3_2ep`. Starting from a converged
IR checkpoint would replicate the H5 setup. H9's claim requires that the two objectives
interact during training, not sequentially.

**Dataset:** `datasets/train_A.jsonl` (3,375 IR token sequences, same as all prior A
variants)

**Positive pairs:** `datasets/h5_pairs_train.json` (12,443 pairs, already built)
Same pair construction as H5 — shared dependency ≥1.

**Objective:** weighted combination at each step

```
loss = (1 - λ) * next_token_loss + λ * nt_xent_loss
```

- `λ = 0.1` (contrastive weight) — default starting point
  Rationale: next-token loss is the primary learning signal for the IR vocabulary;
  contrastive is auxiliary. Too-high λ risks vocabulary collapse (model stops
  predicting tokens correctly). 0.1 keeps the IR learning signal dominant while
  letting the contrastive signal shape the representation layer.
- NT-Xent temperature: 0.07 (same as H5)
- Batch construction: each step draws a minibatch of pairs; the anchor sequences
  are also used for next-token loss in the same forward pass.

**Training config:**
- Epochs: 2 (matched to A_v3_2ep — required for comparison validity under EXPERIMENT_DESIGN.md)
- Batch size: 1, grad_accum: 8 (effective batch 8) — standard protocol from EXPERIMENT_DESIGN.md
- LR: 2e-4 (standard A-variant lr)
- max_seq_len: 512 (matched to all clean variants)
- Seed: 42 (fixed across all variants)
- Device: MPS
- Gradient checkpointing: enabled
- Output: `runs/variant_A_h9/checkpoint-final`

Note: the contrastive auxiliary loss fires on the same minibatch as the next-token
loss. Pair sampling draws from `h5_pairs_train.json (run-time artifact)` at each step; unpaired sequences
contribute next-token loss only (λ * 0 + (1-λ) * ntp_loss).

**Estimated duration:** 10–14 hours (2 epochs, effective batch 8, two forward passes
per step when a pair is available)

**Evaluation:** same retrieval pipeline as H5/H6
- Extract embeddings from `runs/variant_A_h9/checkpoint-final`
- Compare A_h9 vs A_h5_e2e vs A_v3_2ep vs B_small_clean
- Mode 1 (eval→train) and Mode 2 (train→train) both required

---

## Gate sequence (must pass in order)

```
1. manage.py gate dataset              → 63/63 invariants pass (Gate 3 per PIPELINE_QUALITY_GATES)
2. python3 python/test_h9_cotrain.py   → all unit tests pass
3. manage.py run-alias train-h9 -- --smoke-test
   Gate 3a: completes without OOM or hang
   Gate 3b: loss_descended = True in smoke results.json
   Gate 3c: both next_token_loss and contrastive_loss logged per step
   Gate 3d: results.json contains learning_rate, effective_batch_size, max_seq_len, lambda (Gate 4 completeness)
4. manage.py run-alias train-h9        → runs/variant_A_h9/results.json written
   Gate 4a: loss_descended = True
   Gate 4b: final_loss < initial_loss by > 5%
   Gate 4c: results.json comparison validity — epochs=2, seed=42, train_examples=3375 (matches A_v3_2ep)
5. manage.py run-alias extract-h9      → embeddings extracted, shapes verified (3375 train, 376 eval)
6. manage.py run-alias eval-h9         → runs/h9_retrieval/results.json
7. manage.py run-alias eval-h9-mode2   → runs/h9_retrieval/results_mode2.json
```

Do not proceed to step N+1 if step N fails.

---

## What closes H9

| Result | Interpretation |
|---|---|
| A_h9 Recall@10 > A_h5_e2e, CIs non-overlapping in Mode 2 | H9 positive — co-training improves on post-hoc contrastive |
| A_h9 ≈ A_h5_e2e (CIs overlap) | H9 neutral — ordering doesn't matter; contrastive signal is the lever, not when it's applied |
| A_h9 ≤ A_v3_2ep | H9 negative — co-training hurts; objectives conflict at toy scale |
| A_h9 > A_v3_2ep but ≤ A_h5_e2e | Partial — co-training helps over baseline but not over sequential; H5's approach is sufficient |

**Secondary check:** does A_h9 close the gap to the pretrained ceiling (Recall@10≈0.072)?
Any result > 0.01 in Mode 2 would be a meaningful step up from the current 0.003 range.

---

## What this does not test

- Scale (H4/H8) — still 0.5B, 3.5K examples
- Architecture (H12) — still sequence transformer
- λ sensitivity — 0.1 is a single point; a sweep would require multiple runs
- Co-training from A_v3_2ep — training from pretrained base is the clean test;
  starting from the IR checkpoint conflates H5 and H9

---

## Files

| File | Purpose |
|---|---|
| `python/train_h9_cotrain.py` | Joint next-token + NT-Xent training loop |
| `python/test_h9_cotrain.py` | Unit tests for co-training components |
| `datasets/train_A.jsonl` | IR token sequences (already exists) |
| `datasets/h5_pairs_train.json` | Positive pairs (already exists from H5) |
| `runs/variant_A_h9/` | Training output (after run) |
| `runs/retrieval_embeddings_h9/` | Extracted embeddings (after extract) |
| `runs/h9_retrieval/results.json` | Mode 1 eval results (after eval) |
| `runs/h9_retrieval/results_mode2.json` | Mode 2 eval results (after eval) |

---

## Relationship to other hypotheses

- **H5** — H9 is the co-training variant of H5. H5 showed contrastive post-hoc works;
  H9 tests whether earlier application is better.
- **H13 (JEPA)** — H13 is a different objective family (latent prediction vs
  contrastive); H9 does not block or depend on H13.
- **H4/H8 (scale)** — H9 runs at toy scale. If H9 is positive, scale becomes the
  natural next question.
