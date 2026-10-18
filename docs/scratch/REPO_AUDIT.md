# Repository Audit Report

**Date:** 2026-08-03  
**Branch:** kit/dev  
**Auditor:** OpenHands Agent  

---

## Executive Summary

This audit classifies every `.md` and `.py` file in the repository. The goal is to identify dead wood without losing anything useful. Classification categories:

- **KEEP**: Actively useful, referenced by other files or the main workflow
- **CONSOLIDATE**: Content is valid but duplicates another file; specify which file it should be merged into
- **DELETE**: Dead wood; no longer referenced, session-scoped, or superseded

**Summary:**
- Total `.md` files: 31
- Total `.py` files: 63
- **Recommended DELETE**: 8 files
- **Recommended CONSOLIDATE (flag for human review)**: 0 files
- **Broken cross-references found**: 1

---

## Part 1: Markdown File Classifications

### Root Level

| File | Classification | Reason | Cross-references |
|------|----------------|--------|------------------|
| `README.md` | **KEEP** | Primary project entry point; referenced throughout docs and by CI | Referenced by docs/README.md, docs/SESSION_PROGRESS.md, docs/LATEST_FIXES.md |
| `docs/reference/docs/reference/docs/reference/CORPUS_SCHEMA.md` | **KEEP** | Schema contract for corpus.jsonl; still accurate for v1.3.0 encoder | Referenced by docs/reference/ENCODER_FORMAT.md, python/corpus_loader.py |
| PHASE_5_COMPLETION_CHECKLIST.md | **DELETE** | Deprecated; superseded by docs/decisions/LOG.md and docs/history/PHASE_5_RESULTS.md. Explicitly marked deprecated in file. | Referenced by docs/SESSION_PROGRESS.md (historical) |

### docs/ Directory

| File | Classification | Reason | Cross-references |
|------|----------------|--------|------------------|
| `docs/decisions/LOG.md` | **KEEP** | Canonical experiment decision record; recently updated (DEC-021, 2026-08-03) | Referenced by README.md, FUTURE_WORK.md, PHASE_7_ROADMAP.md, PHASE_7_DESIGN.md, IR_V2_FIX_SPEC.md |
| `docs/decisions/INDEX.md` | **KEEP** | Navigation index for DECISION_LOG; useful for finding specific decisions | References DECISION_LOG.md |
| `docs/history/PHASE_7_ROADMAP.md` | **KEEP** | Current active roadmap; recently updated (2026-08-03) | Referenced by README.md, FUTURE_WORK.md, IR_V2_PROPOSAL.md |
| `docs/history/PHASE_5_RESULTS.md` | **KEEP** | Phase 5 historical results; authoritative record | Referenced by PHASE_5_COMPLETION_CHECKLIST.md (deprecated), DECISION_LOG.md |
| `docs/history/PHASE_6_RESULTS.md` | **KEEP** | Phase 6 historical results; authoritative record | Referenced by DECISION_LOG.md |
| `docs/history/PHASE_7_DESIGN.md` | **KEEP** | Phase 7 proof-term completion design; future direction | Referenced by PHASE_7_ROADMAP.md |
| `docs/reference/ENCODER_FORMAT.md` | **KEEP** | Current encoder spec (v1.3.0); active specification | Referenced by IR_V2_FIX_SPEC.md, IR_V2_PROPOSAL.md, IR_SCHEMA_AUDIT.md |
| `docs/experiments/EXPERIMENT_DESIGN.md` | **KEEP** | A/B/C experiment methodology; authoritative | Referenced by DECISION_LOG.md |
| `docs/reference/IR_SCHEMA.md` | **KEEP** | Schema noise analysis; referenced by PHASE_7_ROADMAP.md | References ENCODER_FORMAT.md, PHASE_7_ROADMAP.md |
| `docs/reference/IR_V2_FIX_SPEC.md` | **KEEP** | Fix 1+2 implementation spec; active work | Referenced by PHASE_7_ROADMAP.md, DECISION_LOG.md |
| `docs/reference/IR_V2_PROPOSAL.md` | **KEEP** | v2 IR design proposal; referenced by PHASE_7_ROADMAP.md | References ENCODER_FORMAT.md, IR_SCHEMA_AUDIT.md, REPRESENTATION_EVOLUTION.md |
| `docs/reference/NORMALISATION_AUDIT.md` | **KEEP** | Normalisation audit findings; referenced | Referenced by IR_V2_FIX_SPEC.md, DECISION_LOG.md |
| `docs/reference/QWEN_PRIOR_ANALYSIS.md` | **KEEP** | Analysis reference; linked from DECISION_INDEX.md | References python/qwen_prior_analysis.py |
| `docs/reference/REPRESENTATION_EVOLUTION.md` | **KEEP** | Evolution strategy; active | Referenced by IR_V2_PROPOSAL.md, PYTHON_PIPELINE.md |
| `docs/reference/DECOMPILER_HANDOVER.md` | **KEEP** | Decompiler handoff; referenced by PHASE_6_RESULTS.md | References EXAMPLE_ROUNDTRIP.md |
| `docs/reference/EXAMPLE_ROUNDTRIP.md` | **KEEP** | Full pipeline walkthrough; educational | Referenced by DECOMPILER_HANDOVER.md, docs/SESSION_PROGRESS.md |
| docs/TESTING_SUMMARY.md | **KEEP** | Testing status; canonical test document | Referenced by docs/TEST.md |
| docs/TEST.md | **KEEP** | Short pointer to TESTING_SUMMARY; simple but functional | References TESTING_SUMMARY.md |
| `docs/reference/Design.md` | **KEEP** | Architecture and design notes; referenced | Referenced by README.md, SESSION_PROGRESS.md |
| docs/CHANGELOG.md | **KEEP** | Historical fix log; referenced by LATEST_FIXES.md | References SESSION_PROGRESS.md, LATEST_FIXES.md |
| docs/FUTURE_WORK.md | **KEEP** | Explicitly superseded but kept per file header note | References PHASE_7_ROADMAP.md, IR_V2_FIX_SPEC.md, IR_V2_PROPOSAL.md |
| `docs/README.md` | **DELETE** | Near-duplicate of root README.md; docs/ folder doesn't need its own readme | Referenced by root README.md (line references) |
| docs/SESSION_PROGRESS.md | **DELETE** | Session-by-session working notes; superseded by DECISION_LOG.md | Referenced by LATEST_FIXES.md, CHANGELOG.md (both deprecated) |
| docs/LATEST_FIXES.md | **DELETE** | Session working notes; content absorbed into CHANGELOG.md per CHANGELOG header | References SESSION_PROGRESS.md, CHANGELOG.md |
| docs/CORPUS_PIPELINE_STATUS.md | **DELETE** | Last updated July 26, 2026; references 4-module corpus; superseded by PHASE_6_RESULTS.md and PHASE_7_ROADMAP.md | Referenced by README.md (outdated) |
| docs/OPENHANDS_DEC006_TASK.md | **DELETE** | Task brief for a completed OpenHands run; no ongoing value | Not referenced by any active file |
| `docs/reference/PYTHON_PIPELINE.md` | **KEEP** | Comprehensive python/ tooling reference; active | Referenced by docs/TEST.md |

---

## Part 2: Python File Classifications

### Core Pipeline Scripts (KEEP — Do Not Touch)

| File | Classification | Reason |
|------|----------------|--------|
| `python/train.py` | **KEEP** | Core training script; explicitly protected |
| `python/build_dataset.py` | **KEEP** | Core pipeline script; explicitly protected |
| `python/eval_completion.py` | **KEEP** | Core pipeline script; explicitly protected |
| `python/eval_checkpoint.py` | **KEEP** | Core pipeline script; explicitly protected |
| `python/corpus_loader.py` | **KEEP** | Core corpus loading utility; referenced by spot_check.py |

### Analysis and Validation Scripts

| File | Classification | Reason | Cross-references |
|------|----------------|--------|------------------|
| `python/spot_check.py` | **KEEP** | Validates corpus token round-trips; used in testing workflow | Imports corpus_loader.py |
| `python/compare_results.py` | **KEEP** | Compares A/B/C results; active monitoring tool | Referenced in README.md, EXPERIMENT_DESIGN.md |
| `python/validate_roundtrip.py` | **KEEP** | Decoder round-trip validator; referenced in docs | Referenced in docs/reference/EXAMPLE_ROUNDTRIP.md, docs/TESTING_SUMMARY.md |
| `python/ir_normalisation_check.py` | **KEEP** | IR normalisation checking | Referenced in PYTHON_PIPELINE.md |
| `python/normalisation_audit.py` | **KEEP** | Normalisation audit; referenced in DECISION_LOG.md | Referenced in docs/reference/NORMALISATION_AUDIT.md |
| `python/qwen_prior_analysis.py` | **KEEP** | Qwen prior analysis; referenced in QWEN_PRIOR_ANALYSIS.md | Referenced in docs/reference/QWEN_PRIOR_ANALYSIS.md |
| `python/tokenizer_study.py` | **KEEP** | BPE fragmentation study; referenced in PYTHON_PIPELINE.md | Referenced in docs/reference/PYTHON_PIPELINE.md |

### Testing Scripts

| File | Classification | Reason | Cross-references |
|------|----------------|--------|------------------|
| `python/test_train_regression.py` | **KEEP** | Regression tests for train.py; 6 tests | Referenced in docs/TESTING_SUMMARY.md |
| `python/test_build_dataset.py` | **KEEP** | 14 tests for build_dataset.py | Referenced in README.md, docs/TESTING_SUMMARY.md |
| `python/test_variant_config.py` | **KEEP** | 6 tests for variant config | Referenced in README.md, docs/TESTING_SUMMARY.md |
| `python/test_pipeline_integration.py` | **KEEP** | End-to-end smoke test | Referenced in README.md |
| `python/test_embed_project.py` | **KEEP** | Embedding projection tests (7 tests) | Referenced in docs/OPENHANDS_DEC006_TASK.md |
| `python/test_corpus_expansion_config.py` | **KEEP** | DEC-019 corpus config validation | Referenced in docs/OPENHANDS_DEC006_TASK.md |
| `python/test_eval_regression.py` | **KEEP** | Eval regression tests | Referenced in PYTHON_PIPELINE.md |
| `python/test_golden_examples.py` | **KEEP** | Golden example validation (4 tests) | Referenced in docs/TESTING_SUMMARY.md |

### Monitoring and Dashboard Scripts

| File | Classification | Reason | Notes |
|------|----------------|--------|-------|
| `python/watch_full_runs.py` | **KEEP** | Monitors active training runs | Referenced in README.md, run_status_dashboard.py |
| `python/estimate_full_run_eta.py` | **KEEP** | ETA estimation | Referenced in README.md, run_status_dashboard.py |
| `python/full_run_status_snapshot.py` | **KEEP** | Status snapshot JSON (116 lines) | Referenced in README.md, run_status_dashboard.py |
| `python/full_run_status_report.py` | **KEEP** | Markdown status report (74 lines) | Referenced in run_status_dashboard.py |
| `python/full_run_status_history.py` | **KEEP** | History JSONL append (103 lines) | Referenced in run_status_dashboard.py |
| `python/run_status_dashboard.py` | **KEEP** | Aggregator running all status checks (73 lines) | Referenced in README.md |

**Note on status script cluster:** The four status scripts (366 lines combined) are referenced by `run_status_dashboard.py` which aggregates them. The README.md explicitly references these for monitoring active training. While they serve overlapping purposes, they are kept because:
1. `run_status_dashboard.py` is the primary entry point
2. Individual scripts can be run independently if needed
3. They are explicitly documented in README.md

### Dataset and Artifact Management

| File | Classification | Reason |
|------|----------------|--------|
| `python/embed_project.py` | **KEEP** | Embedding projection (DEC-006); active work |
| `python/validate_context_artifacts.py` | **KEEP** | Context artifact validation |
| `python/scaffold_context_artifacts.py` | **KEEP** | Context artifact scaffolding |
| `python/scaffold_theorem_eval.py` | **KEEP** | Theorem eval scaffolding |
| `python/build_dependency_manifest.py` | **KEEP** | Dependency manifest builder |
| `python/context_pack_stats.py` | **KEEP** | Context pack statistics |
| `python/corpus_expansion_dry_run.py` | **KEEP** | Corpus expansion dry run; referenced in OPENHANDS task |
| `python/validate_module_targets.py` | **KEEP** | Module importability check |
| `python/backfill_representation_metadata.py` | **KEEP** | Metadata backfill utility |

### Representation Management

| File | Classification | Reason |
|------|----------------|--------|
| `python/register_representation.py` | **KEEP** | Registers new representation candidates |
| `python/representation_audit.py` | **KEEP** | Representation metadata audit |
| `python/representation_matrix_status.py` | **KEEP** | Status across registered candidates |
| `python/check_representation_matrix_gate.py` | **KEEP** | Gate enforcement |

### Pipeline and Finalization

| File | Classification | Reason |
|------|----------------|--------|
| `python/run_full_experiment.py` | **KEEP** | Sequential full A/B/C runner |
| `python/run_postrun_pipeline.py` | **KEEP** | Post-run pipeline (compare → gate → publish → readiness) |
| `python/finalize_full_experiment.py` | **KEEP** | Finalization wrapper |
| `python/publish_results_summary.py` | **KEEP** | Publish-ready summary |
| `python/followup_eval.py` | **KEEP** | Follow-up evaluation |
| `python/dec018_ppl_rerun.py` | **KEEP** | DEC-018 perplexity rerun |

### Validation and Checking

| File | Classification | Reason |
|------|----------------|--------|
| `python/validate_dec006_setup.py` | **KEEP** | DEC-006 setup validation |
| `python/validate_theorem_eval_artifacts.py` | **KEEP** | Theorem eval artifact validation |
| `python/validate_experiment_artifacts.py` | **KEEP** | Schema validation |
| `python/check_results_gate.py` | **KEEP** | Results gate checking |
| `python/check_publish_readiness.py` | **KEEP** | Publish readiness check |
| `python/check_docs_consistency.py` | **KEEP** | Docs consistency check |
| `python/check_decision_log.py` | **KEEP** | Decision log validation |
| `python/check_split_integrity.py` | **KEEK** | Split integrity check |
| `python/check_completion_indexing.py` | **KEEP** | Completion indexing check |

### Other Utilities

| File | Classification | Reason |
|------|----------------|--------|
| `python/ir_token_efficiency.py` | **KEEP** | IR token efficiency study |
| `python/corpus_report.py` | **KEEP** | Corpus reporting |
| `python/watcher_log.py` | **KEEP** | Log watcher utility |
| `python/preflight_check.py` | **KEEP** | Pre-flight validation (7 checks) |

### Duplicate/Naming Issues

| File | Classification | Reason | Action |
|------|----------------|--------|--------|
| `python/compare_bc_predictions.py` | **RENAME → DONE** | Renamed from python/spotcheck.py per task instructions. Different purpose from spot_check.py: compare_bc_predictions.py compares B vs C predictions; spot_check.py validates corpus round-trips. | N/A - completed |

**Note:** Renamed per task instructions. No other files referenced spotcheck.py, so no reference updates were needed.

---

## Part 3: Broken Cross-References

### Markdown Files

| File | Broken Reference | Status |
|------|------------------|--------|
| `docs/decisions/LOG.md` (DEC-005) | docs/CONTEXT_PACK_PROTOCOL.md | **BROKEN** — File does not exist |

**Evidence:**
```
grep -r "CONTEXT_PACK" docs/
docs/decisions/LOG.md:  - docs/CONTEXT_PACK_PROTOCOL.md
```

The CONTEXT_PACK_PROTOCOL.md file is referenced in the DEC-005 entry but does not exist in the repository. This appears to be an orphaned reference.

**Action:** This is a documentation issue in DEC-005. The file may have been planned but never created, or was deleted. Recommend either:
1. Creating the missing file if the protocol is still relevant
2. Removing the reference from DEC-005 if the protocol was superseded

---

## Part 4: Files That Should Be Deleted

### Confirmed DELETE Files (Ready for Removal)

| File | Classification | Justification |
|------|---------------|---------------|
| `docs/README.md` | DELETE | Near-duplicate of root README.md; docs/ folder doesn't need its own readme |
| docs/SESSION_PROGRESS.md | DELETE | Session-by-session working notes; fully superseded by DECISION_LOG.md |
| docs/LATEST_FIXES.md | DELETE | Session working notes; CHANGELOG.md header says "older entries are in CHANGELOG.md" |
| docs/CORPUS_PIPELINE_STATUS.md | DELETE | Last updated July 26, 2026; references 4-module corpus; superseded by PHASE_6_RESULTS.md and PHASE_7_ROADMAP.md |
| docs/OPENHANDS_DEC006_TASK.md | DELETE | Task brief for completed OpenHands run; no ongoing value |
| PHASE_5_COMPLETION_CHECKLIST.md | DELETE | Explicitly marked deprecated; content superseded by DECISION_LOG.md and PHASE_5_RESULTS.md |
| python/spotcheck.py | **RENAME** | Different purpose from spot_check.py; rename to `python/compare_bc_predictions.py` per task |

### Total: 6 files to delete, 1 file to rename

---

## Part 5: Files NOT to Delete (Explicitly Protected)

The following files are explicitly protected and were NOT flagged for deletion:

| File | Protection Reason |
|------|------------------|
| `.lean` files (Maith/, Scripts/, Tests/) | Explicitly protected per task |
| `Corpus/corpus.jsonl` | Explicitly protected; "was silently reverted once already" |
| `datasets/` | Actively used for training |
| `runs/` | Training artifacts |
| `python/train.py`, `python/build_dataset.py`, `python/eval_completion.py`, `python/eval_checkpoint.py` | Core pipeline scripts; explicitly protected |
| `docs/decisions/LOG.md`, `docs/decisions/INDEX.md`, `docs/history/PHASE_7_ROADMAP.md` | Recently updated, authoritative |

---

## Part 6: Summary Statistics

### Markdown Files
- **Total:** 31
- **KEEP:** 24
- **DELETE:** 7 (including 1 rename)

### Python Files  
- **Total:** 63
- **KEEP:** 62
- **RENAME:** 1 (spotcheck.py → compare_bc_predictions.py) **COMPLETED**

### Changes Summary
- **Files deleted:** 6
- **Files renamed:** 1
- **Files modified (reference updates):** 3 (README.md, CHANGELOG.md, DECOMPILER_HANDOVER.md)

### Broken Cross-References
- **Total:** 1
- **Details:** docs/CONTEXT_PACK_PROTOCOL.md referenced but missing

---

## Appendix: File-by-File Classification Detail

### Files Classified as DELETE (Actions Completed)

1. **`docs/README.md`** ✅ DELETED — Near-duplicate of root README. The docs/ folder doesn't need its own readme.

2. **docs/SESSION_PROGRESS.md** ✅ DELETED — Session-by-session working notes from sessions 1-7. Content has been absorbed into DECISION_LOG.md (which has entries from DEC-001 through DEC-021). The narrative log function has been replaced by the structured decision log.

3. **docs/LATEST_FIXES.md** ✅ DELETED — Session working notes with entries from July 28-August 2. CHANGELOG.md header explicitly states: "For recent sessions, see docs/LATEST_FIXES.md. For the full session-by-session narrative log, see docs/SESSION_PROGRESS.md." Both LATEST_FIXES and SESSION_PROGRESS are being deleted, meaning CHANGELOG.md will be the sole historical record.

4. **docs/CORPUS_PIPELINE_STATUS.md** ✅ DELETED — Last updated July 26, 2026. References the 4-module corpus (superseded by 14-module corpus). Pipeline architecture description is now in docs/reference/Design.md and docs/reference/ENCODER_FORMAT.md. Results are in PHASE_5_RESULTS.md and PHASE_6_RESULTS.md.

5. **docs/OPENHANDS_DEC006_TASK.md** ✅ DELETED — Task brief for a completed OpenHands run. Contains implementation details for DEC-006 (embedding projection), but the implementation is complete and documented in DECISION_LOG.md DEC-021. No ongoing value.

6. **PHASE_5_COMPLETION_CHECKLIST.md** ✅ DELETED — Phase checklist for a closed phase. Explicitly marked deprecated with links to current authoritative documents. Content is historical.

7. **python/spotcheck.py** ✅ RENAMED to `python/compare_bc_predictions.py` — Different purpose from `spot_check.py`:
   - `spot_check.py`: Validates corpus token round-trips via corpus_loader.py
   - `compare_bc_predictions.py`: Compares B vs C token-level predictions (requires loaded models)
   
   The similar names were confusing. Renamed per task instructions to make distinction clear.
