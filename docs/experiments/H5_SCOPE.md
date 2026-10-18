# H5 Experiment Scope — Contrastive Objective

> **Hypothesis:** The training objective is the bottleneck. Next-token prediction fails
> to reward semantic similarity, so fine-tuning with a retrieval-oriented objective
> (NT-Xent / SimCSE) should produce better embeddings from the same IR at the same scale.

> **Status:** Ready to run. All infrastructure in place as of 2026-08-18.

---

## Motivation

H6 (retrieval eval) was ambiguous — both modes showed weak signal and disagreed on
direction. The most credible explanation at toy scale is not that the IR is wrong, but
that next-token prediction does not optimize for semantic similarity. A model trained
to predict the next token will encode distributional patterns, not necessarily the
structural relationships that make two declarations semantically related.

H5 tests this directly: keep everything the same (model, IR, corpus, scale) and change
only the training objective.

---

## Design

**Base model:** `runs/variant_A_v3_2ep/checkpoint-final`
Already fine-tuned on IR tokens. Contrastive fine-tuning builds on top — we are not
training from scratch.

**Objective:** NT-Xent (SimCSE-style in-batch negatives)
- Anchor: mean-pooled embedding of declaration i
- Positive: mean-pooled embedding of a declaration sharing ≥1 dependency with i
- Negatives: all other anchors in the batch
- Temperature: 0.07 (standard SimCSE default)

**Pair construction:** `build_h5_pairs.py`
- Source: `datasets/train_A.jsonl` + `datasets/dependency_groundtruth.json (built by build_dependency_groundtruth.py)`
- Strategy: shared_dependency (≥1 shared dep = positive pair)
- 12,460 pairs from 3,375 declarations (max 5 per anchor)
- Pairs file: `datasets/h5_pairs_train.json`

**Training:** `train_h5_contrastive.py`
- Epochs: 3
- Batch size: 32 (in-batch negatives = 31 negatives per anchor)
- LR: 2e-5 (lower than next-token fine-tuning to avoid destroying representations)
- Output: `runs/variant_A_h5/`

**Evaluation:** same retrieval pipeline as H6
- Extract embeddings from `runs/variant_A_h5/checkpoint-final`
- Compare A_h5 vs A_v3_2ep vs B_small_clean on Recall@{1,5,10,20}, MRR
- Mode 1 (eval→train) and Mode 2 (train→train) both required

---

## Gate sequence (must pass in order)

```
1. manage.py gate dataset       → 57/57 invariants pass
2. python test_h5_pairs.py      → 15/15 pass
3. python test_h5_contrastive.py → 20/20 pass
4. manage.py run-alias build-h5-pairs  → datasets/h5_pairs_train.json written
5. manage.py run-alias train-h5        → runs/variant_A_h5/results.json written
   Gate 4a: loss_descended = True in results.json
   Gate 4b: final_loss < initial_loss by > 5%
6. manage.py run-alias extract-h5      → embeddings extracted
7. manage.py run-alias eval-h5         → runs/h5_retrieval/results.json
8. manage.py run-alias eval-h5-mode2   → runs/h5_retrieval/results_mode2.json
```

Do not proceed to step N+1 if step N fails.

---

## What closes H5

| Result | Interpretation |
|---|---|
| A_h5 Recall@10 > A_v3_2ep and CIs don't overlap (Mode 1) | H5 positive — objective was the bottleneck |
| Mode 1 and Mode 2 agree on direction | Result is robust |
| A_h5 ≤ A_v3_2ep in both modes | H5 negative at toy scale — bottleneck is elsewhere (scale, architecture) |
| Modes disagree | Ambiguous — same finding as H6, no new information |

**Secondary check:** if A_h5 beats B_small_clean (not just A_v3_2ep), that is a
stronger result — contrastive IR beats BPE even on retrieval, which would be the
first clean positive in the H-series.

---

## What this does not test

- Scale (H4/H8) — still 0.5B, 3.5K examples
- Architecture (H12) — still sequence transformer
- Co-training (H9) — IR-only contrastive, no source signal
- Full IR vs BPE at matched contrastive training — B_small_clean is used as a
  baseline but is not contrastively fine-tuned itself. A future H5b could add
  contrastive B_small_clean to isolate the objective vs representation question
  more cleanly.

---

## Files

| File | Purpose |
|---|---|
| `python/build_h5_pairs.py` | Pair construction from dependency groundtruth |
| `python/train_h5_contrastive.py` | NT-Xent contrastive training loop |
| `python/test_h5_pairs.py` | 15 unit tests for pair builder |
| `python/test_h5_contrastive.py` | 20 unit tests for training components |
| `datasets/h5_pairs_train.json` | Built pairs (12,460 pairs, 3,375 decls) |
| `runs/variant_A_h5/` | Training output (after run) |
| `runs/retrieval_embeddings_h5/` | Extracted embeddings (after extract) |
| `runs/h5_retrieval/results.json` | Mode 1 eval results (after eval) |
| `runs/h5_retrieval/results_mode2.json` | Mode 2 eval results (after eval) |
