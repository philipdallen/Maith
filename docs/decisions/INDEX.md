# Decision Log Index

A navigational guide to `docs/decisions/LOG.md`. Entries are grouped by purpose.
For full details on any entry, search the decision log for `### DEC-NNN`.

**Note on ordering:** The log is append-only and entries were sometimes written
out of numeric order as investigations branched mid-phase. DEC-009 was written
after DEC-012, and DEC-014 was recorded outside the main log. The index below
groups by purpose rather than number for easier navigation.

---

## Phase Conclusions (the results that matter)

These are the primary experimental outcomes. Read these first.

| Entry | Summary | Outcome |
|---|---|---|
| **DEC-016** | Phase 5 conclusion — matched A/B/C rerun on 14-module corpus | A 1.28, B 1.18, C 1.21 (matched cap). Gap confirmed real. |
| **DEC-017** | Follow-up: stratified perplexity + completion accuracy | A 86.2%, B 92.8%, C 91.4% completion accuracy |
| **DEC-018** | Equal-sequence-length perplexity rerun — DEC-017 gate resolved | Gap real, not a truncation artifact |
| **DEC-020** | Phase 6 conclusion — expanded corpus (3,375 examples, 14 modules) | A 1.28, B 1.13, C 1.11. Gap stable across corpus sizes. |
| **DEC-021** | Embedding projection experiment — DEC-006 cold-start confound | Gap not due to initialisation. DEC-006 closed. |

---

## Confound Investigation (why A might lose for the wrong reasons)

These entries document known alternative explanations for A's underperformance
and whether they have been ruled out.

| Entry | Confound | Status |
|---|---|---|
| **DEC-003** | Embedding table size differs between A and B/C | Documented; partially mitigated by DEC-009 |
| **DEC-006** | Cold-start embedding initialisation disadvantages A | **Closed** — DEC-021 ruled this out |
| **DEC-007** | Effective batch size differs across variants | Documented; accepted as known asymmetry |
| **DEC-009** | Embed-pretrain warm-start to mitigate DEC-006 | Implemented — A improved 1.39 → 1.28 |
| **DEC-021** | Embedding projection — stronger DEC-006 isolation | **Closes DEC-006.** Gap is representation quality, not init. |

---

## Experimental Setup and Protocol

Decisions that define how the A/B/C experiment is structured and evaluated.

| Entry | Decision |
|---|---|
| **DEC-001** | A/B/C variant semantics — what each variant represents |
| **DEC-002** | Shared eval cap for apples-to-apples perplexity comparison |
| **DEC-004** | Publication gate — what result is required before publishing |
| **DEC-005** | Context-pack sidecar protocol for proof-context gap |
| **DEC-013** | Training stability fixes — batch size, gradient checkpointing (MPS) |
| **DEC-015** | Corpus expansion from 4 to 14 Mathlib modules |
| **DEC-019** | Corpus expansion planning — Phase 6 scope and diversity track |

---

## Bug Fixes and Eval Corrections

These entries document errors found in the pipeline and their resolutions.
Results from before the fix date should not be cited without checking these.

| Entry | Bug | Impact |
|---|---|---|
| **DEC-010** | `eval_completion.py` had two indexing bugs | All completion accuracy results before DEC-011 are invalid |
| **DEC-011** | DEC-010 fix verified — corrected eval confirmed valid | Completion accuracy results from DEC-011 onward are trustworthy |
| **DEC-012** | Regression test added for DEC-010 bug | Prevents recurrence |

---

## IR Design Decisions (post-DEC-021)

Decisions made after the Phase 6 / DEC-021 IR audit, driving the v1.3.0 changes.

| Entry | Decision |
|---|---|
| **DEC-021 addendum** | 93% alpha-equivalence rate is accurate — mk/_flat_ctor and casesOn/recOn are genuinely distinct Expr types, not a normaliser defect |

For the full IR improvement roadmap (IO markers, type-role prefixes, flat-IR ablation,
IR pretraining), see `docs/history/PHASE_7_ROADMAP.md` and `docs/reference/IR_V2_PROPOSAL.md`.

---

## Missing and Out-of-Sequence Entries

| Entry | Status |
|---|---|
| **DEC-014** | Recorded outside the main log — proof-term completion deferred to Phase 7; next-tactic prediction ruled out. See `docs/history/PHASE_7_DESIGN.md`. |
| **DEC-008** | 3-epoch Variant A cold-start test — partially confirmed cold-start effect (1.39 → 1.26) but gap to B/C persisted |
| DEC-009 | Appears after DEC-012 in the log file — written out of order as the warm-start investigation branched mid-phase |
| **DEC-022** | Polarity tokens (neut) functioned as positional anchors — removal caused 0.074pp regression. Fix 2 deferred until corpus > 10k examples. New baseline: 1.3717 |
| **DEC-023** | Fix 3 (IO markers) applied: vocab 8221 → 1236, Variant A perplexity 1.2751 — new best |
| **DEC-024** | Flat-IR ablation: semantic content adds 0.27 bits/token unrecoverable cost at this scale. Raw PPL comparison invalid across vocab sizes; bits/token is the correct metric. Probing experiment (DEC-025) needed to distinguish data-volume vs format problem |
| **DEC-025** | ✅ Complete — A encodes semantics. Linear probe: Variant A 75.4% vs Flat-IR 13.6% (62pp gap) on 11-class module prediction. Semantic content is linearly decodable; higher perplexity is task-difficulty, not failure to learn. Triggers v2 IR + corpus expansion. |
| **DEC-026** | IR v2 compression gate PARTIAL → implementation. C1+C2 partial run = 1.2458 (beats DEC-021 baseline 1.2978). C4 (GEN module bucketing) was missing from the dataset (encode_ir mapped all gen:* → GEN_UNK); fixed (commit `f194027`), datasets rebuilt (GEN_UNK → 0). Full C1+C2+C4 re-run in progress; gate = improvement over 1.2458 and ultimately over B/C baselines. See `docs/scratch/v2_token_analysis.md`. |
| **DEC-027** | ✅ Complete — B-small control. B-small (BPE, 358M, 601-vocab) = 90.5% top-1 / 1.1294 ppl, essentially tied with A (90.0% / 1.2361). Size explains the A-vs-B/C gap; the v2 IR is not yet doing measurable work *under prediction metrics* beyond small-vocab BPE at this scale. Non-prediction metrics (retrieval, ATP) open (H6/H7). Next levers: corpus expansion, objective redesign, IR pretraining, retrieval eval. See `docs/experiments/V2_COMPARISON_MATRIX.md`. |
| **DEC-028** | ⬜ Accepted — C4 GEN bucketing identified as a competing explanation for the perplexity null. C4 collapses operator identity into ~20 GEN_* tokens, making the IR more lossy than BPE on operator identity. Experiment: `per_operator` mode (un-bucketed) vs current `module` mode. Decisive test of whether H2's null is representation-intrinsic or a C4 artifact. |
| **DEC-029** | ⬜ Accepted — Code review findings (6 items): C4 bucketing (DEC-028), proof terms skipped (doc fix), polarity no-ops (code fix), device priority bug (code fix), asymmetric init framing (already addressed), B/C special-token inconsistency (doc fix). |
| **DEC-036** | ✅ Active (2026-09-15) — Adopt PleaNP CI/toolchain + integrity-gate protocol (`.github/workflows/ci.yml`, `.devcontainer/`, `tooling/gates/`, `docs/TOOLCHAIN_AND_CI.md`); add the axiom-discovery direction (`AXIOM_DISCOVERY.md`, `BENCHMARK_CORPUS_PLAN.md`); consolidate all branches onto a single `dev` branch. |
| **DEC-037** | ✅ Active (2026-09-15) — Port the multi-agent task protocol (`docs/MULTI_AGENT_WORKFLOW.md` + status labels + `blockers/`), reconcile the axiom-discovery docs against reality (corpus source is `PleaNP.Circuits`, not `complexitylib`; structural-similarity search absent; HOF/proj already done), and record four gate-model gaps rather than paper over them. |
| **DEC-038** | ✅ Active (2026-09-15) — Name the axiom-discovery pipeline + its taxonomy in GLOSSARY (§Axiom discovery: the transfer pipeline); flag the "candidate" overload (candidate φ vs IR candidate); restore the glossary §Terminology: family, candidate, structure, lost in DEC-036's consolidation (regression: the readability branch predated `966c49a`). |
| **DEC-039** | ✅ Active (2026-09-15) — Axiom-discovery: name the two substrates (IR for propose, metaprogramming for validate; φ itself is ordinary Lean); define the track's output object (*promoted structure*, schema only, tooling deliberately unbuilt); and record the verified IR-mode constraint (default `module` bucketing collapses operator identity → #28 must use `--per-operator`). |
| **DEC-040** | ✅ Active (2026-09-16) — Cross-repo Lean imports verified feasible (root `lakefile` shim; both repos pin v4.31.0). Option **(a)** chosen: transfer targets formalize in Maith, importing `PleaNP.Circuits`. Blocker filed upstream as PleaNP #102; #26 rewritten around (a) and left unlabeled until it clears. Corrects the earlier "mirror repo" claim. |
| **DEC-041** | ✅ Active (2026-09-16) — Search/proposal refinements filed as **#32** (`failure_mode` enum), **#33** (retrieve prior failures by structure-family/sub-domain), **#34** (gate 6, adversarial significance via independent models) — recorded, deliberately not started. Candidate-dedup folded into **#28** as phase 2 (phase 1 Mathlib remains claimable). Token scope gotcha documented for workflow-touching pushes. |
| **DEC-042** | ✅ Active (2026-09-16) — Part 2 transfer targets drafted (`TRANSFER_TARGETS.md`, T1-T10 + N1/N2 screening). Step 1 done via web research (DeepSeek unavailable); steps 2-3 explicitly left to the maintainer; step 4 blocked on PleaNP #102. Records a corrected T6 statement, a retraction hazard (Blum), and that proof/communication targets need substrate PleaNP lacks. |
| **DEC-043** | ✅ Active (2026-09-16) — PleaNP **#102 landed**: #26 step 4 unblocked (import verified end-to-end from Maith, incl. `Circuits.AC0`). Constraints recorded: pin PleaNP to a **SHA** not `@dev`, and PleaNP `dev` is **not CI-verified** (ci.yml triggers on main only). Mathlib submission **declined as a validation route** (wrong category; PleaNP's own MATHLIB_SUBMISSION.md already scopes it). Permanent Maith-side dependency deferred. |
| **DEC-044** | ✅ Active (2026-09-16) — PleaNP CI enabled on **dev**; **#99 green (40/40)**. First run found two environment-shaped defects (unicode gate scanned vendored `.lake`; galaxy step path-dependent) — both invisible to local checks. Lowers risk of the Maith-side PleaNP dependency (still pin a SHA). **PleaNP #105 open**: main/dev divergence. |
| **DEC-045** | ✅ Active (2026-09-16) — PleaNP `dev` merged to **`main`** (back-merged main->dev first, closing #105, so nothing was lost). **Pin `@ "main"`, not `@ "dev"`**; `main`/`dev` content-identical. CI 40/40 on both. Consumer build verified against `@ "main"`. Still pin a SHA for reproducibility. |
| **DEC-046** | ✅ Active (2026-09-16) — `ENCODER_FORMAT.md`'s testable claims machine-enforced as **Invariant 8** (grammar/arity) and **Invariant 9** (C1 polarity, role-based). Two traps: `neg` is ambiguous (polarity vs arithmetic op), and the grammar applies to IR-token variants only. Mutation guard distinguishes DETECTED/REDUNDANT/GAP. Closes **#23**; known-gaps 1 and 2 now resolved. |
| **DEC-047** | ✅ Active (2026-09-16) — `manage.py gate`/`invariants` resolve all path args explicitly: relative anchors at REPO (not cwd), missing dir is a hard error (exit 2) before any gate runs, and the header prints the resolved tree + provenance. Closes **#24**, the last of the four ported-protocol gaps (#22-#25 all done). |
| **DEC-048** | ✅ Active (2026-09-16) — `#28` phase 1: structural similarity over IR graphs (canonical fingerprints + documented cost function), with the `--per-operator` constraint enforced (measured 0.18 vs 0.54 similarity for unlike graphs, per-operator vs module). Real corpus: 1,401 graphs in shared groups. **Also fixed a serious hazard**: mutation guards could leave stale `.pyc` and corrupt the module under test (truncated the ledger). `#29` now unblocked. |
| **DEC-050** | ✅ Active (2026-09-16) — Five-gate harness (#29): gates 1-3 kernel-discharged, spec-as-data, positive-form obligations; three fixtures incl. a passing control; bridged into the candidate ledger (#37). Took a sibling’s better root-level bytecode fix (#36). **main no longer pushed by instruction** — investigated and PleaNP/Maith are not Netlify-linked; the spend is muse’s dev-branch site. |
| **DEC-049** | ✅ Active (2026-09-16) — mutation-guard bytecode hazard closed at the root (#36). DEC-048's purge sat **outside** the guard's `try/finally`, so a crash or child timeout still skipped it. New shared `tooling/mutation_guard_lib.py`: `guarded_source` binds restore+purge into one `finally` (and purges on entry), `run_python` disables bytecode writes (`-B`) — the cause is disabled, not just cleaned up. 5 tests incl. a positive control; all five guards migrated. |
| **DEC-051** | ✅ Active (2026-09-16) — corpus **filename encodes the bucket mode** (#35): `buildCorpus` wrote `corpus.jsonl` in both modes while the consumers default to `corpus.per_operator.jsonl`, so the documented command fed nothing and a per-op build overwrote the module-mode corpus (KNOWN_ISSUES #3). New `corpusFileNameForMode`; verified with a real Lean build that both modes coexist and `gate ir` / `structural_similarity` find the corpus. Cross-language contract test binds Lean↔Python. |
| **DEC-052** | ✅ Active (2026-09-16) — harness **batch runner** + ledger VCS policy (#37). `harness.py batch <dir|glob> --record` runs a whole candidate batch in one command; a gate failure is data (exit 0), only usage errors exit 2. The ledger is now **committed** with `.gitattributes` `merge=union`, so parallel agents' appends compose instead of conflicting. 18/18 harness tests incl. 5 new non-vacuous batch/policy tests; #30 is now one command away. |
| **DEC-053** | ✅ Active (2026-09-16) — Gate 5 Tier 1b (**binder/lethality**) promoted from advisory to **blocking** (#38). The lone violation (dead `runEnvTest`, unused `env`) was removed; scan now exits 0 on 34 advisory REVIEWs, and a planted unused parameter fails CI (verified non-vacuous). Not `--strict` — entry-point REVIEWs are out of scope. |
| **DEC-060** | ✅ Active, partial (2026-10-26) — Gate 6 (#34), questions 1-2 of 4 decided by maintainer-delegated judgment (reversible): providers are `GOOGLE_API_KEY` + `NVIDIA_BUILD_KEY` (two distinct, no fourth; `OPENHANDS_API_KEY` is not a model provider), and **gate 6 is a non-blocking triage signal, not a hard gate** — `reusable` still requires gate 5 only, recorded as a signal field with a carve-out from ordered-gate validation. Questions 3-4 (cost/volume cap; raw prompt/response retention) remain and keep #34 `status:blocked-needs-input`. |
| **DEC-061** | ✅ Active (2026-10-26) — #33 (prior-failure retrieval), questions 1-2 answered by maintainer-delegated judgment (reversible): a **new `structure_family` field**, not a structure-to-family mapping; and the prompt payload is **counts grouped by `failure_mode` + the cited gate**, not full prior φ texts. Corrects two stale premises in the same comment (**#29 does exist** — closed `status:done`, `harness.py` with `candidate_from_run`/`record`; **#28 phase 2 is not blocked** — #28 and #97 closed, only the ledger wire-in #114 remains). Two premises hold: no ledger locking (live check needs a lock/CAS) and `--per-operator` required for any live signal. #33 **stays unstarted, label unchanged** — #30 still `blocked-needs-input`, ledger empty, #32 enum not yet `done`. |

---

## Research Direction (post-DEC-035)

The active track moved from prediction-metric experiments to axiom discovery.

| Doc | What it specifies |
|---|---|
| [`docs/MULTI_AGENT_WORKFLOW.md`](../MULTI_AGENT_WORKFLOW.md) | Multi-agent task protocol — run-ids, atomic claims, `blocked by` lineages, done-evidence, blockers; includes the known gate-model gaps to close |
| [`docs/experiments/AXIOM_DISCOVERY.md`](../experiments/AXIOM_DISCOVERY.md) | Active track — search for compressive foundations via a structure-preserving map φ with a kernel-checked transfer result. Supersedes the shelved toy-model training path. |
| [`docs/experiments/BENCHMARK_CORPUS_PLAN.md`](../experiments/BENCHMARK_CORPUS_PLAN.md) | How the circuit-complexity benchmark corpus (conservativity corpus + transfer targets) is built and signed off. |
| [`docs/TOOLCHAIN_AND_CI.md`](../TOOLCHAIN_AND_CI.md) | The ported PleaNP CI/toolchain protocol + two-tier integrity gates that guard the axiom-discovery claims. |
| [`tooling/gates/README.md`](../../tooling/gates/README.md) | The gate scanners (hygiene, vacuity, lethality) and their fixtures. |

---

## Quick Reference: What's Open vs Closed

| Question | Status |
|---|---|
| Is the A/B/C gap real? | **Confirmed** — stable across Phase 5, 6, DEC-021 |
| Is it due to cold-start embeddings? | **Closed** — DEC-021 ruled this out |
| Is it due to sequence length? | **Closed** — IR is 2x shorter than BPE (DEC-022) |
| Is it due to Qwen pretraining prior? | **Unlikely** — 25.8% vocab overlap, Lean BPE worse than English |
| Is the normaliser broken? | **Partially** — 93% rate is expected and correct; no fix needed |
| Will v1.3.0 (polarity removal) narrow the gap? | **Closed** — DEC-022: regression confirmed, Fix 2 deferred |
| Can the IR beat the AST (Variant C)? | **Open (size-confounded)** — v2 A=90.0% vs B=91.7% / C=93.0%, but DEC-027 B-small (90.5% at matched params) shows the gap is a size effect, not a representation deficit *under prediction-family metrics at this scale*. IR not yet doing measurable work *under prediction metrics* over small-vocab BPE; non-prediction metrics (retrieval, ATP) untested (H6/H7). Next: corpus expansion, objective redesign, retrieval eval. |
| Does Variant A encode semantic content in its representations? | **Closed** — DEC-025: yes, 62pp probe gap vs Flat-IR. Under prediction metrics, bottleneck appears to be data/objective; under non-prediction metrics, untested (H6/H7). |
| Is Phase 8 validation complete? | **Yes** — 8a, 8a-ii, 8b, 8c, 8d all complete as of 2026-08-05 |
| Is C4 operator bucketing a confound? | **Open (DEC-028)** — C4 collapses operator identity into ~20 GEN_* tokens. May partly explain the perplexity null. `per_operator` experiment designed but not run. |
| Can the IR support ATP eval as built? | **No (DEC-029)** — the IR extracts statement types only, not proof terms. ATP/proof-search eval (H7) requires a proof-term extraction mode that does not exist. Retrieval eval (H6) is not blocked. |

---

## References

- `docs/decisions/LOG.md` — full text of all entries
- `docs/experiments/V2_NEXT_STEPS.md` — current plan (v2 merge-to-main checklist)
- `docs/experiments/V2_COMPARISON_MATRIX.md` — live 2×2 control grid (standard template for any IR candidate)
- `docs/history/PHASE_7_ROADMAP.md` — historical Phase 7 plan (v1 era)
- `docs/reference/IR_V2_PROPOSAL.md` — v2 IR design
- `docs/reference/IR_V2_FIX_SPEC.md` — Fix 1+2 implementation spec
