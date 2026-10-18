# Probing Task: Pre-Proposal Research Guide

**Purpose:** A step-by-step guide for Kit to work through before writing the probing
task proposal. Each step requires reading actual data or files and recording findings
here before moving to the next step. The proposal gets written only after all steps
are complete and findings are recorded.

**Do not write the proposal until every checkbox in every section is ticked.**

---

## Step 1 — Understand what question the probing task must answer

Before designing anything, be clear on what DEC-024 left open and what experiment
design would actually resolve it.

- [ ] Read DEC-024 in full from `docs/decisions/LOG.md`
- [ ] Write in one sentence: what is the ambiguity DEC-024 left open?
- [ ] Write in one sentence: what would a probing task result of "A >> Flat-IR" mean?
- [ ] Write in one sentence: what would a result of "A ≈ Flat-IR" mean?
- [ ] Write in one sentence: why is probing cheaper than the alternatives (IR pretraining, corpus expansion)?
- [ ] Confirm: does the existing data (corpus, checkpoints) have everything needed, or does anything new need to be built first?

**Findings from Step 1:**
<!-- Kit fills this in after completing the checkboxes -->

---

## Step 2 — Audit the available checkpoints

Before designing the probe, verify what is actually on disk and loadable.

- [ ] List every directory under `runs/` that contains a `checkpoint-final/` subdirectory
- [ ] For each relevant checkpoint, read its `config.json (in the checkpoint, not this repo)` and record: `hidden_size`, `vocab_size`, `model_type`
- [ ] Confirm which checkpoints correspond to which variants (A v1.4.0, C Phase 6, Flat-IR)
- [ ] Check whether a pretrained-only Qwen2.5-Coder-0.5B (no fine-tuning) checkpoint exists locally, or whether it would need to be downloaded
- [ ] Record any checkpoint that appears broken or mismatched (wrong vocab_size for its variant)

**Findings from Step 2:**
<!-- Kit fills this in -->

---

## Step 3 — Audit the corpus labels

The probing task needs labels. Understand what is available in `corpus.jsonl` before
deciding what tasks are feasible.

- [ ] Read the first 5 examples from `corpus.jsonl` — list every top-level key present
- [ ] For each key, describe what it contains (string, list, dict, etc.)
- [ ] Count distinct values of the `module` field — how many modules, what are their names, how many examples each?
- [ ] Check whether `declType` or any equivalent declaration-type field exists
- [ ] Check whether the `graph` field has structured subfields (entities, relations, operations) that could be used as derived labels
- [ ] Identify which fields are available as classification targets without any new Lean extraction

**Findings from Step 3:**
<!-- Kit fills this in -->

---

## Step 4 — Characterise the semantic content

Understand what the IR's semantic tokens actually are before deciding whether a probe
can detect them.

- [ ] Count unique `gen:` tokens in the full corpus; record total count and occurrence distribution (min, median, p90, how many appear only once)
- [ ] For each module, count how many unique `gen:` tokens it uses
- [ ] Measure cross-module gen: token sharing: what fraction of gen: tokens appear in more than one module?
- [ ] Check structural tokens (non-gen:): what fraction of the average sequence is structural vs semantic?
- [ ] Identify the top 10 most frequent gen: tokens and which modules they appear in

**Findings from Step 4:**
<!-- Kit fills this in -->

---

## Step 5 — Assess task feasibility

Before committing to a task design, check whether it is actually solvable at this scale.

- [ ] For module classification: are the class sizes balanced enough for a linear probe to learn? Record the smallest and largest class sizes.
- [ ] What is the random baseline accuracy for module classification (1 / N_classes)?
- [ ] Are any modules so similar semantically that a probe could not plausibly separate them? Which ones?
- [ ] What fraction of corpus examples fit in 512 tokens (the likely sequence cap for extraction)?
- [ ] For any alternative label (arity bins, declaration type): what would the class distribution look like?

**Findings from Step 5:**
<!-- Kit fills this in -->

---

## Step 6 — Understand the probe architecture constraints

- [ ] What is the hidden dimension of each checkpoint? (Read from config.json — do not assume)
- [ ] Are all four variants the same hidden dimension? If not, how does the probe handle the mismatch?
- [ ] What pooling strategy makes sense for a causal LM with no CLS token — mean pool, last token, or something else? Write the reasoning.
- [ ] How long does a single forward pass take on the available hardware (MPS)? Estimate total extraction time for 4,029 examples × 4 variants.
- [ ] Is GPU memory a constraint? Can all four models be held in memory simultaneously, or must they be loaded and unloaded one at a time?

**Findings from Step 6:**
<!-- Kit fills this in -->

---

## Step 7 — Define the interpretation criteria before running anything

A probing experiment is only useful if the interpretation criteria are set before seeing
the results. Write these now, before any code is written.

- [ ] Define what counts as "A >> Flat-IR" (the decisive gap threshold) and justify the number
- [ ] Define what counts as "A ≈ Flat-IR" (inconclusive zone) and justify the number
- [ ] For each possible outcome (A >> Flat-IR, A ≈ Flat-IR, Flat-IR >> A, C >> all others, Random ≈ all), write what the next step would be
- [ ] Identify any result that would be ambiguous and describe what follow-up experiment would resolve it

**Findings from Step 7:**
<!-- Kit fills this in -->

---

## Step 8 — Identify risks and mitigations before writing any code

- [ ] What happens if the Flat-IR representations are degenerate (near-identical for all examples)? How would you detect this and what would it mean?
- [ ] Could the module classification task be solved by memorising module-exclusive gen: tokens rather than learning richer structure? How would you detect this?
- [ ] Are there any examples in the corpus that appear in multiple modules (same declaration name, different module)? If so, would they cause label leakage?
- [ ] What is the risk that MPS non-determinism affects representation extraction? Is the extraction deterministic given a fixed seed?

**Findings from Step 8:**
<!-- Kit fills this in -->

---

## Step 9 — Write the proposal

Only start this step when Steps 1–8 are fully completed and all findings are recorded
above. The proposal should:

- Be grounded entirely in the findings above — no assumptions, no estimates
- Specify exact file paths, class counts, threshold values, and checkpoint configs from Steps 2–6
- Include the interpretation table from Step 7
- Include the risk mitigations from Step 8
- Include a step-by-step implementation checklist

The proposal goes in docs/PROBING_TASK_PROPOSAL.md (planned location; no such file yet).

---

## Progress

| Step | Status |
|---|---|
| 1 — Understand the question | 🔴 Not started |
| 2 — Audit checkpoints | 🔴 Not started |
| 3 — Audit corpus labels | 🔴 Not started |
| 4 — Characterise semantic content | 🔴 Not started |
| 5 — Assess task feasibility | 🔴 Not started |
| 6 — Probe architecture constraints | 🔴 Not started |
| 7 — Define interpretation criteria | 🔴 Not started |
| 8 — Identify risks | 🔴 Not started |
| 9 — Write proposal | 🔴 Blocked on 1–8 |
