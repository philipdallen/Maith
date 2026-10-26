# Draft — Lean Zulip critique post (Maith)

> **Status:** draft, not posted. Posting is owner-only (see Maith #104).
> **Source issue:** Maith #105 (agent-side breakout of #104).
> **Prepared:** 2026-10-22, run `20261022-0141-6bsw`.
> **Figures re-verified against source records:** 2026-10-26, run `20261026-0206-a7kd` — every figure
> traced clean except the DEC-025 probe gap, which is pre-reset and now carries an explicit caveat.
> **Every figure below is traced to a record in this repo; the trace table is at the end.**
> **Do not post without the owner reading it first.**

Suggested Zulip stream/topic: `Machine learning` (or `Mathlib` if the audience is the
formalization side) — topic `Maith: semantic IR from elaborated Lean terms — hostile review wanted`.

---

## What this is

Maith is a Lean 4 project that extracts a **canonical semantic intermediate
representation (IR)** from elaborated Lean `Expr`s and asks whether training language
models on that IR — rather than on raw source syntax — makes them better at formal-math
tasks. The transformer base is Qwen2.5-Coder-0.5B for every variant, so all comparisons
are representation comparisons at a fixed base.

I am posting the *record*, not a result, and I would rather be told the design is wrong
now than after more compute. The credibility asset is the reset, so it goes first.

## The reset is the headline, not a footnote

On **2026-08-12** every prior experimental result was invalidated (**DEC-031**). Three
confounds were found in the prediction-era comparison:

1. **Split leakage** — the baselines were trained on a 3,491 / 388 split while the IR
   variant used a 3,375 / 376 split; the comparison mixed dataset with representation.
2. **Epoch confound** — variants were not matched on epochs.
3. **Dataset contamination** — the flat-IR ablation was trained on a different split
   again (3,627 / 402).

The response was to retract the comparison rather than patch the narrative. Baselines
were retrained on the clean 3,375 / 376 split at 2 epochs, `max_seq_len=512`, matched on
size (**DEC-032**):

| Variant | Vocab | Params | Split | Epochs | Perplexity |
|---|---|---|---|---|---|
| A_v3_2ep (IR, per-operator) | 2,254 | 359.9M | 3,375 / 376 | 2 | 1.2928 |
| B_small_clean (BPE) | 601 | 358.4M | 3,375 / 376 | 2 | 1.1385 |
| flat_clean (flat-IR ablation) | 11 | 357.9M | 3,375 / 376 | 2 | 1.063 |

The post-DEC-031 grid is clean on split, epochs, and size. **A fourth confound may still
be present — that is one of the questions below.**

## Where the results actually landed

- **Pipeline.** The extract → normalize → encode → train → decode → decompile pipeline
  round-trips **2,554 of 2,554** declarations on the original 4-module corpus. Scope
  caveat, stated plainly because it matters: that figure is the **v1 string-token**
  round-trip (`validate_roundtrip.py`). The current v2 corpus is **4,029** declarations
  across 14 Mathlib modules.
- **The IR encodes semantics — pre-reset evidence.** A linear probe separates IR from a
  shape-only ablation: **75.4% vs 13.6%** module-classification accuracy (**DEC-025**) — a
  62-point gap. Scope caveat, stated plainly because it is the one figure here the reset
  touches: DEC-025 predates DEC-031, so the hypothesis grid marks H1 *invalidated, pending
  re-test under quality gates* (Maith #110) and the 62-point gap is **historical, not
  current evidence**. It is kept because it is the strongest existing signal that the IR is
  not a syntactic relabelling; the clean re-test is the open item.
- **But it does not beat size-matched BPE on prediction.** At matched params and epochs,
  the IR variant does **not** improve next-token prediction or completion accuracy over
  `B_small_clean` (**DEC-027**). The high perplexity of the IR variant is a task-difficulty
  artifact, not a failure to learn (predicting `typeclass_name:Group` is harder than
  predicting a SLOT).
- **Retrieval (H6) is ambiguous, and the two modes disagree.** Under verified gates
  (**DEC-034**), Mode 1 (eval→train, n=287) puts A numerically ahead with fully
  overlapping CIs; Mode 2 (train→train, n=2,641) puts `B_small_clean` ahead with
  non-overlapping CIs. The modes do not agree.
- **The objective is a live candidate (H5, ambiguous positive).** A contrastive
  objective (projection head, then full end-to-end NT-Xent, **DEC-035**) reliably beats
  the next-token baseline in Mode 2 — `A_h5_e2e` 0.0027 and `A_h5_proj` 0.0029 vs
  `A_v3_2ep` 0.0012, CIs non-overlapping — but the effect is small and both contrastive
  variants only match `B_small_clean` (0.0028). Full end-to-end adaptation does not
  improve on the frozen projection head.

**The honest summary:** the IR carries real semantic structure, and that structure does
not (yet) buy anything under prediction-family metrics at toy scale. Whether it buys
anything under retrieval, ATP, or a different objective is open.

## Questions for critics

1. **Is the clean grid (A_v3_2ep, B_small_clean, flat_clean; all 3,375 / 376 at 2
   epochs) now comparing representation, or is a fourth confound still present?** I am
   specifically unsure whether vocabulary size (2,254 vs 601 vs 11) and tokenizer
   fertility are still doing work that the "matched on split/epochs/size" claim papers
   over.
2. **H6 retrieval disagrees between modes. Which mode should be believed, and what
   measurement settles it?** Mode 2 has ~9× the queries and non-overlapping CIs; Mode 1
   is the direction most people would report first. If you think the right answer is
   "neither — run X", I would rather hear X now.
3. **Is axiom discovery the strongest use of this IR, or a detour from the representation
   question?** The active track (from **DEC-036**) is searching for a kernel-checked
   structure-preserving map φ that transfers existing theorems into new proofs, rather
   than improving a language model. That is a deliberate change of target. Tell me if it
   looks like an escape from a negative result rather than a use of the artifact.

## What would count as decisive

For question 1: a confound you can name that the matched grid does not control, plus the
measurement that would expose it. For question 2: a mode choice with a reason, or a
different measurement. For question 3: an argument, either way.

## Records behind every figure

| Claim in this post | Record |
|---|---|
| 2,554 / 2,554 round-trip (v1 string tokens) | `README.md` §"Fully implemented pipeline"; scope caveat in `docs/reference/EXAMPLE_ROUNDTRIP.md` |
| v2 corpus 4,029 declarations, 14 modules | `README.md`; `docs/reference/GLOSSARY.md` |
| DEC-031 invalidation (leakage / epoch / contamination) | `docs/decisions/LOG.md` DEC-031 |
| Clean retrains, matched splits and sizes | `docs/decisions/LOG.md` DEC-032 |
| 75.4% vs 13.6% probe gap (**pre-reset; H1 invalidated pending re-test**) | `docs/decisions/LOG.md` DEC-025; status in `docs/experiments/HYPOTHESIS_GRID.md` H1; re-test is Maith #110 |
| IR does not beat size-matched BPE on prediction | `docs/decisions/LOG.md` DEC-027 |
| H6 Mode 1 / Mode 2 disagreement | `docs/decisions/LOG.md` DEC-034; `docs/experiments/H6_RESULTS.md` |
| H5 ambiguous positive | `docs/decisions/LOG.md` DEC-035; `docs/experiments/HYPOTHESIS_GRID.md` H5 |
| Axiom-discovery track | `docs/decisions/LOG.md` DEC-036; `docs/experiments/AXIOM_DISCOVERY.md` |
