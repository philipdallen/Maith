# Multi-agent task protocol (ported from PleaNP, 2026-09-15)

How OpenHands agents coordinate work on Maith. Ported from the sibling project
**PleaNP** (`docs/MULTI_AGENT_WORKFLOW.md`), which battle-tested it under a
shared GitHub identity.

> **Why this exists.** Maith consolidated 21 parallel branches into one `dev` in
> DEC-036 precisely because it lacked this protocol: without run-ids, atomic
> claims, dependency lineages, and sweeps, parallel agents double-claim, strand
> dependents, and lose work at rebase. The branch sprawl *was* the symptom. This
> file is the fix.

> **System of record:** the issue queue plus `git log origin/main`. Status tables
> in docs (HYPOTHESIS_GRID, RUN_REGISTRY) are caches updated by sweeps and may
> lag — check the queue and `dev` history before concluding work is undone.

## Run-ids

Every agent session generates a **run-id** at session start:
`<YYYYMMDD-HHMM>-<4 random alphanumerics>` (e.g. `20260915-1430-a1b2`). It appears
in every claim comment, done comment, and blocker the session writes. It is the
only way to distinguish claims under a shared GitHub identity — all agents
authenticate as the same account, so labels, assignees, and author fields cannot
tell claims apart. Without run-ids the re-fetch check in §Claiming has no teeth.

## Task states (labels)

These labels now exist on the repo.

| Label | Meaning |
|---|---|
| `status:available` | Ready to be claimed. All blockers are `done`. |
| `status:claimed` | An agent has claimed it. Claim comment is the heartbeat. |
| `status:done` | Work committed to `main`. The human reviews on `dev` at leisure; anything needing changes spawns a follow-up task. |
| `status:blocked-needs-input` | Agent could not start or finish; needs human input. |
| `priority:high` | Jumps the work queue (default order is lowest issue number). |
| `community-ready` | Good first contribution for external contributors. |
| `needs-gate` | Requires integrity/quality-gate review before acceptance. |

## Task definition

Each issue contains:

- **Summary** — what to build, in one paragraph
- **Definition of done** — the observable end state (files written, checks passing, gate evidence)
- **Context** — links to spec sections, prior art, or related tasks
- **Blocked by** — native GitHub issue-blocking relationships forming the lineage

Sizing rule: one task = completable in **one agent run**. Note what a run now
means: scheduled OpenHands automation runs are hard-capped at **30 minutes
wall-clock**, and a run killed at the cap loses everything not already pushed.
Recon, cloning, and gates consume a large share of that, so **size a task for 20
minutes of work or less**. If a task can't be done in one run, decompose it
before it becomes `available`.

**Planning and research are legitimate tasks, not overhead.** When an issue is
too large or too uncertain to implement in a single run, the right decomposition
is usually a research or planning issue *first* — an investigation whose
Definition of Done is a written finding, a decision record, or a freshly filed
set of smaller issues. A 20-minute run that produces a well-scoped plan for the
next five issues is a good outcome, not a wasted run. Prefer a short, honest
research task over a half-finished implementation.

## Automated runs (bounded, 30-minute cap)

Some `status:available` work is picked up by a scheduled automation rather than
an attended agent. Those runs are hard-capped at **30 minutes** — the platform
rejects any longer timeout — and a run killed at the cap loses everything not
already pushed to GitHub. Three rules follow. Attended agents should follow them
too, because the loss mode is identical.

1. **Push constantly.** Commit and push each coherent step the moment it exists.
   Unpushed work dies with the sandbox; a pushed partial commit is a resumable
   checkpoint. Do not accumulate local edits and push once at the end.
2. **Checkpoint rather than overrun.** If a run cannot finish, push what is
   complete, then post a comment beginning `<!-- oh-agent -->` `CHECKPOINT`
   naming the run-id, the pushed SHAs, what is done, what remains, and the next
   concrete step. Release the claim (restore `status:available`) so the next run
   can pick it up immediately. A run that claims an issue whose last comment is a
   `CHECKPOINT` should **continue that work, not re-derive it**. Never use
   `status:blocked-needs-input` for mere time exhaustion — that label means a
   human decision is required.
3. **Mark every agent comment with `<!-- oh-agent -->`.** Claim comments,
   progress notes, checkpoints, and closing comments alike. This is a
   machine-readable marker, not decoration: an automation watches issue comments
   and would otherwise wake on agent output and spend an entire run deciding to
   do nothing. Omitting it costs a run.

## Writing for the human reviewer

Most issues are resolved without the human reading anything, but every so often
one stops and waits for a person. When that happens, write for someone who has
not read the thread. Two conventions make the human's queue scannable without
anyone spending an agent run to summarise it.

**1. `NEEDS:` — open every `status:blocked-needs-input` comment with it.**

The comment's **first line** must be a single self-contained statement of the one
thing a human must decide or provide:

```
NEEDS: choose whether the detector statistic is re-derived per-rung or once
globally — DEC-030 implies per-rung but the ledger records a single value.
```

Rules for that line:

- One decision or one piece of information. Not two.
- Self-contained: it must make sense to a reader who has read nothing else.
  A pointer ("see above", "as discussed") is not a `NEEDS:` line.
- Say what you already know and where the ambiguity is, so the human can answer
  in one message rather than asking a clarifying question.

This is what makes the whole blocker queue readable in one command — dedicated tooling for it (a needs-audit.sh script, an automations/HUMAN_REVIEW.md recipe) is planned but not yet built. A blocked comment without a `NEEDS:` line is
considered incomplete.

**2. "Not in my lane" — one line on your final comment, when you saw something.**

When a run finishes, if while working it noticed something outside its own task
that it did **not** act on, append one line:

```
Not in my lane: ephapse #21 needs a dependency decision; PleaNP #96 looks like
a duplicate of #77.
```

Only if true — never manufacture items to fill it. This costs nothing beyond a
line on a comment already being written, and it makes the human's periodic scan
surface cross-cutting problems that no single task owns. It is **not** a sweep:
do not go looking for things to report, and never let it extend a run.

**One task = one signal.** Every task's Definition of Done names a single
observable check (or a named sequence of them) that turns green only when the
task is genuinely finished. That check **must be demonstrably able to fail** —
a check that cannot fail is not a check (see §Known gaps).

## Dependencies

Dependencies are expressed as GitHub "blocked by" relationships, forming
lineages. A task becomes `available` only when **every** issue blocking it is
`status:done` (merged — not merely in review). Within a lineage, only one task is
ever available at a time.

## Claiming protocol

The claim lock applies to **any issue an agent is actively working** — a task, a
test follow-up, or a blocker-resolution.

**One claim per agent at a time.** An agent holds **exactly one**
`status:claimed` label across the tracker. Finish the claimed item (commit +
close + unblock dependents) before claiming the next. Parallel agents are safe
because **each** agent respects this rule.

1. **Sweep stale claims.** Before selecting work, list all `status:claimed`
   issues. For each, if the claim comment is older than **1 hour** with no
   activity since (no commits, no new comments), the claim is void: remove
   `status:claimed`, restore the prior label, and comment that the work was
   reclaimed (audit trail). A fresh claim carrying a run-id that is not yours
   belongs to a live sibling — leave it alone.

1a. **Sweep protocol violations.** An issue carrying two status labels at once
   is in an illegal state. The sweep repairs it: the *older* label wins
   (`blocked-needs-input` outranks `claimed`), the extra label is removed, and a
   comment records the repair.

1b. **Docs coherence sweep.** Check that `README.md`, `AGENTS.md`,
   `docs/decisions/LOG.md`, and the relevant `docs/experiments/*` spec agree. If
   a recently-closed task changed the design or the plan, the sibling docs must
   reflect it in the same session — a stale doc is a process failure on par with
   a stale claim.

2. **Pick work.** Any `status:available` issue the agent can start. Default
   order: lowest issue number first; `priority:high` jumps the queue. Before
   concluding any work item is undone, check `git log origin/main` and the issue
   queue — docs tables lag.

2a. **Filing is not atomic — search, file, search again.** Before filing a new
   task, search open issues for its slug. After filing, search again: if a twin
   with a **lower issue number** now exists, close yours as duplicate.

3. **When no task is available, fall through in priority order:**
   - **(a) Open `Tests:` issues.** Claim and complete them one at a time.
   - **(b) Open PRs with unaddressed review comments.** Address each, reply to
     every thread with the fixing commit, mark threads resolved.
   - **(c) Open blockers.** Work through `status:blocked-needs-input` issues one
     at a time; if resolvable, close the blocker and return the task to
     `status:available`.
   - Only when tasks, `Tests:` issues, PR comments, and blockers are exhausted is
     the queue empty and the session done.

4. **Attempt the claim, then verify ownership.** Swap the item's current label to
   `status:claimed` **in one atomic edit** — self-assign, and post a claim
   comment (`claimed by <agent-name> run=<run-id> at <UTC timestamp>`). Then
   re-fetch the issue **and read the latest claim comment**: if its run-id is not
   yours, a sibling won — back off and pick a different item.

5. **Do the work; prove the done.** Commit directly to `main`, the working
   branch and GitHub default (no PR — review happens retrospectively on `main`). Swap `status:claimed` → `status:done` and
   close the issue with a comment linking the commits. **Tasks with
   known-answer criteria close only when the done comment includes the exact
   command and its output** — a done claim without evidence is how full maps ship
   empty and nobody notices.

   **Concurrent-work rules** (agents run in parallel against `dev`):
   - Pull before you start, and again before you push.
   - On push rejection (non-fast-forward): `git pull --rebase origin main`,
     resolve conflicts, push again. Repeat as needed.
   - **Rebase revealed a sibling landed the same work?** Compare the two
     implementations: if yours adds nothing, drop it; if yours genuinely extends
     it, merge the two in the rebase. Never push a second copy.
   - **Never force-push to `dev`** — it can destroy a sibling's committed work.
   - A rebase conflict you cannot resolve confidently is a blocker — file it.

6. **Spec the tests.** Before closing out, write a test spec describing the
   coverage the work needs. If the task introduced behavior with no existing
   coverage, the test spec is mandatory. Then file a follow-up issue titled
   `Tests: <task title>` linking the spec, labelled `status:available`, and
   marked `Blocked by` the task just completed.

7. **Unblock dependents.** Before finishing, check the issues that listed this
   task under "Blocked by". For each whose blockers are all now `status:done`,
   label it `status:available` and comment that it is unblocked. Dependent tasks
   do not become visible to the queue on their own.

8. **Iterate.** If review later finds the work lacking, write a new task rather
   than reopening the old one.

## Gates (done-evidence) — Maith's quality gates

Maith's analogue of PleaNP's integrity gates is the **pipeline quality gate**
system, which already exists and is enforced by code (`python/manage.py gate`).
A task is not `status:done` without the relevant gate command and its output in
the done comment.

| Station | Command | Oracles for |
|---|---|---|
| `ir` | `python3 python/manage.py gate ir` | IR build integrity (Gate 1: `check_ir_build.py`) |
| `corpus` | `python3 python/manage.py gate corpus` | Corpus acceptance (Gate 2: `check_corpus.py`) |
| `dataset` | `python3 python/manage.py gate dataset` | Dataset quality/invariants (Gate 3: `check_invariants.py`) |
| `train` | `python3 python/manage.py gate train` | Training-output integrity (Gate 4) |
| `eval` | `python3 python/manage.py gate eval` | Evaluation integrity (Gate 5) |
| `all` | `python3 python/manage.py gate all` | All five |

Plus the mechanical integrity gates ported in DEC-036 (Tier 1, CI-enforced):

- `python3 tooling/gates/hygiene_scan.py --prove-stage Maith Tests Scripts`
- `python3 tooling/gates/vacuity_scan.py Maith Tests Scripts`
- `python3 tooling/gates/binder_usage_scan.py Maith Tests Scripts`

And the build oracle: `lake build tests` under Lean v4.31.0 / Mathlib v4.31.0.

For experiment-family tasks, `docs/experiments/RUN_REGISTRY.md` is updated in the
same commit (rows added **before** the run starts, never deleted).

## Blockers

When an agent cannot start or complete a task (unclear spec, missing context,
ambiguous definition of done), it must not guess:

1. Write `blockers/open_YYYYMMDD-HHMMSS_<short-slug>.md` containing:
   - the issue attempted
   - what information is missing
   - what is needed to unblock
2. Label the issue `status:blocked-needs-input` and comment with a link to the
   blocker file.
3. Move on to a different available task — never sit idle on a blocker.

**Blocker quality bar.** Blockers are for spec-level ambiguity — missing or
contradictory information only the human can resolve. They are not for
implementation choices, which are the agent's to make. Before writing one,
confirm: you read the relevant spec and can cite the exact gap; the missing
information is a *decision*, not a *mechanism*; you state what you tried and why
it was insufficient.

**Nested blockers.** Any claimed item can be blocked, including a `Tests:`
issue. The exception is blocker-resolution itself: an agent that cannot resolve a
blocker must **not** file a blocker-on-a-blocker and walk away. Instead leave the
issue `status:blocked-needs-input`, comment what is still missing, and flag it in
the end-of-session report.

Resolving a blocker: the human answers on the issue or updates the spec. During
the start-of-session sweep, agents check every `blockers/open_*` file whose issue
has been updated since the file was written; if resolved, rename it to
`closed_YYYYMMDD-HHMMSS_<short-slug>.md` (appending the resolution), remove
`status:blocked-needs-input`, and return the task to `status:available`.

## Known gaps in the current gate model (agents must know these)

> **All four are now closed (2026-09-16).** #22, #23, #24, #25 are `status:done`.
> They are kept below, struck through, rather than deleted — each records a
> specific way a "green check" was weaker than it looked, and the *reason* it was
> weak is worth retaining even after the fix. Read them as a list of traps, not as
> outstanding work.

Porting the protocol surfaced places where a "green check" is weaker than it
looks. Per §Task definition ("one task = one signal"), these must be closed
before the corresponding station can be trusted as done-evidence. Filed as
`priority:high` tasks — do not paper over them:

1. ~~**Most `must_match` fields are declared but unexercised.**~~
   **RESOLVED (#22, 2026-09-16).** `test_invariants.py` now has a table-driven
   fixture per `must_match` field per claim
   (`test_comparison_validity_catches_each_must_match_field`), each asserting the
   checker fires *and* names the field, with an unmutated control per claim. The
   `must_differ` direction is covered too
   (`test_comparison_validity_catches_must_differ_violation`), and the constraint
   set is pinned **per claim** in both directions
   (`test_comparison_claims_all_constraints_exercised`) so a field cannot be
   dropped from one claim while surviving in another — mutation testing caught
   that my first, union-level pin missed exactly that. Guarded by
   `python/test_mutation_guard.py`.

   An "Invariant 5 passed" claim can now be read as covering all declared axes,
   not just `epochs`.
2. ~~**No invariant covers losslessly-verifiable representation claims.**~~
   **RESOLVED (#23, 2026-09-16).** `ENCODER_FORMAT.md`'s testable claims are now
   **Invariant 8** (`check_grammar_arity`: graph envelope, row headers, row
   arities, `IN_N`/`OUT_N` caps) and **Invariant 9** (`check_c1_polarity_absence`,
   role-based). Each has fixtures that can fail, and the doc carries a
   claim → invariant → fixture table plus an explicit list of claims that are
   *deliberately* not machine-checked (rationale prose, historical measurements,
   corpus statistics that would drift). Mutation-guarded:
   `python/test_invariants_8_9_guard.py` reports 6 detected / 3 redundant /
   **0 gaps**.

   Two traps worth knowing before extending this: `neg` is both the polarity
   marker and the arithmetic op token (so C1 must be role-based, not
   string-absence), and the IR grammar applies to IR-token variants only
   (B/C/B-small are BPE, `flat` is the SLOT ablation — checking them against it
   produced ~113k spurious reports on the first attempt).
3. ~~**Repository-wide gate consistency.**~~ **RESOLVED (#24, 2026-09-16).**
   `manage.py gate` and `manage.py invariants` now resolve every path argument
   through one `resolve_repo_path` helper: a relative path anchors at **REPO**,
   not the caller's cwd; a missing directory is a **hard error (exit 2) before any
   gate runs**; and the gate header prints the resolved absolute path plus the
   tree's provenance (`representation_id`, `encoderVersion`, `seed`,
   train/eval counts) so a transcript is self-evidencing.

   The original defect was subtler than "a silent default": the *default* was
   correct, but a user-supplied relative `--datasets datasets` was used verbatim
   and resolved against cwd — and `cmd_invariants` used bare `"datasets"` as both
   default and override. Tests + mutation guard in
   `python/test_manage_gate_paths*.py` (10 tests; 6/6 mutations detected).

   (Two of my own mistakes while fixing this, recorded because the class recurs:
   the first `describe_dataset_dir` read `train_manifest.json`, which is a
   per-example **list**, not a summary, and printed `manifest=unreadable`; and the
   first mutation for `cmd_invariants` left a dangling `except`, so the guard was
   detecting a SyntaxError rather than the behaviour change. Both fixed.)
4. ~~**The Lean test harness exits 0 on failure.**~~ **RESOLVED (#25,
   2026-09-16).** The harness now sums per-suite unexpected failures and exits
   non-zero; the CI `lean` job is a hard gate with no grep workaround.
   Pre-existing failures are listed explicitly in `Tests.Harness.knownFailures`
   (printed as `⊘ SKIPPED`), and a listed test that starts passing *also* fails
   the build, so the list cannot rot. Verified by mutation: an injected unlisted
   failure exits 1. See `docs/TOOLCHAIN_AND_CI.md` §6.

## End-of-session report

Before finishing, every agent reports (with its run-id):

- Tasks completed (with commit links), including gate evidence for known-answer DoDs
- Test specs written (linked `Tests:` issues) and any completed tasks whose test
  follow-up never landed
- Stale claims reclaimed during the sweep
- Protocol violations repaired (issues found with two status labels)
- Duplicate filings closed (twins with lower issue numbers surviving)
- Work dropped at rebase because a sibling landed it first
- New blockers written (with one-line reasons)
- Open blockers still awaiting human input
- Blockers closed during the sweep
- Unresolvable blockers escalated, or **stalled queue** if nothing was workable

## Relationship to the branch protocol

This file governs *task coordination*; `docs/TOOLCHAIN_AND_CI.md` §5 governs
*branches*. They compose: agents commit directly to the single `dev` branch
(no per-task branches — that is what produced the DEC-036 sprawl), and a
different agent/human reviews `dev` before it merges to `main`.