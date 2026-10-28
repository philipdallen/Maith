# Spec: communication-protocol substrate (T7) for the benchmark corpus

**Date:** 2026-10-28
**Status:** Draft spec — no Lean, no Python. Not yet a claimed formalization task.
**Scope:** Turn the `TRANSFER_TARGETS.md` **T7** entry into a formalization-ready
substrate spec: the model, the lower-bound statements with citations, what Maith
extraction needs from each statement, and the open questions.
**Issue:** Maith #115 — "Spec: communication-protocol substrate (T7) for the
benchmark corpus".
**Do not touch:** `PleaNP/`, `Maith/*.lean`, `python/*.py`, `axiom-rewrite/`
(harness, ledger, `specs/` JSON fixtures), `Scripts/BuildCorpus.lean`. This is a
document. It decides nothing the maintainer has not already decided.

---

## 0. Placement note (read first)

The issue asked for this document "under `axiom-rewrite/specs/` (matching existing
spec location)". That path is **not** the spec location for this kind of document.
`axiom-rewrite/specs/` holds the harness's *candidate fixtures* — one JSON object
per candidate φ, in the schema `axiom-rewrite/README.md` §"Record schema" defines
(`control_valid.json`, `fixture_transfer_fails.json`, `fixture_unit_collapse.json`).
The harness globs that directory for `*.json` (`harness.py:318-321`, `:338`) and the
schema validator rejects anything that is not a candidate record.

The established location for **spec documents** in this repo is `docs/`:

| Spec document | Location |
|---|---|
| `SPEC_V3_SEMANTIC_REDUNDANCY.md` (#118) | `docs/reference/` |
| `SPEC_PER_OPERATOR.md` | `docs/reference/` |
| `SPEC_PROOF_TERMS.md` | `docs/reference/` |
| `SUBSTRATE_GAP_SCOPE.md` (#98, the parent of this spec) | `docs/experiments/` |

This document therefore lands in `docs/experiments/`, beside its parent
`SUBSTRATE_GAP_SCOPE.md` and its source `TRANSFER_TARGETS.md`. The issue's
parenthetical is a stale detail; this note records the deviation so it can be
corrected. See the done comment on #115.

---

## 1. What the substrate must make expressible

T7's operational half is a **transfer target**, not a proof obligation: the corpus
needs the *statement shape* of the monotone depth lower bound — the same bar
`PleaNP.Circuits.parity_notin_AC0 : Prop` was held to (a rendered statement, not a
proof). From `TRANSFER_TARGETS.md:170-183`, the target statement is:

> For monotone functions, circuit **depth** equals the **communication complexity**
> of the monotone Karchmer–Wigderson (KW) game, yielding tight monotone depth lower
> bounds (st-connectivity Ω(log² n), k-clique Ω(k log n)). No super-logarithmic
> general depth lower bounds are known for explicit Boolean functions.

Three objects must exist as Lean definitions before that statement can be rendered:

1. a **two-party deterministic protocol model** for a relation `R ⊆ X × Y × Z`,
   with a **communication-cost** measure (the thing the KW theorem equates depth
   with);
2. the **KW game relation** for a monotone function (Alice holds a 1-input, Bob a
   0-input, output an index where they differ);
3. the **statement shape** `monotone_depth_eq_KW_cost : Prop` — the equality of
   `MonotoneGate`-family depth with the KW game's communication cost.

`SUBSTRATE_GAP_SCOPE.md` §1.1 records that **nothing upstream today** provides any
of this: a case-insensitive search of PleaNP's `lean/` for `Karchmer`, `Wigderson`,
`communication`, `protocol` returns only unrelated hits (the Aaronson–Wigderson
*algebrization* barrier, and the word "protocol" in prose comments). This substrate
is **entirely new** — unlike the T9 (Frege) and T10 (ACC⁰[p]) substrates, which
have upstream shape-siblings, T7's has none (`SUBSTRATE_GAP_SCOPE.md` §1.2,
summary table). That is why the parent note flags it as the largest of the three
and possibly over one run (Q3 there).

---

## 2. The model — two-party deterministic communication

### 2.1 Relation and inputs

A communication problem is a relation on three sets:

- `X` — Alice's input set;
- `Y` — Bob's input set;
- `Z` — the answer/output set.

`R : X → Y → Z → Prop` (curried, matching the repo's `Prop`-first style, cf.
`parity_notin_AC0`). A protocol is *correct for `R`* when, on every `(x, y)` with
some valid `z`, it outputs a `z` with `R x y z`.

### 2.2 Deterministic protocol as a decision-tree / transcript object

The minimal formalization is a **deterministic protocol tree** over the two inputs
(equivalently, a pair of decision trees that alternate by turn). The natural Lean
shape mirrors the repo's existing recursive circuit gates
(`BoolGate`, `MonotoneGate`) rather than introducing an interactive-process type:

- a protocol is either a **leaf** carrying an output `Z`, or a **node** owned by
  Alice or Bob that branches on the owner's input and recurses;
- the owner and the branching predicate must be *readable* from that owner's input
  alone — this is the formal content of "each party sees only its own side".

Named definitions to introduce (draft names; the formalization task fixes them):

| Name | Shape | Meaning |
|---|---|---|
| `TwoPartyProtocol X Y Z` | inductive | Leaf (`Z`) or node (`owner`, branch predicate on the owner's input, two sub-protocols) |
| `TwoPartyProtocol.valid` / `correct` | `Prop` | The transcript for `(x, y)` reaches a leaf `z` with `R x y z` |
| `TwoPartyProtocol.cost` | `ℕ` | **Communication cost:** the maximum number of *rounds* (owner switches) on any root-to-leaf path — the quantity the KW theorem compares to circuit depth |
| `CC R` / `commComplexity R` | `ℕ` / `WithTop ℕ` | `⨅` over correct protocols of their `cost` (the deterministic communication complexity of `R`) |

Design note: the model must be **deterministic** to match KW. Randomized and
distributional communication models are out of scope (see §8) — the T7 statement
quoted above is about the deterministic game.

### 2.3 Why "rounds" and not "bits"

KW's theorem equates circuit **depth** with communication **rounds** in the
canonical statement (each round = one level of the protocol tree = one circuit
gate layer). Some presentations state it in bits for a fixed alphabet. The spec
should pick **rounds** as the primary cost measure because the T7 statement is a
*depth* equality, and record the bits variant as an open question (§7, Q2) rather
than defining both.

---

## 3. The KW game

### 3.1 The game

For a monotone Boolean function `f : (Fin n → Bool) → Bool`, the Karchmer–Wigderson
game is the relation

```
KW f : {x // f x = true} → {y // f y = false} → Fin n → Prop
KW f x y i  :=  x.val i ≠ y.val i
```

Alice holds a **1-input** (`f x = true`), Bob a **0-input** (`f y = false`); they
must agree on an **index where the inputs differ**. Monotonicity guarantees such an
index always exists, so the relation is total on its domain — this is the fact that
makes the game well-posed and is itself a small lemma worth stating.

Named definitions to introduce:

| Name | Shape | Meaning |
|---|---|---|
| `kwRelation f` | relation on `{x // f x} × {y // ¬f y}` | The KW game relation above |
| `kwExistsDiff f` | lemma | Monotonicity ⇒ a differing index exists (totality of the relation) |
| `kwCommCost f` | `ℕ` | `commComplexity (kwRelation f)` — the KW game's communication cost |

### 3.2 The theorem shape

The rendered statement is the equality of the monotone circuit depth of `f` (over
`PleaNP.Circuits.Monotone.MonotoneFamily` / `MonotoneGate.depth`, reusing the
existing substrate) with the KW game's communication cost:

```lean
-- draft; the formalization task fixes names and the exact quantifier shape
def monotone_depth_eq_KW_cost : Prop :=
  ∀ (f : (Fin n → Bool) → Bool), Monotone f →
    monotoneDepth f = kwCommCost f
```

This is a `Prop` **target**: rendered, not proved (matching `parity_notin_AC0`).
The substrate must *reuse* `Monotone.lean`'s `MonotoneGate` / `MonotoneFamily` as
the object the game attaches to — `SUBSTRATE_GAP_SCOPE.md` §1.2 Substrate C names
that as the only reuse, since the protocol model has no upstream analogue.

---

## 4. The lower-bound statements, with citations

T7 carries two *resolved* monotone depth lower bounds that a candidate φ can
transfer/compress against, and one *open* general statement that is aspirational:

| Statement | Bound | Status | Citation |
|---|---|---|---|
| st-connectivity monotone depth | Ω(log² n) | RESOLVED | Karchmer–Wigderson 1988; Raz–Wigderson 1992 |
| k-clique monotone depth | Ω(k log n) | RESOLVED | Karchmer–Wigderson 1988; Raz–Wigderson 1992 |
| monotone matching requires linear depth | Ω(n) | RESOLVED | Raz–McKenzie 1999 |
| general (non-monotone) depth for explicit functions | no super-log bound known | **OPEN** ("a major open problem") | `TRANSFER_TARGETS.md:176-177` |

**Citations (as recorded in `TRANSFER_TARGETS.md:182-183`, verification note).**
Confirmed against: Toronto CS 2429 lecture notes; *Communication Lower Bounds via
Critical Block Sensitivity*; the hazard-free KW paper (ITCS 2023). The KW reduction
itself (Karchmer–Wigderson, "Monotone circuits for connectivity require
super-logarithmic depth", STOC 1988) is the primary source for the monotone case;
Raz–Wigderson 1992 and Raz–McKenzie 1999 extend it. The **general** case is the
open half — the spec must record it as a *reference/aspirational* target, never as
gate-3 corpus (per `TRANSFER_TARGETS.md` frozen classification, "T7 general depth |
OPEN | aspirational | no").

**Why it is hard (verbatim from T7).** The KW reduction is *exact*, so the
difficulty is transferred into communication complexity rather than solved by it:
in the general game Alice and Bob must find an index where inputs differ, and for
relations a lower bound must hold against *any* valid answer — much harder than the
monotone variant where the witness index is constrained. The spec should carry this
sentence, because it is the documented technique limitation the gate-3 corpus is
built on (a *resolved* monotone result whose technique does not lift).

---

## 5. What Maith extraction needs from each statement

Maith extracts IR from elaborated `Expr` inside a running Lean process
(`BENCHMARK_CORPUS_PLAN.md` §"Division of labor"), and `Scripts/BuildCorpus.lean`
enumerates only modules it can import. So a T7 statement is extractable only if it
lives in an importable Maith module and is enumerated there. Per statement:

- **The statement `Prop` (`monotone_depth_eq_KW_cost`).** Must be a top-level
  `def … : Prop` in the target module, so the corpus builder's existing
  declaration walk finds it the same way it finds `parity_notin_AC0`. No new
  extraction logic — this is the existing HOF/projection-expression path
  (`Tests/CorpusPipelineTests.lean`: `testHOFApplicationExtracts`,
  `testProjectionExtracts`), known-good on synthetic declarations.
- **The definitions it references (`TwoPartyProtocol`, `kwRelation`,
  `commComplexity`, `kwCommCost`, `monotoneDepth`).** Extraction needs each to be
  reachable by *name* from the elaborated `Expr` of the statement, so they must be
  **imported from PleaNP**, not shadowed by local stand-ins. A local re-definition
  "would violate the point of option (a) — importing the *real* PleaNP models — and
  would produce statements that type-check against the wrong substrate"
  (`BENCHMARK_CORPUS_PLAN.md`, quoted in `SUBSTRATE_GAP_SCOPE.md` §2).
- **Coverage caveat.** Whether these real definitions stay inside the pipeline's
  coverage is exactly the open question the coverage-map step tracks
  (`AXIOM_DISCOVERY.md` §coverage map); the spec cannot promise it, only state the
  bar. Record it as an open question (§7, Q4).
- **Enumeration.** `Scripts/BuildCorpus.lean` must list the new target module in the
  same way it lists the existing benchmark modules; the statement is invisible to
  the corpus until it is enumerated (`BENCHMARK_CORPUS_PLAN.md` §"Part 2
  constraint — RESOLVED: formalize in Maith (option (a))").

The **extraction target** is the *statement shape*, not the protocol internals: the
corpus wants the equality claim as a declaration, so the definitions above are
supporting infrastructure, not themselves corpus rows.

---

## 6. Where the substrate lives

**Decision posture (already recorded, not re-opened):** DEC-040/DEC-043 adopt
option (a) — target statements are formalized in `Maith/Benchmark/`, importing
circuit-model definitions from PleaNP. DEC-043 confirmed the cross-repo import
end-to-end; DEC-050 added the gate harness.

Applying that split to T7:

| Layer | Lives in | Why |
|---|---|---|
| Protocol model + cost + KW game + `commComplexity` (Substrate C) | **PleaNP** (upstream) | General complexity-theory model, reusable across targets; the import direction is one-way (Maith → PleaNP) |
| The T7 statement module (`T7Communication.lean`) | **`Maith/Benchmark/`** | So `Scripts/BuildCorpus.lean` can import it and the statement becomes extractable |

Concrete placement, by analogy with the existing tree (`SUBSTRATE_GAP_SCOPE.md` §2):

- Substrate C → a new `lean/PleaNP/Communication/` (no existing home; nothing in
  `Circuits/` or `ProofComplexity/` fits a protocol model).
- Target statement → `Maith/Benchmark/T7Communication.lean` (the directory is
  created by the first statement task; DEC-043's probe module was reverted).

**Import feasibility evidence.** DEC-043 verified the cross-repo import against the
real GitHub URL, and both repos pin Lean `v4.31.0` / Mathlib `v4.31.0`
(`docs/AGENT_HANDOFF.md` §"Cross-repo imports"), so there is no toolchain drift.
Feasibility of importing is settled; where the new substrate is *authored* is the
open question (Q1 in the parent note, restated here as §7 Q1).

**Sequencing (from `SUBSTRATE_GAP_SCOPE.md` §3).** The T7 chain is task 3
(substrate) → task 6 (statement). Task 3 is independent of the T9/T10 substrate
tasks (1, 2); task 6 is blocked by task 3 only. Tasks 4–6 "may be collapsed into
one `Maith/Benchmark/` task if the per-target rendering proves mechanical once the
substrate exists".

---

## 7. Open questions (listed, not resolved)

**Q1 — Does the substrate belong upstream in PleaNP, or is a Maith-local definition
acceptable?** §6 argues upstream, on DEC-040/043/050 and the corpus plan's
anti-placeholder rule. But DEC-057 did not decide this, and it changes which repo
the tasks are filed in and whether PleaNP's Rung-4 scope grows. **Needs maintainer
sign-off before any T7 substrate task is filed.** (Inherited verbatim from
`SUBSTRATE_GAP_SCOPE.md` Q1; unresolved there.)

**Q2 — Rounds or bits as the cost measure?** §2.3 picks *rounds* to match the depth
equality. The bits variant (fixed alphabet) is common in the literature and may be
needed for a faithful rendering of a specific cited bound. Decide before the
formalization task, because it fixes the type of `cost`/`commComplexity`.

**Q3 — Does the communication substrate pass the one-run size test?** It has no
upstream shape-sibling, unlike the T9/T10 substrates, so it may exceed one run
(`SUBSTRATE_GAP_SCOPE.md` Q3). If so, split it (protocol model + cost measure;
then the KW game; then the statement) rather than checkpointing. This spec is
scoped to *describing* the three pieces, not to deciding the split — but the split
is the likely filing shape.

**Q4 — Do the real PleaNP definitions stay inside the extraction pipeline's
coverage?** §5 states the bar but cannot promise coverage. Track it via the
coverage-map step (`AXIOM_DISCOVERY.md`), not by assertion here.

**Q5 — Is the general-depth (open) statement in scope for the spec at all?** §4
records it as *aspirational/reference*, matching the frozen classification. If the
maintainer wants a rendered `Prop` for the open statement too, that is a separate
statement task with no transfer value; confirm before filing.

---

## 8. Non-goals (explicit)

- **No formalization.** No Lean file, no PleaNP change, no `Maith/Benchmark/`
  module. This is a spec.
- **No proof.** The statement is rendered as a `Prop` target, like
  `parity_notin_AC0`. Proving the KW theorem is not a goal.
- **No randomized / distributional communication models.** Deterministic only
  (§2.2) — that is what the T7 statement quantifies over.
- **No general-depth lower bound.** The general case is open; the spec records it
  as a reference, never as a gate-3 corpus target (`TRANSFER_TARGETS.md` frozen
  classification).
- **No new upstream dependency.** No external communication-complexity library; the
  substrate is authored locally in PleaNP (Q1 pending).
- **No change to #26, to `TRANSFER_TARGETS.md`'s frozen list, or to the
  maintainer's step-2 filtering.** Cross-linking from the T7 entry is the only edit
  to that file.

---

## 9. Cross-references

- `docs/experiments/TRANSFER_TARGETS.md` §"T7 — Monotone depth lower bounds via
  Karchmer–Wigderson games" (source entry; cross-linked from here).
- `docs/experiments/SUBSTRATE_GAP_SCOPE.md` §1.2 Substrate C, §2, §3 task 3/6, §4
  Q1/Q3 (parent note; this spec elaborates its Substrate C).
- `docs/experiments/BENCHMARK_CORPUS_PLAN.md` §"Part 2 constraint — RESOLVED:
  formalize in Maith (option (a))" (placement + import evidence).
- `docs/experiments/AXIOM_DISCOVERY.md` §coverage map (extraction-coverage caveat).
- `docs/decisions/LOG.md` DEC-040, DEC-043, DEC-050, DEC-057 (recorded posture).
- `docs/AGENT_HANDOFF.md` §"Cross-repo imports" (Lean/Mathlib pin parity).
