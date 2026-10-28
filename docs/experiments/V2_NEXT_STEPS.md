# V2 Experiment — Phase Tracker

> **Last updated:** 2026-08-09
> **Purpose:** Single source of truth for what's done, what's in progress, and
> what's next in the v2 IR experiment phase. Updated as work completes.
>
> **Related docs:**
> - [`V2_COMPARISON_MATRIX.md`](V2_COMPARISON_MATRIX.md) — the 2x3 control grid
> - [`V1_COMPARISON_MATRIX.md`](V1_COMPARISON_MATRIX.md) — historical v1 grid
> - [`HYPOTHESIS_GRID.md`](HYPOTHESIS_GRID.md) — 10 testable sub-claims with status
> - [`../decisions/LOG.md`](../decisions/LOG.md) — DEC-026 (v2 results), DEC-027 (B-small)

---

## Done

| Item | Detail |
|---|---|
| v2 IR implemented (C1+C2+C4) | commit f194027; vocab 601 |
| Full v2 A training | ppl 1.2361 / acc 90.0%, runs/variant_A_v2_full |
| B-small control (DEC-027) | ppl 1.1294 / acc 90.5%, runs/variant_B_small |
| DEC-026 + DEC-027 written | Full v2 result table + B-small gate (size confound confirmed) |
| lake build tests passes | Verified on Kit's machine |
| Lean decompiler (BVAR/Test 8/doc) | Tasks 1-3 committed and compile-verified |
| Stale checkpoint guard | eval_completion.py, commit c8d0e4e |
| Stale run dirs quarantined | runs/_stale_variant_{A,B,C} |
| V2_COMPARISON_MATRIX | 2x3 grid, eval protocol, baseline-reuse rules |
| V1_COMPARISON_MATRIX | Historical grid showing why v2 was needed |
| HYPOTHESIS_GRID | 10 sub-claims, 3 closed (H1 yes / H2 no / H3 no), 7 open |
| PRIOR_ART.md | Related-work survey (IRCoder, PACT, JEPA, AMR) |
| Repo reorganized | docs/ into 5 subdirs, scripts/logs moved, .gitignore |
| Language/framing audit | 7 edits: v2 narrative, C1 fix, Fix-N to CN mapping, search framing |
| EXPERIMENT_DESIGN protocol | Fixed eval protocol, 2x2 template, baseline-reuse rules |
| ENCODER_FORMAT v2 section | C1/C2/C4 spec, Python/Lean parity warning |
| Variant-specific LR | B/C use 5e-5 (151k embedding stability), commit 83f18a8 |
| B_SMALL eval support | eval_completion.py loads eval_B_small.jsonl + vocab_B_small |

---

## In progress

### B/C re-run at 2 epochs (fresh v2 grid)

**Why:** Old B (variant_B2) and C (variant_C_v2) used 3 epochs / train cap 384,
inconsistent with A/B-small's 2 epochs / train cap 512. Re-runs use uniform
protocol (2 epochs, seed 42, train cap 512) so only representation and size vary.

| Variant | Status | Run dir | Notes |
|---|---|---|---|
| B (BPE 151k, 494M, 2ep, lr=5e-5) | Training (step ~139/874) | runs/variant_B_v2_2ep | ~134s/step, slow — MPS memory pressure from 151k embeddings at 512 cap |
| C (AST BPE 151k, 494M, 2ep, lr=5e-5) | Queued (after B) | runs/variant_C_v2_2ep | Same expected speed |

**Known issue:** B at 494M + 151k embeddings + 512 train cap is very slow on MPS
(~134s/step vs old B's ~12s/step at 384 cap). Options being considered:
- Reduce train cap to 384 for B/C (matches old profile, reduces memory)
- Accept the slow run (resumable via step-checkpoints at step 218)
- Run on CUDA if available

**After B/C complete:**
1. Eval both (200 samples, mask-10, authoritative checkpoint override)
2. Update V2_COMPARISON_MATRIX with fresh 2-epoch numbers
3. Mark old B (variant_B2, 3ep) and C (variant_C_v2, 3ep) as superseded
4. Update HYPOTHESIS_GRID H2 evidence if numbers change

---

## Next — the open research front (from HYPOTHESIS_GRID)

The hypothesis grid identifies open sub-claims. Per H11 (◐ partly closed: perplexity
cannot be the sole arbiter — the bias is partly fundamental, partly contingent on IR
design quality), the priority is **semantic-task metrics**, not perplexity iteration.
Prediction metrics are structurally biased toward natural language's redundancy; the IR
deliberately sacrifices redundancy for canonicalization. But v1's verbosity was the wrong
kind (structural noise, not semantic redundancy), and v2 didn't add the right kind — so
the design-quality component remains open. See
[EXPERIMENT_DESIGN evaluation framework](EXPERIMENT_DESIGN.md#evaluation-framework-the-correct-metrics-for-this-hypothesis).

### Primary next experiments (test the hypothesis on the right metric family)

| # | Sub-claim | Status | What would close it | Tractability |
|---|---|---|---|---|
| H6 | IR improves retrieval/similarity tasks | Open | Retrieval/similarity benchmark; IR vs AST/BPE embeddings using frozen representations | ✅ Tractable — reuses DEC-025 `extract_representations.py` infra; no training needed |
| H10 | IR beats AST on richer probing tasks | Partial | Extended probing: typeclass arity, theorem-vs-definition, semantic category | ✅ Tractable — extends DEC-025 probe; no training needed |

### Secondary (test whether the bottleneck is the objective or the format)

| # | Sub-claim | Status | What would close it | Tractability |
|---|---|---|---|---|
| H5 | Training objective is the bottleneck | Open | Masked-reconstruction or proof-completion objective experiment | ◐ Requires training-code changes (new loss function) |
| H9 | Co-training (IR alongside source) recovers gains | Open | Multi-objective training experiment (PACT precedent) | ◐ Requires multi-objective training setup |
| C3 | Attribute sparsity (v2.x IR candidate) | Deferred | Implement + evaluate against control grid | ◐ Requires Lean cross-check; **evaluate on retrieval, not perplexity** |
| v3 redundancy | Semantic-redundancy candidate (adds meaningful + predictable tokens; the H11 design-quality component) | Spec drafted ([SPEC_V3_SEMANTIC_REDUNDANCY.md](../reference/SPEC_V3_SEMANTIC_REDUNDANCY.md)) | Build the candidate, then evaluate retrieval-first against the A_v2 / B_small / flat grid | ◐ Spec only; implementation is a separate step. Distinct from C3 (which *removes* attribute noise) |
| **DEC-028** | C4 bucketing confound — `per_operator` mode | Open | Add `bucket_mode` flag to MetaExtractor/encode_ir; re-run A-vs-B-small with `per_operator` | ✅ **Decisive test** — if A beats B-small, the null was a C4 artifact. Requires code change + training run. |

### Code fixes (trivial — DEC-029)

- [x] **Device priority** — reorder `train.py` device selection to `cuda → mps → cpu` (was `mps` first)
- [x] **Polarity no-ops** — deleted `normalizePolarityEntity/Attr/Rel/Op` from `Normalizer.lean` (dead code from C1)
- [x] **B/C special-token note** — documented that B adds BOS/EOS by default, C does not

### Active specs

Two detailed specs are in `docs/reference/`. Their implementation status:

### Spec 1: Operator Un-Bucketing (DEC-028) — [SPEC_PER_OPERATOR.md](../reference/SPEC_PER_OPERATOR.md)

**Status: Gate 4 closed 2026-10-27** (vocab-size report recorded in
[SPEC_PER_OPERATOR.md](../reference/SPEC_PER_OPERATOR.md)). The corpus rebuild was not
run here (no Lean toolchain in this environment); the report is from the tracked
per_operator vocab artifact `datasets/vocab_A_v1.json`. The A-vs-B-small experiment
remains unrun.

| Gate | Description | Status |
|---|---|---|
| 1 | headShortName threading (op:mul_comm emitted for real constants) | ✅ Passed |
| 2 | Mode isolation (switching bucketMode changes only op payload) | ✅ Passed |
| 3 | op:/proj: round-trip (decoder cases prevent silent .pow fallback) | ✅ Passed |
| 4 | Vocab-size report (per_operator vocab meaningfully different from 601) | ✅ Passed 2026-10-27 — 1235 vs 601 content tokens |

**Next steps:** `lake build Mathlib` → `lake exe buildCorpus --per-operator` →
`python3 python/build_dataset.py --bucket-mode per_operator` → check vocab size →
run A-vs-B-small experiment. **Caveat:** the docs cite a 2,254-token A_v3_2ep vocab
that is not in any tracked artifact (tracked per_operator vocab is 1,236; RUN_REGISTRY
lists A-v3 at 8,102). Reconcile that number against a rebuilt corpus before citing it.

### Spec 2: Proof-Term Extraction (DEC-029 #2) — [SPEC_PROOF_TERMS.md](../reference/SPEC_PROOF_TERMS.md)

**Status: Not started.** Spec finalized; implementation deferred until per_operator
experiment is complete. The user is working on spec details.

| Gate | Description | Status |
|---|---|---|
| 1 | Root-ID semantics (proof_of edge connects sensible endpoints) | ⬜ Not started |
| 2 | .thmInfo match-arm binding (compiles without exhaustiveness issues) | ⬜ Not started |
| 3 | Normalizer round-trip with proof_of | ⬜ Not started |
| 4 | Size-threshold skip rate (measured before Layer-2 decisions) | ⬜ Not started |

**Composes with Spec 1:** per-operator identity matters more on proof sub-graphs. The
combined representation is `v2_1_2` (per_operator + proof-enabled).

---

## Pre-existing test failures (resolve after Concern #1 and #2 land)

The following test failures are pre-existing (not caused by the per_operator or proof-term
changes) and should be resolved after both specs are implemented and the corpus is rebuilt:

1. **Decoder round-trip format mismatch (2 tests + 9 Phase 8b tests)** — decoder expects
   `inputs:FVAR_0` format but encoder emits `IN_1`. This is a v1.3.0/v2.0.0 encoder format
   change that the decoder's input-format handling hasn't caught up with. All 11 failures
   show the same pattern: "expected inputs:FVAR_0, got IN_1".

2. **Injectivity: non-commutative operations collapse (1 test)** — `sub(a,b)` and `sub(b,a)`
   produce identical tokens. The normalizer may be treating subtraction as commutative, or
   the operation input ordering isn't preserved through encode → normalize → decode.

3. **Lean validity check (1 test)** — decompiled output doesn't type-check. Pre-existing
   decompiler issue; not related to bucketing or proof-term work.

These are tracked here so they aren't lost. They should be investigated after the corpus
is rebuilt under per_operator mode (which changes the token stream and may surface or
resolve some of these issues naturally).

### Explicitly deprioritized (but not fully closed — see H11 ◐)

- **Perplexity iteration on IR candidates** — the *fundamental* component of the bias
  (canonicalization removes surface variation) means perplexity can't be the sole arbiter.
  But the *contingent* component (v1 was structural noise, v2 didn't add semantic
  redundancy) means a v3 IR with semantically meaningful + contextually predictable tokens
  could partially narrow the gap. Future IR candidates should *report* perplexity for
  completeness and *track* whether typed/semantic tokens narrow the gap — but retrieval
  and probing remain the primary evaluation.

### Blocked on compute

| # | Sub-claim | Status | Blocker |
|---|---|---|---|
| H4 | Model size at scale | Partial | Requires a larger *transformer-capacity* base model (1B+), not just a bigger embedding table |
| H7 | IR improves proof completion / ATP | Open | Theorem-proving eval infrastructure + **proof-term extraction mode** (DEC-029: current IR is statement-only; ATP needs proof terms) |
| H8 | IR advantage above scale threshold | Open | 1B+ base model; blocked on compute |

**Note on scale:** the metric-bias argument (H11) means scale alone will not resolve the
hypothesis if the metric is wrong. A larger model would predict the IR's tokens better, but
it would also predict natural language better — and the bias toward redundancy remains.
Scale testing is valuable but must be paired with semantic-task metrics, not perplexity
alone.

---

## Deferred (post-merge cleanup)

- **train.py vs train_v2_resume.py dedup** — fold v2 fixes back into train.py,
  or delete train.py and rename train_v2_resume.py. Wait until B/C re-runs complete.
- **C-small (optional)** — AST BPE truncated to 601, 358M. Completes the 2x3 grid
  but doesn't change the A-vs-representation conclusion.
- **A-large** — requires a larger-vocab IR candidate (future grid, not a v2 gap).
