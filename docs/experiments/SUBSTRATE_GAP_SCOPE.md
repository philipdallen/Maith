# Substrate gap scope — proof systems (T9) and communication protocols (T7)

**Status:** Scoping note (research only). Filed from issue #98, as the consequence
recorded in DEC-057 ("Real remaining scope limit, recorded rather than absorbed")
and `TRANSFER_TARGETS.md` §"Consequence for formalization (step 4)".

**Scope of this note:** what `PleaNP.Circuits` has today vs the minimal
formalization each missing substrate needs; where each formalization would live;
and a numbered list of fileable sub-tasks, each sized for one agent run.

**Not done here:** no Lean, no Python, no new directories, no re-derivation of the
step-2 filter (DEC-057 signed it off). The `Maith/Benchmark/` formalization work
itself is out of scope — this note only sizes it.

**Evidence base.** `PleaNP` at `main` = `9b52fb4` (2026-10-19, shallow clone);
`Maith` at `main` = `f408c1f`. All file/line citations below are against those
revisions.

---

## 1. What `PleaNP.Circuits` has today vs the minimal formalization each substrate needs

### 1.0 Correction to the DEC-057 shorthand: this is **three** substrates, not two

DEC-057 and #98 both say "**T9/T10** need a propositional-proof-system substrate".
Reading each target's own `Model:` line in `TRANSFER_TARGETS.md`, that shorthand
conflates two different gaps:

| Target | Its own `Model:` line | Substrate actually needed |
|---|---|---|
| T9 | "AC⁰-Frege / bounded-depth PK" (`TRANSFER_TARGETS.md:216`) | **proof system** (bounded-depth Frege) |
| T10 | "Constant-depth circuits with modular counting gates" (`:234`) | **circuit-model extension** (ACC⁰[p]: modular counting gates) |
| T7 (communication half) | "two-party communication complexity" (`:177`) | **communication-protocol model** (Karchmer–Wigderson games) |

T10 is Smolensky's separation, a *circuit* result — MOD_q ∉ AC⁰[p]. Its substrate is
the ACC⁰[p] circuit model, which is a sibling of the existing Boolean-gate model,
**not** a proof system. So the honest count is **three** distinct substrate gaps:
one proof system (T9), one circuit-model extension (T10), one protocol model (T7).

This is a correction to the shorthand, not to the filter: DEC-057's operational
set (T1, T4(monotone), T5, T6, T7(monotone), T9(super-poly), T10) is unchanged.
See open question Q2.

### 1.1 What exists today

**`PleaNP.Circuits` (Boolean-circuit substrate, 7 modules):**

- `Basic.lean` (204 lines): `BoolGate` inductive — gates `input | const | and | or | not`
  (`Basic.lean:43`); `BoolGate.size` / `BoolGate.depth` with `size_pos`,
  `depth_size_le`; `BoolFunc`, `CircuitFamily`, `CircuitFamily.sizeOf` / `depthOf`,
  `IsPPoly`; the natural-proofs scaffolding `PropertyFamily`, `Largeness`,
  `Constructive`, `NaturalProperty` (`:143-167`).
- `AC0.lean` (314 lines): `BoolGate.eval`, `parity`, `IsAC0`
  (`∃ d, ∀ n, depth (C n) ≤ d`), `ComputesParity`, and the frozen zero-`sorry`
  statement target `parity_notin_AC0 : Prop` (`AC0.lean:73`); plus proved
  depth-1 content (`parity_notin_AC0_relativizing`, `depth_eq_zero_iff_input`,
  `not_computes_parity_depth1`).
- `Monotone.lean` (123 lines): `MonotoneGate`, `eval`/`size`/`depth`,
  `BoolBoolLe`, `monotone_eval_preserves_order`, `MonotoneFamily`.
- `MonotoneApprox.lean` (306 lines): `Monomial`, `ApproxSet`, `Reducer.approximate`
  (the Razborov approximation machinery).
- `Restriction.lean` (221 lines): `Restriction`, `agrees`, `extend`, `apply`,
  `fixedCount`/`freeCount`.
- `Switching.lean` (199 lines): `IsRandomRestriction`, `BoolGate.IsDecisionTree`,
  `HasDTDepth`, `SwitchingLemmaStatement` / `SwitchingLemmaExists`.
- `MustRefute.lean` (62 lines).

**`PleaNP.ProofComplexity` (proof-system substrate, 2 modules):**

- `Resolution.lean` (194 lines) — the **only** real proof-system content upstream.
  Defines `Lit`, `Clause`, `CNF`, `Clause.resolve`, `ResStep`, `ResDerivation`,
  and the size/width measures; proved `resolve_sound`, `ResStep.sound`,
  `ResDerivation.sound`. Its own header says it is "Pass 1 of #75" and that
  "Pass 2 (the pigeonhole width lower bound) is tracked as a follow-up".
- `Basic.lean` (13 lines) — a **stub**. Its entire body is a comment naming
  "Resolution proof system (size, width)", "Frege systems", "PCP theorem",
  "Hardness vs. randomness" as "Planned coverage (Rung 4)", ending
  "Stub pending Rung 4."

**Communication complexity: nothing.** A case-insensitive search of `lean/` for
`Karchmer`, `Wigderson`, `communication`, `protocol` returns only unrelated hits:
the Aaronson–Wigderson *algebrization barrier* (`Barriers/Algebrization.lean:6` —
a different result), and the word "protocol" in campaign/creativity-prose comments
in `Calculus/` and `Barriers/BoundaryProbe.lean`. There is no two-party protocol
model, no transcript/communication-cost definition, and no KW game.

### 1.2 Minimal formalization each substrate needs

Each is stated as the smallest object that makes the target's statement *shape*
expressible (the same bar `parity_notin_AC0 : Prop` was held to — a rendered
statement, not a proof).

**Substrate A — bounded-depth Frege / AC⁰-Frege proof system (T9).**

- Reuse: `Resolution.lean`'s `Lit`/`Clause`/`CNF` (`Resolution.lean:42-93`) and its
  `ResDerivation` shape (`:158`) — Frege generalizes clauses to formulas.
- New minimal content: a propositional formula type (or a `Formula` alias over the
  existing `Lit`), a **bounded-depth** line/derivation model (a depth parameter on
  derivation lines, since the depth bound is what T9's statement quantifies over),
  a `size` measure, and the statement shape
  `boundedDepthFrege_notin : Prop` (the "purely exponential, depth-independent"
  form). The Cook–Reckhow system type is *not* needed for the statement shape;
  it is needed only if the T9→T8 implication (`TRANSFER_TARGETS.md:221`) is itself
  formalized, which is beyond the minimal bar.
- Cost driver: Frege is a *different* system from resolution — the derivation
  rules (substitution + structural rules over formulas) are not a small edit of
  `ResDerivation`. This is a new module, not a patch.

**Substrate B — ACC⁰[p] circuit model with modular counting gates (T10).**

- Reuse: the `BoolGate` inductive shape and its `size`/`depth` recursion
  (`Basic.lean:43-99`) and the `IsAC0` predicate shape (`AC0.lean:63`).
- New minimal content: extend the gate set with a modular-counting gate
  (`mod p`, or `threshold`), define `IsACC0p` (constant depth, polynomial size,
  gates drawn from {and, or, not, mod_p}), define the function `MOD_q`
  (mirroring `parity` at `AC0.lean:59`), and render
  `modq_notin_ACC0p : Prop`. This is the *smallest* of the three — it is a
  structural sibling of the existing AC⁰ content.

**Substrate C — two-party communication complexity + Karchmer–Wigderson game (T7).**

- Reuse: `MonotoneGate`/`MonotoneFamily` (`Monotone.lean`) as the object the KW
  game is attached to; nothing else.
- New minimal content: a two-party deterministic protocol model for a relation
  `R ⊆ X × Y × Z` (a transcript/decision-tree object with a communication-cost
  measure), the KW game relation for a monotone function (Alice holds a 1-input,
  Bob a 0-input, output an index where they differ), and the statement shape
  `monotone_depth_eq_KW_cost : Prop`. Entirely new — no upstream analogue exists
  (unlike A and B, which have shape-siblings).

**Summary table:**

| Substrate | Target | Reuses | New | Has an upstream shape-sibling? |
|---|---|---|---|---|
| A: bounded-depth Frege | T9 | `Lit`/`Clause`/`CNF`, `ResDerivation` shape | formula type, depth-bounded derivation, size, statement `Prop` | partial (Resolution) |
| B: ACC⁰[p] gates | T10 | `BoolGate`/`size`/`depth`, `IsAC0` shape | `mod p` gate, `IsACC0p`, `MOD_q`, statement `Prop` | yes (AC⁰) |
| C: communication / KW | T7 (comm. half) | `MonotoneGate`/`MonotoneFamily` | protocol model, cost measure, KW relation, statement `Prop` | **no** |

---

## 2. Where each formalization would live (upstream PleaNP vs `Maith/Benchmark/`)

**Decision posture (already recorded, not re-opened):** DEC-040/DEC-043 adopt
option (a) — the *target statements* are formalized in `Maith/Benchmark/`,
importing the circuit-model definitions from PleaNP. DEC-043 confirms the import
is verified end-to-end (PleaNP `Circuits.Basic`/`AC0` built as a dependency;
`Maith.Benchmark.Probe` built as the consumer; `PleaNP.Circuits.parity_notin_AC0`,
`IsAC0`, `IsPPoly`, `Largeness`, `NaturalProperty` all resolved). DEC-050 adds the
gate harness. `BENCHMARK_CORPUS_PLAN.md` states the constraint explicitly: writing
local stand-in definitions "would violate the point of option (a) — importing the
*real* PleaNP models — and would produce statements that type-check against the
wrong substrate."

**Therefore the split is:**

| Layer | Lives in | Why |
|---|---|---|
| **Substrate/model definitions** (A, B, C) | **PleaNP** (upstream) | General complexity-theory models, reusable across targets; Maith is the IR-extraction project and the import direction is one-way (Maith → PleaNP; PleaNP cannot import Maith). Placing them in Maith would force the local-placeholder anti-pattern the plan forbids. |
| **Target statement modules** (T9/T10/T7-comm statements) | **`Maith/Benchmark/`** | Per option (a)/DEC-040: statements live where Maith's `Scripts/BuildCorpus.lean` can import them. |

Concrete placement, by analogy with the existing tree:

- A → `lean/PleaNP/ProofComplexity/BoundedDepthFrege.lean` (sibling of
  `Resolution.lean`; the `Basic.lean` stub at `ProofComplexity/Basic.lean`
  already names Frege as planned Rung 4 coverage).
- B → `lean/PleaNP/Circuits/ACC0.lean` (sibling of `AC0.lean`/`Monotone.lean`).
- C → a new `lean/PleaNP/Communication/` (no existing home; nothing in
  `Circuits/` or `ProofComplexity/` fits a protocol model).
- Target statements → `Maith/Benchmark/T9.lean`, `T10.lean`, `T7Communication.lean`
  (the directory does not exist yet — `Maith/Benchmark/` is created by the first
  statement task; DEC-043's probe module was reverted).

**Import feasibility evidence:** DEC-043 verified the cross-repo import against the
real GitHub URL, and both repos pin Lean `v4.31.0` / Mathlib `v4.31.0`
(`docs/AGENT_HANDOFF.md` §"Cross-repo imports"), so no toolchain drift. The
*feasibility* of importing is settled; what is unsettled is where the new
substrate itself should be authored (see Q1).

---

## 3. Numbered sub-tasks, each sized for one agent run

Each names one action and one check. "One run" = the repo's ~20-minute work budget
(`docs/MULTI_AGENT_WORKFLOW.md`). The Lean-implementation tasks each carry the
toolchain caveat from §4 — that caveat is why they are listed here rather than
filed as immediately-claimable work.

1. **`PleaNP`: author the ACC⁰[p] circuit substrate (Substrate B).**
   End state: `lean/PleaNP/Circuits/ACC0.lean` defining the `mod p` gate,
   `IsACC0p`, `MOD_q`, and `modq_notin_ACC0p : Prop`; zero `sorry`; module added
   to the CI named build list. Check: `lake build` green for the module and the
   Tier-1 gates pass on it.

2. **`PleaNP`: author the bounded-depth Frege substrate (Substrate A).**
   End state: `lean/PleaNP/ProofComplexity/BoundedDepthFrege.lean` defining the
   formula type, the depth-bounded derivation, the size measure, and
   `boundedDepthFrege_notin : Prop`, built on `Resolution.lean`; zero `sorry`.
   Check: `lake build` green + Tier-1 gates.

3. **`PleaNP`: author the two-party communication / KW substrate (Substrate C).**
   End state: a new module defining the deterministic two-party protocol model,
   the communication-cost measure, the KW game relation, and
   `monotone_depth_eq_KW_cost : Prop`; zero `sorry`. Check: `lake build` green +
   Tier-1 gates. (Largest of the three; may itself need splitting — see Q3.)

4. **`Maith`: create `Maith/Benchmark/` and render the T10 statement.**
   Blocked by task 1. End state: `Maith/Benchmark/T10.lean` importing
   `PleaNP.Circuits.ACC0`, rendering the Smolensky statement as a `Prop` target;
   `Scripts/BuildCorpus.lean` enumeration updated. Check: `lake build` green and
   the statement is visible to the corpus builder.

5. **`Maith`: render the T9 statement.** Blocked by task 2. End state:
   `Maith/Benchmark/T9.lean` importing the new Frege substrate, rendering the
   "purely exponential bounded-depth Frege" statement as a `Prop`; enumeration
   updated. Check: `lake build` green + statement visible to the corpus builder.

6. **`Maith`: render the T7 communication-half statement.** Blocked by task 3.
   End state: `Maith/Benchmark/T7Communication.lean` importing the communication
   substrate, rendering the KW monotone-depth statement; enumeration updated.
   Check: `lake build` green + statement visible to the corpus builder.

Ordering: 1, 2, 3 are independent (any order); 4 ← 1, 5 ← 2, 6 ← 3. Tasks 4–6 may
be collapsed into one `Maith/Benchmark/` task if the per-target rendering proves
mechanical once the substrate exists.

---

## 4. Open questions (maintainer's judgment — not decided here)

**Q1 — Do the substrate definitions belong upstream in PleaNP, or is a
Maith-local definition acceptable?** §2 argues upstream, on the evidence in
DEC-040/043/050 and `BENCHMARK_CORPUS_PLAN.md`'s explicit anti-placeholder rule.
But DEC-057 did not decide this, and it changes which repo the tasks are filed in
and whether PleaNP's Rung-4 scope grows. Needs sign-off before tasks 1–3 are filed.

**Q2 — Is the T10 framing correction accepted?** §1.0 records that T10's substrate
is the ACC⁰[p] circuit model, not a proof system, contrary to the DEC-057 / #98
shorthand. The filter is unchanged; only the substrate description is. Confirm so
the corrected description can propagate to `TRANSFER_TARGETS.md` §"Consequence for
formalization".

**Q3 — Does task 3 (communication substrate) pass the one-run size test?** It has
no upstream shape-sibling, unlike tasks 1–2, so it may exceed one run. If so it
should be split (protocol model + cost measure; then the KW game; then the
statement) rather than checkpointed.

**Q4 — Toolchain availability for the Lean tasks.** Tasks 1–6 are Lean tasks and
therefore carry the same environment blocker PleaNP #63 records ("Lean 4 toolchain
for unattended PleaNP proof runs: provision it, or declare Lean proof work out of
scope", `status:blocked-needs-input`). Until #63 is resolved, tasks 1–3 are not
unattended-runnable. This is a fact about scheduling, not a scope decision.

**Q5 — Does T8 also need Substrate A?** T8 (Frege / Extended Frege) is classified
*aspirational* by DEC-057, so it is out of the operational (gate-3) corpus and no
substrate task is filed for it here. If T8 is later promoted, Substrate A (task 2)
largely covers it; record the decision then, not now.
