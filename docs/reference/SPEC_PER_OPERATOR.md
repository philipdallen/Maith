# Spec: Operator Un-Bucketing (DEC-028 / Concern #1)

> **Status:** Implemented; Gate 4 closed 2026-10-27 (vocab-size report below). The
> A-vs-B-small experiment has not been run.
> See [V2_NEXT_STEPS](../experiments/V2_NEXT_STEPS.md) for task tracking.

## Goal

Replace the current `GEN_*` namespace bucketing of generic operators with per-operator
identity tokens, behind a configurable mode, so that distinct Mathlib operators
(`mul_comm`, `isUnit`, `Function.Injective`, …) remain distinct in the IR rather than
collapsing into ~20 buckets.

## Hypothesis under test

The v2 prediction null (A ties B-small on perplexity) may be a *bucketing artifact*, not
an "objective mismatch" or representation-intrinsic deficit. By bucketing all algebraic
operators to `GEN_ALGEBRA`, the IR discards exactly the operator-identity information that
next-token prediction rewards — making the IR *more* lossy than BPE on operator-heavy
terms, despite preserving other structure. If un-bucketing closes the A-vs-B-small gap (or
reverses it), the null is overturned and the headline result changes. If the gap holds, the
"objective mismatch" interpretation is strengthened. Either outcome is decisive and cheap.

## Scope boundary

This spec adds a `per_operator` bucket mode and runs the A-vs-B-small comparison under it.
It does **not** remove the existing `module` mode (kept for backward compat and as a
control). It does not touch the proof-term work (Concern #2) — but the two compose:
per-operator identity matters even more on proof sub-graphs, where "which lemma was
applied" is the prediction a prover searches over.

## Key finding from code inspection

The current corpus contains no `gen:`-prefixed tokens at all. The Lean `MetaExtractor`
emits the bucket string (`"GEN_ALGEBRA"`) directly as the `OperationOp.generic` payload,
and the encoder's `ToString` instance returns it verbatim. The Python `build_dataset.py`
still contains `gen:`-handling logic, but this is **legacy dead code from v1** — no v2
token ever matches it. The fix is primarily Lean-side (change what string gets emitted),
and the Python changes are about vocab/threshold handling of the new token format.

---

## Implementation (landed on kit/dev)

### Lean changes (MetaExtractor.lean)

- **BucketMode inductive type:** `module` (v2 behavior) | `per_operator` (op:<shortName>)
- **ExtractionState:** added `bucketMode : BucketMode := .module` field
- **genericOpToken function:** centralized op-token emission — module mode returns
  `bucketFromModule st`, per_operator returns `s!"op:{headName}"`
- **shortNameFromLeanName helper:** extracts last component of a Lean Name
- **Three bucketing sites updated:**
  - Site 1 (rel arity fallback, ~line 283): uses fnName short name
  - Site 2 (generic app fallback, ~line 310): uses fnName short name
  - Site 3 (projection, ~line 403): per_operator uses `proj:{typeName}/{idx}` (restores
    documented intent from stale comment); module uses `proj:{bucket}/{idx}` (unchanged)
- **HOF site (~line 322):** unchanged in both modes (structural marker, not operator
  identity)
- **Entry points:** `extractGraphFromConstantInfo`, `graphFromExpr`,
  `extractGraphFromDeclaration` all accept `bucketMode := .module` (backward compatible)

### Lean changes (Decoder.lean)

- Added `op:` and `proj:` cases to `parseOperationOpToken` (prevents silent `.pow` fallback
  on decode — without these, `op:mul_comm` would be silently corrupted to `pow`)

### Lean changes (corpus builder chain)

- `ProcessingPipeline.lean`: `transpileLeanToGraph` and `processDeclaration` accept
  `bucketMode`
- `MathlibCorpusBuilder.lean`: `buildMathlibIRCorpus` and
  `buildMathlibIRCorpusCustomModules` accept `bucketMode`
- `BuildCorpus.lean`: parses `--per-operator` CLI flag

### Python changes (build_dataset.py)

- `build_ir_vocab`: `op:` tokens below frequency threshold (5) excluded from vocab;
  `proj:` tokens always kept (deterministic, low-count by nature)
- `encode_ir`: below-threshold `op:` tokens map to `GEN_UNK`
- `--bucket-mode` CLI flag: `module` (default, v2.0.0) | `per_operator` (v2.1.1)
- Auto-sets `representation_id` from bucket mode

### Test changes

- `CorpusPipelineTests.lean`: projection test updated to test both module mode
  (`proj:GEN_MATHLIB/0`) and per_operator mode (`proj:Semigroup/0`)
- `InjectivityTests.lean`: polarity test updated (polarity does NOT affect token output,
  C1 removed it)

---

## Verification gates

**Gate 1 — headShortName threading ✅ PASSED.** `shortNameFromLeanName` extracts the last
component of a Lean Name. Verified via compilation and projection test.

**Gate 2 — mode isolation ✅ PASSED.** Projection test confirms mode switch changes only
the operation op payload (module → `proj:GEN_MATHLIB/0`, per_operator →
`proj:Semigroup/0`). Entity/relation/attribute structure unchanged.

**Gate 3 — op:/proj: round-trip ✅ PASSED.** Decoder cases added; compilation succeeds.
(Pre-existing decoder round-trip failures are documented in V2_NEXT_STEPS — unrelated to
per_operator changes.)

**Gate 4 — vocab-size report ✅ PASSED (2026-10-27).** The per_operator vocab is
~4× the module vocab, so the experiment is informative (not near-identical by
construction). Evidence, from tracked artifacts:

| Artifact | Mode | Vocab (incl. `<PAD>`) | Vocab (content tokens) |
|---|---|---|---|
| `datasets/vocab_A.json` | module (GEN_* buckets) | 602 | 601 |
| `datasets/vocab_A_v1.json` | per_operator (gen:FullName) | 1236 | 1235 |

- `Corpus/corpus_manifest.json` records `"format": "per_operator"`, `n_declarations: 4029`
  (sha256 `1376cf2a…`).
- `datasets/vocab_A_v1.json` holds `gen:FullName` tokens (`gen:hof`, `gen:Set`,
  `gen:Membership.mem`, …) — the per_operator token format — while `datasets/vocab_A.json`
  holds only `GEN_*` bucket tokens. The two differ by exactly the un-bucketing.
- Verdict: **601 → 1235** content tokens. Since 1235 is far more than the 601 module
  vocab (not "within 10%"), the DEC-028 decision rule does **not** trigger a threshold
  lowering. Gate 4 passes.

**⚠ Unresolved discrepancy — the "2254" figure is not in any tracked artifact.**
`AGENTS.md`, `docs/decisions/DEC-030.md`, `docs/reference/EXPERIMENT_MEASUREMENT.md`
and others cite the A_v3_2ep per-operator vocab as **2,254**. That number appears in
no tracked artifact in this repository:
- the tracked per_operator vocab `datasets/vocab_A_v1.json` is **1,236** entries;
- `RUN_REGISTRY.md` lists A-v3 at **8,102** and the earlier per-op runs at **8,144**;
- `python/build_perop_dataset.py` (the per-op builder) targets a **8,102**-vocab
  checkpoint and writes to the gitignored `datasets_perop/`, which is not present here.

The three values (1,236 / 2,254 / 8,102) come from different vocab-construction rules
(threshold, `TERM_MANY` filtering) and cannot be reconciled without rebuilding the
corpus. The corpus bytes are not mirrored (rebuild-on-demand, maintainer decision on
#57, `RUN_REGISTRY.md`) and are gitignored, so the discrepancy cannot be settled in
this environment. **The 2,254 figure should be treated as unverified until the
per_operator corpus is rebuilt and its vocab counted.** Recorded here rather than
copied forward, per the issue's instruction to confirm against artifacts.

**Original Gate 4 procedure (retained):**
1. `lake build Mathlib` (one-time, ~10-20 min)
2. `lake exe buildCorpus --per-operator`
3. `python3 python/build_dataset.py --bucket-mode per_operator`
4. Report vocab size. If within 10% of 601, lower `GEN_UNK_THRESHOLD` to 2 or 1.

Decision rule: if per_operator vocab is barely larger than module vocab (601), the
experiment is uninformative — per_operator would be near-identical to module mode by
construction. Lower the threshold before running.

---

## The experiment (not yet run)

Run variant A (per_operator IR) and variant B-small (BPE truncated to per_operator vocab
size) with identical hparams to the existing v2 runs. Compare perplexity and top-1
accuracy. This is the same control structure as DEC-027, just under the new representation.

- **Vocab-size matching:** B-small must be truncated to match A-per_op's vocab size (not
  the old 601), so the size-control invariant holds.
- **Versioning:** `semantic_graph_ir_v2_1_1` for per_operator.
- **Scale note:** At 14 modules / 3.5K examples, the per_operator vocab is smaller than at
  full Mathlib. A null at this scale is still suggestive. A positive result is more
meaningful.

---

## What this spec deliberately does NOT include

- No removal of `module` mode (kept as control + backward compat)
- No change to HOF (`"hof"`) or relation-arity-fallback bucketing
- No proof-term changes (that's Concern #2; the two compose but are separate specs)
- No full-Mathlib-scale run (14-module scale, same as existing v2)
- No threshold tuning beyond applying the existing `GEN_UNK_THRESHOLD = 5` to `op:` tokens
