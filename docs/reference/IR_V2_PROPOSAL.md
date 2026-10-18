# IR v2 Proposal: semantic_graph_ir_v2_candidate_1

**Date:** 2026-08-03  
**Reference:** DEC-021 (post-Phase 6 analysis)  
**Status:** Implemented (DEC-026, commit `f194027`). See `docs/experiments/V2_COMPARISON_MATRIX.md` for results.  
**Implementation:** Requires changes to `MetaExtractor.lean` (out of scope for this proposal)

---

## Executive Summary

The current IR (`semantic_graph_ir_v1_2_0`) trails BPE baselines by ~0.17 perplexity points and ~6-7% completion accuracy across Phases 5, 6, and DEC-021. Analysis (see `docs/reference/IR_SCHEMA.md`) identifies ~40-50% of sequence tokens as structural noise that does not contribute to predictive signal:

- **Polarity tokens** (`pos`, `neg`, `neut`) are 99.7% `neut` — inflating sequences by ~24%
- **`eq` relations** comprise 83% of R rows — these are mostly type annotations
- **Attribute (A) rows** may duplicate information available in operation (O) rows
- **IO markers** create 7,014 unique tokens for simple positional patterns

This proposal defines `semantic_graph_ir_v2_candidate_1`, a streamlined IR that removes identified noise while preserving the core semantic content.

---

## 1. What to Keep from v1.2.0 and Why

### Keep: Graph Structure (E/R/O Rows)

The graph representation is the core hypothesis of the Maith project. The E/R/O row structure:
- Establishes entities before using them
- Makes dependency relationships explicit
- Is essential for the decompiler to reconstruct expressions

**Verdict:** Keep unchanged.

### Keep: Positional Binder References (FVAR_N, BVAR_N, TERM_N)

Binder and term references are essential for completion:
- The model must know which variable/term is being referenced
- Positional encoding is the correct trade-off (avoiding 21k unstable scoped names)

**Verdict:** Keep unchanged.

### Keep: `gen:*` Named Constants

Named constants are the primary semantic content:
- 628 unique tokens covering the corpus vocabulary
- The model predicts these to complete expressions
- Collapse-to-GEN_UNK for frequency < 5 is acceptable

**Verdict:** Keep unchanged (with current GEN_UNK threshold).

**Update (DEC-026):** C4 superseded this — `gen:FullName` tokens are now bucketed
by module into `GEN_<area>` tokens (GEN_ALGEBRA, GEN_ORDER, etc.) at
`build_dataset.py` encode time, not kept granular. See `ENCODER_FORMAT.md` v2.0.0.

### Keep: Relational Operators (eq, lt, le, gt, ge)

Non-trivial relations carry signal. However, `eq` (83% of relations) should be handled differently (see Section 2).

**Verdict:** Keep for non-trivial relations; collapse `eq` into implicit type annotations.

---

## 2. What to Remove or Collapse

### Remove: Polarity Tokens

**Current:** Every E/A/R/O row has a polarity token (`pos`/`neg`/`neut`)  
**Frequency:** `neut` appears 186,914 times (99.7% of all polarity tokens)  
**Waste:** ~24% of sequence length

**Proposal:** Remove polarity tokens entirely. Encode `pos`/`neg` as a prefix modifier when genuinely needed (e.g., `NEG_EQ` instead of separate `neg` + `eq` tokens).

**Rationale:** If 99.7% of polarity tokens are `neut`, the model learns to ignore polarity. Removing it reduces sequence length without information loss.

### Collapse: `eq` Relations into Entity Declarations

**Current:** R rows express type annotations: `R FVAR_0 TERM_0 eq neut`  
**Frequency:** 83% of all relations are `eq`  
**Waste:** 30,411 tokens (4% of corpus)

**Proposal:** Merge type information into E row declarations:
```
# Current v1.2.0
E TERM_0 neut
R FVAR_0 TERM_0 eq neut

# Proposed v2
E TERM_0 type:TERM  # Type annotation embedded in E row
```

This eliminates the most common R-row pattern entirely.

### Collapse: IO Markers

**Current:** `inputs:FVAR_0,FVAR_1` creates 7,014 unique tokens  
**Frequency:** `inputs:FVAR_0` alone appears 4,943 times  
**Waste:** High token count with low information density

**Proposal:** Replace IO markers with positional counts:
```
# Current v1.2.0
O inputs:FVAR_0,FVAR_1 output:TERM_2 gen:Semigroup.toMul neut

# Proposed v2
O 2 3 gen:Semigroup.toMul  # 2 inputs, output at position 3
```

This collapses 7,014 tokens into ~10 (arity 0-9).

### Evaluate: Attribute (A) Rows

**Current:** A rows assign attributes to entities: `A BVAR_1 typeclass CommMagma neut`  
**Frequency:** 13,647 tokens  
**Concern:** A rows may duplicate information available in O rows (the operation that consumes the entity implies its type)

**Proposal:** Test two variants:
1. **Keep A rows** (v2a) — conservative, preserves all information
2. **Remove A rows** (v2b) — aggressive, tests redundancy hypothesis

Run ablation experiment to determine if A rows improve or are redundant.

---

## 3. What to Add

### Add: Cross-Graph Semantic Anchors (Type-Role Tokens)

**Problem:** `FVAR_0` in one graph has no relationship to `FVAR_0` in another (per ENCODER_FORMAT.md). The model cannot learn "the first bound variable usually represents the carrier type."

**Proposed Solution:** Add a type-role prefix to binder declarations:

```
# Current v1.2.0
GRAPH_BEGIN
E FVAR_0 neut
E FVAR_1 neut
...

# Proposed v2 with type roles
GRAPH_BEGIN
E FVAR_0 ROLE:CARRIER neut  # First forall binder is the structure
E FVAR_1 ROLE:INSTANCE neut   # Second is a typeclass instance
E FVAR_2 ROLE:ARGUMENT neut   # Additional arguments
...
```

**Concrete Type Roles (initial set):**
- `ROLE:CARRIER` — First/type-level forall binder (e.g., `G` in `Group G`)
- `ROLE:INSTANCE` — Typeclass instance binders
- `ROLE:ARGUMENT` — Operation arguments
- `ROLE:RESULT` — Result type
- `ROLE:PROPERTY` — Property/relation binders

**Implementation:** Derive from binder scope string analysis in `MetaExtractor.lean`:
- Scope containing `∀:` at top level → `CARRIER` or `ARGUMENT`
- Scope containing `[...]` → `INSTANCE`
- Scope containing `λ:` → argument role

**Rationale:** This gives the model semantic anchors across graphs without increasing token count significantly (10-20 new tokens).

### Regarding Attribute (A) Token Redundancy

The A rows add type information (`typeclass`, `sort`, `literal`) that could potentially be inferred from O rows. However:

**Evidence against removal:**
- A rows appear in 81% of examples
- Typeclass attributes help distinguish between structural vs instance entities

**Evidence for removal:**
- The head symbol in O rows (e.g., `gen:CommMagma.toMul`) implies the typeclass
- Removing A rows would reduce sequence length by ~14K tokens

**Decision:** Implement as ablation (v2b without A rows) rather than removing by default.

### Regarding Polarity (`pos`/`neg`/`neut`)

**Current:** Polarity appears on every E/A/R/O row  
**Distribution:** 99.7% `neut`, <0.3% `pos` or `neg`

**Decision:** Remove polarity tokens entirely. If `pos`/`neg` carry signal in specific contexts (e.g., equation rewriting), encode them as prefix modifiers:
- `POS_EQ` instead of `eq pos`
- `NEG_EQ` instead of `eq neg`
- Default (`neut`) is implicit

This collapses 3 tokens into 1 while preserving signal for non-default cases.

---

## 4. Token Efficiency Target

**Current v1.2.0 Performance:**
- Mean sequence length: 226 tokens
- Trailing BPE (Variant B) by 0.15-0.17 perplexity points

**v2 Efficiency Targets:**

| Metric | v1.2.0 | v2 Target | Change |
|--------|--------|-----------|--------|
| Mean sequence length | 226 | ≤200 | -12% |
| Unique token types | 8,144 | ≤1,000 | -88% |
| Token types (excluding gen:*) | ~300 | ≤50 | -83% |
| Polarity token overhead | 24% | 0% | -24pp |
| IO marker overhead | 13.5% | ~2% | -11pp |

**Justification for Sequence Length:**

If v2 achieves ≤200 mean tokens vs BPE's 405 mean tokens, the IR is still 2x shorter than BPE. The efficiency argument is not about matching BPE length but about:
1. Reducing noise tokens
2. Improving signal-to-noise ratio
3. Enabling the model to focus on semantic content

**Acceptable if:** Completion accuracy improves or remains within 1% of v1.2.0 despite shorter sequences.

---

## 5. Concrete Flat-IR Ablation

To answer "Is the graph structure helping at all?", define a flat-IR baseline:

### Flat IR Specification

```
FLAT_IR_V1:
  HEAD <head_symbol>
  ARITY <n>
  BINDER_DEPTH <n>
  UNIVEL <level>
  ARG_1_TYPE <type_ref>
  ...
  ARG_N_TYPE <type_ref>
```

**Token breakdown:**
- `HEAD`: The main operation/target (e.g., `gen:Semigroup.toMul`)
- `ARITY`: Number of arguments (0-9, collapsed token)
- `BINDER_DEPTH`: Nesting depth of binders (0-9)
- `UNIVEL`: Universe level (categorical: u_0, u_1, u_2, MAX)
- `ARG_N_TYPE`: Type role of each argument (CARRIER, INSTANCE, ARGUMENT)

**Example transformation:**

```
# Current IR (v1.2.0)
GRAPH_BEGIN
E FVAR_0 neut
E FVAR_1 neut
E TERM_0 neut
A FVAR_1 typeclass Semigroup neut
R FVAR_0 TERM_0 eq neut
O inputs:FVAR_0,FVAR_1 output:TERM_1 gen:Semigroup.toMul neut
GRAPH_END

# Flat IR (v1)
FLAT_HEAD gen:Semigroup.toMul
FLAT_ARITY 2
FLAT_DEPTH 1
FLAT_UNIV u_1
FLAT_ARG_TYPE CARRIER INSTANCE
```

**Token count comparison:**
- v1.2.0: 22 tokens
- Flat IR v1: 7 tokens

**Test Protocol:**

1. Implement Flat IR v1 in `MetaExtractor.lean`
2. Build dataset with Flat IR tokens
3. Train on Flat IR variant (Variant D in experiment matrix)
4. Compare against:
   - Variant A (v1.2.0 IR)
   - Variant B (BPE baseline)

**Decision Criteria:**
- If Flat IR ≈ Variant A: Graph structure is noise; collapse to flat
- If Flat IR << Variant A: Graph structure carries signal; keep
- If Flat IR ≈ Variant B: IR encoding is noise; use BPE
- If Flat IR > others: Something is wrong with the experiment

---

## 6. Registration Command

To register this candidate in the family registry:

```bash
python3 python/register_representation.py \
  --family-id semantic_graph_ir \
  --representation-id semantic_graph_ir_v2_candidate_1 \
  --status planned \
  --notes "Streamlined IR proposal based on DEC-021 analysis. Removes polarity tokens, collapses eq relations, reduces IO marker granularity, adds type-role prefixes for cross-graph identity. Includes flat-IR ablation variant."
```

**Registration metadata:**
- Family: `semantic_graph_ir`
- Candidate: `semantic_graph_ir_v2_candidate_1`
- Status: `planned`
- Core contract: `core_v1` (preserves `gen:*` token semantics)
- Key changes: polarity removal, relation collapse, IO marker simplification, type-role prefixes

---

## Implementation Plan

### Phase 1: Lean Implementation (MetaExtractor.lean changes)

1. **Remove polarity emission** — Stop emitting `pos`/`neg`/`neut` tokens; default to implicit neut
2. **Collapse eq relations** — Merge type annotations into E row declarations
3. **Simplify IO markers** — Replace `inputs:X,Y` with arity count
4. **Add type-role prefixes** — Derive from binder scope analysis

### Phase 2: Dataset Build

1. Register new representation ID
2. Rebuild corpus with v2 IR
3. Validate round-trip (encode → decode → compare)

### Phase 3: Ablation Experiment

1. Build Flat IR variant
2. Run A/B/C/D experiment (D = Flat IR)
3. Compare completion accuracy and perplexity

### Phase 4: Decision

- If v2 ≤ v1.2.0 on all metrics: Promote v2 to active
- If v2 < v1.2.0 but Flat IR ≈ v2: Collapse to flat representation
- If v2 > v1.2.0: Investigate; may need schema adjustment

---

## References

- `docs/reference/ENCODER_FORMAT.md` — Current IR token grammar
- `docs/reference/IR_SCHEMA.md` — Detailed analysis of current schema
- `docs/decisions/LOG.md` — DEC-006 through DEC-021
- `docs/reference/REPRESENTATION_EVOLUTION.md` — Registration and evolution workflow
- `Scripts/representation_families.json` — Current registered candidates
