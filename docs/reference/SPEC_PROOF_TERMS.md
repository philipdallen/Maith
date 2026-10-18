# Spec: Proof-Term Extraction (DEC-029 #2 / Concern #2)

> **Status:** Not started. Spec finalized; implementation deferred until per_operator
> experiment (Concern #1) is complete. The user is working on this spec's details.
> See [V2_NEXT_STEPS](../experiments/V2_NEXT_STEPS.md) for task tracking.

## Goal

Enable raw proof-term extraction from theorem declarations, linked to the statement graph
via an explicit `proof_of` relation, so that proof-completion / proof-search evaluation
(section 10's decisive untested metrics) has a substrate.

## Design principle

Extract faithfully, do not filter. The elaborated proof-term scaffolding (`Eq.refl`,
`casesOn`/`recOn`, instance arguments) is plausibly the predictable backbone a sequence
model needs — the high-frequency, regular structure that lets a model build representation
before tackling rare lemma choices. This is consistent with the repo's own thesis: that
elaborated `Expr` (including implicits and coercions the human never wrote) is the right
representation level because it exposes resolved semantics. **Measure the distribution
before deciding any normalization.**

## Scope boundary

This spec covers Layer 1 only: mechanical extraction + linking + instrumentation. No
`ProofNormalizer`, no collapsing of `Eq.refl`/`recOn`, no depth capping beyond existing
size thresholds. Layer 2 (empirical filtering) is deferred pending the measurement this
spec produces.

## Convergence with Concern #1

During discussion we established that the Layer-2 decision, if it ever happens, converges
on Concern #1's fix (un-bucket operators / give distinct identity to lemma applications)
rather than on collapsing structural tokens. So the efficient roadmap is: un-bucket
operators once (Concern #1), enable raw proof extraction (this spec), then run both
statement-side and proof-side evals against the un-bucketed representation.

---

## Planned implementation

### Lean changes

**RelationOp.lean:** Add `proof_of` constructor to `RelationOp` with `ToString` case.

**MetaExtractor.lean:**
- Change A: Unskip `.thmInfo` in `constantValueExpr?` — add
  `| .thmInfo info => some info.value`
- Change B: Thread root entity IDs and emit `proof_of` relation linking proof root to
  statement root. Only theorems get `proof_of`; definitions don't (their value IS their
  meaning).

**Decoder.lean:** Add `proof_of` case to `parseRelationOpToken` (prevents silent `.eq`
fallback — same pattern as the op:/proj: fix in Concern #1).

**Normalizer.lean:** Verify `proof_of` sorts correctly under `normalizeRelations` (by
`toString op`, lexicographic). No code change expected.

**Size-threshold policy:** Leave existing thresholds unchanged. The skip rate is itself the
measurement (Gate 4) — it bounds how much of Mathlib's proof corpus is representable.

### Python changes

**build_dataset.py:** Add `--include-proofs` flag:
- Without flag (default): behavior unchanged — statement-only, current v2 datasets
  reproduce identically (regression-guarded)
- With flag: for theorem examples, variant A uses full token sequence including proof rows
  and `proof_of` link; variants B/C set `leanExpr` to combined type + value string

**proof_token_stats.py (NEW):** Instrumentation script that reads corpus and reports:
- Theorem count vs definition/axiom count
- Token-length distribution (statement vs proof portions, split at `proof_of` relation)
- Op-token frequency table within proof sub-graphs
- P50/P90/P99 proof-token length
- Skip rate: `skippedTooLarge` before (v2.0.0) vs after (v2.1.0)
- Output: `docs/history/PROOF_TOKEN_MEASUREMENT.md` + `Corpus/proof_token_stats.json`

### Dataset / eval comparability (critical)

Do **not** retrofit proof content into the existing v2 A/B/C perplexity comparison. That
comparison is a statement-prediction result (DEC-026/027) and stays as-is. Proof-term
extraction enables a **new**, separate eval surface with new datasets (`*_proof_*`).

---

## Verification gates

**Gate 1 — Root-ID semantics (must pass before landing).** The `proof_of` edge connects
`proofRoot` to `typeRoot`, but these are the topmost sub-expression entities, not named
"statement/proof roots." Manual graph inspection of at least one real theorem required.

**Gate 2 — `.thmInfo` match-arm binding (must pass before landing).** Confirm the
`proof_of` emission gate composes with `constantValueExpr?` destructuring without
exhaustiveness warnings.

**Gate 3 — Normalizer round-trip with `proof_of` (must pass before landing).** Golden
round-trip test must pass. If `proof_of` doesn't sort deterministically, fix is a sort-key
adjustment.

**Gate 4 — Size-threshold skip rate (must be reported before any Layer-2 decision).**
Decision rule:
- <20% skip: Layer 1 useful as-is; proceed to proof-completion eval
- 20-50% skip: reportable limitation; Layer 1 useful on representable subset
- >50% skip: truncation promotes from "Layer 2, maybe" to "blocker" — re-scope

---

## Versioning

- `irVersion`: `semantic_graph_ir_v2_1_0` (additive: new relation op, theorem graphs grow)
- `encoderVersion`: v1.5.0
- Backward compat: old corpora (v2.0.0) have no `proof_of` rows → decode identically
- If combined with per_operator: `semantic_graph_ir_v2_1_2`

---

## Implementation order

1. Lean types + extraction (RelationOp, MetaExtractor)
2. Lean decoder + normalizer verify
3. Lean tests (round-trip, faithfulness)
4. Rebuild corpus, run validate_roundtrip.py
5. Python instrumentation (proof_token_stats.py) — produce measurement (Gate 4)
6. Inspect measurement — decide whether Layer 2 is warranted
7. Python dataset flag + proof-completion eval scaffold
8. Docs

Steps 1-5 are the self-contained Layer-1 deliverable. Steps 6-8 are where the research
decision lives.

---

## What this spec deliberately does NOT include

- No ProofNormalizer.lean / no collapsing of structural tokens (deferred to Layer 2)
- No truncation / honesty-token mechanism beyond existing size thresholds
- No tactic-state capture (tactics aren't in `Expr`)
- No change to the v2 A/B/C perplexity comparison (preserved as statement-prediction result)
- No ATP type-checking feedback loop
- No un-bucketing of operators (that's Concern #1's scope; this spec composes with it)
