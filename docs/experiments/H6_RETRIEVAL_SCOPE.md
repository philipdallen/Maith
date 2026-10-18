# H6 Retrieval Experiment — Scoping Document for Implementation

> **Purpose.** This document scopes the H6 (retrieval/similarity) experiment for a
> downstream implementation agent. It contains everything needed to build and run the
> experiment without re-deriving the design. It is a *specification*, not an
> implementation; the agent writes the code.
>
> **Context.** H6 is the one untested experiment-cell that is both tractable on current
> hardware (M4/16GB or a single CUDA GPU) and capable of producing an honest result
> either way. See [`HYPOTHESIS_GRID`](HYPOTHESIS_GRID.md) H6 and
> [`EXPERIMENT_DESIGN`](EXPERIMENT_DESIGN.md#evaluation-framework-the-correct-metrics-for-this-hypothesis)
> for the hypothesis-level framing. The central prediction claim (H2) is closed-negative;
> this is the complementary test on the *retrieval* task family, where canonicalization is
> an advantage rather than a penalty.

---

## 1. The experiment in one paragraph

For each trained variant (A, B-small, B, C, flat, random), extract per-declaration
embeddings by feeding that variant's *actual training input* through its trained
checkpoint and mean-pooling the final hidden layer. Then, for each eval declaration that
has ≥1 in-corpus dependency, rank the training-set declarations by embedding cosine
similarity and measure whether the declaration's true dependencies are retrieved near the
top. Compare recall@k and MRR across variants. The question: does Variant A (canonical
semantic IR) retrieve true dependencies better than size-matched BPE (B-small) and
full BPE (B)?

**This is premise selection** — the task family where the field's positive results live
(ReProver, Wang et al. 2017, the 2025 Lean graph-retrieval work). It is the right test
because canonicalization should make semantically related declarations more similar in
embedding space, which is exactly what retrieval rewards and next-token prediction does
not.

---

## 2. What is already built (do not rebuild)

| Asset | Location | Role |
|---|---|---|
| Trained checkpoints | `runs/variant_A_v2_full/checkpoint-final`, `runs/variant_B_small/checkpoint-final`, `runs/variant_B_phase6/checkpoint-final`, `runs/variant_C_phase6/checkpoint-final`, `runs/variant_flat/checkpoint-final` | The models whose embeddings are compared |
| Per-variant training inputs (integer token IDs) | `datasets/train_{A,B,B_small,C,flat}.jsonl`, `datasets/eval_{A,B,B_small,C,flat}.jsonl` | **Use these as the forward-pass input**, each carries the `input_ids` the variant was trained on |
| Full corpus with IR graphs + tokens | `Corpus/corpus.jsonl` | Source of dependency ground truth (`gen:<Name>` tokens reference other declarations) |
| Embedding extraction scaffold | `python/extract_representations.py` | Reusable model-loading + pooling logic; **but see the bug warning in §5** |
| Probing infrastructure | `python/probing_task.py`, `python/extract_representations.py` | The DEC-025 probing that this experiment extends from (different eval, same embeddings) |
| Manifests | `datasets/representation_manifest.json`, `datasets/train_manifest.json`, `datasets/eval_manifest.json` | Provenance: representation_id, seed=42, 3491 train / 388 eval |

**Do not re-train any model.** All checkpoints exist. The experiment is retrieval eval on
existing trained weights.

---

## 3. Dependency ground truth — construction spec

### 3.1 What counts as a dependency

A declaration D *depends on* declaration E if D's IR tokens contain `gen:<E>` (after
stripping the `gen:` prefix) AND E is a declaration in the corpus. This is extracted
directly from `Corpus/corpus.jsonl`'s `tokens` field — no Lean re-elaboration needed.

**Exclusions:**
- `gen:hof` and `gen:proj` are generic operation markers, not named-constant references. Strip them.
- A declaration's reference to itself (e.g., a recursive `rec`/`casesOn` mentioning its own name) does not count. Filter `E == D`.
- References to constants *not* in the corpus (external Mathlib declarations) are not retrievable from the training pool and must be dropped from the ground-truth set for this experiment. They are out-of-pool negatives by definition.

### 3.2 The two retrieval modes

The experiment supports two eval modes. **Implement both** — they answer slightly
different questions and the second is the cleaner test.

#### Mode 1: eval → train (the headline test)
- **Query set:** the 388 eval declarations.
- **Candidate pool:** the 3,378 train declarations.
- **Ground truth per query:** the query's `gen:` references that resolve to train
  declarations.
- **Feasibility (measured from the actual data):** 294 / 388 eval declarations have ≥1
  dependency in train (76%); mean 3.53 in-train deps; median 3; max 26. This is a healthy
  query set — enough for stable recall@k estimates.
- **What it tests:** can a model trained on the train set retrieve, for a held-out
  declaration, the train declarations it depends on? This is the closest analogue to
  real premise selection (the query is unseen at training time).

#### Mode 2: train → train (sanity / density check)
- **Query set = candidate pool:** the 3,378 train declarations (leave-one-out: a
  declaration is not its own candidate).
- **Ground truth per query:** its `gen:` references that resolve to *other* train
  declarations.
- **Feasibility:** 2,731 / 3,491 train declarations are queryable (78%).
- **What it tests:** retrieval density on seen data. If a variant can't retrieve deps it
  was trained on, it can't retrieve anything and Mode 1's null is explained by
  memorization limits, not representation. Use this to calibrate Mode 1.

### 3.3 Known split caveat — handle it

The train/eval split has **13 name collisions** (same short declaration name in different
modules, e.g. `Set.Ici.lattice._proof_3` appears in both splits as distinct
declarations). This is a pre-existing property of the split, not introduced by this
experiment. For retrieval:
- Match dependencies by **full corpus `name`**, not by the short `name` field alone —
  the `name` in `corpus.jsonl` is already the full declaration name and is unique within
  the corpus (3,901 unique names across 4,029 records; the duplicates are the same
  declaration extracted once — de-duplicate by `name` before building the candidate
  pool).
- **Do not** filter the 13 collisions out; just ensure dependency matching uses the full
  name and that the candidate pool is de-duplicated so each declaration appears once as a
  candidate.

---

## 4. Embedding extraction spec — the critical correctness requirement

### 4.1 The bug to avoid

The existing `python/extract_representations.py` feeds `ex["tokens"]` (the **IR token
list**) to *every* variant, including B and C. This is correct for DEC-025's
representation probing of the IR, but it is **wrong for H6**: B and C were trained on
`leanExpr` text and AST-split text respectively, not on IR tokens. Feeding IR tokens to a
B/C checkpoint produces meaningless embeddings for those variants and would make the
A-vs-B comparison invalid (A gets its trained input; B/C get an input distribution they
never saw).

**The fix:** extract each variant's embeddings from the `input_ids` field of that
variant's own dataset file (`datasets/eval_{variant}.jsonl` for the query embeddings,
`datasets/train_{variant}.jsonl` for the candidate-pool embeddings). These files already
contain the exact integer token sequences each model was trained on. Feed `input_ids`
directly to the model (no re-tokenization, no string round-trip), mean-pool the final
hidden layer, save per-variant tensors of shape `[N, 896]`.

### 4.2 Per-variant extraction recipe

For each variant V ∈ {A, B_small, B, C, flat, random}:
1. Load checkpoint `CHECKPOINTS[V]` (or base `Qwen/Qwen2.5-Coder-0.5B` for `random`).
2. Load the matching tokenizer from the checkpoint dir.
3. For each record in `datasets/eval_V.jsonl` (query embeddings) and
   `datasets/train_V.jsonl` (candidate embeddings): take `input_ids`, truncate to
   `MAX_SEQ_LEN=512`, forward-pass with `output_hidden_states=True`, mean-pool
   `hidden_states[-1]` over the (non-padding) sequence dimension.
4. Save two tensors per variant: `retrieval_embeddings_{V}_eval.pt` (shape
   `[388, 896]`) and `retrieval_embeddings_{V}_train.pt` (shape `[~3378, 896]`).
   Also save the `name` ordering alongside (`eval_names_{V}.json`,
   `train_names_{V}.json`) so embeddings can be aligned to ground truth.

**Important:** the `name` field in each dataset record is the full declaration name and
is the join key to the corpus dependency graph. Preserve ordering exactly.

### 4.3 Reuse what you can

The model-loading, device selection, NaN-check, and pooling helpers in
`extract_representations.py` are reusable. The only change is the input source: replace
`" ".join(ex["tokens"])` + re-tokenize with direct `input_ids` from the per-variant
dataset file. Consider adding a new script `python/extract_retrieval_embeddings.py`
rather than modifying the probing extractor (the probing one must keep its current
behavior for DEC-025 reproducibility).

---

## 5. Retrieval evaluation spec

### 5.1 Metrics

For each query declaration q with ground-truth dependency set G_q (non-empty) and
candidate pool C:

- **Recall@k** (k ∈ {1, 5, 10, 20}): fraction of G_q in the top-k retrieved candidates
  by cosine similarity. Average over all queryable queries.
- **MRR (Mean Reciprocal Rank):** average of 1/rank of the *first* retrieved true
  dependency. Standard IR metric.
- **Recall@k normalized by pool size:** report pool-size alongside so A vs B-small vs B
  (same pool, but different embedding spaces) are comparable. Pool is identical across
  variants (same 3,378 train declarations); only the embedding space differs.

### 5.2 The comparison (the actual hypothesis test)

| Comparison | What it isolates | Gate |
|---|---|---|
| A vs B-small | Representation (semantic IR vs BPE) at matched 358M params / 601-vocab | **A Recall@10 > B-small Recall@10 by a meaningful margin → H6 positive** |
| A vs B | Representation + size (A 358M vs B 494M) | Secondary; size confound present |
| A vs C | Representation (semantic IR vs AST-split BPE) | Secondary |
| A vs flat | A vs shape-only IR ablation | Confirms semantics (not structure) drives any A win |
| A vs pretrained | Fine-tuned vs pretrained (un-fine-tuned) baseline | Sanity: pretrained should be near chance |

**Primary gate: A vs B-small on Recall@10, Mode 1.** This is the size-controlled
representation test, mirroring the DEC-027 B-small control that made H2's null
interpretable. If A > B-small by a meaningful margin (define "meaningful" before
running — suggest ≥2pp Recall@10 + non-overlapping bootstrap CIs), H6 is positive: the
canonical semantic graph IR helps dependency retrieval where it did not help prediction. If
A ≈ B-small, H6 is negative: at this scale, canonicalization doesn't produce more
useful retrieval embeddings than BPE, and the project's reachable evidence is a clean
characterization (encodes semantics, doesn't beat BPE on prediction or retrieval at toy
scale).

### 5.3 Statistical reporting

- Report point estimates **and** 95% bootstrap confidence intervals (resample queries,
  1000 resamples) for Recall@k and MRR, per variant, per mode. The n is 294 (Mode 1) /
  2731 (Mode 2) — large enough for stable CIs.
- Report a paired comparison: for each query, does A rank its deps higher than B-small?
  A paired bootstrap over queries is the right test, not a two-sample test, because the
  same queries are evaluated under both variants.

### 5.4 The confound to acknowledge (do not hide it)

A's IR tokens *contain* the dependency names as literal tokens (`gen:AddMonoid` is a
token in the declaration that depends on `AddMonoid`). BPE embeddings encode surface
substrings, which include the name but not as a discrete semantic unit. This means the
test is **somewhat loaded in IR's favor** for *directly-referenced* dependencies: A can
retrieve deps partly because the dep name is a clean token, while B must match surface
substrings. A positive is real but should be read with this grain of salt — it is
evidence that the IR's explicitness helps retrieval, not pure evidence that the IR's
*semantic canonicalization* helps. State this in the results writeup. A negative, by
contrast, is a strong signal: if IR can't win even with the dep name as a clean token,
the representation isn't producing useful semantic embeddings.

---

## 6. Deliverables

1. `python/extract_retrieval_embeddings.py` — per-variant embedding extraction from
   `input_ids` (fixing the §4.1 bug; does not modify the probing extractor).
2. `python/build_dependency_groundtruth.py` — parses `Corpus/corpus.jsonl`, emits
   `datasets/dependency_groundtruth.json (built by build_dependency_groundtruth.py)` mapping each declaration name → set of
   in-corpus dependency names (per the exclusions in §3.1).
3. `python/retrieval_eval.py` — loads embeddings + ground truth, computes Recall@k / MRR
   per variant for Mode 1 and Mode 2, emits `runs/h6_retrieval/results.json` with
   point estimates + bootstrap CIs + paired bootstrap p-values (A vs B-small).
4. `docs/experiments/H6_RESULTS.md` — results table, the A-vs-B-small verdict, the
   §5.4 confound acknowledgment, and a one-line update to
   [`HYPOTHESIS_GRID`](HYPOTHESIS_GRID.md) H6 (status → ✅/❌ with DEC ID).
5. A `DEC-0xx` entry in `docs/decisions/LOG.md` recording the result.

---

## 7. What "done" looks like

- All five variants' embeddings extracted from their actual training inputs (not IR
  tokens), saved with name-ordering.
- Dependency ground truth built from `Corpus/corpus.jsonl`, exclusions applied.
- Recall@{1,5,10,20} + MRR reported for Mode 1 (eval→train) and Mode 2 (train→train)
  for all variants, with bootstrap CIs and a paired A-vs-B-small test.
- `H6_RESULTS.md` states the verdict against the gate in §5.2 and acknowledges the §5.4
  confound.
- `HYPOTHESIS_GRID.md` H6 row updated; `LOG.md` has a new DEC entry.

**Time estimate:** 2–4 focused days. Embedding extraction is ~1–2 hours of compute on
MPS (the model is 0.5B, the corpus is 4K examples × 6 variants); the ground-truth
builder is ~50 lines of Python; the eval is ~100 lines; analysis and writeup are the
remainder.

---

## 8. What this experiment does *not* settle

- It does not test ATP success (H7) — that requires a prover loop and is above the
  compute ceiling.
- It does not test scale (H4/H8) — same 0.5B model, same 3.5K corpus.
- It does not test objective redesign (H5) — same next-token-trained weights, just a
  different *eval* on top of them.
- A positive is evidence the IR helps *retrieval at toy scale*, not that it helps
  theorem proving at large scale. Read accordingly.

This is the one experiment the project can run that produces an honest result either
way at the project's compute scale. Run it, then write up and close out per the gate in §5.2 — do not let it become the entry to a new chase.
