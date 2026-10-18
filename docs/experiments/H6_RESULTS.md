# H6 Retrieval Results — A_v3_2ep vs B_small_clean

> **Date:** 2026-08-18 (supersedes 2026-08-12 DEC-030 result)
> **Status:** ◐ Partial — IR numerically ahead of B_small_clean on Recall@10 but CIs
> fully overlap. H6 stays ⬜ in the grid pending a clean Mode 2 triangulation run.

> **⚠ DEC-030 (2026-08-12) was invalid:** compared A_v3_2ep against B_small trained on
> the old leaky split (3491/388). DEC-031 caught this; DEC-032 retrained B_small_clean
> on the correct split. Results below use verified clean embeddings.
>
> **Gate status:**
> - Invariant checker: 57/57 pass (0 failures)
> - Embedding shapes: all variants train=3375, eval=376 — matches datasets exactly
> - Invariant 5 (comparison validity): pass — A_v3_2ep and B_small_clean matched on
>   split (3375/376), epochs (2), size (~358–360M params)
> - Results file: `runs/h6_retrieval/results_clean.json`

---

## The comparison

- **A_v3_2ep:** IR per-operator, 2254-vocab, 359.9M params, 2 epochs, 3375/376, perplexity 1.2928
- **B_small_clean:** BPE 601-vocab, 358.4M params, 2 epochs, 3375/376, perplexity 1.1385
- **flat_clean:** flat-IR ablation, 11-vocab, 357.9M params, 2 epochs, 3375/376, perplexity 1.063

---

## Results — Mode 1 (eval → train)

| Variant | Recall@1 | Recall@5 | Recall@10 | Recall@20 | MRR |
|---|---|---|---|---|---|
| A_v3_2ep | 0.0009 [0, 0.0026] | 0.0009 [0, 0.0026] | 0.0052 [0, 0.0113] | 0.0096 [0.0033, 0.0168] | 0.0095 [0.0045, 0.0187] |
| B_small_clean | 0.0026 [0, 0.0070] | 0.0033 [0, 0.0078] | 0.0049 [0.0009, 0.0101] | 0.0070 [0.0026, 0.0126] | 0.0140 [0.0060, 0.0247] |
| flat_clean | 0.0009 [0, 0.0026] | 0.0009 [0, 0.0026] | 0.0035 [0.0004, 0.0079] | 0.0065 [0.0016, 0.0124] | 0.0091 [0.0043, 0.0171] |

n_queryable=287, pool_size=3375, 1000 bootstrap resamples.

**Primary gate:** ◐ Not met cleanly. A Recall@10=0.0052 vs B_small_clean=0.0049 — A
numerically ahead but CIs fully overlap. Not a statistically meaningful difference.

**Key shift from DEC-030:** original result showed B_small *beating* A (0.0064 vs 0.0052).
Against the correct B_small_clean comparator the direction flipped, but overlap is too
large to call.

---

## Results — Mode 2 (train → train)

| Variant | Recall@1 | Recall@5 | Recall@10 | Recall@20 | MRR |
|---|---|---|---|---|---|
| A_v3_2ep | 0.0001 [0, 0.0004] | 0.0008 [0.0003, 0.0014] | 0.0012 [0.0005, 0.0019] | 0.0034 [0.0020, 0.0049] | 0.0051 [0.0041, 0.0065] |
| B_small_clean | 0.0001 [0, 0.0004] | 0.0011 [0.0005, 0.0019] | 0.0028 [0.0016, 0.0041] | 0.0041 [0.0026, 0.0056] | 0.0061 [0.0050, 0.0075] |
| flat_clean | 0.0005 [0.0001, 0.0010] | 0.0011 [0.0005, 0.0019] | 0.0024 [0.0013, 0.0035] | 0.0048 [0.0031, 0.0067] | 0.0068 [0.0052, 0.0086] |

n_queryable=2641, pool_size=3375, 1000 bootstrap resamples.

**Mode 2 verdict:** B_small_clean beats A on Recall@10 (0.0028 vs 0.0012), CIs do not
overlap. This **disagrees with Mode 1** where A was numerically ahead. The two modes
point in opposite directions — result is ambiguous.

---

## Verdict

**H6 is ambiguous — cannot close in either direction.** Mode 1 shows A numerically ahead
(0.0052 vs 0.0049, CIs overlap). Mode 2 shows B_small_clean clearly ahead (0.0028 vs
0.0012, CIs do not overlap). The two modes disagree, which the retest plan defined as
neither trustworthy. H6 stays ⬜ in the hypothesis grid.

The disagreement likely reflects the difference in query pool size (287 eval queries in
Mode 1 vs 2,641 train queries in Mode 2) — Mode 2 has more statistical power and is
probably the more reliable signal. Under that reading, H6 leans negative at toy scale,
consistent with the original DEC-030 direction.

**Next step:** H6 is not worth re-running at this scale. The more informative path is
H5 (contrastive objective) or scale (H4/H8).

---

## What this does not settle

- **Mode 2:** must confirm direction before H6 closes
- **Scale (H4/H8):** toy scale only — IRCoder gains start at 1.1B
- **Objective (H5):** next-token prediction weights; contrastive objective untested
- **Co-training (H9):** joint IR + source training untested
- **ATP success (H7):** retrieval is a proxy, not a direct ATP test

---

## Files

- Results (clean, Mode 1): `runs/h6_retrieval/results_clean.json`
- Results (stale/invalid): `runs/h6_retrieval/results_v3_2ep.json`, `results_v3_2ep_mode2.json (run-time artifact)`
- Embeddings (clean): `runs/retrieval_embeddings_clean/`
- Checkpoint A: `runs/variant_A_v3_2ep/checkpoint-final`
- Checkpoint B_small_clean: `runs/variant_B_small/checkpoint-final` (retrained DEC-032)
