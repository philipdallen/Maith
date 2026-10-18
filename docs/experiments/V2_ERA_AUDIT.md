# V2-Era Repo Audit — Artifact Summary & Needed Edits

**Audited:** 2026-08-09 (post docs reorg; B-small training in progress)
**Purpose:** Summarize what every artifact is now that the project is in the v2 IR
era, and list the concrete edits/additions needed so the repo consistently reflects
v2 (C1+C2+C4) rather than the superseded v1.x state.

## Where the project actually is (v2 era)

- **IR version:** `semantic_graph_ir_v2_0_0` — C1 (polarity removal), C2 (typeclass
  enrichment), C4 (GEN module bucketing). Vocab 601 (was 8,221 in v1.2.0 / 1,236 in v1.4.0).
- **Current A result:** v2 full run = perplexity **1.2361**, top-1 **90.0%**
  (`runs/variant_A_v2_full`). Beats C1+C2 partial (1.2458) but still trails B (91.7%)
  and C (93.0%).
- **DEC-025 (closed):** A encodes semantics (62pp probe gap vs Flat-IR) → bottleneck
  is data/objective, not the representation.
- **DEC-026 (closed):** v2 implemented + full A run recorded.
- **DEC-027 (open):** B-small control experiment (training in progress) — isolates
  representation from model-size confound. Gate: B-small < 88% → IR does real work;
  ≥ 90% → size explains the gap.
- **Merge to main is gated** on B-small eval + DEC-027 + matrix update + `lake build`
  (see `docs/experiments/V2_NEXT_STEPS.md` checklist).

## Artifact inventory — what each is, and v2 status

### decisions/ (current, good)
- `INDEX.md` — navigational guide to the decision log. **Mostly current** (DEC-026
  complete, DEC-027 open). ⚠️ "References" section still calls
  `docs/history/PHASE_7_ROADMAP.md` the "current plan" — that's now historical; the
  current plan is `docs/experiments/V2_NEXT_STEPS.md`.
- `LOG.md` — DEC-001…DEC-026 written; DEC-026 has the full v2 A/B/C table.
  ⚠️ **DEC-027 not yet written** (pending B-small result).

### experiments/ (current, good — the v2 home)
- `V2_COMPARISON_MATRIX.md` — the 2×2 control grid (A, B, C done; B-small/A-large/
  C-small pending). Current. Needs the B-small cell filled after eval.
- `V2_NEXT_STEPS.md` — merge-to-main checklist + B-small steps. Current.
- `EXPERIMENT_DESIGN.md` — ⚠️ **v1.x-stale.** Variants table says "A (v1.3.0),
  vocab 8,144"; datasets "2,213 train / 246 eval"; embedding "8,102". Results tables
  are Phase 5/6 (v1.2.0). Needs a v2 addendum or a clear "superseded by V2_*" header.
- `PROBING_TASK_FINAL.md` / `PROBING_TASK_GUIDE.md` — DEC-025 probing spec. Current
  (historical record of a closed decision).

### reference/ (mostly v1.x — needs v2 updates)
- `ENCODER_FORMAT.md` — ⚠️ **documents v1.2.0/v1.3.0/v1.4.0 token format only.**
  No v2.0.0 section documenting: C4 `GEN_<bucket>` tokens (GEN_ALGEBRA etc., replacing
  the single GEN_UNK), the `typeclass` attribute, polarity removal. **Needs a v2 section.**
- `IR_SCHEMA.md` (was IR_SCHEMA_AUDIT) — v1 schema with polarity/gen:FullName. Needs
  a v2 note (polarity gone, gen→GEN buckets).
- `CORPUS_SCHEMA.md` — shows v1 graph schema (polarity, gen:FullName). Needs v2 note.
- `Design.md` — architectural overview; mentions A/B/C. Mostly evergreen but references
  v1 tokenization. Light v2 touch.
- `IR_V2_PROPOSAL.md` / `IR_V2_FIX_SPEC.md` — the v2 design docs. ⚠️ Proposal says
  "Status: Proposal — not implemented" but v2 IS now implemented. Update status to
  "Implemented (DEC-026)".
- `EXAMPLE_ROUNDTRIP.md` — Stage 6 decompiler audit (updated this session to reflect
  Phase 8d + BVAR). Current.
- `REPRESENTATION_EVOLUTION.md`, `NORMALISATION_AUDIT.md`, `QWEN_PRIOR_ANALYSIS.md`,
  `PYTHON_PIPELINE.md`, `DECOMPILER_HANDOVER.md` — historical reference; v1-era
  content, fine as-is (they're reference/history of how we got here).

### history/ (frozen per-phase records — correct as historical)
- `PHASE_5_RESULTS.md`, `PHASE_6_RESULTS.md`, `PHASE_7_DESIGN.md`,
  `PHASE_7_ROADMAP.md`, `PHASE_8_VALIDATION_PLAN.md` — per-phase records.
  `PHASE_7_ROADMAP.md` "Where We Stand" was updated to v2 this session. These are
  correctly historical; no edits needed (they document the v1 phases).

### scratch/ (session analyses — current)
- `runs_audit.md`, `variant_c_eval_bug.md`, `v2_token_analysis.md`,
  `REPO_AUDIT.md`, `AUDIT_2026_08_04.md`,
  `Openhands_Proposal.md` — all current session analyses. Fine as scratch.

### Root
- `README.md` — ⚠️ **stale header.** Says "Phase 7 active (DEC-022–024, 2026-08-04),
  v1.4.0 perplexity 1.2751". Should reflect v2: DEC-025 complete, v2 (C1+C2+C4) =
  1.2361, DEC-027 B-small in progress. (Note: README was file-owner-locked at time
  of audit — needed a delete+rewrite or Kit edit.)

### Code
- `python/build_dataset.py` — ✅ v2 (C4 `bucket_from_module` + `encode_ir` gen-bucketing).
- `python/train_v2_resume.py` — ✅ v2 (step checkpoints, B_small wiring, bos/eos null).
  Note: `python/train.py` (original) is still v1-era (no B_small, epoch save-strategy,
  bos/eos). `train_v2_resume.py` is the canonical trainer now; consider folding the
  fixes back into `train.py` or deleting the duplicate.
- `python/eval_completion.py` — ✅ v2 (stale-checkpoint guard).
- `python/build_b_small_vocab.py`, `python/summarize_abc_results.py` — ✅ v2-era tools.
- `python/test_c4_bucketing.py`, `test_c4_consistency.py`,
  `test_eval_checkpoint_guard.py`, `test_eval_completion_authoritative.py` — ✅ v2 tests.
- `Maith/Transpiler.lean`, `Tests/DecompilerTests.lean` — ⚠️ **UNVERIFIED** (Tasks 1-3:
  BVAR/lambda support, Test 8 IO.Process, doc-comment). Committed but pending `lake
  build` on Kit's machine. Blocks the "lake build tests passes" merge checkbox.
- `datasets/representation_manifest.json` — ⚠️ says `encoderVersion: "1.3.0"` but
  `representation_id: "semantic_graph_ir_v2_0_0"`. Inconsistent; encoderVersion
  should be v2.0.0 (or note that C4 bucketing is applied at build_dataset.py time).

### runs/ (gitignored; authoritative vs stale)
- **Authoritative:** `variant_A_v2_full` (A v2), `variant_B2`/`variant_B_phase6` (B),
  `variant_C_v2`/`variant_C_phase6` (C), `variant_A_v1_4_0` (best pre-v2 A),
  `variant_flat` (DEC-024 ablation), `variant_B_small` (in progress).
- **Quarantined (stale):** `_stale_variant_{A,B,C}` — do not use (checkpoint/results
  mismatch). See `docs/scratch/runs_audit.md`.

## Needed edits / additions — prioritized

### P0 — blocks merge to main (do before merging kit/dev → main)
1. **Finish B-small** (training in progress) → eval → fill the B-small cell in
   `V2_COMPARISON_MATRIX.md` → write **DEC-027** in `decisions/LOG.md` with the gate
   outcome → update `decisions/INDEX.md` DEC-027 line.
2. **Verify `lake build tests`** on Kit's machine (Lean decompiler Tasks 1-3 are
   unverified). Fix any compile errors. Until this passes, the decompiler work is
   scaffolding, not merged-quality.

### P1 — v2 consistency (should fix before merge; not strictly blocking)
3. **`README.md` header** — update from v1.4.0/Phase-7 to v2 (1.2361, DEC-025/027
   status). Was file-owner-locked at time of audit — needed a delete+rewrite or Kit edit.
4. **`experiments/EXPERIMENT_DESIGN.md`** — add a v2 addendum (or a "Superseded by
   V2_COMPARISON_MATRIX" header) noting v2.0.0: vocab 601, 3,491 train, C4 buckets,
   A=1.2361. The v1 tables are fine as historical record but must be marked historical.
5. **`reference/ENCODER_FORMAT.md`** — add a v2.0.0 section documenting the C4
   `GEN_<bucket>` tokens, `typeclass` attribute, polarity removal, and the
   `build_dataset.py`-side `bucket_from_module` mapping (Python/Lean parity).
6. **`reference/IR_V2_PROPOSAL.md`** — update "Status: Proposal — not implemented"
   → "Implemented (DEC-026, commit f194027); see V2_COMPARISON_MATRIX for results."
7. **`datasets/representation_manifest.json`** — fix `encoderVersion` to `"2.0.0"`
   (or document that C4 bucketing is a build_dataset.py post-processing step).
8. **`decisions/INDEX.md` References** — point "current plan" at
   `experiments/V2_NEXT_STEPS.md` (not `history/PHASE_7_ROADMAP.md`).

### P2 — cleanup / nice-to-have
9. **`reference/IR_SCHEMA.md` + `CORPUS_SCHEMA.md`** — add a short v2 note (polarity
   removed, gen→GEN buckets) so the schema docs aren't misleading.
10. **`python/train.py` vs `train_v2_resume.py`** — either fold the v2 fixes
    (step checkpoints, B_small, bos/eos null) back into `train.py`, or delete
    `train.py` and make `train_v2_resume.py` the canonical trainer (rename). Having
    two trainers is a footgun.
11. **`reference/Design.md`** — light v2 touch (mention v2 token format + C4).
12. **`summarize_abc_results.py`** — extend to print the full 2×2 grid
    (A/B/C/B-small) once B-small lands.

## One-line status
The v2 IR is implemented, trained, and evaluated (A=1.2361/90.0%); the repo's
*structure* is now clean (post-reorg), but several *reference/docs* still describe
v1.x and need v2 updates, and two merge-gates remain open: B-small eval (DEC-027)
and `lake build` verification of the Lean decompiler.
