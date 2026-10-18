# Pipeline Hardening & Test Harness — Scoping Document

> **Purpose.** This document scopes the test-harness and pipeline-hardening work needed
> so that experimental results can be trusted. The current pattern — where experiments
> primarily surface pipeline bugs — must change. This is the specification for a downstream
> implementation agent.
>
> **The problem, stated plainly.** Most experiments so far have been the mechanism by
> which pipeline bugs were discovered: stale checkpoints, epoch confounds, the IR-tokens-
> fed-to-all-variants extraction bug, the bos/eos out-of-range crash. Each was found
> *because* a surprising result triggered investigation. That means the pipeline was the
> thing being tested, not the hypothesis. The goal of this work is to invert that: make
> the pipeline self-validating, so that when a result comes out, it is trustworthy by
> construction — not trustworthy because someone happened to notice an anomaly.

---

## 1. Diagnosis: why bugs keep arising (the pattern to break)

Every bug found so far has the same shape: an **assumed invariant was silently violated**,
and nothing checked it. The pipeline *could* produce an invalid result and *did*, because
there was no gate that rejected invalid configurations before the experiment ran.

| Bug | Invariant that was violated | Where it should have been caught |
|---|---|---|
| Stale checkpoint (Variant C 1.5% bug) | The checkpoint loaded at eval matches the `results.json` it claims to evaluate | At eval-load time; the mtime guard was added *after* the bug — it should be a precondition, not a warning |
| Epoch confound (B/C 3-epoch vs A/B-small 2-epoch) | Compared runs are epoch-matched | At comparison time, before any table is emitted |
| IR tokens fed to B/C in `extract_representations.py` | Each variant's embeddings come from the input it was trained on | At extraction time — the input source must match the variant's `source` field |
| bos/eos out-of-range crash | Every `input_ids` value is in the loaded checkpoint's vocab range | At eval-load time |
| (Non-bug, but a near-miss) The "13 name collisions" | Train/eval disjointness is checked by full identity, not bare name | Already handled by `example_id` in `check_split_integrity.py` — but this *almost* became a bug, and the invariant isn't documented |

The common thread: **invariants were implicit, not asserted.** The fix is to make every
invariant explicit, checked, and blocking. A pipeline that can fail silently is a pipeline
that will produce untrustworthy results; a pipeline that hard-fails on invariant violation
is one whose results can be read at face value.

---

## 2. Architectural principle: separate validation from experimentation

The current process conflates two phases:

- **Phase A — pipeline validation:** does the pipeline do what I think? (invariants hold,
  artifacts are well-formed, comparisons are valid)
- **Phase B — hypothesis testing:** does the representation help? (run the experiment,
  read the result)

The project has been running Phase B on an unvalidated Phase A. That is why every
experiment surfaced a bug: Phase B was the only thing testing Phase A. The fix is a
**validation layer that runs before any experiment and blocks it if invariants fail.**
Then Phase B runs on a validated pipeline, and its results are trustworthy by construction.

Concretely: no experiment script (train, eval, extract, retrieve) should be runnable
without the validation layer passing first. And the validation layer should be fast
(seconds, not the hours an experiment takes) so it can run on every commit and every
experiment invocation.

---

## 3. What already exists (build on this, don't rebuild)

The repo is not starting from zero. There is real validation infrastructure already:

| Existing asset | What it checks | Gap |
|---|---|---|
| `check_split_integrity.py` | Train/eval disjointness (by `example_id`, correctly), cross-variant eval identity | Only covers A/B/C; doesn't check B-small/flat; doesn't block, just reports |
| `check_results_gate.py` | results.json present, not smoke, eval cap/count identical across variants | Doesn't check epoch match, doesn't check provenance fields |
| `eval_completion.py` stale-checkpoint guard | results.json mtime vs checkpoint mtime | A warning, not a hard fail |
| `test_eval_checkpoint_guard.py`, `test_eval_regression.py`, `test_eval_completion_authoritative.py` | Regression tests for the eval bugs that were found | Reactive — test the *specific* bugs, not the *class* of invariant |
| `test_pipeline_integration.py` | End-to-end smoke test on synthetic corpus | Good, but synthetic; doesn't validate real-artifact invariants |
| `validate_experiment_artifacts.py` | JSON schema of status files | Schema-only, not semantic invariants |
| `test_c4_consistency.py` | Python/Lean skew in GEN bucketing | Good example of a cross-language invariant check |

**The pattern:** the existing checks are *bug-specific regressions* (testing that the last
bug doesn't recur) and *schema validators* (is the JSON well-formed). What's missing is a
*semantic invariant layer* — checks that the relationships between artifacts hold
(checkpoint matches results, variant input matches variant checkpoint, compared runs are
epoch-matched, embeddings came from the right input). That is the layer this work adds.

---

## 4. The harness to build — four components

> **File-specific implementation details** (from repo inspection) are interleaved below
> in `>` blockquotes. These are the exact line numbers, field names, and code patterns
> a downstream agent needs.

### 4.1 Provenance manifests (the foundation)

Every artifact gets a manifest recording *what it is and how it was made*. This already
partially exists (`representation_manifest.json`, `results.json` fields) but is
inconsistent. Standardize a single manifest schema applied to every artifact type.

**Manifest fields (every artifact):**
- `artifact_type`: `checkpoint` | `dataset` | `embeddings` | `results` | `ground_truth`
- `variant`: `A` | `B_small` | `B` | `C` | `flat` | `random` | `multi`
- `representation_id`: e.g. `semantic_graph_ir_v2_0_0`
- `source_input`: what input representation this artifact was produced from
  (`ir_tokens` | `leanExpr` | `ast_split` | `bpe_601` | `bpe_full`) — **critical for the
  extraction bug**
- `seed`, `epochs`, `train_examples`, `eval_examples`
- `created_at`, `created_by_commit` (git SHA), `pipeline_version`
- `provenance_hash`: a content hash of the inputs that produced it (so two artifacts can
  be proven to come from the same source data)

**Why this matters:** the IR-tokens-to-B/C bug existed because nothing recorded "these
embeddings came from `ir_tokens`, but this checkpoint was trained on `leanExpr`." A
manifest with `source_input` on both artifacts makes that mismatch *detectable* — and
the comparison gate (§4.3) makes it *blocking*.

> **Current results.json format** (train.py line 610-628):
> ```json
> {"variant": "A", "vocab_size": 601, "n_params_M": 358.4, "train_examples": 3491,
>  "eval_examples": 388, "epochs": 2, "eval_perplexity": 1.2361, "seed": 42,
>  "base_model": "Qwen/Qwen2.5-Coder-0.5B", "smoke_test": false,
>  "embed_pretrain": false, "embed_project": false}
> ```
> Fields to add: `actual_learning_rate`, `actual_batch_size`, `actual_max_seq_len`,
> `checkpoint_sha256`, `source_input`, `config_vocab_size`, `config_hidden_size`.
>
> **Note:** per-variant hparam overrides (B/C's 5e-5 LR from commit `83f18a8`) are NOT
> recorded in results.json — it records the global `LEARNING_RATE` (2e-4), not the
> per-variant override. The `actual_*` fields fix this.

**Deliverable:** `python/manifest.py` — write/read/verify manifests. Every existing
pipeline step (build_dataset, train, extract, eval) writes a manifest alongside its
output. Backfill manifests for existing artifacts.

### 4.2 The invariant checker (the gate that runs before experiments)

A single script `python/check_invariants.py` that asserts every semantic invariant the
experiments rely on. It runs in seconds, exits non-zero on any violation, and is called
as a precondition by every experiment script.

**Invariants to check (each is a real bug class, not hypothetical):**

1. **Split integrity (extend existing `check_split_integrity.py`):**
   - Train/eval disjoint by `example_id` for *all* variants (A, B_small, B, C, flat), not
     just A/B/C.
   - Eval example identity identical across all variants (same declarations evaluated).
   - Train example count identical across all variants being compared.

2. **Checkpoint-results consistency (harden the stale guard to a hard fail):**
   - For each `results.json`, the checkpoint it references exists and its mtime is within
     tolerance of the results timestamp.
   - The `results.json` records the checkpoint path and git SHA it was produced from;
     these match the checkpoint dir.

3. **Variant-input consistency (the extraction bug, generalized):**
   - For each checkpoint, the `source` field of the dataset it was trained on matches the
     `source_input` in its manifest.
   - For embeddings: the `source_input` of the embeddings manifest matches the
     `source_input` of the checkpoint manifest. **This is the exact check that would have
     caught the IR-tokens-to-B/C bug.**
   - For eval: the eval dataset's variant matches the checkpoint's variant.

> **The bug in detail:** `extract_representations.py` line 219 feeds `ex["tokens"]` (the
> IR token list from `Corpus/corpus.jsonl`) to every variant. It joins tokens with spaces,
> re-tokenizes, and forward-passes. Correct for A and flat (both trained on IR tokens);
> **wrong for B, C, B_small** (trained on `leanExpr`/AST text via their own `input_ids`).
>
> **The fix:** extract each variant's embeddings from the `input_ids` field of that
> variant's own dataset file (`datasets/eval_{variant}.jsonl`). All variant datasets have
> identical field structure: `source, representation_id, example_id, name, module,
> input_ids, labels, seq_len`. The `input_ids` field contains the exact integer token
> sequences each model was trained on — feed directly, no re-tokenization.
>
> **The assertion to add:**
> ```python
> expected_source = variant  # "A", "B", "C", "B_small", "flat"
> for record in dataset:
>     assert record.get("source") == expected_source, (
>         f"Input-variant mismatch: record source={record.get('source')} "
>         f"but expected variant={expected_source}.")
> ```

4. **Vocab-range consistency (the bos/eos crash, generalized):**
   - For each checkpoint and its matching dataset, every `input_ids` value is within
     `[0, vocab_size)` of the checkpoint's embedding table. Hard-fail on any out-of-range.

5. **Comparison validity (the epoch confound, generalized):**
   - Before emitting any comparison table, assert that the compared runs share:
     `representation_id` (same corpus), `seed`, `train_examples`, `eval_examples`, and
     — for the specific comparison being claimed — `epochs`.
   - The comparison script takes an explicit `--claim` argument (e.g.
     `representation_at_matched_size`) and the invariant checker validates *that specific
     claim's* required matches. The A-vs-B-small claim requires epoch match; the A-vs-B
     claim does not (and the checker must say so, not silently allow it).

> **Current per-variant hparam state** (from commit history and DEC entries):
>
> | Variant | Epochs | LR | Batch | Max seq | Vocab | Params | Notes |
> |---|---|---|---|---|---|---|---|
> | A (v2) | 2 | 2e-4 | 8 | 1024 | 601 | 358M | embed-project |
> | B_small | 2 | 2e-4 | 8 | 1024 | 601 | 358M | DEC-027 control |
> | B (v1-era) | 3 | 5e-5 | 4 | 512 | 151K | 494M | epoch confound |
> | C (v1-era) | 3 | 5e-5 | 4 | 512 | 151K | 494M | epoch confound |
> | flat | 2 | 2e-4 | 8 | 1024 | 11 | 358M | DEC-024 ablation |
>
> B/C's LR was reduced to 5e-5 for stability (commit `83f18a8`) but this is NOT recorded
> in their results.json. The v2 2-epoch re-runs (in progress) would use 2e-4 matching
> A/B_small. The `assert_comparable()` gate would flag the A-vs-B/C epoch mismatch
> (2 vs 3) and the LR mismatch (2e-4 vs 5e-5) before any comparison table is emitted.

> **Split integrity details** (verified from actual data):
> - Train: 3,378 unique names | Eval: 386 unique names | Overlap: 13 names
> - The 13 overlaps are distinct declarations in different modules sharing a short name.
> - `check_split_integrity.py` already uses `example_id` (which includes module), so it
>   correctly sees them as distinct — the collision is a phantom when matching on bare
>   `name`, not a real bug.
> - For retrieval: match by full `name` field and de-duplicate the candidate pool.

6. **Provenance hash consistency:**
   - Two artifacts compared as "same data, different representation" must have matching
     provenance hashes on their input corpus. Catches the case where a v3 candidate's
     baseline is carried over from v2 but the corpus actually changed.

**Deliverable:** `python/check_invariants.py` — the single gate. Plus a
`python/test_invariants.py` that runs the checker against fixture artifacts (both valid and
intentionally-broken) and confirms it passes/fails correctly.

### 4.3 The comparison gate (blocks invalid comparisons)

A function called by any script that emits a comparison (perplexity table, retrieval
results, probe scores):

```python
def validate_comparison(artifacts: list[Manifest], claim: str) -> None:
    """Hard-fail if the artifacts don't support the claimed comparison."""
```

`claim` is a documented string (`representation_at_matched_size`,
`representation_vs_full_bpe`, `ir_vs_flat_ablation`, etc.) with a spec of which manifest
fields must match and which must differ. This makes the *intended variable* of each
comparison explicit and checked — so you cannot accidentally produce a table where two
variables changed at once (the original A-vs-B/C size confound) without the gate rejecting
it.

**Deliverable:** python/comparison_gate.py (planned, not yet built) + the claim spec registry. Every existing
compare/results script routes through it.

### 4.4 Deterministic reproduction checks (trust requires repeatability)

A result is only trustworthy if the same command on the same inputs produces the same
output. Add:

- **Embedding determinism:** run extraction twice on a small subset, assert bit-identical
  (or within float tolerance) embeddings. Catches nondeterministic pooling/device issues.
- **Eval determinism:** run eval twice on the same checkpoint, assert identical perplexity
  and accuracy. Catches eval nondeterminism (dropout not disabled, sampling without seed).
- **Dataset determinism:** rebuild a small dataset from the corpus, assert identical
  `input_ids` to the committed one. Catches split/tokenization nondeterminism.

These are cheap (seconds-minutes) and catch an entire class of "the result changed when I
re-ran it" bugs that currently require a human to notice.

**Deliverable:** python/test_determinism.py (planned, not yet built) — runs the three checks on fixtures and
committed artifacts.

---

## 5. The process change (more important than the code)

The harness only works if it is *used*. The process must enforce:

1. **No experiment runs without `check_invariants.py` passing.** Every experiment script
   (train, eval, extract, retrieve) calls the checker at startup and exits if it fails.
   This is a one-line addition per script and is non-negotiable.

2. **Every comparison routes through `validate_comparison`.** No ad-hoc comparison tables
   emitted by scripts that didn't call the gate. This is enforced by code review and by
   the comparison scripts sharing the gate function.

3. **Manifests are written, not optional.** Every artifact-producing step writes a
   manifest. An artifact without a manifest is treated as untrustworthy and rejected by
   downstream consumers.

4. **The invariant checker runs in CI (or as a pre-commit).** It is fast enough. Bugs
   should surface on commit, not on experiment.

5. **When a new bug is found, add an invariant, not just a regression test.** The current
   pattern (test the specific bug) is necessary but insufficient — it guards one instance.
   The new pattern: identify the invariant the bug violated, add it to
   `check_invariants.py`, then add a regression test for the specific instance. The
   invariant is the general guard; the regression test confirms the guard fires.

---

## 6. Priority and sequencing

Do this in order — each component unblocks the next:

1. **Manifests first (§4.1).** Nothing else can check provenance without manifests on
   artifacts. Backfill existing artifacts.
2. **Invariant checker (§4.2).** The core gate. Once manifests exist, the invariants are
   checkable. This is where the IR-tokens-to-B/C bug, the epoch confound, and the
   vocab-range crash all get caught generically.
3. **Comparison gate (§4.3).** Depends on manifests; blocks invalid comparisons.
4. **Determinism checks (§4.4).** Independent; can be done anytime but is most valuable
   once 1-2 are in place so the "validated pipeline" is confirmed repeatable.

**Time estimate:** 3–5 focused days. Manifests + backfill ~1 day; invariant checker ~1.5
days (most of it enumerating and testing each invariant against fixture artifacts);
comparison gate ~0.5 day; determinism checks ~0.5 day; wiring into existing scripts and
process ~1 day.

---

## 7. What "done" looks like

- `python/manifest.py` + manifests on all existing artifacts (checkpoints, datasets,
  embeddings, results, ground truth).
- `python/check_invariants.py` passing on all current artifacts, with documented invariants
  and a test suite (`test_invariants.py`) that confirms it fails on intentionally-broken
  fixtures.
- python/comparison_gate.py with a claim registry; every comparison script routed through
  it.
- python/test_determinism.py passing (embedding/eval/dataset determinism confirmed).
- Every experiment script calls `check_invariants.py` at startup and hard-fails on
  violation.
- The IR-tokens-to-B/C bug, if it were reintroduced, is caught by invariant 3 and blocks
  the extraction — not discovered weeks later via a surprising retrieval result.

**The success criterion is cultural, not just technical:** after this work, when an
experiment produces a result, the first question is no longer "is this a bug?" but "what
does this mean?" That shift — from debugging results to interpreting them — is what
"trustworthy by construction" means, and it is what unblocks doing the remaining reachable
experiments (H5, H6, H9, H10) with confidence in their outputs.

---

## 8. Relationship to the experiments

This harness is not an experiment; it is the precondition for the experiments being
worth running. After it is in place:

- **H6 (retrieval)** can run on a validated pipeline — the per-variant embedding extraction
  (the §4.1 bug in the H6 scope) is enforced by invariant 3, not hoped for.
- **H5 (objective redesign)** can be compared to the prediction baseline without epoch or
  provenance confounds slipping in.
- **H9, H10** inherit the same guarantees.

The order is: **harden the pipeline, then run the reachable experiments on it.** Running
more experiments on the current pipeline reproduces the pattern — each will surface a bug,
because the pipeline is still the thing being tested. Invert that first.

---

## 9. What this does not do

- It does not make the *interpretation* of results easier — only their *trustworthiness*.
  A validated pipeline can still produce a null that means "the representation doesn't
  help," and that's a real result, not a bug.
- It does not reach the scale ceiling (H4/H8) or ATP (H7) — those remain above compute.
- It does not replace the need to design good experiments — it removes the confound of
  not knowing whether a result reflects the hypothesis or a pipeline failure.
