# Transfer Targets — circuit / proof / communication complexity (corpus plan Part 2)

**Status:** research pass complete (step 1); **awaiting human filtering (step 2)**.
**Issue:** Maith #26. **Date:** 2026-09-16.

**Provenance of this list.** `BENCHMARK_CORPUS_PLAN.md` Part 2 assigns step 1 to a
DeepSeek research pass. That tool was not available in this environment, so step 1
was executed with a **web research pass** instead (Tavily, targeted queries, primary
sources preferred). That substitutes the *tool*, not the *role*: the maintainer's
step-2 filtering and sign-off are still required and have **not** happened.

**How to read each entry.** Every candidate carries its citation, its current
status, the documented reason it is hard, and a verification note. Anything I could
not confirm against a primary source or a reliable secondary is marked as such
rather than smoothed over.

---

## The distinction this list is organised around

`BENCHMARK_CORPUS_PLAN.md` Part 2 asks for results that are "**open or hard**". Those
are not the same thing for this track, and conflating them would quietly change what
a candidate φ is being tested against:

- **OPEN** targets — no known proof. A φ that reaches one is a *new result*.
  (Highest value, lowest probability.)
- **RESOLVED, but only by an unusually novel technique** — a proof exists, but the
  literature documents that the technique was special, or that a barrier blocks the
  obvious approach. A φ that *re-derives* one of these has produced a **transfer /
  compression test**: the theorem is known, so the win is that a small generator
  repays across scales (the "fractal" signal in `AXIOM_DISCOVERY.md`).
- **NEGATIVE (barrier) results** — meta-theorems stating what *cannot* be proved by a
  technique family. These are the screening instruments, not targets: they are what
  `#barrier_check` operationalises, and a candidate that trips one is dead.

The list below therefore includes all three, labelled. My reading of the plan is
that OPEN and RESOLVED-novel are the targets proper, and NEGATIVE is reference
material — but that is an interpretation the maintainer should confirm at step 2.

---

## The targets

### T1 — Parity ∉ AC⁰

- **Statement.** The PARITY function requires exponential size for constant-depth
  circuits over {AND, OR, NOT} with unbounded fan-in.
- **Model.** AC⁰ (constant depth, poly size).
- **Status.** **RESOLVED** (Furst–Saxe–Sipser 1984; Ajtai 1983; Yao 1985; Håstad
  1986 for the tight bound).
- **Why it is hard / what it illustrates.** The switching lemma is the canonical
  technique; it is *AC⁰-natural* in the Razborov–Rudich sense, and works precisely
  because AC⁰ is too weak to compute pseudorandom functions. This makes it the clean
  demonstration of *where the natural-proofs barrier bites and where it does not*.
- **Relevance to this repo:** high — it is the one target PleaNP already has
  **stated but unproved**: `PleaNP.Circuits.AC0.parity_notin_AC0` is a
  `def : Prop` with no proof (`AC0.lean`), and PleaNP #72 is the in-progress proof
  via the switching lemma. It also has partial results landed
  (`parity_notin_AC0_relativizing`, depth-0/1 exclusion lemmas).
- **Verification:** confirmed against multiple sources incl. the CKK survey
  (`Lower Bounds against Weakly-Uniform Threshold Circuits`) and standard texts.

### T2 — TC⁰ lower bounds for an explicit function

- **Statement.** **No explicit function is known to require super-polynomial size
  for constant-depth threshold circuits (TC⁰).** Stated more starkly in the
  literature: no function in EXPNP is even known to be hard for TC⁰.
- **Model.** TC⁰ (constant depth, polynomial size, unbounded fan-in majority / LTF).
- **Status.** **OPEN.**
- **Why it is hard.** Explicitly attributed to the natural-proofs framework: TC⁰ is
  believed (under widely-held cryptographic conjectures) to contain exponentially
  hard pseudorandom functions, so natural proofs cannot separate it. The CKK survey
  states the barrier attribution directly.
- **Best known:** Impagliazzo–Paturi–Saks (1993/1997) — parity is hard for depth-*d*
  LTF circuits of size Ω(n^{1+ε^{−d}}); Kane–Williams 2016 improved the *d*=2 case
  to n^2.49. Both are far below super-polynomial.
- **Relevance:** high. A restricted, specific, barrier-documented target — exactly
  the "aim narrow" shape the plan asks for, and one where a transferred technique
  would be genuinely notable.
- **Verification:** confirmed — the CKK survey states "no lower bounds are known for
  the class TC⁰"; the NSF-hosted `Fooling Constant-Depth Threshold Circuits` paper
  states the EXPNP variant.

### T3 — Extending the Williams paradigm to TC⁰ / NC¹

- **Statement.** Whether the Williams (2011) technique — lower bounds from faster
  CircuitSAT algorithms — extends beyond ACC⁰ to TC⁰ or NC¹.
- **Model.** TC⁰, NC¹.
- **Status.** **OPEN.** The ACC⁰ result itself is RESOLVED (Williams 2010/2011,
  NEXP ⊄ ACC⁰), and was explicitly non-relativizing, non-natural, non-algebrizing.
- **Why it is hard.** The technique works by exploiting the *weakness* of ACC⁰
  (fast satisfiability algorithms). For TC⁰ the required algorithm is not known, and
  natural proofs are believed blocked. Standard texts flag "it needs to be
  investigated if Williams's paradigm could extend to showing lower bounds [for]
  higher complexity classes such as TC⁰, NC¹".
- **Relevance:** high — a *methodological* target rather than a single theorem. It is
  the closest thing in the literature to the shape `AXIOM_DISCOVERY.md` is chasing
  (a new technique that evades a documented barrier).
- **Verification:** confirmed against the Arora–Barak web addendum and Williams's own
  SIGACT survey.

### T4 — Razborov's monotone CLIQUE bound, and the gap to general circuits

- **Statement.** CLIQUE_{k,n} requires monotone circuits of size 2^{Θ(√k)} for
  k ≤ n^{1/4}; super-polynomial. General (non-monotone) circuits computing CLIQUE
  are *not* known to require super-polynomial size.
- **Model.** Monotone circuits (AND/OR only, no negation).
- **Status.** **RESOLVED** (Razborov 1985; improved by Alon–Boppana 1987 to
  exp(Ω(n^{1/3})) for the approximating version). The *gap to general circuits* is
  **OPEN**.
- **Why it is hard — stated by the literature explicitly.** Two independent quotes
  from course notes: "the proof of Razborov's lower-bound doesn't extend to general
  circuits"; and "if we could prove similar claim for general circuits, then we would
  have proved NP ⊄ P/poly." This is the cleanest documented instance of a
  technique that works in a restricted model and *provably fails to generalise*.
- **Relevance:** very high. A φ that transfers across this gap would be exactly the
  kind of result the track is built to find.
- **Verification:** confirmed — Moshkovitz course notes (MIT 6.841), Dagstuhl
  LIPIcs CCC 2025 (`Hardness of Clique Approximation for Monotone Circuits`).

### T5 — Tardos's function: exponential monotone vs non-monotone gap for a P function

- **Statement.** There is a monotone function in **P** (Tardos's function — the
  Lovász theta function, suitably rounded, computed by a semidefinite program) with
  an **exponential** gap between its monotone and non-monotone circuit complexity.
- **Model.** Monotone vs general circuits.
- **Status.** **RESOLVED** (Tardos 1988; the general-circuit upper bound follows from
  the ellipsoid method / SDP for the theta function, Grötschel–Lovász–Schrijver).
- **Why it is hard / why it matters.** Matching (T4's cousin) gives only a
  super-polynomial gap and is in RNC; Tardos's function gives the *exponential* gap
  for a P function, but it is "relatively complex, as it is computed by solving a
  semidefinite program". The combination — a P function with exponential monotone
  complexity — is the strongest known separation of this kind.
- **Caution recorded:** there is a known retraction in this area. Norbert Blum's 2017
  claimed proof of P ≠ NP (which used the approximation method on monotone
  functions) was retracted by the author; the arXiv entry is now titled *"On the
  Approximation Method and the P versus NP Problem"* and its comments field reads
  "the replacement of the incorrect paper". Any φ touching this area must cite the
  *established* papers (Tardos 1988; Grötschel–Lovász–Schrijver), not the retracted
  claim.
- **Verification:** confirmed — arXiv:1708.03486 (the replacement paper, with the
  retraction in its comments field), plus contemporaneous discussion on the
  complexity blogs (Lipton, Aaronson) and the Fortnow/Gasarch post with its reader
  correction on the theta-function detail, which the blog then corrected.

### T6 — Perfect matching requires exponential monotone circuits

- **Statement.** The perfect matching function on *n*-vertex graphs requires
  monotone circuits of size 2^{n^{Ω(1)}}.
- **Model.** Monotone circuits.
- **Status.** **RESOLVED, and improved recently** — Razborov 1985 gave
  n^{Ω(log n)}; the exponential bound is a 2025 result. (The paper's abstract
  states it for **perfect matching**; its Theorem 1 additionally gives
  2^{n^{1/3−o(1)}} for the **bipartite** case, noting the general-vs-monotone gap
  for bipartite matching is exponential.)
- **Why it is hard / recent.** The older bound left an exponential gap open for
  matching specifically (Tardos had it for a different, SDP-based function). The
  improvement uses "the standard approximation method together with a new sunflower
  lemma for matchings" — i.e. it needed a *new* combinatorial tool, not just
  stronger bookkeeping. It also is not known for Tardos's function to admit an
  efficient parallel algorithm, whereas bipartite matching does (RNC).
- **Relevance:** high and *live* — a case where the frontier moved in the last year.
  Precisely the situation the plan's step-3 cross-check exists to catch: citing
  Razborov 1985 from memory would understate the current bound.
- **Verification:** confirmed by reading the abstract directly from arXiv
  (`arxiv.org/abs/2507.16105`, v2 Nov 2025), quoted above; the paper also tabulates
  the separation timeline (Razborov '85 → Alon–Boppana '87 → Tardos '88 →
  BGW '99 → GGKS/GKRS '19-'20 → CO '23 → this work).

### T7 — Monotone depth lower bounds via Karchmer–Wigderson games, and why general depth is stuck

- **Statement.** For monotone functions, circuit depth equals the communication
  complexity of the monotone KW game (Karchmer–Wigderson), yielding tight monotone
  depth lower bounds (e.g. st-connectivity Ω(log² n), k-clique Ω(k log n)).
  **No super-logarithmic general depth lower bounds** are known for explicit Boolean
  functions.
- **Model.** Boolean circuits, depth; two-party communication complexity.
- **Status.** Monotone case **RESOLVED** (Karchmer–Wigderson 1988; Raz–Wigderson
  1992 for matching requiring linear depth; Raz–McKenzie 1999). General case **OPEN**
  and described in the literature as "a major open problem".
- **Why it is hard.** The KW reduction is exact, so the difficulty is *transferred*
  into communication complexity rather than solved by it. In the general game Alice
  and Bob must find an index where inputs differ; for relations, lower bounds must
  hold against *any* valid answer, which is much harder than the monotone variant
  where the witness index is constrained.
- **Relevance:** high — this is the bridge between two of the three domains the plan
  names (circuit depth ↔ communication complexity), so a transfer result here would
  span sub-domains, which is what gate 5 (breadth) asks for.
- **Verification:** confirmed — Toronto CS 2429 lecture notes; `Communication Lower
  Bounds via Critical Block Sensitivity`; the hazard-free KW paper (ITCS 2023).

### T8 — Super-polynomial lower bounds for Frege and Extended Frege

- **Statement.** Whether either Frege or Extended Frege requires super-polynomial
  size to prove some family of tautologies.
- **Model.** Propositional proof systems (Cook–Reckhow programme).
- **Status.** **OPEN** — and "perhaps the major open question in proof complexity."
  Best known for Frege is only quadratic; no super-linear lower bounds are known.
- **Why it is hard — documented.** The literature states it is "believed to be very
  hard — it is non-trivial even to think of plausible candidate tautologies for which
  superpolynomial lower bounds are believed to hold." It is also conjectured that
  proving it requires circuit lower bounds against NC¹ or P/poly, which are out of
  reach; and establishing that implication formally would itself imply NEXP ⊄ P/poly
  (Pich–Santhanam 2023, cited in arXiv:2405.02232).
- **Relevance:** high value, but note the **coupling** — this target is believed to
  require the very circuit lower bounds that are blocked. A φ reaching it would be
  extraordinary; more realistically it is a *reference* target explaining why the
  frontier sits where it does.
- **Verification:** confirmed — Filmus–Impagliazzo–? `Exponential Lower Bounds for
  AC⁰-Frege Imply Superpolynomial …`; Beame–Pitassi survey; arXiv:2405.02232.

### T9 — Purely exponential lower bounds for bounded-depth Frege

- **Statement.** Whether bounded-depth (AC⁰) Frege requires size 2^{Ω(n^c)} with a
  constant c *independent of the depth*.
- **Model.** AC⁰-Frege / bounded-depth PK.
- **Status.** Super-polynomial **RESOLVED** (Ajtai; Beame–Pitassi–et al.; Pitassi et
  al.; Krajíček et al.; Fu–Urquhart). Purely exponential **OPEN** — the best known is
  Ω(2^{n^{5^{−d}}}) for depth *d*, where the exponent degrades with depth.
- **Why it is hard — and why it is useful.** The depth-degradation is the specific
  documented limitation. Crucially, there is a **proved implication**: exponential
  AC⁰-Frege lower bounds would imply super-polynomial Frege lower bounds (Filmus et
  al.). So this is a *stepping stone* target with a known downstream payoff.
- **Relevance:** very high — it is a restricted model (the plan's preference), it has
  a documented technique limitation, and it has a proven connection to a bigger open
  problem, which makes partial progress meaningful rather than binary.
- **Verification:** confirmed — Filmus et al., `Exponential Lower Bounds for AC⁰-Frege
  Imply Superpolynomial …` (both the Toronto PDF and the ACM TOCT version).

### T10 — Lower bounds for AC⁰[p] vs AC⁰[q] (Smolensky's separation)

- **Statement.** For distinct primes p, q, MOD_q is not computable by polynomial-size
  AC⁰[p] circuits.
- **Model.** Constant-depth circuits with modular counting gates.
- **Status.** **RESOLVED** (Razborov 1987; Smolensky 1987).
- **Why it is hard / why it is here.** It is a *natural* proof (Razborov–Rudich note
  that naturalizing Smolensky's proof "takes real work"), which makes it a useful
  contrast case for T2: the same technique family that works here is believed blocked
  one level up. Lowers to reference material as much as a target.
- **Verification:** confirmed via the CKK survey's statement of [Raz87, Smo87].

---

## NEGATIVE / screening results (reference, not targets)

### N1 — The natural proofs barrier

- **Statement.** If exponentially-hard pseudorandom function families exist, then no
  *natural* proof can show NP ⊄ SIZE(n^k) — where "natural" means useful (large) and
  constructive.
- **Status.** **RESOLVED** (Razborov–Rudich 1994/1997), conditional on the existence
  of one-way functions.
- **Why it matters here.** It is the barrier `#barrier_check`'s philosophy comes from,
  and it explains the TC⁰ gap (T2): TC⁰ is believed to contain PRFs, so natural
  proofs cannot separate it. Note the AC⁰ unconditional version (Nisan–Wigderson
  generator) — the barrier bites at a *circuit-power threshold*, not universally.
- **Caveat worth recording:** the barrier is not universally accepted as decisive —
  Fortnow has publicly argued it is "not the barrier you think it is" (2024), and
  Williams's ACC⁰ proof is explicitly non-natural, showing the barrier is escapable.
- **Verification:** confirmed — Razborov–Rudich, Wikipedia's summary (which also notes
  the TC⁰ belief), the 2024 blog post, and the arXiv 2026 unconditional-AC⁰-natural
  barrier paper.

### N2 — Relativization (BGS) and algebrization

- **Statement.** Relativizing proof techniques cannot resolve P vs NP (Baker–Gill–
  Solovay 1975); algebrizing techniques cannot either (Aaronson–Wigderson 2008).
- **Status.** **RESOLVED.**
- **Why it matters here.** This is the screening half of the pipeline: PleaNP's
  `#barrier_check` elaborator operationalises the relativization one. A transferred
  circuit-complexity theorem that it marks **DEAD** cannot resolve P vs NP.
- **Verification:** confirmed — Moshkovitz notes list all three barriers and note
  Williams's proof is non-relativizing, non-natural, non-algebrizing; `#barrier_check`
  exists in PleaNP (`lean/PleaNP/Calculus/BarrierCalculus.lean`).

---

## Filtering decision (step 2) — SIGNED OFF 2026-10-07

**Decision owner:** maintainer. **Recorded:** DEC-057. This closes the single
blocker on #26 (see `blockers/open_20260916-1050_issue26-transfer-target-steps23.md`).

### The two questions the blocker named, answered

**Q1 — open-only, or open + resolved?** **Keep both, split into two tiers.**

This is decided by what gate 3 can actually do, not by preference. Gate 3 is the
**transfer test**: pull an *existing* theorem back through φ and check the
kernel accepts the new proof. A transfer needs a theorem that already exists to
pull back. So:

- **OPEN** targets (no known proof) **cannot pass gate 3** — there is no proof to
  transfer. A φ that "reaches" one has not transferred anything; it has asserted
  something unverifiable. These are **aspirational**: they define where a
  technique would *eventually* aim, and they are legitimate proposal material, but
  they are not a corpus gate 3 can run against.
- **RESOLVED-novel** targets (a proof exists, but the literature documents that the
  technique was special or that a barrier blocks the obvious route) **are the
  operational corpus**. They are exactly what gate 3 needs: the theorem is known,
  so the transfer is checkable, and the win is compression — a small generator
  repays across scales (`AXIOM_DISCOVERY.md`'s "fractal" signal).

Restricting to OPEN-only (the blocker's alternative) would therefore leave the
track with **no gate-3-passable corpus at all**, because every open target in this
list is believed to require the very circuit bounds that are blocked. That is the
decisive reason to keep resolved targets: they are the only ones the harness can
actually validate against today.

**Q2 — is the list too circuit-heavy?** **Accepted as-is.** Part 2's criterion is
"a restricted-enough model," not breadth; breadth is Part 1's requirement (the
reason #31 is blocked), not Part 2's. 7/10 circuit results is consistent with
Part 2's brief. The breadth-expanding entries already present are the
proof-complexity targets (T8/T9) and the communication half of T7 — and those are
precisely the ones needing substrate PleaNP does not have (below), so their
presence is a *scope flag*, not a filter failure.

### Frozen classification

| Target | Status | Tier | Gate-3 passable? |
|---|---|---|---|
| T1 parity ∉ AC⁰ | RESOLVED | **operational** | yes — and already stated unproved in PleaNP (`parity_notin_AC0`) |
| T2 TC⁰ lower bounds | OPEN | aspirational | no — no proof to transfer |
| T3 Williams → TC⁰/NC¹ | OPEN (method) | aspirational | no — methodological; no theorem to pull back |
| T4 monotone CLIQUE | RESOLVED | **operational** | yes |
| T4 gap to general circuits | OPEN | aspirational | no |
| T5 Tardos function | RESOLVED | **operational** | yes |
| T6 matching (2025) | RESOLVED | **operational** | yes — live frontier (arXiv:2507.16105) |
| T7 monotone KW depth | RESOLVED | **operational** | yes |
| T7 general depth | OPEN | aspirational | no |
| T8 Frege / E-Frege | OPEN | aspirational | no — coupled to blocked circuit bounds |
| T9 super-poly AC⁰-Frege | RESOLVED | **operational** | yes |
| T9 purely-exponential part | OPEN | aspirational | no |
| T10 Smolensky AC⁰[p] vs AC⁰[q] | RESOLVED | **operational + reference** | yes |
| N1 natural proofs | RESOLVED | **reference only** | n/a — screening instrument |
| N2 relativization / algebrization | RESOLVED | **reference only** | n/a — `#barrier_check` operationalises it |

**Operational set (gate-3 corpus):** T1, T4(monotone), T5, T6, T7(monotone),
T9(super-poly), T10. **Aspirational set (proposal targets, not gate-3 corpus):**
T2, T3, T4(gap), T7(general), T8, T9(exponential). **Reference:** N1, N2.

A candidate φ's `domain` field must name the target **and its tier**, so the
ledger records whether a result was checkable or aspirational.

### Consequence for formalization (step 4) — one real scope limit remains

Step 4 (formalize each statement in `Maith/Benchmark/`, importing
`PleaNP.Circuits`) is unblocked for the **blanket** case: PleaNP #102 landed
(DEC-043/050) and the import is verified.

**But the operational set is not uniformly importable.** `PleaNP.Circuits` is
Boolean-circuit-shaped (gates, families, AC⁰, monotone). Under that substrate:

- **T1, T4(monotone), T5, T6, T7(monotone)** — circuit-shaped; formalizable against
  `PleaNP.Circuits.Basic`/`AC0`/`Monotone`.
- **T9, T10** — need a **propositional-proof-system substrate** (Frege / AC⁰-Frege
  definitions, Cook–Reckhow) that PleaNP does **not** currently have.
- **T7 (communication half)** — needs a **communication-protocol substrate**, also
  absent upstream.

So the honest status is: the transfer-target **list** is frozen and #26's blocker
is cleared; formalizing the operational set fully requires **new substrate** for
T9/T10 (proof systems) and T7's communication half. That is a *new* task, not part
of #26, and it is filed as a consequence here rather than absorbed silently.

### What this unblocks

- **#26** — its single blocker (step 2 filtering) is resolved; the list is frozen.
- **#30** — with a frozen, tiered target list, the first candidate batch can run
  against the **operational** set (gate-3-passable), while aspirational targets
  feed the proposal step only. #30 no longer waits on a research pass; it waits on
  candidate φ's being authored, which is the next task.

---

### Step-2 preliminary read (retained for the record)

The research pass recorded its own preliminary read before this sign-off; it is
retained below so the reasoning is auditable. The three criteria, applied:

| Target | Specific (named result)? | Hardness documented (barrier/technique)? | Restricted-enough model? | Preliminary |
|---|---|---|---|---|
| T1 parity ∉ AC⁰ | yes | yes (switching lemma; AC⁰-natural, works) | yes | **accept** |
| T2 TC⁰ lower bounds | yes | yes (natural proofs; explicit) | yes | **accept** |
| T3 Williams → TC⁰/NC¹ | yes (methodological) | yes (barrier-evasion question) | yes | **accept** |
| T4 monotone CLIQUE + gap | yes | yes ("doesn't extend to general circuits") | yes | **accept** |
| T5 Tardos function | yes | yes (SDP-based, exponential gap) | yes | **accept** |
| T6 matching monotone | yes | yes; recent improvement | yes | **accept** |
| T7 KW games / depth | yes | yes ("major open problem") | yes | **accept** |
| T8 Frege / E-Frege | yes | yes (coupled to circuit bounds) | yes | **accept** |
| T9 exponential AC⁰-Frege | yes | yes (depth degradation; proven implication) | yes | **accept** |
| T10 Smolensky separation | yes | yes (natural, distinctive) | yes | **accept as reference** |
| N1, N2 | n/a | n/a | n/a | **reference only** |

**Concerns for the maintainer to weigh at step 2:**

1. **Is the list too circuit-heavy?** 7 of 10 are circuit complexity. The plan asks
   for breadth across sub-areas, and Part 1's breadth requirement was what blocked
   #31. For *this* list the plan only asks for restricted models, so I read circuit
   concentration as acceptable — but it is a judgement call, and if the intended
   spread is wider, proof complexity (T8/T9) and communication complexity (T7) are
   the candidates to expand.
2. **RESOLVED vs OPEN.** If the track wants only OPEN targets, this list shrinks to
   T2, T3, T4(gap), T7(general), T8, T9 — and every one of those is *believed to
   require* the blocked circuit bounds. That is a real constraint on what a φ could
   reach, and worth knowing before targets are frozen.
3. **Nothing here is P vs NP or NP vs P/poly**, per the plan's exclusion. Confirmed
   by inspection of each entry.

---

## Formalization status (step 4) — BLOCKED, recorded per target

`BENCHMARK_CORPUS_PLAN.md` Part 2 step 4 formalizes each target's *statement* in
`Maith/Benchmark/`, importing circuit-model definitions from `PleaNP.Circuits`
(option (a), DEC-040). **That path is blocked on PleaNP #102** — Maith cannot
`require PleaNP` until the root `lakefile` shim lands, because PleaNP's Lake package
sits at `lean/` and Lake resolves a dependency's root at the repo root.

Per the DoD, "a recorded reason it could not be formalized" is acceptable. Recording
it honestly, per target, rather than faking it:

| Target | Formalization status | Reason |
|---|---|---|
| T1 parity ∉ AC⁰ | **partially available already** | PleaNP `Circuits/AC0.lean` already defines `parity`, `IsAC0`, `ComputesParity`, and `parity_notin_AC0 : Prop` (unproved). Not yet importable into Maith (blocked), but the statement shape exists and is verified by inspection. |
| T2–T10 | **not formalized** | blocked on PleaNP #102 (no cross-repo import). Would need `Maith/Benchmark/` modules importing `PleaNP.Circuits.Basic` (and, for the proof-complexity targets, definitions that may not exist upstream at all — T8/T9 need a propositional-proof-system substrate that PleaNP does not currently have). |

**What was deliberately NOT done:** no stand-in `Maith/Benchmark/` definitions were
written to make the table look complete. Writing local placeholder definitions would
violate the point of option (a) — importing the *real* PleaNP models — and would
produce statements that type-check against the wrong substrate, which is precisely
the failure mode the integrity gates exist to catch.

**Additional finding, relevant to scope:** T8/T9 (Frege, AC⁰-Frege) and T7's
communication-complexity half may need substrates PleaNP does **not** currently
have. `PleaNP.Circuits` is Boolean-circuit-shaped (gates, families, AC⁰, monotone).
Proof systems and communication protocols are different models. So even after #102
lands, some of these targets need new substrate, not just import — worth knowing
before #26 is called done.

---

## Cross-check status (step 3) — OUT OF SCOPE

> **Decision (maintainer, 2026-09-16): no second model is available, so this step is
> out of scope.** The list rests on a single research pass. Treat it as
> **provisional**: re-confirm a target's status against its primary source *at the
> moment it is used* (before citing it in a DEC entry or a result). The per-target
> `Verification:` notes below are therefore the only remaining check, and the three
> citations flagged as resting on *secondary* summaries are the weakest points —
> promote those to primary when their targets are actually worked on.
>
> This is a live risk, not a formality: primary-source checking during drafting
> already caught one real misstatement (T6 below).

The plan asks for a second, differently-prompted pass because "a single LLM pass can
miss a recent result or misstate a theorem's actual status." Partial mitigation
applied here:

- Queries were run across **multiple independent sources** per target (course notes,
  surveys, arXiv, Dagstuhl LIPIcs, conference proceedings), not a single pass.
- **One recent-result catch actually landed:** T6's exponential matching bound is a
  2025 improvement (arXiv:2507.16105), not the 1985 Razborov bound one might cite
  from memory. The newer result is what is recorded. **A first draft of T6 also
  misstated it** — I wrote "bipartite matching, 2^{n^{1/3−o(1)}}" from a search
  snippet; reading the arXiv abstract directly showed the headline theorem is
  **perfect** matching at 2^{n^{Ω(1)}}, with bipartite as a separate theorem. Fixed
  by going to the primary source, which is the point of this section.
- **One retraction was avoided:** T5 records the retracted Blum claim explicitly so
  no future reader cites it.
- **One claim resisted confirmation:** I could not confirm a cleanly-scoped "no
  super-linear formula lower bounds remain" claim, so nothing of that shape is
  listed. Unverified claims are omitted rather than included with a caveat.

**Not done:** a genuinely independent second model's pass, as the plan specifies.
Recommend the maintainer run one before freezing the list — the plan is explicit
that this step is mandatory given how load-bearing the list is.

---

## Suggested next actions

1. **Maintainer: step 2 filtering** (the three criteria above), and decide the
   RESOLVED-vs-OPEN question in §Filtering concerns 2 — it changes the list.
2. **Maintainer: step 3 independent cross-check**, as the plan requires.
3. **Then** unblock step 4: PleaNP #102, after which `Maith/Benchmark/` statements
   can be written against the real `PleaNP.Circuits` models — plus a scope check on
   whether proof-complexity/communication substrates need building first.
4. **Note:** nothing in this list has been put into the candidate ledger
   (`axiom-rewrite/`). Targets are not candidates — a candidate is a φ, and no φ has
   been proposed yet. The `domain` field of a future candidate should reference a
   target id (T1–T10) from this list.