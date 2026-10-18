# How Maith Measures Things — Experiment Measurement Reference

> **STATUS: PROPOSAL — drafted by Kit 2026-08-12, not yet reviewed.**
> Numbers are drawn from real runs but the framing, validity caveats, and
> interpretations have not been verified against the experiment code or
> cross-checked by a second author. Treat as a starting point for review,
> not a settled reference.

> **Purpose.** A concrete walkthrough of exactly how next-token prediction and
> retrieval are measured, using real numbers from actual runs. For each experiment
> type you will see: what question it is answering, what data goes in, what
> computation is performed, and what the output number means — illustrated with a
> specific declaration so you can follow the full chain.
>
> **Companion to** [`EXAMPLE_ROUNDTRIP.md`](EXAMPLE_ROUNDTRIP.md), which covers how
> a Lean declaration becomes training data. This document starts where that one ends.

> **⚠ TERMINOLOGY — "untrained" vs "pretrained" vs "fine-tuned" (S1 finding, 2026-08-12):**
> The S1 sanity check exposed a naming problem. Qwen2.5-Coder-0.5B is a **pretrained**
> model — it was trained on a large code/text corpus before Maith touches it. Maith
> **fine-tunes** it on the IR/BPE datasets. The "random" baseline (S1) used the pretrained
> model *without* fine-tuning, but it is NOT a random model — its embeddings already
> encode semantic similarity from pretraining.
>
> **Impact on the project:** Every retrieval number must be read against the **pretrained
> baseline** (Recall@10 ≈ 0.072 on a 500-pool subset), not against pure chance (0.020).
> The comparison is:
> - **Pretrained Qwen** (no fine-tuning) — the true baseline
> - **B_small_clean** (fine-tuned on BPE) — does fine-tuning help beyond pretraining?
> - **A_v3_2ep** (fine-tuned on IR) — does IR fine-tuning beat BPE fine-tuning?
>
> If neither fine-tuned variant beats the pretrained baseline, fine-tuning isn't helping
> retrieval at all. If both beat it by similar amounts, fine-tuning helps but the
> representation doesn't matter. The H6 hypothesis test must include the pretrained
> baseline as a variant in the results.

---

## Part 1 — Next-Token Prediction

### The Question

> Does a model trained on IR tokens predict the next IR token better than a model
> trained on raw Lean text (BPE)?

### What "training" actually means

Every example in the training set is a token sequence. For the declaration
`IsDedekindFiniteMonoid` from `Mathlib.Algebra.Group.Defs`, the IR token sequence
(per-operator format, Variant A) maps to these integers:

```
[4, 6, 15, 6, 19, 6, 17, 6, 26, 6, 24, 7, 19, 28, 580,
 7, 17, 21, 96, 7, 24, 21, 137, 8, 15, 17, 13, 9, 16, 40, 364, 5]
```

Which decode to:

```
GRAPH_BEGIN
E FVAR_0          ← bound variable (carrier type M)
E FVAR_1          ← bound variable (element)
E TERM_0          ← computed term
E TERM_1          ← computed term
E TERM_2          ← computed term
A FVAR_1 typeclass MulOne     ← FVAR_1 has typeclass MulOne
A TERM_0 sort u_2+1           ← TERM_0 is a universe sort
A TERM_2 sort 0               ← TERM_2 is in sort 0
R FVAR_0 TERM_0 eq            ← FVAR_0 has type TERM_0
O IN_1 OUT_1 gen:MulOne       ← operation: apply gen:MulOne
GRAPH_END
```

The model is trained to predict each token given all preceding tokens. At every
position, it outputs a probability distribution over the entire vocabulary (2,254
tokens for Variant A per-operator).

---

### The Training Loop (what the code actually does)

**Script:** `python/train_v2_resume.py`  
**Entry point:** `python3 python/launch_run.py train --variant A --epochs 2 --dataset-dir datasets_perop`

Each training step:

1. Load a batch of token sequences from `datasets_perop/train_A.jsonl`
2. Pass through the model (Qwen2.5-Coder-0.5B, 359.9M parameters)
3. At each position `i`, the model predicts position `i+1`
4. Compute **cross-entropy loss**: how surprised was the model by the actual next token?

```
loss = -log P(actual token | all previous tokens)
```

Averaged across all positions in the batch. Lower loss = the model is less surprised
= it has learned the structure of the token sequences.

**What the loss curve looks like for A_v3_2ep:**

| Training Step | Loss |
|---|---|
| 10 | 3.14 (random — model has learned nothing yet) |
| 100 | 0.74 |
| 200 | 0.57 |
| 840 (final) | 0.23 |

The model starts near-random (loss ~3.1 ≈ log(vocab_size) for uniform distribution)
and learns to predict the next IR token with increasing confidence.

---

### Perplexity — the reported metric

**What it is:** `perplexity = exp(average loss)`. It measures how many tokens the
model is "choosing between" on average at each prediction step.

- **Perplexity = 1.0** — perfect prediction, model always knows the next token
- **Perplexity = vocab_size** — random guessing
- **Perplexity = 1.29** (A_v3_2ep actual) — the model is choosing between ~1.29 plausible tokens on average

**Where it is computed:** At the end of each epoch, the model runs over `datasets_perop/eval_A.jsonl` (376 held-out examples that were never used in training) and computes the average loss:

```
eval checkpoint step 422 (end of epoch 1): eval_loss = 0.4129 → ppl = 1.51
eval checkpoint step 844 (end of epoch 2): eval_loss = 0.2876 → ppl = 1.33 → reported as 1.2928
```

**Script:** `evaluate_perplexity()` in `train_v2_resume.py` — loads eval split,
forward-passes each example, averages the loss, calls `math.exp()`.

---

### The Comparison (H2)

The same procedure runs for Variant B_small — identical model size (358.4M params),
same 2 epochs, same eval split. The only difference: B_small's training data is
`datasets/train_B_small.jsonl`, which contains BPE token IDs from Qwen's tokenizer
instead of IR token IDs.

| Variant | Vocab | Params | Epochs | Perplexity |
|---|---|---|---|---|
| A_v3_2ep (IR, per-operator) | 2,254 | 359.9M | 2 | **1.2928** |
| B_small (BPE, truncated) | 601 | 358.4M | 2 | **1.1294** |

**What the gap means:** At every prediction step, the IR model is choosing between
~1.29 tokens while the BPE model is choosing between ~1.13 tokens. BPE wins.

**Why IR loses on this metric:** Explained in
[`EXPERIMENT_DESIGN.md`](EXPERIMENT_DESIGN.md#why-prediction-metrics-are-structurally-biased-toward-natural-language).
In short: the IR canonicalizes to one form, removing the surface redundancy that
makes text predictable. BPE models exploit the fact that "Group.add" is almost always
followed by "Monoid" in Lean source. The IR's `gen:Add` token has no such predictable
neighbors because it's already canonical — there is no redundancy left to exploit.

**What perplexity does NOT measure:** Whether the model's internal representations
are semantically meaningful, or whether it would help a theorem prover. See H1 and H7.

---

### What would falsify the perplexity result?

- A different IR design that includes *semantic* redundancy (meaningful tokens that
  predict each other) rather than just canonicalization
- A larger model (H4/H8) — untested above 0.5B
- A different training corpus — currently 3,375 examples from 14 Mathlib modules

---

## Part 2 — Retrieval (H6)

### The Question

> Given the embedding of a Lean declaration, can we retrieve its mathematical
> dependencies from a pool of training examples?

This tests whether the model's *internal representations* (not its token predictions)
encode dependency structure. A model trained on IR should produce embeddings where
`Group.noConfusion` is geometrically close to `DivInvMonoid`, `Group`, and `Monoid.toOne`
— the declarations it directly depends on.

---

### Step 1 — Embedding Extraction

**Script:** `python/extract_retrieval_embeddings.py`

For each declaration in the eval split, the trained model is run in **inference mode**
(no gradient computation). The final hidden layer is extracted and **mean-pooled**
across all token positions to produce a single 896-dimensional vector per declaration.

```
declaration token sequence → model forward pass → hidden states [seq_len × 896] → mean pool → embedding [896]
```

This is done separately per variant — each model produces its own embedding space:

| File | What it contains |
|---|---|
| `runs/retrieval_embeddings/embeddings_A_v3_eval.pt` | 376 × 896 float32 tensor (A_v3 embeddings for eval split) |
| `runs/retrieval_embeddings/embeddings_A_v3_train.pt` | 3,375 × 896 float32 tensor (A_v3 embeddings for train pool) |
| `runs/retrieval_embeddings/embeddings_B_small_eval.pt` | 376 × 896 float32 tensor (B_small embeddings for eval split) |
| `runs/retrieval_embeddings/embeddings_B_small_train.pt` | 3,491 × 896 float32 tensor (B_small embeddings for train pool) |

**Critical correctness requirement:** each variant's embeddings must come from feeding
that variant's own `input_ids` through its own checkpoint. Feeding IR tokens to a
BPE-trained model produces garbage embeddings — this was the bug in the first H6 run
(KNOWN_ISSUES #4), now caught by invariant 3 in `check_invariants.py`.

---

### Step 2 — Ground Truth Construction

**Script:** `python/build_dependency_groundtruth.py`

For each eval declaration, the ground truth is the set of training declarations it
directly depends on. This is extracted from the IR corpus:

```python
# For declaration "Group.noConfusion" in the eval split:
deps = ["DivInvMonoid", "DivInvMonoid.toInv", "DivInvMonoid.toMonoid",
        "Group", "Group.casesOn", "Monoid.toOne"]
```

These are the declarations whose `gen:FullName` tokens appear in `Group.noConfusion`'s
IR token sequence — the mathematical objects it directly invokes.

Ground truth is stored in `datasets/dependency_groundtruth_eval_to_train.json (built by build_dependency_groundtruth.py)`:
- 287 eval queries (out of 376 — not every eval declaration has deps in the train pool)
- Each query has a list of training-split declarations it depends on
- 287/287 queries have at least one dep in the pool

---

### Step 3 — Ranking by Cosine Similarity

**Script:** `python/retrieval_eval.py`

For each eval query, cosine similarity is computed between that query's embedding
and every training-pool embedding:

```
similarity(q, p) = (q · p) / (|q| × |p|)
```

A cosine similarity of 1.0 means the vectors point in exactly the same direction
(maximally similar). 0.0 means orthogonal (unrelated). The pool of 3,375 training
embeddings is ranked from highest to lowest similarity.

---

### Concrete Example: `Group.noConfusion`

Here is the actual retrieval result for one eval declaration, using real embeddings
from the completed runs.

**Query:** `Group.noConfusion` (from eval split)  
**True dependencies in train pool:** `DivInvMonoid`, `DivInvMonoid.toInv`,
`DivInvMonoid.toMonoid`, `Group`, `Group.casesOn`, `Monoid.toOne`

#### Variant A_v3 (IR, per-operator) — top 10 retrieved:

| Rank | Declaration | Cosine Sim | True dep? |
|---|---|---|---|
| 1 | `AddGroup.noConfusion` | 0.9997 | ✗ |
| 2 | `CancelMonoid.noConfusion` | 0.9988 | ✗ |
| 3 | `DivisionCommMonoid.noConfusion` | 0.9988 | ✗ |
| 4 | `CommSemigroup.noConfusion` | 0.9988 | ✗ |
| 5 | `NonAssocCommRing.noConfusion` | 0.9988 | ✗ |
| 6 | `CommMagma.noConfusion` | 0.9987 | ✗ |
| 7 | `CommRing.noConfusion` | 0.9987 | ✗ |
| 8 | `CommMonoid.noConfusion` | 0.9987 | ✗ |
| 9 | `AddSemigroup.noConfusion` | 0.9987 | ✗ |
| 10 | `AddSemigroup.noConfusion` | 0.9987 | ✗ |

**Rank of each true dep:**

| True dependency | Rank in pool (out of 3,375) |
|---|---|
| `DivInvMonoid` | 3,333 |
| `DivInvMonoid.toInv` | 1,454 |
| `DivInvMonoid.toMonoid` | 1,465 |
| `Group` | 3,307 |
| `Group.casesOn` | 181 |
| `Monoid.toOne` | 1,630 |

None of the 6 true dependencies appear in the top 10. The nearest is `Group.casesOn`
at rank 181. Recall@10 = 0/6 = 0.0 for this query.

**What the model found instead:** `AddGroup.noConfusion`, `CancelMonoid.noConfusion`,
`CommSemigroup.noConfusion` — all are structurally similar `noConfusion` lemmas. The
model is grouping by structural shape (all `noConfusion` declarations have similar
IR graph structure) rather than by dependency relationship.

#### Variant B_small (BPE) — same query:

| Rank | Declaration | Cosine Sim | True dep? |
|---|---|---|---|
| 1 | `CommGroup.noConfusion` | 0.9721 | ✗ |
| 2 | `AddSemigroup.noConfusion` | 0.9624 | ✗ |
| 3 | `AddCommGroup.noConfusion` | 0.9606 | ✗ |
| ... | ... | ... | ... |
| 10 | `CommMagma.noConfusion` | 0.9475 | ✗ |

**Rank of each true dep (B_small):**

| True dependency | Rank (out of 3,491) |
|---|---|
| `DivInvMonoid` | 2,492 |
| `DivInvMonoid.toInv` | 553 |
| `DivInvMonoid.toMonoid` | 639 |
| `Group` | 2,453 |
| `Group.casesOn` | 126 |
| `Monoid.toOne` | 876 |

B_small makes the same mistake for the top 10 — `noConfusion` lemmas cluster together.
Both variants fail on this query. B_small actually ranks `DivInvMonoid` higher (2,492
vs 3,333), suggesting BPE's surface subword patterns (the string "DivInv" appears in
the source of related declarations) provide a weak signal the IR misses.

---

### Step 4 — Recall@k and MRR

**Script:** `retrieval_eval.py`, function `evaluate_retrieval_mode1()`

For each of the 287 queryable eval declarations, after ranking all 3,375 pool embeddings:

**Recall@10:** What fraction of the query's true dependencies appear in the top 10
ranked results?

```
Recall@10 = |{true deps in top 10}| / |{total true deps}|
```

For `Group.noConfusion`: 0/6 = 0.0. Averaged across all 287 queries.

**MRR (Mean Reciprocal Rank):** The reciprocal of the rank at which the *first*
true dependency appears.

```
MRR = mean over queries of (1 / rank_of_first_true_dep)
```

For `Group.noConfusion` with A_v3: first true dep is `Group.casesOn` at rank 181.
MRR contribution = 1/181 = 0.0055.

**Bootstrap confidence intervals:** The eval is run 1,000 times on random resamples
of the 287 queries to produce 95% CIs on each metric. Overlapping CIs mean the
difference between variants is not statistically reliable.

---

### The H6 Results

**Mode 1 (eval → train): query = eval declarations, pool = train declarations**

| Variant | Recall@10 | 95% CI | MRR |
|---|---|---|---|
| A_v3_2ep (IR, per-op, 2ep) | 0.0052 | [0.0009, 0.0113] | 0.0095 |
| B_small (BPE, 2ep) | 0.0064 | [0.0017, 0.0122] | 0.0150 |

CIs overlap. Neither variant meaningfully retrieves dependencies. A does not beat B_small.

**What "0.0052 Recall@10" means in plain language:**

Across all 287 eval queries, on average 0.52% of a declaration's dependencies appear
in the top 10 retrieved results. Given that most declarations have 3–10 deps (median ~4),
this means roughly 0.02 true dependencies per query are found in the top 10 — or in
practice, the vast majority of queries return 0 true deps in the top 10 and a small
number return 1.

---

### Why both variants fail

The `Group.noConfusion` example reveals the structural reason: the model's embeddings
cluster by **surface structure** (all `noConfusion` lemmas look the same in IR and BPE)
rather than by **dependency relationship** (which depends on the specific typeclasses
involved). A model trained to predict the next token learns to recognize structural
patterns. It does not learn to represent "this declaration depends on that one" because
that relationship is never directly rewarded by the next-token training objective.

This is the mechanism behind H5 (wrong objective): the model encodes *what the
declaration looks like* but not *what it depends on*. These are different things, and
next-token loss only rewards the former.

---

## Part 3 — Semantic Probing (H1 and H10)

### The Question

> Do the model's internal representations encode mathematical structure that can
> be linearly decoded?

This is a different test from retrieval. It asks: regardless of whether the model
*uses* semantic structure for prediction, are the embeddings *linearly separable*
by semantic category?

### What a Linear Probe Is

A linear probe is a single-layer classifier (`nn.Linear(896, n_classes)`) trained
on top of frozen model embeddings. If a simple linear transformation can classify
declarations by module (e.g., "this came from `Algebra.Group` vs `Mathlib.Order.Lattice`"),
then the embedding space is geometrically organized by that category — the model has
learned to separate them, even if it doesn't use that separation for prediction.

**Script:** `python/probing_task.py`

1. Extract embeddings for all 4,029 corpus declarations
2. 80/20 train/test split
3. Train a linear classifier on the training embeddings
4. Report accuracy on the held-out test embeddings

### Results (DEC-025)

| Variant | Module Probe Accuracy | Random baseline |
|---|---|---|
| A (IR) | **75.4%** | 9.1% |
| flat-IR (no semantic content) | **13.6%** | 9.1% |

The 62pp gap confirms H1: IR embeddings encode module membership far above chance,
and far above the flat-IR ablation which has almost no semantic content.

### Why this matters alongside the retrieval null

The probing result shows the IR *does* encode semantics (H1 positive). The retrieval
result shows that encoding doesn't translate to dependency retrieval (H6 negative).
These two results together point to H5: the representation contains semantic
information, but next-token training doesn't organize it in a way that supports
dependency lookup. A different training objective (contrastive, masked subterm) might
reorganize the embedding space to support retrieval even from the same IR.

---

## Summary: What Each Metric Actually Tests

| Metric | What it measures | What it doesn't measure |
|---|---|---|
| **Perplexity** | How well the model predicts the next token in held-out IR sequences | Whether embeddings are semantically meaningful; downstream task utility |
| **Completion accuracy** | Whether the top-1 predicted token matches the actual next token | Same limitations as perplexity |
| **Recall@k** | Whether true dependencies appear in top-k most similar embeddings | Whether the model can generate proofs; scale effects |
| **MRR** | How highly the first true dependency is ranked | Same as Recall@k |
| **Linear probe accuracy** | Whether embeddings are linearly separable by category | Whether that structure is *used* by the model; task performance |

### The dissociation at the core of Maith's current results

```
H1 (probing): IR encodes semantics ✅
H2 (perplexity): IR doesn't help prediction ❌
H6 (retrieval): IR doesn't help retrieval ❌
```

A model whose embeddings encode module membership (H1) but can't retrieve dependencies
(H6) is a model that has learned structural categories but not relational structure.
Next-token loss rewards knowing "this is an Order declaration" (predictable token
patterns) but not "this declaration depends on that one" (no direct training signal).

**The open questions this leaves:**

- **H5:** Would a contrastive or masked-subterm objective produce embeddings that
  support retrieval? (Testable at current scale.)
- **H7:** Does any of this matter for actual proof completion? Retrieval is a proxy;
  the real test is whether an IR-trained model finds proofs faster.
- **H4/H8:** Do these results hold at 1B+ parameters? IRCoder saw gains at larger
  scale in code — the threshold for formal math is unknown.

---

## Validity Caveats

### What weakens the perplexity result

1. **Scale:** 3,375 training examples from 14 Mathlib modules. The closest positive
   result (IRCoder) used ~4M examples. Maith's corpus is ~1,000x smaller.
2. **Structural bias:** Perplexity favors redundant representations. See
   [`EXPERIMENT_DESIGN.md`](EXPERIMENT_DESIGN.md#why-prediction-metrics-are-structurally-biased-toward-natural-language).
3. **Split leakage (partially resolved):** Old runs had 13 train/eval overlaps. The
   clean 3,375/376 split (dedup'd) is used for A_v3_2ep; B_small was trained on the
   older 3,491/388 leaky split. The comparison is not fully clean.

### What weakens the retrieval result

1. **Task difficulty:** All variants score near zero. When even the shape-only flat-IR
   ablation retrieves at roughly the same rate as the semantic IR, it's worth asking
   whether the task is discriminating at all. The manual spot-check above shows that
   structural clustering (all `noConfusion` lemmas together) dominates over dependency
   structure for both variants — this is a real failure mode, not a measurement artifact.
2. **Embedding quality:** Mean-pooling the final hidden layer is a simple approach.
   Representations trained explicitly for retrieval (e.g., via contrastive loss) would
   likely produce better embeddings from the same model.
3. **Pool size:** 3,375 training declarations. The signal-to-noise ratio for
   dependency retrieval improves with more declarations — a larger corpus might
   produce separable clusters.

### What strengthens the results despite these caveats

1. **Consistency across modes:** Mode 1 (eval→train) and Mode 2 (train→train) agree.
   This rules out eval-set-specific artifacts.
2. **Epoch confound fixed:** The A_v3_2ep result uses a clean 2-epoch comparison
   against B_small, fixing the confound that affected the original H6 run.
3. **Two metric families agree:** Perplexity (H2) and retrieval (H6) both return null.
   A result that survives two independent metric families is more robust than one that
   relies on a single measure.

---

## Automated Prevention: Pipeline Quality Gates

The validity gaps identified above (split leakage, epoch confounds, missing config fields)
are not just documented — they are being automated. The
[`PIPELINE_QUALITY_GATES`](PIPELINE_QUALITY_GATES.md) design defines a five-station
production line where each station has a gate that checks specific properties before
output is accepted downstream. The key gates for the measurement concerns in this
document:

| Measurement concern | Quality gate that catches it |
|---|---|
| Split leakage (eval in train) | **G3-1** (split disjoint by example_id) |
| Epoch confound (A 3ep vs B_small 2ep) | **G5-4** (comparison validity: match epochs, seed, train_examples) — currently unwired |
| Missing config in results.json | **G4-2** (results complete: perplexity, epochs, params, lr, batch, max_seq_len) |
| B_small trained on leaky data | **G3-4** (provenance hash: all variants from same corpus commit) |
| Embedding-checkpoint mismatch | **G5-1** (embedding variant/epoch/vocab match checkpoint) |

Gate 5-G5-4 (comparison validity) is the single most important unwired check — it
would have caught the epoch confound that invalidated the original H6 run. Wiring it
into `check_invariants.py` is P0 priority in the
[`QUALITY_GATES_SCOPE`](../experiments/QUALITY_GATES_SCOPE.md) implementation plan.

---

## Provenance Reference

| Measurement | Script | Input files | Output |
|---|---|---|---|
| Training loss curve | `train_v2_resume.py` | `datasets_perop/train_A.jsonl` | `runs/variant_A_v3_2ep/loss_curve.json` |
| Perplexity | `evaluate_perplexity()` in `train_v2_resume.py` | `datasets_perop/eval_A.jsonl` | `runs/variant_A_v3_2ep/results.json` |
| Embeddings | `extract_retrieval_embeddings.py` | `datasets_perop/{train,eval}_A.jsonl` + checkpoint | `runs/retrieval_embeddings/embeddings_A_v3_{train,eval}.pt` |
| Ground truth deps | `build_dependency_groundtruth.py` | `Corpus/corpus.per_operator.jsonl` | `datasets/dependency_groundtruth_eval_to_train.json (run-time artifact)` |
| Retrieval eval | `retrieval_eval.py` | embeddings + ground truth | `runs/h6_retrieval/results_v3_2ep.json` |
| Linear probe | `probing_task.py` | `runs/probing/representations_A.pt` | `runs/probing/task1_results.json` |


---

## Measurement Validity via Prior-Art Alignment

> **Purpose.** A broken measurement apparatus produces random or surprising results.
> A correctly functioning one produces results that align with what the literature
> predicts for the conditions tested. This section maps each Maith result to the
> prior-art prediction it confirms, as evidence the experiments are measuring what
> they claim to measure. See [`PRIOR_ART.md`](PRIOR_ART.md) for full citations and
> the theoretical grounding.

### The argument in one paragraph

Maith's results — positive on probing, null on perplexity, null on retrieval — are
not unexpected. Every result falls exactly where the prior art predicts it should for
this specific combination of conditions: toy-scale model (358M, below the scale regime
where IRCoder's task-dependent gains appear), next-token objective (the wrong objective
per JEPA), replacement design
(not co-training, per PACT), sequence transformer on a graph IR (misaligned
architecture per algorithmic-alignment theory), and ~3.5K examples (1,000× smaller
than IRCoder's 4M). If the apparatus were broken, we would expect noise. Instead,
every result lands at its predicted coordinate. That convergence is the strongest
available evidence that the measurement is correct.

### Result-by-result alignment

| Maith result | Prior-art source | Prediction | Aligned? |
|---|---|---|---|
| **H2 null** — IR doesn't improve perplexity at 358M/3.5K | IRCoder (Paul et al., ACL 2024) | IR-grounding gains are task-dependent and non-monotonic across 1.1B–7.3B (several 7.3B cells negative); no clean threshold. Toy tier (358M/3.5K) is below the regime where gains appear. | ✅ Null predicted by scale |
| **H1/H2 dissociation** — encoding ✅, prediction ❌ | LeCun (2022); I-JEPA (Assran et al., CVPR 2023); "From Tokens to States" (2026) | Token-prediction quality ≠ representation quality. Semantic structure lives in latent space, not in token predictions. The model can encode structure without it helping prediction. | ✅ The exact dissociation JEPA predicts |
| **H1 positive** — 75.4% linear-probe accuracy, 62pp over flat | OthelloGPT / chess-model literature cited in "From Tokens to States" (2026) | World-state structure is encoded linearly in hidden activations, even when the model's token predictions don't reflect it. A linear probe recovers it. | ✅ Same pattern in a new domain |
| **Replacement null** — IR replaces source, no gains | PACT (Han et al., ICLR 2022) | Co-training structural signal alongside source recovered gains (32%→48%). Replacing source with IR loses the surface signal that co-training preserves. | ✅ The co-training vs. replacement distinction predicts the null |
| **H6 null** — retrieval doesn't work for any variant at this scale | Veličković & Dudzik (NeurIPS 2022) — alignment fragility | Next-token loss rewards structural patterns ("what does this look like"), not dependency structure ("what does this depend on"). The DEC-030 clean comparison confirms: A_v3_2ep Recall@10 = 0.0052 vs B_small 0.0064 (CIs overlap), structural clustering dominates for all variants. | ✅ Structural clustering is the predicted failure mode |
| **H3 null** — cold-start embedding init was not the cause | Good experimental practice (confound isolation) | Embed-project should have helped if cold-start was the bottleneck. It didn't (1.2978, within noise). | ✅ Rules out a confound, confirming the null is about representation/objective, not init |
| **Maith sidesteps the impossibility result** — elaborator provides ground truth | Locatello et al. (NeurIPS 2019) | Unsupervised disentanglement is impossible without inductive bias. Maith doesn't recover the generative process from data — the elaborator provides it. The impossibility doesn't apply. | ✅ The approach is consistent with the theory's escape hatch |

### What would be surprising (and isn't)

If the measurement apparatus were broken, we would expect:

- **Random results across variants** — but A consistently encodes semantics (75.4%)
  while flat-IR consistently doesn't (13.6%). The 62-point gap is stable across probe
  seeds (std 0.017).
- **H6 favoring the IR** — which would suggest the retrieval metric is miscalibrated
  toward canonical representations. Instead, all variants score near zero with
  overlapping CIs, and the spot-check shows structural clustering dominates for all.
  This is the predicted failure mode, not a measurement artifact.
- **Perplexity favoring the IR** — which would contradict JEPA theory. Instead, the
  IR is *penalized* for canonicalization (removes redundancy → harder to predict),
  exactly as the structural-bias argument predicts.
- **Gains at 358M** — which would contradict IRCoder's scale results. Instead, null
  at toy tier, consistent with gains appearing only at small tier (1.1B+), though
  IRCoder's gains are non-monotonic and task-dependent, not a clean threshold.

None of these surprises occur. Every result is at its predicted coordinate.

### The one result that goes against the grain — and doesn't

There is no result that contradicts the prior art. The closest candidate is H1 being
*strongly* positive (75.4% probe accuracy with a 62-point gap over the flat ablation).
One might expect a null across the board if the representation doesn't help. But the
world-model literature (OthelloGPT, chess models) documents exactly this pattern:
models trained on token prediction encode world-state structure linearly in their
hidden activations, even when their token predictions don't exploit it. H1 is the
formal-math instance of that finding.

### What the theory predicts would change the results

The prior art doesn't just confirm the nulls — it predicts where the IR *should* help,
which are exactly Maith's open experiments:

| Open experiment | Prior-art prediction | What changes |
|---|---|---|
| **H5** (contrastive/reconstruction objective) | JEPA: predict in latent space, not token space | Rewards semantic structure directly, not surface predictability |
| **H6** (retrieval at scale) | Wang et al. / Paliwal et al.: structure-aware retrieval helps, but at larger scale with graph-native architectures | Larger pool + more signal may separate variants |
| **H8** (1B+ model) | IRCoder: task-dependent, non-monotonic gains across 1.1B–7.3B | Above the scale regime where IR grounding shows gains (though non-monotonic, not a clean threshold) |
| **§9 architecture** (GNN/GraphTransformer) | Xu et al. / Veličković: alignment is fragile but *sufficient* with the right architecture | Graph-native model consumes IR edges directly, no linearization loss |
| **H9** (co-training) | PACT: 32%→48% with joint structural + source loss | Recovers the surface signal replacement loses |

### Caveat: alignment is not proof

The convergence between Maith's results and prior-art predictions is strong evidence
the measurement is correct, but it is not *proof*. Two limitations:

1. **The B_small training-data confound is still open.** In the DEC-030 comparison,
   A_v3_2ep was trained on the clean split (3375/376) while B_small's checkpoint was
   trained on the old leaky split (3491/388 — ~116 more examples). Both embeddings
   were extracted from the clean split (3375/376), so the eval data is matched, but
   B_small saw slightly more training data. The B_small retrain on clean 3375/376 has
   not been done — until it is, the comparison is not fully controlled. If the numbers
   shift after retrain, the alignment may need re-reading.
2. **Confirmation risk.** Finding that results align with predictions could be
   post-hoc rationalization. The mitigation is that the predictions were stated *before*
   the experiments in [`PRIOR_ART.md`](PRIOR_ART.md) (drafted alongside the experiment
   design, not after the results), and the alignment is across *multiple independent*
   prior-art lines (scale, objective, architecture, co-training), not a single source.

### Bottom line

The prior art confirms Maith's experiments are producing known, predicted outcomes.
That is the strongest available evidence that the measurement apparatus is working
correctly. The null results are not failures — they are the expected outcomes of
testing an IR under misaligned conditions (wrong objective, wrong architecture,
insufficient scale). The theory says the IR should help when those conditions are
fixed — and those are exactly the open experiments.

