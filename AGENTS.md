# AGENTS.md

> Condensed project reference — dense by design, not narrative prose. For human-readable
> introductions see `README.md`; for term definitions see `docs/reference/GLOSSARY.md`.
> For machine-specific details (paths, checkpoints, Python/Lean locations), read
> `AGENTS_LOCAL.md` on the local machine (gitignored, not in this repo).


## Portfolio front door — read this before you start work

This repository is one part of a wider portfolio. Before you claim or start work
here, spend five minutes in **`philipdallen/portfolio-ops`** (private), in this order:

1. `HANDOFF.md` — current portfolio state, what is blocked and on whom.
2. `EXECUTION_PLAN.md` — the week's priorities and the sequencing principles.
3. `RISK_REGISTER.md` and `AGENTS.md` — open risks, and the rules that apply to you.

Why this is worth five minutes: it is the only place that records **decisions already
made** and **work already owned by a human**. Skipping it is how a session redoes
someone else's work, contradicts a recorded decision, or spends its run on something
a human must do anyway.

**If you are an unattended automation run, skip this step** — the operating contract
is already inlined at the top of your prompt, and this orientation is for
human-directed and ad-hoc sessions.

**Do not confuse the two queues.** Work here is claimed and executed locally. Janitorial
work — lint sweeps, stale references, mechanical hygiene — is deliberately tracked
privately in `portfolio-ops`, not filed here. If you find mechanical work, do not file
it publicly; note it in your run output so it can be routed.

## Branches

`main` is the working branch and the GitHub default — every commit lands here, and it is
the branch visitors and all tooling read. `dev` also exists and is kept level with `main`;
it is a legacy name, and nothing should be committed to it. If the two ever differ, treat
`main` as authoritative.

**Edit workflows on `main`.** A `schedule:` trigger fires only from the default branch, so
a workflow that exists only on `dev` will not run. The sweep and audit workflows check out
`main` and push there for the same reason — the status snapshot must land where the default
branch points, or the dashboard reads a stale log.
## Project overview

Maith is a Lean 4 project that extracts a canonical semantic intermediate representation
(IR) from formal mathematics and tests whether training language models on that IR —
rather than raw source syntax — improves performance on formal-math tasks.

- **Domain:** formal mathematics (Lean 4 / Mathlib)
- **Base model:** Qwen2.5-Coder-0.5B (all variants share this transformer base)
- **Central hypothesis:** a canonical semantic representation improves formal math
  tooling. Decomposed into 11 testable sub-claims (H1–H11); see hypothesis grid below.
- **Active track (2026-09-15):** axiom discovery — searching for a kernel-checked
  structure-preserving map φ that transfers existing theorems into new proofs
  (`docs/experiments/AXIOM_DISCOVERY.md`). Toy-model training is shelved, not deleted.

## Current state (v2 era, 2026-08-09)

- **IR version:** `semantic_graph_ir_v2_0_0` (C1 polarity removal, C2 typeclass
  enrichment, C4 GEN module bucketing). Vocab: 601 tokens.
- **Corpus:** 14 Mathlib modules, ~4,029 extracted declarations → 3,491 train / 388 eval.
- **Result:** The IR encodes semantic structure (DEC-025: 75.4% linear-probe accuracy vs
  13.6% for shape-only ablation, 62-point gap) but does not improve next-token prediction
  or completion accuracy over size-matched BPE at toy scale (DEC-027). Prediction metrics
  are structurally biased against the IR's canonicalization goal (H11 ◐). Whether it helps
  under non-prediction metrics (retrieval, ATP) or at larger scale is open.
- **Direction (DEC-036, 2026-09-15):** the active track is now axiom discovery on a
  circuit-complexity benchmark, guarded by the ported PleaNP integrity gates
  (`tooling/gates/`, `docs/TOOLCHAIN_AND_CI.md`). All development is on the single
  `main` branch.

## Key terms (see `docs/reference/GLOSSARY.md` for full definitions)

| Term | Meaning |
|---|---|
| **A** | IR tokens (semantic graph) — per-operator mode uses gen:FullName, 2254-vocab |
| **B** | Raw leanExpr via Qwen BPE, 151K-vocab, 494M params |
| **C** | AST-split leanExpr via Qwen BPE, 151K-vocab, 494M params |
| **B-small** | BPE truncated to 601 tokens, 358M params (size-matched control for A) |
| **IR** | Intermediate Representation — semantic graph from elaborated Lean `Expr` |
| **Flat-IR** | DEC-024 ablation: IR with all semantic content replaced by SLOT |
| **per_operator** | DEC-028: un-bucketed operator identity (gen:FullName instead of GEN_*) |
| **DEC-0XX** | Decision-log entry in `docs/decisions/LOG.md` |
| **Pretrained** | Qwen2.5-Coder-0.5B before fine-tuning — has existing retrieval signal (S1 finding) |
| **Fine-tuned** | Pretrained model + Maith training on IR/BPE data |

> **⚠ All prior experimental results invalidated (2026-08-12, DEC-031/032).**
> The results table below has been removed. Previous numbers were from runs with
> split leakage, epoch confounds, and dataset contamination. Clean retrains are
> complete (A_v3_2ep, B_small_clean, flat_clean — all 3375/376, 2 epochs) but
> hypothesis tests have not been re-run under verified quality gates.
>
> **For current status, see:**
> - [`docs/experiments/HYPOTHESIS_GRID.md`](docs/experiments/HYPOTHESIS_GRID.md) — per-claim status (all ⬜ reset)
> - [`docs/decisions/LOG.md`](docs/decisions/LOG.md) — DEC-031 (invalidation), DEC-032 (retrains + sanity checks)
> - [`docs/reference/EXPERIMENT_MEASUREMENT.md`](docs/reference/EXPERIMENT_MEASUREMENT.md) — how each metric is measured + validity gaps
> - [`docs/reference/PIPELINE_QUALITY_GATES.md`](docs/reference/PIPELINE_QUALITY_GATES.md) — gate design + status

## Model-size taxonomy (see `docs/experiments/EXPERIMENT_DESIGN.md` for full table)

All Maith variants are **toy tier** (<1B). IRCoder's positive results start at 1.1B.
"Open at larger scale" means larger *transformer capacity*, not just a bigger embedding table.

## Hypothesis grid summary (see `docs/experiments/HYPOTHESIS_GRID.md`)

| # | Sub-claim | Status |
|---|---|---|
| H1 | IR encodes semantic structure | ✅ Closed (positive) |
| H2 | IR improves next-token prediction over BPE | ❌ Closed (negative, v2 IR as designed) |
| H3 | Cold-start embedding init explains the null | ❌ Closed (ruled out) |
| H4 | Model size explains the null | ◐ Partial (ruled out at 358M; open at 1B+) |
| H5 | Training objective is the bottleneck | ⬜ Open |
| H6 | IR improves retrieval / similarity tasks | ⬜ Open (decisive test — see `H6_RETRIEVAL_SCOPE.md`) |
| H7 | IR improves proof completion / ATP | ⬜ Open (needs proof-term extraction — see `SPEC_PROOF_TERMS.md`) |
| H8 | IR advantage above a scale threshold | ⬜ Open (blocked on compute) |
| H9 | Co-training recovers gains | ⬜ Open (PACT precedent) |
| H10 | IR beats AST on richer probing | ◐ Partial |
| H11 | Is perplexity a valid primary metric? | ◐ Partially closed (bias is partly fundamental, partly contingent on IR design) |

## File map

| Path | Contents |
|---|---|
| `README.md` | Human-readable project introduction, results, roadmap |
| `docs/decisions/LOG.md` | Chronological experiment record (DEC-001 through DEC-036) |
| `docs/experiments/AXIOM_DISCOVERY.md` | **Active research track** — search for a kernel-checked structure-preserving map φ (supersedes toy-model training) |
| `docs/experiments/BENCHMARK_CORPUS_PLAN.md` | Companion: how the circuit-complexity benchmark corpus (transfer targets + conservativity corpus) is built and signed off |
| `docs/experiments/TRANSFER_TARGETS.md` | The Part 2 target list (T1–T10 + N1/N2 screening results) — drafted, awaiting maintainer filtering + cross-check |
| `docs/AGENT_HANDOFF.md` | **Cross-repo state** — PleaNP pin guidance (`@ "main"`, content-identical to `dev`, a legacy name), CI status, known gotchas |
| `docs/TOOLCHAIN_AND_CI.md` | CI + toolchain bootstrap, two-tier integrity gates, single-branch protocol (ported from PleaNP) |
| `docs/MULTI_AGENT_WORKFLOW.md` | **Multi-agent task protocol** — run-ids, atomic claims, sweeps, `blocked by` lineages, done-evidence (ported from PleaNP); includes the known gate-model gaps |
| `docs/AGENT_HANDOFF.md` | **New-agent entry point** — pick-up protocol, current state, open issues, upstream dependency, constraints |
| `blockers/` | Agent blocker files (`open_*` → `closed_*`), per the workflow protocol |
| `tooling/gates/README.md` | Integrity scanners (hygiene/vacuity/lethality) + fixtures |
| `docs/experiments/HYPOTHESIS_GRID.md` | Sub-claims H1–H11 with status, evidence, experiment-scope matrix |
| `docs/experiments/V2_NEXT_STEPS.md` | Active specs, gate tracking, pre-existing test failures, next steps |
| `docs/experiments/H6_RETRIEVAL_SCOPE.md` | H6 retrieval experiment spec (the decisive test) |
| `docs/experiments/PIPELINE_HARDENING_SCOPE.md` | Verification harness spec (build before running experiments) |
| `docs/reference/SPEC_PER_OPERATOR.md` | per_operator un-bucketing spec (DEC-028) |
| `docs/reference/SPEC_PROOF_TERMS.md` | Proof-term extraction spec (DEC-029 #2) |
| `docs/reference/PRIOR_ART.md` | Related work + theoretical grounding (§8: algorithmic alignment, disentanglement) |
| `docs/reference/GLOSSARY.md` | Term definitions for cross-domain readers |
| `docs/reference/ENCODER_FORMAT.md` | Canonical token format spec |
| `docs/experiments/EXPERIMENT_DESIGN.md` | Experiment protocol, evaluation framework, model-size taxonomy |
| `python/manage.py` | Self-service control layer (status, results, aliases, dashboard) — wraps `launch_run.py` |

## Build and test commands

**Lean (bootstrap — any sandbox or CI runner, no bespoke machine):**
```bash
curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
  | sh -s -- -y --default-toolchain none
export PATH="$HOME/.elan/bin:$PATH"
lake exe cache get          # restore precompiled Mathlib oleans (community Azure cache)
lake build tests
./.lake/build/bin/tests
```

**Integrity gates (Tier 1 — run before citing any Lean claim as evidence):**
```bash
python3 tooling/gates/hygiene_scan.py --prove-stage Maith Tests Scripts   # no sorry/admit/axiom
python3 tooling/gates/vacuity_scan.py Maith Tests Scripts                 # no dishonest placeholders
python3 tooling/gates/binder_usage_scan.py Maith Tests Scripts            # every binder load-bearing
```

**Python:**
```bash
python3 python/train.py --variant A --datasets datasets/ --embed-project datasets/embed_proj_A.pt
python3 python/eval_completion.py --variants A B_SMALL --samples 200 --mask-last 10
python3 python/validate_roundtrip.py
```

**Self-service control (manage.py):**
```bash
python3 python/manage.py status          # grid + processes + latest results
python3 python/manage.py results         # H6 retrieval + probing formatted
python3 python/manage.py grid            # comparison matrix (valid vs confounded)
python3 python/manage.py invariants      # invariant checker
python3 python/manage.py train-av3-2ep   # pre-configured A v3 retrain (guarded)
python3 python/manage.py watch --once    # HTML dashboard snapshot
```

**Corpus rebuild:**
```bash
lake exe buildCorpus              # module mode (GEN_* buckets) → Corpus/corpus.jsonl
lake exe buildCorpus --per-operator  # per_operator mode (op:<shortName>) → Corpus/corpus.per_operator.jsonl
```
The bucket mode is encoded in the output filename (#35), so the two modes no
longer overwrite each other. An explicit `--corpus <path>` on the Python
consumers still overrides the default.

> Note: exact Python binary and lake paths vary by machine. See `AGENTS_LOCAL.md`.

## Git workflow

**Working branch: `main` (convention changed 2026-09-22).** All work lands on
`main`, the GitHub default. `dev` is a **legacy name**, kept level with `main`;
nothing commits to it. (DEC-036 consolidated 21 parallel branches into `dev` in
2026-09-15; the single-branch consolidation stands, only the branch is renamed in
effect.) The review-evidence control is unchanged — `needs-review` still marks
work a human must accept, and gate output is still pasted into the done comment.

**Task coordination** (claiming, run-ids, sweeps, `blocked by` lineages,
done-evidence) is governed by `docs/MULTI_AGENT_WORKFLOW.md`. Commit directly to
`dev` — do not open a per-task branch; that is what produced the DEC-036 sprawl.
An agent holds at most one `status:claimed` issue at a time.

```bash
# Commit (identifies as AI agent)
git -c user.name="openhands" -c user.email="openhands@all-hands.dev" commit -m "message"

# Work on main; push to main
git fetch origin
git checkout main && git pull origin main --ff-only
git push origin main
```

## Conventions

- **Decision log:** Append-only; format `### DEC-0XX` with Date, Status, Scope, Decision, Rationale
- **Task protocol:** Coordinate via `docs/MULTI_AGENT_WORKFLOW.md` — run-id per session, one `status:claimed` issue at a time, commit to `dev`, evidence in the done comment, blockers in `blockers/`.
- **Gate discipline:** No Lean claim is cited as evidence before the Tier-1 integrity gates pass (`tooling/gates/`); `--prove-stage` for claimed-complete proofs. See `docs/TOOLCHAIN_AND_CI.md`.
- **Load-bearing claims:** Before calling a definition "load-bearing" or a flaw "fixed", run `binder_usage_scan.py` — the header is not evidence, the body is.
- **Axiom-discovery claims:** candidates follow the gate pipeline in `docs/experiments/AXIOM_DISCOVERY.md` (homomorphism → faithfulness → transfer → compression → breadth); compression/entropy numbers are recorded only for candidates already at the kernel-checked transfer gate.
- **Audit resolution:** When resolving an audit item in `docs/experiments/AUDIT_2026_08_10.md`, mark it `[RESOLVED <commit-sha>]` next to the heading (e.g., `### P0-2. ... [RESOLVED 73dfc18]`). Use the commit SHA, not a date — it's unique, orderable, and traces directly to the diff. The `manage.py` alias system checks for this marker before allowing experiments that depend on the audit item to launch.
- **Negative-claim scoping:** Every "not a representation deficit" must carry "under prediction-family metrics at this scale"
- **Grid axes:** Use "narrow-vocab" / "full-vocab" (not "small model" / "large model")
- **H11:** Perplexity cannot be the sole arbiter; use semantic-task metrics as primary

## Pitfalls to avoid

- Don't cite a Lean claim as evidence without the Tier-1 gates passing — "it compiles" is not "it means what we intended" (see `docs/TOOLCHAIN_AND_CI.md`)
- Don't call a definition load-bearing from its header — run `binder_usage_scan.py`; the body is the evidence
- Don't record compression/entropy numbers for candidates that failed the transfer gate — they are bookkeeping on an existing result, never validation (`AXIOM_DISCOVERY.md`)
- Don't treat AXIOM_DISCOVERY.md's target as resolving P vs NP — that is a possible downstream consequence of a real result, never a search target
- Don't state the hypothesis is disproven — only H2's prediction-metric null at toy scale is closed
- Don't use "small model" / "large model" for grid axes — both are toy-scale
- Don't cite B/C numbers without the epoch-confound caveat
- Don't conflate embedding-table size with transformer capacity
- Don't run `extract_representations.py` for H6 — it has the input-variant bug (feeds IR tokens to all variants). Use `python/extract_retrieval_embeddings.py` instead, which reads per-variant `input_ids` and has the invariant checker wired as a precondition
- Don't use `train.py` directly — it's deprecated (no invariant checker, no manifest writes, no per-variant LR). Use `launch_run.py train` which calls `train_v2_resume.py` (the canonical script) with enforced preconditions
- Don't run experiments without `check_invariants.py` passing first — it's wired into `extract_retrieval_embeddings.py` and `retrieval_eval.py` as an enforced precondition, and `launch_run.py` enforces it for training runs
- Don't overwrite `datasets/` — use versioned dirs (`datasets_perop/`, `datasets_v{N}/`). See `docs/experiments/RUN_REGISTRY.md` contamination rules
- Don't treat G1-4 (330 sequences > 512 tokens) as a blocker — it is a **known accepted warning** grandfathered in by DEC-032. It affects all variants equally and does not bias the comparison. The path to H6 is not blocked by G1-4. See `docs/decisions/LOG.md` ~line 1760.
- Don't run `python/manage.py` (or `python3 manage.py`) without specifying the ML Python binary explicitly — the system `python3` (`/usr/bin/python3`, 3.9.6) lacks ML packages and doesn't support `str | Path` union syntax (fails at `manifest.py:98`). Always invoke as `/usr/local/bin/python3 python/manage.py ...`. See Issue 9 in `docs/experiments/KNOWN_ISSUES.md`.
- Don't use old checkpoint names `variant_A_v1_4_0`, `variant_A_v2_full`, or `variant_B_small` for evaluation — these are dirty (trained on the leaky 3491/388 split). Use `variant_A_v3_2ep` and `variant_B_small_clean` (both 3375/376, 2ep) instead. The dirty checkpoints remain on disk but must not be used.

### GitHub token lifecycle (verified 2026-09-27, all surfaces)

`GITHUB_TOKEN` is short-lived and has no agent-side refresh step: the platform
re-injects the current value into each command whose text contains the literal
string `GITHUB_TOKEN`. A fresh value arrives by referencing it again in a new
command, not by retrying.

- Do not trust an early `export`: a later command that names `GITHUB_TOKEN` gets
  the platform's current value and overwrites whatever the shell held.
- A long-running process (server, supervisor) captures the token at start. After
  a rotation it 401s on every call until restarted.
- `git push` with the token embedded in the `origin` URL is the same trap: after
  a rotation it prompts for a password and reads as a hang. Re-point the remote
  and use `GIT_TERMINAL_PROMPT=0`.

401 bodies: `Bad credentials` = rotated (transient - reference `$GITHUB_TOKEN`
again in a new command); `Requires authentication` = no token sent; `Resource not
accessible by integration` = App permission gap (permanent, stop).

`gh` prefers `GH_TOKEN` over `GITHUB_TOKEN`. Do not `unset` it; pin it so `gh`
cannot fall back to a stale or absent one:

```bash
export GH_TOKEN=$GITHUB_TOKEN && gh api user -q .login
```

Full mechanism and evidence: `portfolio-ops/ACCESS_AND_IDENTITIES.md`.
