# Task — Untrack the `datasets/` build artifacts (117 MB) that `.gitignore` already lists

**Repo:** philipdallen/Maith
**Filed:** 2026-10-01T12:00:00Z by openhands `run=20261001-1200-rlm1`
**Directive:** DEC-057 (`docs/decisions/LOG.md`)
**Labels:** status:available, kind:hygiene

## Finding

`.gitignore` declares the dataset files build artifacts — "Datasets are build artifacts (derived from corpus). Only manifests + vocabs tracked" — and lists `datasets/train_*.jsonl`, `datasets/eval_*.jsonl`, `datasets/embed_proj_*.pt`. But 22 files under `datasets/` are still tracked, about 117 MB, because they were committed before the rule was added and `.gitignore` does not untrack already-tracked files. The intent is recorded and the tree does not match it.

## Evidence (verified against raw files)

- `git ls-files datasets/` lists `train_B.jsonl` (15 MB), `train_C.jsonl` (16 MB), `embed_proj_A.pt` (28 MB), `embed_proj_A_v130.pt` (29 MB), and 18 more.
- `git ls-files -z datasets/ | xargs -0 du -b | awk` totals ~117 MB.
- `Maith/.gitignore` already lists these exact patterns as build artifacts.

## Fix

`git rm --cached` the tracked `*.jsonl`/`*.pt` artifacts under `datasets/` so the tree matches the stated rule, keeping the manifests and vocabs tracked. Add a short note that the existing history still carries the bytes and that shrinking history is a separate, owner-approved decision.

## Verification

`git ls-files datasets/` shows only `*_manifest.json` and `vocab_*.json`; `git status` is clean; the dataset build still regenerates the files.

## Out of scope / do not re-derive

Do not rewrite history (`git filter-repo`/BFG). Removing the blobs from history is destructive and is the owner's call, filed separately if wanted.

---
Filed from the RLM Analyzer triage pass. Filing policy: DEC-057 in `docs/decisions/LOG.md`; consolidated record in `philipdallen/portfolio-ops` (`RLM_TRIAGE_2026-10-01.md`, branch `tasks/rlm-triage-2026-10-01`).
