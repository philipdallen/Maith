# A/B/C Experiment Design

> **v2 era (2026-08-09).** The current IR is `semantic_graph_ir_v2_0_0`
> (C1+C2+C4, vocab 601). Variant A v2 = perplexity 1.2361 / top-1 90.0%.
> See `docs/experiments/V2_COMPARISON_MATRIX.md` for the live 2×2 control grid
> and `docs/experiments/V2_NEXT_STEPS.md` for the merge-to-main checklist.
> The v1.x content below (variants table, Phase 5/6 results) is **historical** —
> retained as the record of how the protocol was developed, not the current
> experiment state. The protocol sections (hyperparameters, eval, "what a valid
> result looks like") remain authoritative and are **fixed across IR candidates**
> so that every candidate — a v2.x variant, a v3 redesign, or an experimental tweak — is
> directly comparable. The goal is a search for a reasonably optimized IR that supports
> the representation hypothesis, not a sequence of numbered versions.

---

## Standard protocol — fixed across all IR candidates

This is a **search** for an IR representation that supports the hypothesis (that models
trained on semantic structure learn math more efficiently). The unit of work is an
**IR candidate** — a concrete token configuration (e.g. v2.0.0, a v2.1 tweak like
revised GEN buckets, or a v3 redesign). We don't know yet whether the answer is a
refined v2 or a new design; the protocol below keeps every candidate comparable so
the search can proceed without re-baselining.

These elements are **frozen** so that any IR candidate produces results directly
comparable to v2. Do not change them between candidates; if a protocol change is ever
needed, version it separately and re-baseline.

### Eval protocol (fixed)
- **Metric:** top-1 next-token completion accuracy (teacher-forced, last N tokens masked).
- **Sample count:** 200 eval examples.
- **Mask-last:** 10 tokens.
- **Checkpoint selection:** always pass an explicit `--checkpoint-<X> <authoritative run dir>`.
  Never rely on the default `runs/variant_X/` path (stale-checkpoint bug — see
  `docs/scratch/runs_audit.md`, `docs/scratch/variant_c_eval_bug.md`). The
  `eval_completion.py` stale-checkpoint guard warns if `results.json` mtime is >1d off
  from the checkpoint weights.
- **Command template (identical for every variant/IR version):**
  ```bash
  python3 python/eval_completion.py \
    --variants <X> --checkpoint-<X> runs/<authoritative_dir> \
    --samples 200 --mask-last 10
  ```
- **Primary metric:** perplexity on the held-out eval split (lower = better).
- **Secondary metric:** completion accuracy (top-1, last 10 masked).

### Comparison structure — the 2×2 control matrix (standard template)

Every IR candidate gets **its own comparison matrix** (e.g.
`docs/experiments/V2_COMPARISON_MATRIX.md`, or a V2_1_COMPARISON_MATRIX.md / V3_COMPARISON_MATRIX.md for a later candidate (names hypothetical) in the same format as
`docs/experiments/V2_COMPARISON_MATRIX.md`. The 2×2 grid (representation × model
size) is the standard template:

| | Narrow-vocab (matching IR-vocab params) | Full-vocab (full BPE params) |
|---|---|---|
| **IR vocab (candidate)** | **IR-X** (the candidate) | **IR-X-large** (ceiling) |
| **BPE vocab (control)** | **B-small** (size control) | **B** (full baseline) |

- The **B-small** cell is the critical control for any IR candidate: it isolates
  whether the IR's competitiveness comes from semantic structure or merely from a
  small vocabulary / small embedding table.
- **Gate (general):** IR-X vs B-small at matched params. If IR-X > B-small by a
  meaningful margin, the representation is doing work beyond vocab compression.
- When adding a new candidate (whether a v2.x tweak or a v3 redesign), create a new
  `docs/experiments/<CANDIDATE>_COMPARISON_MATRIX.md` using the same structure, and
  link it from `docs/decisions/INDEX.md`. The candidate's IR version is recorded in
  `datasets/representation_manifest.json` (`representation_id`).

**When baseline cells must be re-run vs carried over:**

Each IR candidate needs its own grid because the baseline cells are only valid
if the underlying data and size-match haven't changed. The rules:

| What changed in the new candidate? | A (IR) | B-small | B, C (large baselines) |
|---|---|---|---|
| Tokenization only (same corpus, same vocab size) | Re-run | **Carry over** — same BPE, same size match | **Carry over** — same declarations, same BPE |
| Vocab size changed (e.g. 601 → 800) | Re-run | **Re-run** — re-truncate BPE to the new vocab size via `build_b_small_vocab.py` | **Carry over** — B/C use full 151k BPE, unaffected by IR vocab size |
| Corpus changed (new modules, different filtering, different split) | Re-run | **Re-run** — new train/eval data | **Re-run** — new train/eval data; the declarations changed |
| Corpus expanded (more examples, same modules + split) | Re-run | **Re-run** — new train data | **Re-run** — new train data |

**Why this matters:** without these rules, a future contributor might reuse v2's
B/C/B-small numbers for a v3 candidate that changed the corpus, producing an
invalid comparison (v3 IR tokens vs v2-era BPE on different declarations). The
grid is the template; the cells are re-evaluated per candidate per the table above.

**Provenance check:** before carrying over any baseline, verify the candidate's
`datasets/representation_manifest.json` (train_examples, eval_examples, seed)
matches the baseline's `results.json`. If train_examples or eval_examples differ,
the corpus changed — re-run everything.

### Hyperparameters (fixed across IR candidates)
| Parameter | Value | Rationale |
|-----------|-------|----------|
| Base model | Qwen2.5-Coder-0.5B (MPS) / 1.5B (CUDA) | Small enough to train locally; code-aware |
| Max sequence length | 1,536 (train cap 512 for stability) | Covers variant A p99 with headroom |
| Batch size | 1 (effective 32 with grad accum 8 → grad_accum=8) | Fits in 16GB VRAM |
| Learning rate | 2e-4 (A); B/C reduced to 5e-5 (stability) | Standard for small fine-tunes |
| LR schedule | Cosine with warmup (5%) | |
| Epochs | 2 (A/IR candidates); B/C historically 3 | Matched to A for fair comparison |
| Optimizer | AdamW, weight decay 0.01 | |
| Seed | 42 | Fixed across all variants and IR candidates |
| Eval metric | Perplexity on eval split (primary); top-1 completion (secondary) | |

> **Base model scope condition (2026-08-12).** Qwen2.5-Coder-0.5B is a **fixed condition**
> of the current experiment, not a variable being tested. All variants (A, B_small, flat)
> share the same base model — the only thing that differs is the input representation.
> This controls for base model quality while isolating representation.
>
> **Why Qwen2.5-Coder-0.5B:**
> - **Code pretraining is the right prior.** Lean is a programming language; formal math
>   has code-like structure. The S1 sanity check confirmed the pretrained model has
>   retrieval signal (Recall@10 ≈ 0.072) specifically from code pretraining.
> - **Size is intentional (toy tier).** The question is "does the IR encode semantics?"
>   (H1) and "does IR fine-tuning beat BPE fine-tuning?" (H6), not "does a bigger model
>   do better?" Scale is tested separately in H4/H8.
> - **Consistent with prior art.** IRCoder (the closest positive result) also fine-tuned
>   a code-pretrained model (CodeLlama) on IR.
> - **Supports custom vocab resizing.** IR variants need custom vocabularies (601, 2254
>   tokens). Qwen2.5-Coder supports embedding table resizing cleanly.
>
> **When a different model would be appropriate:**
>
> | Hypothesis | Model to use | Why |
> |---|---|---|
> | H4/H8 (scale) | Qwen2.5-Coder-1.5B or 3B | Same family, next tier up. Tests whether IR gains appear at larger scale. |
> | H12 (architecture) | GNN / GraphTransformer | Different architecture class. The IR is a graph; a sequence transformer is misaligned. |
> | H7 (ATP) | Lean-specific prover (DeepSeek-Prover, Kimina) | Different task (proof search). Not a representation comparison. |
>
> Results do not generalize beyond "Qwen2.5-Coder-0.5B fine-tuned on Maith's IR" without
> re-testing. The within-model comparison (A vs B_small) is valid regardless of base model
> choice.

### What a valid result looks like (unchanged)
- **IR < B and IR < C**: IR tokens improve sample efficiency — representation hypothesis has preliminary support.
- **IR ≈ B**: IR tokens are no better than raw Lean source at this scale.
- **IR > B**: IR tokens hurt. Investigate vocab/format.
- **Always pair with B-small** to rule out the size confound before claiming the hypothesis.

### What this experiment does NOT prove (unchanged)
- That IR tokens improve theorem-proving performance (requires downstream prover eval).
- That results generalise beyond the modules in the current corpus.
- That the effect holds at scale (larger corpus, larger model).

---

## v2 result summary (DEC-026)

| Variant | Representation | Vocab | Params | Perplexity | Top-1 Acc |
|---|---|---|---|---|---|
| A (v2, C1+C2+C4) | Semantic IR graph → tokens | 601 | 358M | 1.2361 | 90.0% |
| B | Raw leanExpr → Qwen BPE | 151,643 | 494M | 1.107 | 91.7% |
| C | AST-style → Qwen BPE | 151,643 | 494M | 1.098 | 93.0% |
| B-small (DEC-027) | BPE truncated to 601 | 601 | 358M | *(in progress)* | *(in progress)* |

A beats the C1+C2 partial (1.2458 → 1.2361, so C4 helped) but still trails B/C.
DEC-027 (B-small) is the open control that isolates representation from size.
See `docs/decisions/LOG.md` DEC-026 for the full record.

---

# Historical: v1.x experiment design

> The v1 comparison grid is preserved at [V1_COMPARISON_MATRIX.md](V1_COMPARISON_MATRIX.md) —
> it illustrates the confounds (no size control, epoch mismatch) that motivated v2. (Phase 5/6)

> The sections below are the original v1.x design record (variants table, Phase 5/6
> results, confound investigations). They are retained as history. The current
> experiment uses the v2 values above; do not read the v1 variants table as current.

> **Phase 6 complete (DEC-020, 2026-08-02). DEC-006 closed (DEC-021, 2026-08-03).**
> A trails B/C by ~0.17pp across Phase 5, Phase 6, and embedding projection experiment.
> Gap is not due to cold-start initialisation (DEC-021), sequence length (IR is 2x shorter
> than BPE), or Qwen pretraining prior (25.8% vocab overlap). v1.3.0 IR retraining in
> progress — polarity removed, casesOn/recOn normalised. See `docs/history/PHASE_7_ROADMAP.md`
> for current status and next steps.

Controlled comparison of three input representations for next-token prediction on Mathlib IR.

## Variants (v1.x — historical)

| Variant | Representation | Tokenizer | Vocab size |
|---------|---------------|-----------|------------|
| A | Maith IR tokens (v1.3.0) | Custom (`vocab_A.json`) | 8,144 |
| B | Raw `leanExpr` string | Qwen2.5-Coder BPE | tokenizer: 151,643 / model embeddings: 151,936 |
| C | AST-style split `leanExpr` | Qwen2.5-Coder BPE | tokenizer: 151,643 / model embeddings: 151,936 |

Datasets: `datasets/train_*.jsonl` / `datasets/eval_*.jsonl` (2,213 train / 246 eval, seed=42 — rebuilt for v1.3.0).

## Known confound: embedding table size

Variant A uses an 8,102-token embedding table. Variants B and C use a 151,643-token table.
A model trained on A with a small embedding table is not the same total parameter count as
one trained on B/C with the full Qwen vocab.

**Resolution — choose one and document it:**

**Option 1: Hold architecture fixed (recommended for first run)**
Use the same base model architecture for all three variants. For variant A, replace only the
tokenizer and embedding/unembedding layers with ones sized to 8,102 tokens. All other layers
(attention, FFN, norms) are identical. This controls for architecture while allowing the
embedding table to differ — which is exactly the variable being tested.

**Option 2: Hold parameter count fixed**
Size variant A's embedding table to match B/C's parameter count by using a larger hidden dim
or more layers. More complex to implement and harder to interpret.

**Recommended: Option 1.** The research question is whether the representation improves
learning, not whether a smaller embedding table is faster. Holding architecture fixed and
letting the embedding table reflect the actual vocab is the cleanest test.

## Model-size taxonomy

The field uses rough parameter-count bands to classify models. Maith's variants all fall
in the **toy** tier — this is a deliberate constraint (consumer M4/16GB hardware), not an
oversight, but it means results are not directly comparable to work at small/frontier
scale without accounting for the gap.

| Tier | Parameter range | Examples | Maith's position |
|---|---|---|---|
| Toy / micro | <1B | Qwen2.5-Coder-0.5B, Pythia-160M | **All Maith variants** (358M–494M; same 0.5B base) ¹ |
| Small | 1B–8B | Qwen2.5-1.5B, Llama-3-8B, Phi-3-mini | Not tested — IRCoder's gains are task-dependent and non-monotonic here (1.1B–7.3B); no clean threshold |
| Medium | 8B–30B | CodeLlama-13B, Qwen2.5-14B | Not tested |
| Large | 30B–100B | Llama-3-70B, Qwen2.5-72B | Not tested |
| Frontier | 100B+ (often 500B+ with MoE) | GPT-4-class, Claude-class, Gemini-class | Not tested |

**Key distinction for interpreting Maith's results:** the 2×2 comparison matrices
([V1](V1_COMPARISON_MATRIX.md), [V2](V2_COMPARISON_MATRIX.md)) label their axes
"Narrow-vocab" and "Full-vocab" — not "Small model" and "Large model" — because the
parameter difference between columns is **embedding-table size** (601 vs 151K tokens),
not transformer capacity. The attention heads, FFN layers, and hidden dimensions are
identical across all variants (same Qwen2.5-Coder-0.5B base). The ~136M parameter gap
is `(151,643 − 601) × 896 ≈ 135.5M` embedding rows.

**What this means for scale claims (H4/H8):** "Open at larger scale" means open at larger
*transformer capacity* (a 1B+ base model with correspondingly more attention/FFN
capacity), not just a bigger embedding table on the same 0.5B base. Varying embedding-table
size within a single 0.5B base — which is what Maith's grid does — tests vocabulary
representation, not model-capacity scaling.

> ¹ "0.5B base" refers to the model name (Qwen2.5-Coder-**0.5B**), not the parameter count
> after vocab resize. The base model ships with ~494M params (including its 151K-token
> embedding table); after resizing the embedding table to Maith's 601-token IR vocab,
> Variant A drops to ~358M. The transformer layers (attention, FFN, norms) are unchanged.

## Hyperparameters (fixed across all variants)

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Base model | Qwen2.5-Coder-0.5B (MPS) / 1.5B (CUDA) | Small enough to train locally; code-aware |
| Max sequence length | 1,536 | Covers variant A p99 (1,252) with headroom |
| Batch size | 8 (effective 32 with grad accum 4) | Fits in 16GB VRAM |
| Learning rate | 2e-4 | Standard for small fine-tunes |
| LR schedule | Cosine with warmup (5%) | |
| Epochs | 3 | Enough to compare without overfitting |
| Optimizer | AdamW, weight decay 0.01 | |
| Seed | 42 | Fixed across all three runs |
| Eval metric | Perplexity on eval split | Primary comparison metric |

Current execution note (stabilization pass): due observed B/C instability (`NaN` eval on a prior non-smoke B run),
the active rerun uses a bounded profile in `python/train.py`:
- 1 epoch for A/B/C
- train sequence caps: A=1024, B=512, C=512
- B/C learning rate reduced to `5e-5` with warmup ratio `0.10`
- explicit `max_grad_norm=1.0`, periodic cache clears, and non-finite loss/perplexity hard-fail guards

### v1 → v2 IR optimization assessment

The v2 IR (C1+C2+C4) was designed to improve on v1 by removing structural noise and
reducing vocabulary size. The optimization theory was partially confirmed, with a critical
caveat:

**Confirmed:**
- v1 had structural noise. DEC-024's flat-IR ablation confirmed ~40-50% of v1 tokens were
  noise (polarity markers, IO markers, rare unique tokens).
- Removing noise improved perplexity. v1.4.0 (1,236-vocab) achieved 1.2751; v2 (601-vocab)
  achieved 1.2361 — a real improvement.
- C4 (GEN module bucketing) helped: C1+C2 alone got 1.2458; adding C4 got 1.2361.

**Not confirmed:**
- Optimization did not close the gap to BPE. A (v2, 1.2361) still trails B-small
  (size-matched BPE, 1.1294) by 0.11 perplexity points.
- The theory that a cleaner IR would be more learnable under next-token prediction is only
  partially true — it's more learnable than v1, but not more learnable than BPE.

**Not tested:**
- C3 (attribute sparsity) — deferred; needs a Lean cross-check. An untested v2.x candidate.

**The critical contradiction:**
DEC-024 found that the IR's semantic content adds ~0.27 bits/token of prediction difficulty.
This means v2's perplexity improvement came partly from *removing* semantic content
(polarity tokens, rare unique tokens via C4 bucketing) — which is the opposite of the
hypothesis's goal of making the representation more semantically rich. Optimizing the IR
for perplexity is partially contradictory with optimizing it for semantic utility: you can
make the IR more predictable by stripping semantics, but that may strip the value.

**Implication for future IR candidates:** an IR candidate that improves perplexity is not
necessarily a better semantic representation — it may simply be a more predictable one.
Future IR candidates should be evaluated on non-prediction metrics (retrieval, probing,
ATP) alongside perplexity, not on perplexity alone. See the experiment-scope matrix in
[`HYPOTHESIS_GRID`](HYPOTHESIS_GRID.md).

## Evaluation

Primary metric: **perplexity on held-out eval split** (lower = better).

Secondary metrics (if time permits):
- Next-token accuracy at positions 1, 5, 10 (how quickly does the model "get" the graph?)
- Perplexity stratified by sequence length bucket (short/medium/long graphs)
- Perplexity on the `BVAR_*`/`TERM_*` positions specifically (variant A) vs equivalent positions in B/C

### What perplexity measures — and what it doesn't

**What perplexity measures:** how predictable the next token is. Lower = the model is less
surprised. It is a prediction-family metric — it rewards the model for correctly guessing
what comes next in the token stream.

**What perplexity does not measure:** whether the model's representations contain useful
semantic structure, whether the representation helps with any task beyond prediction, or
whether the model "understands" the mathematics. A model can achieve low perplexity by
learning surface statistical patterns without encoding meaning.

**Why this matters for the IR:** semantic tokens are inherently less predictable than
syntactic tokens. They carry information that depends on *meaning* (what does this entity
represent? what typeclass is in play? what is this declaration's semantic role?), not on
*what came before in the token stream*. DEC-024 found that the IR's semantic content adds
approximately 0.27 bits/token of prediction difficulty above what shape alone requires.

**The optimization contradiction:** this means optimizing the IR for perplexity is partially
contradictory with the hypothesis's goal. Making the IR semantically richer (the whole point)
makes perplexity *worse*, because richer tokens are harder to predict. The v2 improvements
(C1 polarity removal, C4 GEN bucketing) improved perplexity partly by *removing* semantic
content — polarity tokens and rare unique tokens — which is the opposite of making the
representation more semantically useful. See the v1→v2 optimization assessment below.

**Implication:** perplexity is a necessary but insufficient metric. A complete evaluation
requires non-prediction metrics (retrieval, probing, ATP) that measure whether the IR's
semantic structure translates to task-level advantage. The probing experiment (DEC-025)
confirmed that the IR's semantics are encoded in representations despite not helping
perplexity — but encoding is a necessary condition, not proof of task benefit (see
[`HYPOTHESIS_GRID`](HYPOTHESIS_GRID.md) H1 vs. H6/H7).

### Why prediction metrics are structurally biased toward natural language

The perplexity null raises a philosophical question: if a deliberately designed
representation can't beat evolved natural language at predictability, does that mean natural
language is already the optimal way to store knowledge? That conclusion would be
astronomically improbable — and the improbability is the clue that the metric is circular.

Natural language is highly predictable not because it's semantically optimal, but because
it's *redundant*. It's full of conventions, formulaic patterns, and surface variation that
constrains what comes next. When Lean source has 50 syntactic ways to express the same idea,
each with its own predictable token patterns, the model can exploit those patterns. The IR
canonicalizes to one form — removing the surface variation, which is semantically cleaner
but statistically less predictable.

This means prediction metrics are structurally biased toward natural language's properties
(redundancy, convention, predictability) and against the IR's design goal (canonicalization,
uniqueness, explicitness). Evaluating a semantic representation with a metric that favors
redundancy is circular: you'll always conclude that the most redundant representation — raw
text — is best. The IR being harder to predict is evidence it's doing its job (compressing
away ambiguity), not evidence it's a worse representation.

**But the bias has two components — and only one is fundamental.**

The bias against the IR on perplexity is partly **fundamental** (canonicalization
inherently removes surface variation, so a canonical form will always be less predictable
than raw text) and partly **contingent** (the current IR designs haven't included the
*right kind* of redundancy). These are different claims with different implications:

- **Fundamental:** no canonical IR can match raw text on perplexity, because
  canonicalization removes the multiple surface forms that make text predictable. This
  is settled.
- **Contingent:** v1's verbosity was structural noise (polarity tokens, IO markers —
  predictable but meaningless, ~40-50% of tokens per DEC-024), not semantic redundancy.
  v2 removed the noise but didn't add anything in its place. Neither v1 nor v2 tested
  whether a well-designed canonical form could include redundancy that is *both*
  semantically meaningful *and* contextually predictable.

Natural language has **semantic redundancy**: multiple surface forms for the same meaning,
each constrained by convention ("therefore" → conclusion; "by" → theorem name). This is
redundancy *between meaningful tokens* — it helps prediction without adding ambiguity.

v1 had **structural verbosity**: constant markers (neut, IN_, OUT_) and rare unique strings
(gen:Mathlib.Algebra.Group.Basic.add) that were either trivially predictable or
fundamentally unpredictable, but in neither case semantically useful. This is verbosity
*scaffolding meaningful tokens* — it pads the sequence without helping the model predict
the meaningful parts.

**Implication for a v3 IR candidate:** the design goal would be tokens that are *both*
semantically meaningful *and* contextually predictable — every token carries information
about what the entity/relation/operation IS, AND constrains what comes next. Examples:

- Instead of bare `TERM_3`, use a typed entity token like `TERM_RING_ELEM_3` — the type
  constrains what operations follow (predictable) and carries semantic information (meaningful)
- Instead of generic `GEN_ALGEBRA`, use operation-specific buckets like `GEN_ASSOC`,
  `GEN_COMM`, `GEN_DIST` — more informative, and the preceding typeclass context constrains
  which operation is likely
- Instead of `eq`, use typed relations like `eq_on_Nat`, `eq_on_Ring` — the type is
  predictable from context and carries semantic information

The design principle: **every token should carry semantic information that also constrains
what comes next.** That's what natural language does — "the" tells you a noun is coming
(predictable) AND marks definiteness (meaningful). v1's "neut" was predictable but
meaningless. A v3 typed token would be both.

This doesn't guarantee perplexity parity — the fundamental component (canonicalization
removes surface variation) still applies. But it could narrow the gap, making perplexity
*partially informative* as a secondary metric. Primary evaluation remains retrieval/probing/ATP.

### Evaluation framework: the correct metrics for this hypothesis

Given that prediction metrics are structurally biased (above), the hypothesis requires
evaluation on metrics that measure what the IR was designed to provide — semantic utility,
not predictability.

| Metric family | What it measures | Why it's the right test | Status |
|---|---|---|---|
| **Retrieval / similarity** | Can the model find semantically relevant declarations? | Tests the IR's canonicalization advantage directly: if two declarations mean the same thing, their IR should be similar; their surface text may not be. This is the IR's core value proposition. | Untested (H6) |
| **Richer probing** | Does the model encode semantic structure beyond surface patterns? | Tests representation quality, not prediction quality. DEC-025 showed a 62-point gap on module classification; richer probes would confirm the gap generalizes to other semantic distinctions. | Partial (H10) |
| **Downstream task (ATP, proof completion)** | Does the IR help the model actually do mathematics? | The actual research claim — "improves formal math tooling" means tools that prove, complete, and search. This is the only metric that can definitively close the hypothesis. | Untested (H7) |
| **Objective redesign** | Does a different training loss reward the IR's semantics? | Tests whether the bottleneck is the objective, not the representation. If the IR wins under masked-reconstruction but not next-token, the objective was the problem. | Untested (H5) |

**How we know these are better than perplexity** (three layers):

1. **Theoretical:** perplexity measures predictability (redundancy exploitation), not
   semantic utility. The IR trades redundancy for canonicalization. The metric and the
   representation are misaligned by design — see the circularity argument above.
2. **Empirical:** DEC-024 showed semantic content adds 0.27 bits/token of prediction
   difficulty. DEC-025 showed the IR encodes 62pp more semantic content. Together: the IR
   is doing what it's supposed to (encoding semantics) and being penalized for it by the
   metric.
3. **Precedent:** IRCoder — the positive counterpart in the code domain — evaluated on task
   metrics (code completion, understanding, instruction following), not just perplexity.
   Their gains appeared on tasks where structural representation helps, not on raw
   prediction. See [`PRIOR_ART.md`](../reference/PRIOR_ART.md) §2.

**What perplexity is still useful for:** confirming the model learned *something* from the
training data (a sanity check that training worked). It is not a valid arbiter of the
hypothesis. Future IR candidates should report perplexity for completeness but should not
be judged on it.

## What a valid result looks like

- **A < B and A < C**: IR tokens improve sample efficiency — the representation hypothesis has
  preliminary support.
- **A ≈ B**: IR tokens are no better than raw Lean source at this scale. May indicate the model
  is large enough to handle BPE fragmentation, or that the 2,459-example corpus is too small
  to show a difference.
- **A > B**: IR tokens hurt. Investigate: is the custom vocab too small? Is structural
  information lost in the encoding?

## What this experiment does NOT prove

- That IR tokens improve theorem-proving performance (that requires downstream eval on a prover)
- That the results generalise beyond the 4 modules in the current corpus
- That the effect holds at scale (larger corpus, larger model)

## Known limitations going in

1. **Corpus size is small** (2,459 training examples after filtering). Perplexity differences
   may not be statistically significant. Run the experiment, but treat results as directional.
2. **Cross-graph positional identity is absent** in variant A — see `ENCODER_FORMAT.md`.
   If A underperforms, this is the first thing to investigate.
3. **`mathlibCommitHash` is unknown** — corpus is not pinned to a specific Mathlib version.
   Not a blocker for the first experiment but should be fixed before publishing results.
4. **Only algebraic/order modules** — the corpus is structurally homogeneous. Results may not
   generalise to tactic-heavy or analysis modules.
5. **Cross-graph binder identity remains positional** — v1.2.0 now distinguishes binder kinds
   (`FVAR_N` for `forall`, `BVAR_N` for `lambda`), but IDs are still positional per graph. So
   `FVAR_0`/`BVAR_0` do not carry stable identity across declarations.

## Results

### Phase 5 final — expanded corpus, matched 3-epoch rerun (2026-08-01, authoritative)

All three variants: 3,375 train / 376 eval, 3 epochs, seed=42. DEC-007 and DEC-015 resolved.
See DEC-016 in DECISION_LOG.md for full methodology and follow-up requirements.

**Perplexity:**

| Variant | Representation | Vocab | Perplexity | Train time | Params |
|---------|---------------|-------|------------|------------|--------|
| A | Maith IR tokens (v1.2.0) | 8,102 | 1.2812 | 77.4 min | 365M |
| B | Raw leanExpr → Qwen BPE | 151,643 | 1.107 | 523.0 min | 494M |
| C | AST-style → Qwen BPE | 151,643 | 1.098 | 272.8 min | 494M |

**Completion accuracy (eval_completion.py, 50 examples, mask_last=5, teacher-forced):**

| Variant | Top-1 Accuracy | Correct / Total |
|---------|---------------|-----------------|
| A | 89.6% | 224 / 250 |
| B | 94.4% | 236 / 250 |
| C | 90.8% | 227 / 250 |

**Phase 5 finding:** A trails B and C on both metrics. The gap is real (~0.18 perplexity
points, ~5pp completion accuracy) and materially smaller than earlier mismatched estimates.
DEC-017/018 confirmed the gap persists at matched 512-token cap and across all sequence length
buckets. DEC-006 (cold-start confound) remains unresolved.

**Open confound — DEC-006:** A uses a randomly initialized embedding table (8,102 tokens).
B and C use Qwen pretrained embeddings (151,643 tokens). The warm-start attempt (DEC-009)
achieved only 0.51% token overlap and did not isolate the confound. DEC-006 remains open:
we cannot cleanly separate "IR representation is worse" from "random initialization is worse."

**Required follow-ups before Phase 6 — COMPLETE:**
1. ✅ DEC-017: stratified perplexity analysis — stratify by sequence length bucket (short/medium/long)
   to confirm B/C's advantage is not an artifact of asymmetric truncation at the 512-token cap.
   **Result:** B/C lead A in every bucket. Gap is not a truncation artifact.
2. ✅ Higher-confidence completion eval — run eval_completion.py with --samples 200 --mask-last 10
   against variant_A_v3, variant_B2, variant_C_v2. **Result:** A=86.2%, B=92.8%, C=91.4%.

**Phase 5 is complete. Phase 6 design may proceed.**

### Matched-batch rerun (2026-07-28 — superseded by 2026-08-01 run above)

All variants at effective batch=8 (grad_accum=8). DEC-007 resolved.

| Variant | Representation | Vocab | Perplexity | Train time | Grad steps | Eff. batch |
|---------|---------------|-------|------------|------------|------------|------------|
| A | Maith IR tokens (v1.2.0) | 4,495 | 1.39 | 22.7 min | 277 | 8 |
| B | Raw leanExpr → Qwen BPE | 151,936 | 1.15 | 112.7 min | 277 | 8 |
| C | AST-style → Qwen BPE | 151,936 | 1.13 | 50.0 min | 277 | 8 |

Superseded by DEC-015 (corpus expansion) and the 2026-08-01 matched rerun above.

### Previous run (2026-07-27 — carries DEC-007 confound, superseded)

| Variant | Perplexity | Eff. batch | Note |
|---------|------------|------------|------|
| A | 1.3922 | 8 | — |
| B | 1.1420 | 4 | DEC-007 ⚠ |
| C | 1.1298 | 4 | DEC-007 ⚠ |

**Run profile:** Qwen2.5-Coder-0.5B (MPS), seed 42, 2,213 train / 246 eval, shared eval cap 512,
encoder v1.2.0, 1 epoch. A: lr=2e-4, train cap 1024. B/C: lr=3e-5, train cap 384.

## Ordered execution checklist (build-out process)

1. Run full non-smoke A/B/C training with shared logging:
   - `python3 python/run_full_experiment.py`
2. Monitor progress during the long run:
   - `python3 python/watch_full_runs.py`
3. Generate comparison summary:
   - `python3 python/compare_results.py --runs-dir runs/`
4. Gate for decision-grade readiness:
   - `python3 python/check_results_gate.py --runs-dir runs/`
5. Once gate passes, record final A/B/C conclusions in this document.

## Phase 6 — Results (DEC-020, 2026-08-02)

Phase 6 ran an expanded-corpus A/B/C rerun (14 modules, 3,375 train / 376 eval examples)
with embed-pretrain warm-start applied to all variants. The gap did not close.

| Variant | Vocab | Params | Epochs | Eval Perplexity | Training time |
|---------|-------|--------|--------|----------------|--------------|
| A (IR tokenization) | 8,144 | 365M | 3 | 1.2792 | 105 min |
| B (BPE, standard FT) | 151,643 | 494M | 2 | 1.1295 | 181 min |
| C (BPE, embed-pretrain) | 151,643 | 494M | 2 | 1.1102 | 189 min |

A trails B/C by 0.15–0.17pp — identical margin to Phase 5. The gap is stable across corpus sizes.
Phase 6 is complete. See DEC-020 in `docs/decisions/LOG.md` for full interpretation.

**Open items carrying forward:**
- DEC-006 (cold-start embedding confound) — not yet definitively isolated
- DEC-019 diversity track (topology/lattice generalization) — not yet run
- Decompiler Lean validity (Phase 7 concern, see `docs/reference/DECOMPILER_HANDOVER.md`)

Representation IDs are recorded in dataset rows and `runs/variant_*/results.json` so future IR
candidate families can be compared without changing the reporting pipeline.

## Finalization checklist (publishability gate)

Run these after full A/B/C training completes:

1. Run the full post-run pipeline:
   - `python3 python/run_postrun_pipeline.py --runs-dir runs/`
2. Enforce full-run-only comparison:
   - `python3 python/compare_results.py --runs-dir runs/ --strict-full`
3. Re-check decision-grade gate:
   - `python3 python/check_results_gate.py --runs-dir runs/`
4. Build publish summary artifact:
   - `python3 python/publish_results_summary.py --runs-dir runs/`
5. Check publish readiness:
   - `python3 python/check_publish_readiness.py --runs-dir runs/`
6. Validate artifact schemas:
   - `python3 python/validate_experiment_artifacts.py --runs-dir runs/`
7. Validate representation matrix gate:
   - `python3 python/check_representation_matrix_gate.py --runs-dir runs/`
8. Confirm required artifacts exist:
   - `runs/variant_A/results.json`
   - `runs/variant_B/results.json`
   - `runs/variant_C/results.json`
   - `runs/loss_curves.json`
   - `runs/full_results_gate.json` (`decision_grade=true`)
   - `runs/publish_results_summary.json`
9. Only after all checks pass, update the Results table and interpretation in this document as final.
10. Record any protocol/interpretation changes in:
   - `docs/decisions/LOG.md`
