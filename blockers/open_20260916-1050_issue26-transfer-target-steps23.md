# Blocker: #26 — transfer-target list needs maintainer steps 2-3 (and step 4 is blocked upstream)

**Opened:** 2026-09-16T11:0x UTC by openhands `run=20260916-1050-e8a2`
**Issue:** Maith #26 (`status:blocked-needs-input`)
**Deliverable so far:** `docs/experiments/TRANSFER_TARGETS.md` (DEC-042)

## What was completed

Step 1 of `BENCHMARK_CORPUS_PLAN.md` Part 2 — the research pass. Executed with web
research (Tavily, primary sources preferred) because the plan's named tool (DeepSeek)
was not available in this environment. Output: 10 targets (T1-T10) plus 2 screening
results (N1/N2), each with citation, status, documented hardness, and a per-target
verification note.

## What is missing — three distinct gaps, all outside agent authority

### Gap 1 — Step 2 (filtering): the plan assigns this to the maintainer

`BENCHMARK_CORPUS_PLAN.md` step 2 applies three plain-language criteria (specific?
hardness-documented? restricted-enough model?) and is explicitly "your job, plain
English only". I recorded a **preliminary** table in the doc so the maintainer can
check rather than start cold, but it is not the sign-off and the doc says so.

**Decision needed within step 2:** whether the list should contain **only OPEN**
targets. If yes, it shrinks to T2, T3, T4-gap, T7-general, T8, T9 — every one of
which is *believed to require* the circuit lower bounds that are currently blocked.
That changes what a candidate φ could realistically reach, so it should be decided
before targets are frozen, not discovered afterwards.

### Gap 2 — Step 3 (cross-check): **OUT OF SCOPE — no second model available**

**Decision (maintainer, 2026-09-16):** there is no second model to run this pass, so
it is out of scope. The plan called it mandatory; the constraint is availability,
not willingness, so the step is dropped rather than deferred indefinitely.

**Residual risk, stated rather than waved away.** The target list therefore rests on
a **single research pass**. The plan's own rationale for the step applies in full:
"a single LLM pass can miss a recent result or misstate a theorem's actual status."
This is not hypothetical — the primary-source checks already caught one real error
in the drafting (see below), which is evidence the class of error is present here.

**What therefore becomes more load-bearing:** the per-target `Verification:` notes.
Since there is no second pass, primary-source confirmation is the only remaining
check, and the three citations still resting on *secondary* summaries (T3's
Arora–Barak addendum, T8's Feige–Filmus cross-reference, T10's Smolensky via the CKK
survey) are the weakest points. They are marked as such in
`TRANSFER_TARGETS.md`. Promoting them to primary sources is worth doing when each
target is actually worked on, rather than up front.

**Consequence for downstream use:** treat the list as *provisional*. Before a target
is used to make a claim (i.e. cited in a DEC entry or a result), its status should be
re-confirmed against the primary source at that point. That is a per-target check at
the moment of use, which is cheaper than a full second pass and catches the same
class of error where it matters.

The original text of this gap, for the record:

The plan is explicit that this is mandatory given how load-bearing the list is.

**What I did instead (mitigation, not the step):** multiple independent sources per
target (course notes, surveys, arXiv, Dagstuhl LIPIcs, proceedings), and I verified
the two load-bearing claims against their **primary** sources — which caught a real
error (T6 was drafted from a snippet as "bipartite matching 2^{n^{1/3−o(1)}}"; the
arXiv abstract shows the headline theorem is **perfect** matching at
**2^{n^{Ω(1)}}`, bipartite separate). Recorded in the doc's cross-check section.

**What is still needed:** a genuinely independent pass by a different model,
differently prompted. I cannot be the independent check on my own research.

### Gap 3 — Step 4 (formalization): blocked upstream on PleaNP #102

Maith cannot `require PleaNP` until PleaNP's root `lakefile` shim lands (PleaNP's
Lake package is at `lean/`; Lake resolves a dependency's root at the repo root).
Verified empirically in DEC-040.

**New scope finding recorded in the doc:** even after #102 lands, **T8/T9
(proof complexity: Frege, AC⁰-Frege) and T7's communication-complexity half likely
need substrate `PleaNP.Circuits` does not have.** `PleaNP.Circuits` is
Boolean-circuit-shaped (gates, families, AC⁰, monotone). Proof systems and
communication protocols are different models. So some targets need *new substrate*,
not just import — this is a scope decision for the maintainer, not an implementation
choice, which is why it is recorded here rather than absorbed into the estimate.

### Related gap — the doc-quality follow-through

The doc contains a `Verification:` note per target, but three secondary citations
rest on summaries rather than the papers themselves (T3's Arora-Barak addendum, T8's
Feige-Filmus cross-reference, T10's Smolensky via the CKK survey). They are marked
as such. A maintainer-run cross-check is the natural place to promote them to primary.

## What unblocks each gap

> **RESOLVED 2026-10-07 (DEC-057).** Gap 1 cleared: maintainer filtering applied,
> OPEN-vs-RESOLVED decided (keep both, split into operational/aspirational tiers).
> See `TRANSFER_TARGETS.md` §"Filtering decision (step 2) — SIGNED OFF 2026-10-07".
> This file is closed; #26's blocker is gone.

| Gap | Unblocked by |
|---|---|
| 1 (filtering) | **RESOLVED 2026-10-07 (DEC-057)** — maintainer chose "keep both, split by gate-3 passability" (operational vs aspirational tiers). |
| 2 (cross-check) | **OUT OF SCOPE** — no second model available (2026-09-16); mitigated by per-target primary-source checks at time of use. **Closed as a blocker.** |
| 3 (formalization) | **Cleared** — PleaNP #102 landed 2026-09-16 and the import was verified end-to-end (DEC-040/DEC-050). Remaining: the maintainer's decision on proof/communication substrate for T7/T8/T9 — a *scope* question, not a blocker on #26. |

**Net: #26 has no blocker.** Step 2 filtering landed 2026-10-07 (DEC-057); step 3 is
out of scope; step 4's upstream dependency cleared. #26 can be closed. The one
*new* consequence — substrate for T7(communication)/T9/T10 — is filed separately and
does not block #26.

## Why this is a blocker and not an implementation detail

Per `docs/MULTI_AGENT_WORKFLOW.md` §Blockers, a blocker is for spec-level ambiguity
only the human can resolve. All three gaps qualify: the plan assigns steps 2-3 to the
maintainer by role, and Gap 3's substrate question changes scope rather than
mechanism.

The alternative — writing stand-in `Maith/Benchmark/` definitions to complete the
formalization table — was **deliberately rejected**. It would violate the point of
option (a) (import the *real* PleaNP models) and produce statements type-checking
against the wrong substrate, which is the failure mode the integrity gates exist to
catch. #26's DoD explicitly permits "a recorded reason it could not be formalized",
so the honest record is the correct output.

## Not done / next agent should not redo

- Do **not** re-run the step-1 research; it is complete and dated.
- Do **not** claim #26 again until at least Gaps 1-2 are resolved; it is
  `status:blocked-needs-input`.
- The Part 2 work already unblocks nothing downstream on its own: #30 (first
  candidate batch) needs #26 **and** #27 **and** #29, and no φ has been proposed yet.
