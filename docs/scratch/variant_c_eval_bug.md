# Variant C Completion-Eval Bug (1.5% top-1) — Root Cause & Fix

**Investigated:** 2026-08-08
**Symptom:** `eval_completion.py --variants B,C` reported B=91.7% but C=1.5% top-1,
despite C's recorded perplexity being 1.098.

## Root cause: wrong checkpoint directory

`eval_completion.py` evaluates C from the default `runs/variant_C/`, whose
`checkpoint-final/` is **stale** — it is from an earlier 2,213-example run
(Jul 31), not the authoritative C model. Evidence:

| artifact | date | what it says |
|---|---|---|
| `runs/variant_C/checkpoint-final/` | Jul 31 09:46 | old run (loss_curve final eval_loss 0.305 → ppl **1.357**) |
| `runs/variant_C/results.json` | Aug 1 22:28 | ppl **1.098** (overwritten by a later run) |
| `runs/variant_C/loss_curve.json` | Jul 31 09:46 | 277 steps/epoch × 3 = 831 steps (the 2,213-ex run) |

So `runs/variant_C/` is internally inconsistent: its `results.json` (1.098) was
written Aug 1 but its `checkpoint-final` (Jul 31) is the older, weaker model.
The eval loads the checkpoint → ~1.5% top-1.

The **authoritative** C model is `runs/variant_C_v2/` (Aug 1, consistent
timestamps): `checkpoint-final` + `results.json` (1.098) + loss_curve.json
all dated Aug 1 19:53; loss_curve final eval_loss 0.137 (ppl 1.147 by the
Trainer's batched eval, vs 1.098 by the final full-split perplexity eval —
consistent measurement difference, same model).

`runs/variant_C_phase6/` is a separate Phase 6 run (2 epochs, ppl 1.1102).

## Why B was unaffected

B's eval loads `runs/variant_B/checkpoint-277` (a numeric step checkpoint),
which happens to be a good model (91.7%). B also has stale/inconsistent artifacts
(results.json Aug 1 vs checkpoint Jul 28; loss_curve final eval = NaN), but the
specific checkpoint the eval picks is valid. C was unlucky: its default dir
held the stale checkpoint.

## Fix

`eval_completion.py` already supports a per-variant checkpoint override, and its
own help text names the right dir. Run C against the authoritative checkpoint:

```bash
python3 python/eval_completion.py --variants C \
    --checkpoint-C runs/variant_C_v2 --samples 200 --mask-last 10
```

(And for a fair A/B/C, point each variant at its authoritative run, e.g.
`--checkpoint-B runs/variant_B2` etc. — verify each dir's checkpoint is the
intended model first.)

## Verification still TODO (needs MPS — run after v2 A training finishes)

Confirm `runs/variant_C_v2/checkpoint-final` yields a sensible top-1 (expect
~90%, matching B) rather than 1.5%. This was deferred to avoid competing with
the v2 A training run for MPS.

## Recommendation

Either (a) always pass `--checkpoint-C runs/variant_C_v2` for C evals, or
(b) canonicalize `runs/variant_C/` to hold the real checkpoint (copy
`variant_C_v2/checkpoint-final` over the stale one, or replace the dir with a
symlink). Option (a) is safer until the run-dir mess is audited.
