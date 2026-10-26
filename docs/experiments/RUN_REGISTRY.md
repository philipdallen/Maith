# Run Registry — Checkpoint Provenance Reference

> **Purpose.** Single source of truth for what each checkpoint was trained on,
> what config it used, and which comparisons it belongs to. This exists because
> the manifest system was built but never wired into the training scripts, so
> provenance must be reconstructed from results.json files and commit history.
>
> **Update protocol.** Every new training run adds a row here BEFORE the run
> starts, with a designated run ID. After the run, fill in the actual values.
> Never delete rows — superseded runs are marked SUPERSEDED.

## Shared provenance inputs

These are the inputs every run below shares. Per-run rows record what differs
between runs; this table records what does not. Without it, a Run ID resolves
only *within* the repo — it does not pin the base weights or the corpus bytes
that produced a figure, so the figure cannot be re-derived from the registry
alone (the gap this table closes; see issue #57).

### Base transformer

| Field | Value |
|---|---|
| Model repo | `Qwen/Qwen2.5-Coder-0.5B` |
| Revision | `8123ea2e9354afb7ffcc6c8641d1b2f5ecf18301` |
| Resolved at | 2026-09-22 (HuggingFace `lastModified` 2024-11-18) |
| Note | Every variant (A, B, B_small, C, flat) shares this transformer base and is fine-tuned from it. **The revision is pinned** in `python/train_v2_resume.py` (`BASE_MODEL_REVISION`, passed as `revision=` at every tokenizer/model load and written to `results.json` as `base_model_revision`), so a fresh HuggingFace pull cannot silently differ. Verified by `python/verify_registry_inputs.py`. |

### Corpus

| Field | Value |
|---|---|
| Manifest | `Corpus/corpus_manifest.json` (tracked) |
| Content hash | `sha256:d3da238290f5ca46232de5df280d4bcfeab60b127e1b2898cff4172e898e7fe9` |
| Format / count | `per_operator`, 4029 declarations |
| Producing commit | `9e0c485ea1f837e73bf95b54e613598755fbac47` |
| Mathlib commit | `fabf563a7c95a166b8d7b6efca11c8b4dc9d911f` (`Corpus/stats.json`) |
| Note | `Corpus/corpus.jsonl` is gitignored (60 MB build artifact), so it is **absent from a fresh clone**. The hash is now re-verified: `check_corpus.py` gate **G2-6** recomputes the sha256 of the corpus and fails if it does not match `corpus_manifest.json` ("a check that cannot fail is not a check" — the earlier state wrote the hash but never read it back). Gate **G2-7** fails if version strings disagree across `Corpus/stats.json` / `datasets/representation_manifest.json` / `Maith/Encoder.lean`. The previously inconsistent manifests are reconciled: `representation_manifest.json` now derives `encoderVersion` from the corpus stats at build time (`build_dataset.py`) and reads `1.4.0`, matching `stats.json` and `Encoder.lean`. `stats.json.irVersion` (`semantic_graph_ir_v1_4_0`) is a *different namespace* from `encoderVersion` (`1.4.0`) — the IR graph id vs the encoder, by design (see `LEAN_PIPELINE_AUDIT_2026_08.md` F2). Remaining gap: the corpus bytes themselves are not tracked, so G2-6 can only verify a locally rebuilt corpus. |

### Dataset splits (clean, 3375/376)

These are the split hashes for the rebuilt dedup'd datasets that Variant A and
flat were retrained on (DEC-031). **The split `.jsonl` files are gitignored
build artifacts, not tracked** (`.gitignore`: `datasets/train_*.jsonl`,
`datasets/eval_*.jsonl`), so they are absent from a fresh clone and the hashes
below cannot be checked until the split is rebuilt — see "Rebuild commands". The
tracked manifest that *is* checked is `datasets/train_manifest.json` /
`datasets/eval_manifest.json` (the declaration-name lists) and
`datasets/representation_manifest.json` (the 3375/376 counts).

| Variant | Train file | Train sha256 | Eval file | Eval sha256 |
|---|---|---|---|---|
| A | `datasets/train_A.jsonl` | `161b3defb62d89b797e403f92e506d97ec86b6ac1f1593760c0b44b9427580d7` | `datasets/eval_A.jsonl` | `7dd41021995875dd5d6fea5093f365249f267b8ed5e89abeb4623ba7432a7e66` |
| B | `datasets/train_B.jsonl` | `8f51502ee1cbcfaaef604ef244870b3d1d7fb16ad88fe65c34e78104072af419` | `datasets/eval_B.jsonl` | `edb4545b2e825f151c80f3d9edb89dc9615bc3d300d266513d587980f456fec2` |
| B_small | `datasets/train_B_small.jsonl` | `1178585446c36c8ba47b21fb28b0200abd7c46346603c90b4170d6fdb56fb556` | `datasets/eval_B_small.jsonl` | `ebd7b256d2f0ad0d8ea79c38b844df81b69569f1d0731fb4f330bb69ec582847` |
| C | `datasets/train_C.jsonl` | `c86f73b584045066d8e9289a07dba203e416bfa3514efd2de6ca7a2610ca112c` | `datasets/eval_C.jsonl` | `5686da1b4b133614c7a62b9a89849590a4a97591c1d0c956f608886338ce15b0` |
| flat | `datasets/train_flat.jsonl` | `edcd2030382c7d861e40384f4b2018b072e2cd252aeb69826ae480d88dc8e2a4` | `datasets/eval_flat.jsonl` | `152d4dfb2637abf56d6a9a52cd2bc1ff9178f608378e0f779878c36728d389bc` |

### Tracked provenance inputs (re-verifiable on a bare clone)

These files are committed, so a fresh clone can re-hash them and detect drift.
`python3 python/verify_registry_inputs.py` checks each against the hash below.

| Artifact | sha256 |
|---|---|
| `datasets/train_manifest.json` | `ca2adea1898b07fd290998e184fc082bf2d2cf99dc100634a46d135342ded528` |
| `datasets/eval_manifest.json` | `1b69e3010416792b3e3f14bcb590283882b535b9fb4b50dbbf069fe2da4f3f2f` |
| `datasets/representation_manifest.json` | `d3e1603d0e3113bf9f793bc428896ca4b76a62eacfac11dd693837bcb6b11a4e` |
| `datasets/vocab_A.json` | `44a56373e1bd1ade61c6a69690e497a5eb265efe31fcaf1127b7134525623f28` |
| `Corpus/corpus_manifest.json` | `1376cf2a345a36d4e818aae9fa2db0f5a3304756ce9555c81c20f83b89f40909` |
| `Corpus/stats.json` | `d561f3300f3180106cd8ad1139ef60476c2bbd36249da6e388191e9e030a775b` |
| `Maith/Encoder.lean` | `31dd19eb34a1b6cbbe1791af9c190b9baf510fb5e8cf388c19fbfd822b66cef6` |

### Rebuild commands

The registry entry is the complete rebuild spec (maintainer decision on issue
#57, 2026-10-25: **rebuild-on-demand** — corpus bytes and checkpoints are not
mirrored). Regenerate each untracked artifact from the tracked inputs:

```bash
# 1. Corpus bytes — needs the Lean toolchain + Mathlib (elan/lake).
#    Output is gitignored; check_corpus.py gate G2-6 then re-hashes it.
tooling/install_elan.sh && export PATH="$HOME/.elan/bin:$PATH"
lake exe cache get
lake exe buildCorpus                 # per_operator → Corpus/corpus.jsonl
python3 python/check_corpus.py --corpus Corpus/corpus.jsonl   # expect G2-6 PASS

# 2. Dataset splits — needs transformers (Qwen2.5-Coder-0.5B tokenizer).
python3 python/build_dataset.py --corpus Corpus/corpus.jsonl --out datasets/ --seed 42

# 3. Checkpoint + figure — needs torch + a GPU. Launch via the canonical entry
#    point (launch_run.py enforces the invariant checker and writes results.json).
python3 python/launch_run.py train --variant A --config <config_tag>
```

### Producing config

The per-run rows above record vocab, train n, epochs and LR (the fields that
differ per row). Every row also inherits the **shared inputs** (base transformer
repo + revision, corpus content hash, Mathlib commit) and the constants below.
Together those two blocks are the complete generating config for a row — the
rebuild spec a fresh clone needs (issue #57).

| Field | Value |
|---|---|
| Base model repo | `Qwen/Qwen2.5-Coder-0.5B` (see "Base transformer") |
| Base model revision | `8123ea2e9354afb7ffcc6c8641d1b2f5ecf18301` |
| Corpus content hash | `sha256:d3da238290f5ca46232de5df280d4bcfeab60b127e1b2898cff4172e898e7fe9` |
| Script | `python/train_v2_resume.py` (canonical), via `python/launch_run.py train`. `python/train.py` is deprecated |
| Seed | `42` (`SEED`) |
| Effective batch size | `8` (`BATCH_SIZE` 1 × `GRAD_ACCUM` 8) |
| Max seq len | `1024` |
| Where config is written | `runs/<run_id>/results.json` (`variant`, `vocab_size`, `n_params_M`, `train_examples`, `epochs`, `eval_perplexity`, `seed`, `base_model`, `base_model_revision`, `learning_rate`, `effective_batch_size`, `max_seq_len`) |
| Tracked? | The *config* is recorded here and in `results.json`; `runs/` itself is gitignored, so the checkpoint is rebuilt via "Rebuild commands" rather than recovered from a clone |
| Note | The values above are the constants `train_v2_resume.py` applies to every row. They are recorded here so a row's config is recoverable without the (untracked) `results.json`. |

### Reproducing a published figure

Run the registry verifier — it re-derives what a figure depends on from the
values recorded here, and reports PASS / FAIL / SKIP per input:

```bash
python3 python/verify_registry_inputs.py --variant A        # or B_small
```

Example (Variant A, clean clone), 2026-10-26 — issue #57 verify step:

```
  PASS  base_model_revision: pinned + used at all load sites
  SKIP  corpus content_hash: SKIP — Corpus/corpus.jsonl is gitignored (absent from a fresh clone)
  PASS  version consistency: stats.json == representation_manifest.json == Encoder.lean
  PASS  tracked manifests: hashes match registry
  PASS  split counts: 3375 train / 376 eval
  SKIP  dataset hashes (A): SKIP — datasets/{train,eval}_A.jsonl are gitignored build artifacts; rebuild via python3 python/build_dataset.py
  SKIP  figure value: eval_perplexity=1.2812 (in gitignored runs/; cannot be recomputed without the checkpoint)

PASSED — 4/4 verifiable checks passed; 3 skipped (inputs not tracked).
```

**What "reproduce from the registry entry alone" means here.** Every tracked
input a figure depends on is pinned and re-verified on a bare clone: the base
model repo+revision, the corpus content hash, the version strings, the tracked
manifests and the split counts. The corpus bytes, the split `.jsonl` files and
the checkpoint are **not mirrored** (rebuild-on-demand, maintainer decision
2026-10-25); the registry entry is the rebuild spec, and "Rebuild commands"
above regenerates each artifact. Rebuilding the checkpoint and re-deriving
`eval_perplexity` additionally needs the Lean/Mathlib toolchain, `torch` and a
GPU, none of which a bare clone supplies.

## Checkpoint inventory

### Variant A (semantic IR)

| Run ID | Dir | Vocab | Train n | Epochs | Corpus mode | LR | Perplexity | Notes |
|---|---|---|---|---|---|---|---|---|
| A-dec006 | variant_A_dec006 | 8144 | 3375 | 2 | per-op (gen:FullName) | 2e-4 | 1.2978 | Early per-op run |
| A-phase6 | variant_A_phase6 | 8144 | 3375 | 3 | per-op (gen:FullName) | 2e-4 | 1.2792 | 3-epoch per-op |
| A-v1.3.0 | variant_A_v1_3_0 | 4554 | 2213 | 2 | v1.3.0 (pre-C4) | 2e-4 | 1.4325 | Old corpus, small |
| A-v1.3.0-ep | variant_A_v1_3_0_ep | 4554 | 2213 | 2 | v1.3.0 | 2e-4 | 1.4226 | Duplicate of above |
| A-v1.3.0-final | variant_A_v1_3_0_final | 8144 | 3375 | 2 | per-op | 2e-4 | 1.3016 | |
| A-v1.3.0-proj | variant_A_v1_3_0_proj | 8221 | 3491 | 2 | per-op, old (leaky) | 2e-4 | 1.3717 | Trained on leaky data |
| A-v1.3.0-true | variant_A_v1_3_0_true | 8221 | 3491 | 2 | per-op, old (leaky) | 2e-4 | 1.3896 | Trained on leaky data |
| A-v1.4.0 | variant_A_v1_4_0 | 1236 | 3491 | 2 | v1.4.0 (IO markers) | 2e-4 | 1.2751 | Trained on leaky data |
| **A-v2** | **variant_A_v2_full** | **601** | **3491** | **2** | **v2 module (GEN_ buckets)** | **2e-4** | **1.2361** | **DEC-026/027, trained on leaky data** |
| A-v2.0.0-smoke | variant_A_v2_0_0 | 601 | 50 | 1 | v2 module | 2e-4 | 16.06 | Smoke test |
| **A-v3** | **variant_A_v3** | **8102** | **3375** | **3** | **per-op (gen:FullName)** | **2e-4** | **1.2812** | **DEC-029, 3 epochs** |

### Variant B (raw BPE)

| Run ID | Dir | Vocab | Train n | Epochs | LR | Perplexity | Notes |
|---|---|---|---|---|---|---|---|
| B2 | variant_B2 | 151643 | 3375 | 3 | 5e-5 | 1.107 | 3-epoch, dedup'd train |
| B-phase6 | variant_B_phase6 | 151643 | 3375 | 2 | 5e-5 | 1.1295 | 2-epoch |
| **B-v2-2ep** | **variant_B_v2_2ep** | **151643** | **3491** | **2** | **5e-5** | **1.099** | **Trained on leaky data** |

### Variant B_small (BPE truncated to 601)

| Run ID | Dir | Vocab | Train n | Epochs | LR | Perplexity | Notes |
|---|---|---|---|---|---|---|---|
| **B-small** | **variant_B_small** | **601** | **3491** | **2** | **2e-4** | **1.1294** | **DEC-027, trained on leaky data** |

### Variant C (AST-split BPE)

| Run ID | Dir | Vocab | Train n | Epochs | LR | Perplexity | Notes |
|---|---|---|---|---|---|---|---|
| C-phase6 | variant_C_phase6 | 151643 | 3375 | 2 | 5e-5 | 1.1102 | |
| **C-v2** | **variant_C_v2** | **151643** | **3375** | **3** | **5e-5** | **1.098** | **3-epoch** |

### Variant flat (shape-only IR)

| Run ID | Dir | Vocab | Train n | Epochs | LR | Perplexity | Notes |
|---|---|---|---|---|---|---|---|
| flat | variant_flat | 11 | 3627 | 2 | 2e-4 | 1.0551 | Old split (3627, unmatched) |

---

## Comparison matrix — what's valid to compare

### Valid comparisons (confound-free)

| Comparison | A side | B side | Matched on | Differs on | Status |
|---|---|---|---|---|---|
| A-v2 vs B-small | A-v2 (2ep, 601v, leaky) | B-small (2ep, 601v, leaky) | epochs, vocab, train_n, corpus | representation | ✅ VALID (DEC-027) |
| A-v1.4.0 vs flat | A-v1.4.0 (2ep, 1236v) | flat (2ep, 11v, old split) | epochs | representation, split | ⚠️ SPLIT MISMATCH |

### Confounded comparisons (NOT valid as representation tests)

| Comparison | Confound | Why it matters |
|---|---|---|
| A-v2 vs B-v2-2ep | Size (601v vs 151Kv) | 136M param difference |
| A-v2 vs C-v2 | Size + epochs (2 vs 3) | Two variables changed |
| A-v3 vs B-small | **Epochs (3 vs 2)** | A-v3 had 50% more training |
| A-v3 vs A-v2 | Epochs (3 vs 2) + corpus mode | Two variables changed |
| A-v3 vs B-v2-2ep | Size + epochs + corpus mode | Three variables changed |
| Any vs flat | Split mismatch (3627 vs 3375/3491) | Different eval declarations |

### Needed: clean A-v3 comparison

To isolate C4 bucketing as the only variable, need:
- **A-v3-2ep**: A-v3 retrained at 2 epochs (matching B-small)
- Then compare A-v3-2ep vs B-small (both 2ep, 601-vocab-ish, same split)
- OR: B-small-3ep: B-small retrained at 3 epochs (matching A-v3)

---

## Dataset version history

| Version | Dir | Train n | Eval n | Dedup'd | Split matches A/B/C | Notes |
|---|---|---|---|---|---|---|
| Original (leaky) | datasets/ (overwritten) | 3491 | 388 | No | Yes (A/B/C shared it) | 128 duplicates, 13 train/eval overlaps |
| Rebuilt (dedup'd) | datasets/ (current) | 3375 | 376 | Yes | Yes | Invariant checker: 50/50 pass |
| Per-operator | datasets_perop/ | 3375 | 376 | Yes | Yes (same split) | For A-v3; gen:FullName tokens |
| Old flat | (overwritten) | 3627 | 402 | No | No (different split) | SUPERSEDED by rebuilt flat |

---

## Embedding extraction history

| Extraction | Dir | Datasets used | Variants | Bug? | Notes |
|---|---|---|---|---|---|
| DEC-025 probing | runs/probing/ | Original (4029) | A, flat (IR tokens to all) | Yes — IR tokens to B/C | Only A and flat extracted |
| H6 first (invalid) | runs/retrieval_embeddings/ (overwritten) | Mixed (A=dedup'd, others=leaky) | A, B_small, B, C, flat | No (per-variant input_ids) | INVALID — mismatched dataset versions |
| H6 validated | runs/retrieval_embeddings/ (current) | Rebuilt (3375/376) | A, B_small, B, C, flat | No | All shapes match |
| A-v3 | runs/retrieval_embeddings/ (current) | Per-op corpus + dedup'd split | A_v3 | No | IR tokens via Qwen BPE tokenizer |

---

## Rules to prevent contamination

1. **Never overwrite a dataset directory.** New builds go to `datasets_v{N}/` or `datasets_{mode}/`. The `datasets/` dir is the current canonical version; previous versions are preserved with a suffix.

2. **Never overwrite an embeddings directory.** Each extraction round goes to `runs/retrieval_embeddings_v{N}/`. The current one is preserved.

3. **Every new training run gets a new directory.** `runs/variant_{V}_{config}/`, not overwriting an existing one. Example: `variant_A_v3_2ep/` for the 2-epoch retrain.

4. **Run the invariant checker before every extraction and eval.** Not optional.

5. **Record the run in this registry before starting.** Assign a run ID, note the config, then run.

6. **Manifests must be written by the training script.** Until the manifest system is wired in, manually create a manifest after each run using `manifest.py`.
