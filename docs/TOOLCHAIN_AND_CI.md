# Toolchain and CI protocol (ported from PleaNP, 2026-09-15)

This document records the CI and toolchain protocols Maith adopts from the
sibling project **PleaNP**. They were hardened there while formalizing the
complexity barriers, in direct response to observed AI-authored proof
failures â€” including the general lesson from the claimed OpenAI
Navierâ€“Stokes resolution: *a proof that compiles and reads plausibly can
still be worthless* when the difficulty is hidden in a definition, an
unstated axiom, or an unused hypothesis.

The Lean kernel checks **proofs**. It does not check that a statement says
what we meant, that a definition is non-vacuous, or that a hypothesis is
load-bearing. Everything below exists to make those failures mechanical.

## 1. Toolchain bootstrap (reproducible, cloud-capable)

Maith pins Lean `v4.31.0` (`lean-toolchain`) and Mathlib `v4.31.0`
(`lakefile.lean`), the same pins PleaNP uses. No bespoke machine is required:
the community Mathlib olean cache is the persistence layer.

```bash
# 1. elan (Lean version manager) — checksum-pinned, no curl|sh (Maith #82)
tooling/install_elan.sh
export PATH="$HOME/.elan/bin:$PATH"

# 2. toolchain + precompiled Mathlib oleans (Azure community cache)
lake exe cache get

# 3. build and run the test suite
lake build tests
./.lake/build/bin/tests
```

`lake exe cache get` avoids ever building Mathlib from source. Any sandbox,
Codespace, or CI runner converges to the same warm state in minutes.

### devcontainer

`.devcontainer/` provides a warm Codespaces/Gitpod environment (elan +
pinned toolchain + cache restore + `lake build tests`) so a fresh session
does no from-scratch provisioning. Same pattern as PleaNP's, retargeted to
Maith's targets.

## 2. CI (`.github/workflows/ci.yml`)

Runs on pushes/PRs to `main` and `dev`. Three jobs:

| Job | What it is the oracle for | Fails when |
|---|---|---|
| `lean` | code + proofs | build or `./.lake/build/bin/tests` fails |
| `gates` | statements/definitions | a Tier-1 scanner finds a violation |
| `python` | the pipeline data contract | a stdlib-only invariant/schema test fails |

The `python` job deliberately runs only the stdlib-only tests (the pipeline's
data-contract guards). The torch/transformers tests need the ML stack and, for
some, a built corpus; they remain a local-agent responsibility.

**A green check is necessary, not sufficient.** It means "builds, tests pass,
Tier-1 clean." Tier 2 (below) and human review are separate.

## 3. Two-tier integrity gates

Ported verbatim from PleaNP. See `tooling/gates/README.md` for the full
reference and `tooling/gates/tests/` for the fixtures proving the scanners
detect what they claim.

### Tier 1 â€” Python scanners (CI, no Lean needed)

- **Gate 6 (hygiene):** no `sorry` / `admit` / custom `axiom`.
- **Gate 5 (vacuity):** no dishonest placeholders (`: True := by trivial`,
  ` True`, `:= True`, `:= none`).
- **Gate 5 (lethality, Tier 1b):** every parameter, binder, and declaration is
  load-bearing â€” catches the "compiles but means nothing" shapes (unused
  parameters, discarded `let _x := â€¦`, vacuous `âˆƒ` witnesses).

```bash
python3 tooling/gates/hygiene_scan.py --prove-stage Maith Tests Scripts
python3 tooling/gates/vacuity_scan.py Maith Tests Scripts
python3 tooling/gates/binder_usage_scan.py Maith Tests Scripts
```

### Tier 2 â€” Lean-dependent (local agent's job)

`hygiene_scan.py` cannot see `sorry` smuggled through a meta-program (a custom
tactic/macro that synthesizes a `sorry` term). Tier 2 closes that gap with
Lean's own axiom inspection:

```lean
#print axioms <Fully.Qualified.Name>
```

Accept iff the axiom set is exactly the trusted standard set
(`propext`, `Classical.choice`, `Quot.sound`, `funext`, `Quot.ind`); reject on
`sorryAx` or any custom axiom. `tooling/gates/axiom_check.py` is the runner
(retarget imports/declarations to Maith before wiring it into CI).

"A gate passed" requires **both** tiers to run.

## 4. Gate discipline â€” the protocol Maith now follows

1. **No claim without a gate.** Any statement Maith asserts (a homomorphism
   obligation, a transfer result, an IR-property claim) runs the Tier-1 gates
   before it is cited as evidence.
2. **No `sorry` in a claimed-complete proof.** Render-stage placeholders are
   allowed during development (hygiene runs without `--prove-stage`); frozen
   claims run `--prove-stage`.
3. **Lethality is required for "load-bearing" claims.** The header is not
   evidence; the scan and the body are. This is the Flaw-A/B/C discipline that
   PleaNP adopted after a definition whose parameters were inert.
4. **Barrier triage (once relevant).** Any Maith candidate that produces a
   transferred circuit-complexity theorem is screened through PleaNP's
   `#barrier_check` before being treated as interesting â€” see
   `AXIOM_DISCOVERY.md` Â§"Existing infrastructure". This is the concrete
   PleaNPâ†”Maith integration point.
5. **Compression/entropy numbers are bookkeeping, never validation.** Per
   `AXIOM_DISCOVERY.md`, they are recorded only for candidates already
   surviving the kernel-checked transfer gate.

## 5. Branch protocol (one dev branch)

Ported from PleaNP's branch discipline:

- `dev` is the **single** integration branch. All work lands there first.
- `main` is the working branch and the GitHub default (convention changed
  2026-09-22). Commit and push there directly. `dev` is a **legacy name**, kept
  level with `main`; nothing commits to it. The review control is unchanged: the
  agent that writes a change is not the agent that approves it (Gate 1/Gate 3
  isolation, applied to the repo itself) -- that is enforced by the review
  evidence in the done comment, not by the branch name.
- Historical per-task branches were consolidated on 2026-09-15 (see
  `docs/decisions/LOG.md` DEC-036). Do not recreate long-lived parallel
  branches; work on `main` or short-lived topic branches that merge back.

```bash
git checkout main && git pull origin main
# ... work ...
git -c user.name="openhands" -c user.email="openhands@all-hands.dev" commit -m "message"
git push origin main
```

## 6. Known advisory items (as of 2026-09-15)

**Gate 5 Tier 1b (binder/lethality) is now BLOCKING (issue #38, 2026-09-16).**
The one VIOLATION it surfaced on adoption — the dead `runEnvTest` helper (unused
`env` parameter, zero call sites) — has been removed, so the scan exits 0 and a
*new* unused-parameter regression now fails CI rather than going green. The
remaining items are REVIEWs and deliberately do not fail the build (not
`--strict`; see #38).

- **REVIEW** ~34 unreferenced declarations (47 before allow-listing) — almost all are entry points
  (`runAll*`, `main`, `default*`) that are unreferenced by construction. These
  are whitelisted via `--allow-unreferenced` rather than chased. One worth a
  follow-up if `--strict` is ever considered: the `discarded_let` at
  `Maith/CorpusSerializer.lean:126` (`let _ := config` in
  `trainingExampleToJsonLine`).

### Test-harness exit code (RESOLVED — issue #25, 2026-09-16)

**Previously:** `Tests/Main.lean` printed `⚠ Some tests failed!` but **exited 0
regardless**, so "CI green" could not distinguish all-pass from 3-failures. The CI
`lean` job grepped the output and emitted a warning rather than a false green.

**Now:** each suite returns its count of *unexpected* failures, `main` sums them,
and the process exits `1` if the total is non-zero. The CI `lean` job runs
`lake env ./.lake/build/bin/tests` as a **hard gate** — no grep workaround.

Pre-existing failures are **not** deleted or silently skipped. They are listed in
`Tests.Harness.knownFailures`, each naming what tracks it (`V2_NEXT_STEPS.md`
entries). A listed failure prints as `⊘ … SKIPPED (known failure: …)`; anything
else prints `✗` and fails the build.

The allowlist is **self-cleaning in both directions**: a listed test that starts
*passing* prints `FIXED? … remove it from Tests.Harness.knownFailures` and also
fails the build. So fixing a bug forces pruning the entry, and the list cannot rot
into a dumping ground.

Current known failures (3 — the earlier note said 4; see `V2_NEXT_STEPS.md`):

1. Decoder round-trip, mixed FVAR/BVAR graph — decoder `inputs:FVAR_0` vs encoder
   `IN_1` format drift.
2. Injectivity: `sub(a,b)` and `sub(b,a)` collapse to identical tokens.
3. Decompiled Lean output fails to type-check (`lean` exits 255).

Note on the third: `Tests/DecompilerTests.lean` shells out to the `lean` binary, so
the suite must run under `lake env` for that test to be meaningful. Run *without*
`lean` on `PATH`, `IO.Process.output` throws an uncaught exception and the process
aborts early — which also exits non-zero, but stops the suite before later suites
run. Hence `lake env` in CI.

**Verification that this gate can actually fail** (mutation-tested, not assumed):

- Inject an unlisted failure in `EncoderTests` → exit `1`, failure named. ✅
- Add a `knownFailures` entry for a test that passes → exit `1`, `FIXED?` printed. ✅
- Clean state → exit `0`, 3 known failures skipped. ✅

A check that cannot fail is not a check — and the first verification attempt at
this *was* vacuous (`str.replace` silently no-ops on a missed anchor), so the
probes now assert their mutation applied before trusting the result.

## References

- `tooling/gates/README.md` â€” gate reference and fixtures
- PleaNP `docs/ARCHITECTURE.md`, `docs/VALIDATION_SUITE.md`,
  `docs/TOOLCHAIN_SOLUTIONS.md` â€” the source protocol
- `docs/experiments/AXIOM_DISCOVERY.md` â€” the axiom-discovery track the gates now
  guard
- `docs/experiments/BENCHMARK_CORPUS_PLAN.md` â€” the benchmark corpus that the
  transfer gate consumes