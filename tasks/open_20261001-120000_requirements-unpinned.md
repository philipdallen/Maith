# Task — Pin the Python dependencies in `requirements.txt`

**Repo:** philipdallen/Maith
**Filed:** 2026-10-01T12:00:00Z by openhands `run=20261001-1200-rlm1`
**Directive:** DEC-057 (`docs/decisions/LOG.md`)
**Labels:** status:available, kind:repair

## Finding

`requirements.txt` declares floating ranges — `torch>=2.0`, `transformers>=4.40`, `numpy>=1.24`, `scikit-learn>=1.3` — and the repo ships no lockfile. Every other reproducibility surface in Maith is pinned (Lean toolchain `v4.31.0`, Mathlib `v4.31.0`), and ephapse pins its stack (`torch==2.14.0+cpu`, `transformer-lens==3.9.0`). A floating range means a reported figure can be produced by a different dependency set than the one recorded, which is the reproducibility property the gates and RUN_REGISTRY depend on.

## Evidence (verified against raw files)

- `Maith/requirements.txt` — four `>=` ranges, no `==`, no lockfile.
- `Maith/lean-toolchain` and `lean/lakefile.lean` pin the Lean side exactly.
- `ephapse/requirements.txt` pins torch/transformer-lens exactly.

## Fix

Pin each runtime dependency to an exact version (`==`) that is known to work with the current code, and record the set. If a range is genuinely intended for one of them, say why in a comment rather than leaving the choice implicit.

## Verification

`grep -E '>=|~=' requirements.txt` returns nothing for the runtime dependencies; a fresh `pip install -r requirements.txt` succeeds.

## Out of scope / do not re-derive

Do not add a packaging framework or restructure the repo into a package. A pinned `requirements.txt` (optionally plus a generated lock) is enough.

---
Filed from the RLM Analyzer triage pass. Filing policy: DEC-057 in `docs/decisions/LOG.md`; consolidated record in `philipdallen/portfolio-ops` (`RLM_TRIAGE_2026-10-01.md`, branch `tasks/rlm-triage-2026-10-01`).
