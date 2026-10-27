# H5 analysis note — the contrastive margin against the pretrained baseline

> **Status:** Analysis note. No new experiment was run; every figure below is quoted
> from DEC-035 or the H5 row of `HYPOTHESIS_GRID.md`. Sources are named inline.
>
> **Question:** DEC-035 is the cleanest H5 result (contrastive beats next-token, by a
> small margin, far below pretrained). This note interprets it into a decision input
> for next-week planning, which currently re-quotes the result without reading it.

---

## 1. The per-mode margins (DEC-035)

Source: DEC-035, "Retrieval eval results" (`docs/decisions/LOG.md`); restated in the
H5 row of `HYPOTHESIS_GRID.md`.

**Mode 1 (eval→train, n=287)** — DEC-035: "All CIs overlap — no statistically
significant separation."

| Variant | Recall@10 |
|---|---|
| A_h5_e2e | 0.0042 [0.0009, 0.0082] |
| A_h5_proj | 0.0057 [0.0013, 0.0118] |
| A_v3_2ep (next-token baseline) | 0.0052 [0.0009, 0.0113] |
| B_small | 0.0049 [0.0009, 0.0101] |

**Mode 2 (train→train, n=2641)** — DEC-035: the contrastive variants are
"statistically ahead of A_v3_2ep (CIs non-overlapping)".

| Variant | Recall@10 | vs A_v3_2ep |
|---|---|---|
| A_h5_e2e | 0.0027 [0.0016, 0.0040] | +0.0015 (≈2.3×) |
| A_h5_proj | 0.0029 [0.0014, 0.0048] | +0.0017 (≈2.4×) |
| A_v3_2ep (next-token baseline) | 0.0012 [0.0005, 0.0019] | — |
| B_small | 0.0028 [0.0016, 0.0042] | — |

The margin is the Mode-2 contrastive-minus-next-token difference: **+0.0015 to
+0.0017 Recall@10**, and it holds only in Mode 2 (Mode 1 is flat across all four
arms). DEC-035 also records that full end-to-end fine-tuning does not improve over
the frozen-encoder projection head — the two contrastive variants are
"statistically indistinguishable from each other."

## 2. The size of the gap to the pretrained baseline

Source: S1 row of `HYPOTHESIS_GRID.md` — the pretrained (un-fine-tuned)
Qwen2.5-Coder-0.5B scores Recall@10 = 0.072 on the 500-pool subset, ~3.6× chance
(0.020). DEC-035 names the same figure as the comparison anchor.

| | Recall@10 | share of the pretrained baseline (0.072) |
|---|---|---|
| Pretrained baseline (S1) | 0.072 | 100% |
| A_h5_proj (best H5 arm) | 0.0029 | ≈4.0% |
| A_h5_e2e | 0.0027 | ≈3.8% |
| A_v3_2ep (next-token) | 0.0012 | ≈1.7% |

Every H5 arm, including the contrastive winners, sits **more than an order of
magnitude below** the pretrained baseline. The objective change moved the IR from
≈1.7% to ≈4.0% of that baseline; it did not approach it. DEC-035 states this
directly: "The effect is real but small — well below the pretrained baseline."

## 3. Why the margin is small

Three readings, each grounded in a cited source:

1. **The objective lever alone brings the IR up to the control, not past it.** In
   Mode 2 both contrastive variants match B_small_clean (0.0028; CIs overlapping per
   DEC-035). So the contrastive objective removes the next-token penalty on the IR
   (A_v3_2ep 0.0012 → 0.0027/0.0029) but yields no IR *advantage* over size-matched
   BPE. The objective was the bottleneck the grid asked about; removing it exposes
   the representation/scale question underneath.

2. **The base model already carries retrieval signal, so there is little headroom at
   toy scale.** S1 records that Qwen is pretrained on code, so its token embeddings
   already encode semantic similarity (0.072 vs 0.020 chance) — "This is not
   contamination." Fine-tuning 3,375 declarations at <1B parameters can only perturb
   an existing signal, not build one from scratch.

3. **The grid names scale as the remaining lever.** The H5 row closes with "Cannot
   close positive at toy scale. Next: H4/H8 (scale) or H9 (co-training). Full e2e vs
   proj-head distinction is now resolved — scale is the remaining lever." The small
   margin is consistent with that: the objective question is answered, the scale
   question is not.

## 4. One named decisive next experiment

**H4/H8 — a scale test at ≥1B transformer capacity, holding the objective fixed.**

Rationale, from the grid (not asserted): H5's next-step line names scale as "the
remaining lever," and H4 is already "ruled out at 358M; open at 1B+" (H4 row).
Because the contrastive objective is now known to be at least as good as next-token
and no worse, the scale test should be run with the contrastive objective fixed, so
that the only variable is transformer capacity. This isolates the one lever the grid
says is untested.

**What result would change the plan:**

- If an IR-vs-BPE Recall@10 gap *appears* above some capacity threshold → scale is
  the lever; the H2/H6 nulls become scale-contingent, and the plan moves to
  capacity-matched IR-vs-BPE comparisons at the threshold.
- If the gap *stays null at 1B+* → the prediction/retrieval line is exhausted at
  reachable scale, and the front moves to the architecture and objective families
  the grid already flags as unblocked-by-reading or testable at current scale:
  H12 (graph-native architecture; partially answerable by reading Nazrin/ExprGraph)
  and H13 (JEPA-style latent objective).

No other experiment is named, and no new figure is introduced; the decisive test is
one the grid already places on the critical path.

---

## Sources

- `docs/decisions/LOG.md` — DEC-035 (H5 end-to-end contrastive fine-tune; Mode 1/Mode 2
  AUROCs), DEC-033 (projection-head result).
- `docs/experiments/HYPOTHESIS_GRID.md` — H5 row (per-mode summary, next-step line),
  S1 row (pretrained baseline 0.072 vs chance 0.020), H4 row (scale status).
- `docs/experiments/H5_SCOPE.md` — objective, pair construction, gate sequence.
