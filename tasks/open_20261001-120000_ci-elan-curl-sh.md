# Task — Replace `curl | sh` elan install with a checksum-pinned installer

**Repo:** philipdallen/Maith
**Filed:** 2026-10-01T12:00:00Z by openhands `run=20261001-1200-rlm1`
**Directive:** DEC-057 (`docs/decisions/LOG.md`)
**Labels:** status:available, kind:repair, security

## Finding

Maith installs the Lean toolchain by piping a remote script straight into a shell. `.github/workflows/ci.yml:36` runs `curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y`, and `.devcontainer/Dockerfile` runs the same one-liner. Nothing verifies the script before it executes, so a compromise of the `master` branch of `leanprover/elan` (or a TLS failure the `-sSf` does not catch) executes arbitrary code in CI and in every devcontainer build. This is the exact class PleaNP already closed in #136: `tooling/install_elan.sh` downloads a tagged release asset and checks its SHA-256 before running it.

## Evidence (verified against raw files)

- `Maith/.github/workflows/ci.yml:36` — `curl ... elan-init.sh | sh -s -- -y`.
- `Maith/.devcontainer/Dockerfile` — same `curl ... | sh` install.
- `Maith/AGENTS.md:151` and `docs/TOOLCHAIN_AND_CI.md:23` also document the curl|sh form.
- PleaNP already ships the fixed form: `tooling/install_elan.sh` with a hard-coded `ELAN_SHA256` and `sha256sum --check --status` (PleaNP #136).
- The RLM security report flags CI secret scanning and supply-chain gaps; this is the one with a verified, concrete instance.

## Fix

Port PleaNP's `tooling/install_elan.sh` into Maith (same checksum-pinned shape), call it from `ci.yml` and the devcontainer `Dockerfile` in place of the pipe, and update the two docs that show the old one-liner. Bump `ELAN_VERSION` and `ELAN_SHA256` together; do not pin to `master`.

## Verification

`grep -rn 'curl .* | sh' .github/ .devcontainer/` returns nothing; CI still installs the pinned toolchain (`lean --version` in the log) and the devcontainer still builds.

## Out of scope / do not re-derive

Do not change the Lean toolchain version. This is an install-mechanism change only, and it must not move `lean-toolchain` or the Mathlib pin.

---
Filed from the RLM Analyzer triage pass. Filing policy: DEC-057 in `docs/decisions/LOG.md`; consolidated record in `philipdallen/portfolio-ops` (`RLM_TRIAGE_2026-10-01.md`, branch `tasks/rlm-triage-2026-10-01`).
