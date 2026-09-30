# Hypothesis Grid

> **Purpose.** Decomposes Maith's central hypothesis into testable sub-claims, tracks each
> one's status (open / closed), and points to the evidence that closes it. This is the
> authoritative answer to "is the hypothesis open or closed?" — the answer is *which part*.
>
> The central hypothesis — *a canonical semantic representation improves formal math
> tooling* — is not a single claim. It is a family of claims, some closed (positive and
> negative), most still open. Reading any single experiment's result as the status of the
> whole hypothesis is the error this document exists to prevent.
>
> Decision IDs (DEC-0xx) refer to [`docs/decisions/LOG.md`](../decisions/LOG.md).

> **⚠ RESET NOTICE (2026-08-12):** All previous experimental results have been declared
> invalid pending pipeline quality-gate verification (see
> [`PIPELINE_QUALITY_GATES`](../reference/PIPELINE_QUALITY_GATES.md)). All status icons
> have been reset to ⬜ and evidence fields cleared. Previous DEC entries remain in the
> decision log as a historical record but are not considered valid evidence until the
> experiments are re-run under verified quality gates. Hypothesis definitions and
> literature citations are preserved. No real hypothesis tests until all gates are green
> and sanity-check hypotheses pass.

## Status legend

| Mark | Meaning |
|---|---|
| ✅ | Closed — positive (evidence supports the sub-claim) |
| ❌ | Closed — negative (evidence refutes the sub-claim) |
| ◐ | Partial — some evidence, not fully resolved |
| ⬜ | Open — not yet tested (or results invalidated, pending re-test under quality gates) |

## The grid

| # | Question | Status | Sub-claim | Evidence | What would close it |
|---|---|---|---|---|---|
| H1 | Does the IR encode semantic structure that source/AST don't? | ⬜ | The IR encodes semantic structure not present in source/AST | *Invalidated — pending re-test under quality gates.* | Linear probe (module classification) comparing IR vs flat-IR vs BPE embeddings. |
| H2 | Does IR improve next-token prediction over BPE? | ⬜ | The IR improves next-token prediction over BPE | *Invalidated — pending re-test under quality gates.* | Perplexity comparison at matched params/epochs (A vs B-small). See [`EXPERIMENT_MEASUREMENT`](../reference/EXPERIMENT_MEASUREMENT.md) Part 1. |
| H3 | Was cold-start embedding init masking a real benefit? | ⬜ | Cold-start embedding init explains the perplexity null | *Invalidated — pending re-test under quality gates.* | Embed-project experiment: does projection initialization close the gap? |
| H4 | Does model size explain the perplexity null? | ⬜ | Model size explains the perplexity null | *Invalidated — pending re-test under quality gates.* | A larger *transformer-capacity* base model (1B+, e.g. Qwen2.5-Coder-1.5B/3B) with a corresponding IR vocab; blocked on IR design and compute. Note: IRCoder's gains across 1.1B–7.3B are task-dependent and non-monotonic (several 7.3B cells negative) — no clean scale threshold is established; see [`LITERATURE_REVIEW_2026_08`](LITERATURE_REVIEW_2026_08.md) §H4/H8. |
| H5 | Is the training objective the bottleneck — does next-token loss fail to reward semantics? | ◐ | The training objective is the bottleneck (next-token doesn't reward semantics) | **Stage 1 (projection head, DEC-033, 2026-08-18):** Freeze A_v3_2ep encoder, train 1M-param MLP projection head on 12,443 dependency pairs (5 epochs, batch=64, temp=0.07). **Stage 2 (end-to-end, DEC-035, 2026-08-19):** Full encoder fine-tune (NT-Xent, 388 steps, loss 3.93→2.68, 5.9h MPS). Mode 1 (n=287): all CIs overlap, no significant separation. Mode 2 (n=2641): A_h5_e2e=0.0027, A_h5_proj=0.0029, A_v3_2ep=0.0012, B_small=0.0028. Both contrastive variants statistically ahead of A_v3_2ep (CIs non-overlapping); e2e and proj-head indistinguishable from each other; both match B_small. Ambiguous positive — contrastive objective reliably beats next-token baseline, but effect is small (far below pretrained ≈0.072). Full e2e does not improve over projection-head. Gates: 63/63 pass. Results: `runs/h5_retrieval/results_e2e.json`, `results_e2e_mode2.json`. | Cannot close positive at toy scale. Next: H4/H8 (scale) or H9 (co-training). Full e2e vs proj-head distinction is now resolved — scale is the remaining lever. |
| H6 | Does the IR improve retrieval / similarity tasks (semantic, not predictive)? | ◐ | The IR improves retrieval / similarity tasks (semantic, not predictive) | Both modes run against clean embeddings (2026-08-18). Mode 1 (n=287): A=0.0052, B_small_clean=0.0049 — A ahead, CIs overlap. Mode 2 (n=2641): A=0.0012, B_small_clean=0.0028 — B ahead, CIs do not overlap. Modes disagree → ambiguous by retest plan definition. Mode 2 has more power and leans negative. Not worth re-running at toy scale. Gates: 57/57 pass. See `H6_RESULTS.md`. | H5 (contrastive objective) or H4/H8 (scale) are more informative next steps than re-running H6 at toy scale. |
| H7 | Does the IR improve proof completion / ATP success? | ⬜ | The IR improves proof completion / ATP success | *Invalidated — pending re-test under quality gates.* | Theorem-proving evaluation (Phase 7 scaffold in [`PHASE_7_ROADMAP`](../history/PHASE_7_ROADMAP.md)). SOTA provers (Goedel-V2, Kimina, BFS-Prover, AlphaProof) train on tactics/proof-state via RL, not IR — representation lever untouched. See [`LITERATURE_REVIEW_2026_08`](LITERATURE_REVIEW_2026_08.md) §H7. |
| H8 | Does the IR's advantage appear only above a scale threshold? | ⬜ | The IR's advantage appears only above a scale threshold | *Invalidated — pending re-test under quality gates.* | A larger *transformer-capacity* base model (1B+); blocked on IR design and compute. See [`LITERATURE_REVIEW_2026_08`](LITERATURE_REVIEW_2026_08.md) §H4/H8. |
| H9 | Would co-training (IR alongside source) recover gains where replacement didn't? | ⬜ | Co-training (IR alongside source) recovers gains where replacement didn't | *Invalidated — pending re-test under quality gates.* | Multi-objective training experiment (joint IR + source loss). |
| H10 | Does the IR beat AST on semantic probing tasks beyond module classification? | ⬜ | The IR beats AST specifically on semantic probing tasks | *Invalidated — pending re-test under quality gates.* | Extended probing: typeclass arity, theorem-vs-definition, semantic category. Methodological precedent: "Meaning in Language Models" (WFVML 2023) does the same probe + perplexity-divergence methodology in program traces — Maith's contribution is the formal-math + flat-IR-ablation specificity, not the dual-eval method itself. See [`LITERATURE_REVIEW_2026_08`](LITERATURE_REVIEW_2026_08.md) §H10. |
| H11 | Is perplexity a valid primary metric for evaluating semantic representations? | ⬜ | Perplexity is a valid primary metric for evaluating semantic representations | *Invalidated — pending re-test under quality gates.* | Core finding stands (perplexity cannot be the sole arbiter). But the design-quality component is open — a v3 IR with semantic redundancy (meaningful + predictable tokens) could partially narrow the gap. Test retrieval first; perplexity second. See [prediction-metric bias analysis](EXPERIMENT_DESIGN.md#why-prediction-metrics-are-structurally-biased-toward-natural-language). |
| H12 | Does a graph-native architecture (GNN/GraphTransformer) outperform a sequence transformer on the same IR? | ⬜ | A graph-native model that consumes the IR's edges directly as message-passing paths will outperform a sequence transformer on the linearized IR, because algorithmic alignment reduces sample complexity (Xu et al., ICML 2021) | Not tested. All Maith experiments use sequence transformers (the misaligned case). The theory predicts the null is caused by architecture misalignment, not by the IR being wrong. **Partially answerable by reading:** Nazrin/ExprGraph (arXiv:2602.18767) is a Lean 4 GNN prover that operates on expression graphs. If it outperforms tactic-based sequence models on the same theorems, that's field evidence for H12 without implementation work. Read that paper first. | (1) Read Nazrin/ExprGraph results — if positive, partial answer. (2) Implement a GraphTransformer on Maith's IR graph and compare to the sequence transformer at matched capacity. |
| H13 | Would a JEPA-style latent-prediction objective produce better representations than next-token prediction? | ⬜ | A latent-space prediction objective (predict in embedding space, not token space) will produce representations that support retrieval better than next-token prediction, even from the same IR and model (LeCun, 2022; I-JEPA, Assran et al., CVPR 2023) | Not tested. Refinement of H5 with a specific mechanism: JEPA theory predicts token-prediction quality ≠ representation quality, and latent prediction should close the gap. H5 stays open as the broad claim; H13 is the specific JEPA instantiation. | Implement a masked-latent-prediction loss (predict the embedding of masked IR sub-graphs, not the tokens) and compare retrieval/probing performance to next-token training. |
| S1 | *Sanity check:* Does a pretrained (un-fine-tuned) model score at chance on retrieval? | ⚠️ | Pretrained model Recall@10 ≈ k/pool_size (chance baseline) | ⚠️ **WARNING** — pretrained Qwen2.5-Coder-0.5B scores above chance (Recall@10=0.072 vs chance=0.020 on 500-pool subset). Qwen is **pretrained** on code, not random — its token embeddings already encode semantic similarity. This is not contamination. It means every H6 retrieval number must be compared against the **pretrained baseline** (0.072), not pure chance (0.020). The A-vs-B_small comparison is "IR fine-tuning vs BPE fine-tuning, both on top of a pretrained model with existing retrieval signal." See [`EXPERIMENT_MEASUREMENT`](../reference/EXPERIMENT_MEASUREMENT.md) terminology note. | Extract embeddings from pretrained (un-fine-tuned) Qwen2.5-Coder-0.5B, run retrieval eval. **Finding:** pretrained model scores ~3.6x chance — the baseline is "pretrained," not "random." H6 results must include this as a variant. |
| S2 | *Sanity check:* Does a known-identical pair score Recall@10 = 1.0? | ✅ | Identical embeddings retrieve each other at rank 1 | **PASS — Recall@1=1.0, MRR=1.0** (identical embedding retrieved at rank 1), recorded in [DEC-032](../decisions/LOG.md) (2026-08-12). Run *before* the H5/H6 tests (2026-08-18/19), so the stated pre-condition was met, not skipped — the grid had simply not recorded the result. | Duplicate one declaration's embedding as both query and pool entry. Expected: Recall@1 = 1.0, MRR = 1.0. If not, the cosine similarity or ranking logic is broken. |

> **H14 (footnote, not a row):** An operational IR (compact, regular, predictable — closer to LLVM IR's
> design philosophy) would improve perplexity over Maith's semantic-graph IR, even if it sacrifices
> some semantic content. This is not a new hypothesis — it's a validation of the existing theory (H11's
> fundamental component: canonicalization removes redundancy → harder to predict). Building a less
> canonical IR would just confirm that explanation. Tracked here as a footnote, not a research claim.

## How to read this grid

> **All statuses are ⬜ as of 2026-08-12.** Previous results were invalidated due to
> pipeline quality issues (split leakage, epoch confounds, dataset contamination — see
> [`PIPELINE_QUALITY_GATES`](../reference/PIPELINE_QUALITY_GATES.md) for the full gate
> design and [`QUALITY_GATES_SCOPE`](QUALITY_GATES_SCOPE.md) for the implementation plan).
> Previous DEC entries in [`LOG.md`](../decisions/LOG.md) remain as historical record
> but are not valid evidence. Hypothesis definitions and literature citations are
> preserved. The grid will be re-populated as experiments pass quality gates and
> produce verified results.

**Pre-condition for any hypothesis test:**
1. All pipeline quality gates (G1–G5) pass cleanly
2. Sanity-check hypotheses (S1, S2) pass — S2 recorded PASS ([DEC-032](../decisions/LOG.md), 2026-08-12); S1 recorded as a documented warning (see the S1 row above)
3. Only then may real hypothesis tests (H1–H11) run

**What is open and tractable on current hardware (M4/16GB):**
- H5 (objective redesign), H9 (co-training), H10 (richer probing). These are the live
  research front and should be prioritized over scale. H13 (JEPA objective) is a specific
  refinement of H5 — both stay open; H13 is the mechanistic instantiation.

**What is open and partially answerable by reading:**
- H12 (architecture alignment) — Nazrin/ExprGraph (arXiv:2602.18767) may partially
  answer this before any implementation work. Read first, then decide whether to build.

**What is open and blocked on compute:**
- H4 at scale (A-large), H7 (ATP eval — partially blocked; scaffold exists), H8 (scale
  threshold). These require resources outside the current setup.

**The key non-obvious point:** Even if H2 is re-confirmed negative, it does *not* close
the central hypothesis. Perplexity measures predictability, not semantic utility (see
[`PRIOR_ART.md`](../reference/PRIOR_ART.md) §4). The IR's value proposition lives in
H6/H7/H10/H12/H13 — tasks where semantic structure, not token predictability, is what
matters.

## Relationship to the decision log

This grid is a *structured view* of the hypothesis; [`LOG.md`](../decisions/LOG.md) is the
*chronological record* of experiments. They are complementary: the decision log proves
the evidence is real and reproducible; this grid makes the hypothesis's decomposition
legible. When a new DEC entry closes a sub-claim, update the corresponding row here.

For the structured experiment layout underlying the evidence — the 2×2 control grid of
IR/BPE × narrow-vocab/full-vocab — see [`V2_COMPARISON_MATRIX.md`](V2_COMPARISON_MATRIX.md)
(current v2 era) and [`V1_COMPARISON_MATRIX.md`](V1_COMPARISON_MATRIX.md) (historical).

## Experiment-scope matrix

The H1–H10 rows above track *sub-claims* (does X help?). This matrix tracks the *dimensions
of variation* — what values have been tested vs. what hasn't. It makes visible that what's
been tested is one corner of a multi-dimensional space, not the whole hypothesis.

| Dimension | Tested | Untested |
|---|---|---|
| **Model size** | Toy (0.5B base, 358–494M params) | Small (1B–8B), Medium (8B–30B), Large+ (30B+) — see [taxonomy](EXPERIMENT_DESIGN.md#model-size-taxonomy) |
| **Training objective** | Next-token prediction (causal LM) | Masked reconstruction, proof-completion, contrastive |
| **Evaluation metric** | Perplexity, completion accuracy (prediction family); linear probe (representation) | Retrieval/similarity, ATP success rate, proof-search efficiency |
| **Corpus size** | ~3.5K examples (14 modules) | 10K+, 100K+, full Mathlib (~190K declarations) |
| **IR version** | v1.2.0 → v1.4.0 → v2.0.0 (C1/C2/C4) | C3 (attribute sparsity, deferred), `per_operator` mode (DEC-028 — un-bucketed operators), v3 candidates — see [v1→v2 assessment](EXPERIMENT_DESIGN.md#v1--v2-ir-optimization-assessment) |
| **Mathematical domain** | Algebra, order, topology (declaration-heavy) | Tactics, analysis, number theory, category theory |
| **Model architecture** | Sequence transformer (causal LM) | GNN / GraphTransformer (graph-native — see [theoretical grounding](PRIOR_ART.md#the-alignment-fragility-barrier-where-maiths-null-is-predicted-by-theory)). Concrete realization: Nazrin/ExprGraph (arXiv:2602.18767, 2026) — a GNN over Lean expression graphs for tactic prediction. See [`LITERATURE_REVIEW_2026_08`](LITERATURE_REVIEW_2026_08.md) §H4/H8. |

**How to read this matrix:** each "Tested" cell is a single point; each "Untested" cell is
an open dimension. The hypothesis has been evaluated at one model size, one objective, two
metric families, one corpus scale, four IR versions, and three domain families. The closest
positive precedent (IRCoder) saw gains at 1B+ parameters and 4M examples — roughly 1,000x
larger on data and 3x larger on model capacity than what's been tested here.

**Priority for closing dimensions:** the most tractable untested cells are objective
redesign (H5/H13 — testable at current scale) and co-training (H9 — testable at current
scale). Architecture alignment (H12) is partially answerable by reading Nazrin/ExprGraph
before building. Model size and corpus scale are blocked on compute. IR version and domain
are blocked on design work (C3 cross-check, corpus expansion).

## Update protocol

- When an experiment produces a result that resolves a sub-claim, change its status mark
  and add the DEC ID to the evidence column.
- Do not delete closed rows — the grid's value is showing the full decomposition,
  including what has been ruled out.
- If a new sub-claim emerges (e.g. a new task type or confound), add a row rather than
  editing an existing one.
