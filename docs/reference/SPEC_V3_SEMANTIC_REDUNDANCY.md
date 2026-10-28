# Spec: v3 IR semantic-redundancy candidate (H11 design-quality component)

**Date:** 2026-10-28
**Status:** Draft spec — no implementation. Not yet a claimed experiment.
**Scope:** A v3 candidate in the `semantic_graph_ir` family that *adds* semantically
meaningful, contextually predictable tokens to the v2 token stream, with a
retrieval-first evaluation plan (H6-style). Documentation only.
**Do not touch:** `Maith/*.lean`, `python/*.py`, `datasets/`, `Corpus/`, the v2.0.0
token format, `ENCODER_FORMAT.md`'s version history. This document does not change
any existing IR.

**Issue:** Maith #118 — "Spec: v3 IR semantic-redundancy candidate (C3), evaluated on
retrieval, not perplexity".

---

## 0. Naming note (read first)

The issue calls this candidate "C3". In the existing docs, **C3 already means
"attribute sparsity"** — a v2.x candidate that *removes* attribute noise
(`docs/experiments/V2_NEXT_STEPS.md` §Secondary, `docs/reference/ENCODER_FORMAT.md`
v2.0.0, `docs/reference/GLOSSARY.md`). Semantic redundancy is the **opposite
direction**: it *adds* tokens. Reusing "C3" for both is ambiguous.

This spec therefore names the candidate **`semantic_graph_ir_v3_redundancy_candidate`**
and leaves the label question to the open-questions list (§7, Q1). It is a **v3**
candidate (a new tokenization of the same `semantic_graph_ir` family), not a v2.x
tweak and not a different-structure candidate — see `GLOSSARY.md` §"family, candidate,
structure".

---

## 1. Why this candidate exists

H11 is partially closed: perplexity cannot be the sole arbiter of a semantic
representation, and the bias against the IR has **two components**
(`docs/experiments/EXPERIMENT_DESIGN.md` §"Why prediction metrics are structurally
biased toward natural language"):

- **Fundamental** — canonicalization inherently removes the multiple surface forms
  that make raw text predictable. Settled.
- **Contingent** — v1's extra tokens were *structural verbosity* (polarity, IO markers:
  predictable but meaningless, ~40–50% of tokens per DEC-024). v2 removed the noise
  (C1/C4) but **added nothing in its place**. Neither v1 nor v2 tested whether a
  canonical form can carry redundancy that is *both* semantically meaningful *and*
  contextually predictable.

This candidate is the test of the contingent component. It is a **representation
candidate**, not a metric change: the prediction is that adding semantic-redundant
tokens narrows the perplexity gap *and* improves retrieval/probing — and the
retrieval result is the one that decides whether the addition is a real gain or
just prediction padding.

---

## 2. Definitions — semantic redundancy vs structural verbosity

The design principle (quoted from `EXPERIMENT_DESIGN.md`): **every token should carry
semantic information that also constrains what comes next.**

| Property | Structural verbosity (v1) | Semantic redundancy (target) |
|---|---|---|
| Example | `neut`, `IN_3`, `OUT_VAR` | `typeclass Ring`, typed relation `eq` |
| Predictable from context? | Yes, trivially (near-constant) | Yes, but not trivially — constrained by the type/operation context |
| Carries semantic content? | No | Yes — narrows what the entity/relation *is* |
| Retrieval value | None (constant) | Yes — makes semantically related declarations more similar |

The failure mode to avoid is **adding back v1's noise under a new name**: any token
that is predictable *because it is nearly constant* and carries no discriminating
signal is structural verbosity, not semantic redundancy. Every mechanism in §3 must
state which side it falls on, and the evaluation (§5) must be able to falsify the
claim that a given token is the good kind.

---

## 3. The redundancy mechanisms (candidate token additions)

Each mechanism is stated as: **what is added**, **why it is the good kind of
redundancy**, and **what it risks**. Mechanisms are independent; the spec does not
commit to shipping all of them (see §7 Q2).

### M1 — Typed entity tokens

**Add.** Annotate a positional entity with its type when the elaborated `Expr` carries
one, so `TERM_3` in a ring context is accompanied by (or suffixed with) a type marker,
e.g. an `A TERM_3 typeclass Ring`-style row or a compound `TERM_RING_ELEM_3`.

**Why good.** The type is *predictable from the operation context* (a `mul` input is
usually a ring element) yet carries information (it distinguishes a Nat element from a
Ring element). It constrains which operations can follow.

**Risk.** The `EXPERIMENT_DESIGN` example writes the type into the token *name*
(`TERM_RING_ELEM_3`), which explodes the vocabulary and — if it replaces the positional
index — destroys the positional identity that `ENCODER_FORMAT.md` deliberately chose
(FVAR_N/BVAR_N/TERM_N are graph-local). **Preserving positional identity is a hard
constraint**; the open question is whether the type is added as a separate `A` row
(vocab-cheap, position-safe) or as a suffix on the entity token (position-unsafe).
See §7 Q3.

### M2 — Operation-specific semantic buckets

**Add.** Replace (or supplement) the coarse `GEN_<area>` bucket with a bucket derived
from the *operation's semantic class* rather than the declaration's module — e.g.
`GEN_ASSOC`, `GEN_COMM`, `GEN_DIST`, `GEN_NEUTRAL` for algebraic-law operations.

**Why good.** The bucket is constrained by the preceding typeclass context
(associativity follows a semigroup hypothesis) yet carries semantic information
(the law's shape), unlike the module bucket which is arbitrary with respect to the
operation's role.

**Risk.** Bucketing *by law* requires a classifier for operations that the current
extractor does not have — this is the Lean-side work, and it may not be decidable
syntactically. It also interacts with DEC-028 `per_operator` (which un-buckets
operators entirely) — see §6.

### M3 — Typed relations

**Add.** Distinguish relation *instances* by the type they hold on, e.g. a typed
`eq` marker reflecting the ambient type when the relation is type-restricted.

**Why good.** `eq` currently comprises 83% of R rows (`IR_V2_PROPOSAL.md`) and is
therefore near-constant — a candidate structural-verbosity token. A typed relation is
predictable from the surrounding entity types and carries discriminating content.

**Risk.** The type of an equality is usually already recoverable from its operands'
entity types (M1). If M1 ships, M3 may be redundant with it — double redundancy is
verbosity. Must be evaluated as a *pair* with M1, not independently.

### M4 — Contextual restatement (redundancy-by-repetition)

**Add.** Deliberately repeat a semantic fact already emitted earlier in the same graph
at the point where it constrains the next token (e.g. re-emit the typeclass of the
current term immediately before the operation that consumes it).

**Why good.** This is the mechanism closest to what natural language does
(agreement, articles): the repeat is *contextually predictable* and *reinforces* the
constraint, which is exactly the redundancy the model can exploit without ambiguity.

**Risk.** Highest verbosity risk of the four — it inflates sequence length with tokens
that are predictable *because they repeat*, which is close to the v1 failure mode.
This mechanism is the strongest test of the "meaningful *and* predictable" criterion;
if it does not improve retrieval, it is verbosity.

---

## 4. What stays fixed (constraints on any v3 redundancy candidate)

1. **Family and structure.** E/A/R/O rows, positional entity IDs, and the
   `GRAPH_BEGIN`/`GRAPH_END` framing are unchanged. This is a re-tokenization of the
   `semantic_graph_ir` family, not a new structure (`typed_term_ir` etc. remain out of
   scope — `GLOSSARY.md`).
2. **Positional identity is preserved.** Adding type information must not collapse
   distinct `TERM_N`/`FVAR_N`/`BVAR_N` positions onto one token (§3 M1 risk).
3. **Decompiler round-trip.** Any token that the decompiler must reverse
   (`python/validate_roundtrip.py`) needs a defined inverse. New tokens that
   are purely annotational (type markers, law buckets) must be *droppable* on decode —
   the decoder must reconstruct the same `Expr` with or without them.
4. **Encoder-version bump.** A vocabulary-affecting change is breaking and requires a
   version bump plus a new `representation_id` in
   `datasets/representation_manifest.json` (`ENCODER_FORMAT.md` — the version-bump rule
   stated at the top of that document).
5. **Quality gates first.** No v3 run is evaluated until the pipeline gates (G1–G5)
   pass and `python/check_invariants.py` is green — the same precondition every
   hypothesis test carries (`HYPOTHESIS_GRID.md` §pre-condition).

---

## 5. Evaluation plan — retrieval first, perplexity reported only

**Primary question.** Does adding semantic-redundant tokens make *semantically related
declarations more retrievable* — i.e. is the added redundancy semantic, or is it
prediction padding?

### 5.1 Design (H6-style, reuse the H6 infrastructure)

Reuse the H6 retrieval protocol verbatim where possible
(`docs/experiments/H6_RETRIEVAL_SCOPE.md`):

- **Ground truth:** a declaration D depends on E if D's IR tokens contain `gen:<E>`
  (strip `gen:hof`/`gen:proj`, drop self-references, drop out-of-pool constants).
- **Mode 1 (headline):** eval → train, query set = eval declarations with ≥1 in-train
  dependency, candidate pool = train declarations.
- **Mode 2 (density check):** train → train leave-one-out.
- **Embeddings:** extract from each variant's own `input_ids` via
  `python/extract_retrieval_embeddings.py` — **not** `extract_representations.py`
  (the input-variant bug is a documented pitfall in `AGENTS.md`).
- **Metrics:** Recall@{1,5,10,20} and MRR, with pool size reported alongside. Compare
  against the **pretrained baseline** (S1: Recall@10 = 0.072), not pure chance.

### 5.2 Variants (the comparison that can falsify the claim)

| Variant | Role |
|---|---|
| `A_v2` (current 601-token IR) | incumbent representation |
| `A_v3_redundancy` | the candidate |
| `B_small` (BPE truncated to 601, 358M) | size-matched control |
| `flat` (all content → SLOT) | shape-only ablation: bounds what *structure* alone gives |
| `pretrained` (un-fine-tuned base) | S1 baseline |

The claim is supported only if `A_v3_redundancy` beats `A_v2` on retrieval **and** the
gain is not reproduced by `flat` (which would mean the gain came from structure, not
from the redundant tokens). A tie between `A_v2` and `A_v3_redundancy` is a negative
result for the mechanism, reported as such.

### 5.3 Secondary and sanity metrics

- **Probing (H10-style):** linear probe for typeclass arity, theorem-vs-definition,
  semantic category on the same embeddings — tests whether the added tokens encode
  real semantic structure (`HYPOTHESIS_GRID.md` H10).
- **Perplexity:** reported **for completeness only**, never as the verdict. The H11
  finding is precisely that perplexity cannot be the arbiter; a perplexity win with no
  retrieval win is *prediction padding*, not a representation gain.
- **Invariant checker** must pass before any extraction or eval runs.

### 5.4 Pre-registration

The success/failure thresholds must be fixed **before** the run, in the style the
portfolio already uses for pre-registered criteria. The spec deliberately does **not**
set the numbers here — that is a separate step, and setting them after seeing the
result would defeat the test.

---

## 6. Relationship to existing specs and decisions

- **DEC-028 `per_operator` (un-bucketing)** and **M2 (semantic bucketing)** pull in
  opposite directions. `per_operator` restores operator identity; M2 replaces one
  bucketing axis with another. They are not necessarily contradictory (a per-operator
  stream could still carry a semantic-class marker), but they must not both be
  evaluated as if independent — the combined representation needs its own candidate ID.
  See `docs/reference/SPEC_PER_OPERATOR.md`.
- **DEC-029 proof-term extraction** changes the sub-graph the tokens describe; a
  redundancy candidate evaluated on statement-only graphs may not transfer to
  proof-enabled graphs. `SPEC_PROOF_TERMS.md` composes here as a later axis.
- **C3 = attribute sparsity** (`V2_NEXT_STEPS.md`) is a *removal* candidate; it is not
  this one (§0). If both are ever built, they are separate candidates in the same grid.

---

## 7. Open design questions (listed, not resolved)

> Per the issue's Definition of Done, these are recorded as questions. None is
> answered by assertion in this document.

- **Q1 — Label.** Is this candidate "C3", a new "C5", or a named v3 candidate? The
  current C3 label is taken by attribute sparsity. Owner decision.
- **Q2 — Which mechanisms ship?** M1–M4 are independent. Is the candidate M1 only, a
  bundle, or a factorial set of candidates (one per mechanism) so each can be
  attributed? The factorial design costs more runs; the single-bundle design cannot
  attribute a null.
- **Q3 — Position vs type.** Does the type annotation ride as a separate `A` row
  (position-safe, vocab-cheap) or as a compound entity token (position-unsafe, larger
  vocab)? This determines whether M1 is admissible at all under constraint §4.2.
- **Q4 — Is M4 (restatement) distinguishable from v1 verbosity?** What observable
  separates "contextually predictable *and* meaningful" from "predictable because it
  repeats"? The retrieval delta is the proposed discriminator, but that assumes the
  retrieval test is sensitive to this difference — unverified.
- **Q5 — Classifier for M2.** Can an operation's semantic law-class (assoc/comm/dist)
  be derived from the elaborated `Expr` without a hand-maintained table, and is that
  derivation stable across Mathlib? Unknown; needs a Lean-side feasibility probe.
- **Q6 — Thresholds.** What retrieval delta counts as support, and over how many
  queries, given the S1 pretrained baseline noise? To be pre-registered separately.
- **Q7 — Vocab budget.** What is the maximum acceptable vocabulary size for a v3
  candidate before it stops being "size-matched" to the 601-token control? Without a
  ceiling, a redundancy candidate can win by simply growing the embedding table.

---

## 8. Non-goals (explicit)

- **No perplexity-only verdict.** Perplexity is reported for completeness; it cannot
  close or open the candidate on its own (H11).
- **No implementation.** This is a spec. No Lean, no Python, no dataset rebuild, no
  training run, no corpus change.
- **No change to the v2 IR.** v2.0.0 is untouched; this document describes a separate
  candidate.
- **No re-litigating the metric.** The evaluation family (retrieval/probing primary,
  perplexity secondary) is fixed by H11 and `EXPERIMENT_DESIGN.md`; this spec adopts
  it rather than re-arguing it.
- **No commitment of the mechanism set or thresholds** — those are §7 open questions.

---

## 9. Implementation sketch (named files, out of scope here)

For the eventual implementation task (a *separate* issue, not this one):

| Layer | File | Change |
|---|---|---|
| Extraction | `Maith/MetaExtractor.lean` | emit the type/law annotation for M1/M2 |
| Encoding | `Maith/Encoder.lean` | new token emission; version bump |
| Decoding | `Maith/Decoder.lean`, `Maith/Transpiler.lean` | drop annotational tokens on decode (§4.3) |
| Dataset | `python/build_dataset.py` | new `representation_id`, bucket-mode parity |
| Eval | `python/extract_retrieval_embeddings.py` | reuse; add the v3 variant |
| Registry | `datasets/representation_manifest.json`, `docs/experiments/RUN_REGISTRY.md` | register the new representation |

Each of these is a step in a split, not one task — see the operating contract's
right-sizing rule.
