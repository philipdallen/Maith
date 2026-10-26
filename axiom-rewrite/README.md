# `axiom-rewrite/` — candidate ledger, coverage map, and gate harness

Tooling for the axiom-discovery track (`docs/experiments/AXIOM_DISCOVERY.md`).
Issues #27 (ledger), #29 (harness), #37 (batch runner + ledger VCS policy).

> **Scope.** This directory holds the **tracking data structures** (the ledger and
> the derived coverage map) *and* the **five-gate harness** that runs a candidate
> through the gates (`harness.py`). It does not *propose* candidates — that is
> #30/#33 — and it never asserts that a candidate is interesting: it records what
> was tried and what the kernel discharged.

## The two structures

| Thing | Where | Nature |
|---|---|---|
| **Candidate ledger** | `candidates.jsonl` | Append-only. One record per candidate φ. Failed candidates are **kept** — the search history is itself data (which regions of the space are exhausted). **Committed to git** (see §Ledger VCS policy). |
| **Coverage map** | *derived* | Computed from the ledger on every read, never stored. Per benchmark declaration: how many candidates were tried and how they fared. |

The coverage map is deliberately **not** a stored file. A second copy would be a
second source of truth that can drift; the ledger is append-only, so deriving is
cheap and always consistent.

## Ledger VCS policy (decided in #37)

The ledger **is version-controlled**, like `docs/decisions/LOG.md`, and for the
same reason: a reader must be able to verify "we tried this" from the repo rather
than trusting a local file. Because the repo runs parallel agents, two of them can
append between the same two commits — so `.gitattributes` gives the ledger
`merge=union`, and concurrent appends compose instead of conflicting on the last
line. Order within the file is then not meaningful; the ledger is read by
`candidate_id`, and `read_ledger`/`coverage` do not depend on position.

## Record schema

One JSON object per line in `candidates.jsonl`:

| Field | Type | Meaning |
|---|---|---|
| `candidate_id` | string | Sequential, `C-001`, `C-002`, … Stable and orderable. Unique. |
| `target_structure` | string | What φ maps *into* — an existing Mathlib structure (group, lattice, category, module) or a novel self-referential one. |
| `domain` | string | The benchmark declaration (or subset) this candidate is tested against. Joins to the coverage map. |
| `phi` | string | The proposed map, expressed as a real Lean definition — *not* a claim, and *not* IR-encoded. See `AXIOM_DISCOVERY.md` §"Two jobs, two substrates". |
| `provenance` | string | How it was proposed (search heuristic, seed, or model prompt). Logged so we can later see which proposal strategies actually pay off. |
| `gates` | object | `{"1": "pass", "2": "fail", …}`. Gates are recorded independently because the pipeline is ordered and admission-controlled: a candidate that fails gate 2 never reaches gate 3, and the ledger should show that rather than collapse to one pass/fail. |
| `compression` | object or null | Proof-term size or IR node count before/after. **Only valid when gate 3 passed.** |
| `reusable` | bool | Promoted past the breadth check. **Only valid when gate 5 passed.** |
| `failure_mode` | string or null | Fixed enum naming the mode of the **first failed gate** — `not_homomorphism` (1), `degenerate_collapse` (2), `target_too_weak` (3), `no_replication` (5). **Required on failure, null otherwise.** Gate 4 is non-failing and so has no mode. |
| `note` | string | Free text. |
| `status` | string (derived) | `failed_gate_N`, `passed_gate_N`, or `proposed`. Written for convenience; recomputed on read. |

Gate numbers (`AXIOM_DISCOVERY.md` §Validation pipeline): **1** homomorphism,
**2** faithfulness, **3** transfer, **4** compression accounting, **5** breadth.
Gates 1-3 and 5 are admission control and each carries a `failure_mode`; gate 4 is
bookkeeping and is **declared non-failing** (issue #32) — `gate 4 = fail` is
rejected by the schema.

## Rules enforced on append, not merely documented

`AXIOM_DISCOVERY.md` states rules that a naive ledger would let you violate
silently. All are **enforced in code** and a violating record is **rejected with a
nonzero exit rather than written**:

1. **Compression requires gate 3.** Only a candidate that survived the transfer
   test may carry a compression number. Recording it earlier presents bookkeeping
   as evidence — the exact failure the doc's non-goals warn against.
2. **`reusable` requires gate 5.** A one-off hit is logged but is not validated
   infrastructure until it replicates across a second, unrelated sub-domain.
3. **`failure_mode` is required on failure and fixed** (issue #32). It names the
   first failed gate's mode, must be one of the four enum values, and is rejected
   if absent on failure, present without a failure, or mismatched to the failed
   gate. Free text is refused so failures stay groupable across candidates.
4. **Gate 4 is non-failing.** `gate 4 = fail` is rejected: compression accounting
   is bookkeeping on a result that already exists, so it has no failure mode.

Plus one structural check: **the pipeline is ordered** — a candidate cannot pass a
later gate while an earlier one failed.

The tests for these rules are themselves mutation-tested
(`test_mutation_guard.py`): each rule is disabled in turn and the suite must detect
it. A check that cannot fail is not a check.

## Usage

### The five-gate harness (`harness.py`)

A candidate is a **spec** (JSON, one per candidate, in `specs/`): a prelude plus one
Lean obligation per gate. The harness elaborates each obligation with
`lake env lean` under `warningAsError`, so a `sorry` fails rather than passes.

```bash
python3 axiom-rewrite/harness.py list                 # available specs
python3 axiom-rewrite/harness.py run control_valid.json

# A candidate batch (#30): one command over a directory or glob, recording each.
python3 axiom-rewrite/harness.py batch axiom-rewrite/specs \
    --record axiom-rewrite/candidates.jsonl

# Or one spec, recording it:
python3 axiom-rewrite/harness.py run control_valid.json --record axiom-rewrite/candidates.jsonl
```

A spec that **fails a gate is data, not an error**: `batch` records it and keeps
going (exit 0). Only a usage problem — no specs found, a malformed spec, an
unrecordable row — exits 2. `run` exits 1 when its own spec fails a gate.

### The ledger CLI (`candidates.py`)

```bash
# Record a candidate that got through the transfer gate.
python3 axiom-rewrite/candidates.py add \
  --target-structure Group --domain "parity_notin_AC0" \
  --phi "def phi := ..." --provenance "homomorphic-first heuristic" \
  --gate 1=pass --gate 2=pass --gate 3=pass \
  --compression '{"nodes_before":10,"nodes_after":7}'

# Record a candidate that died at the homomorphism obligation.
python3 axiom-rewrite/candidates.py add \
  --target-structure Lattice --domain "monotone_razborov" \
  --phi "def phi := ..." --provenance "recursive bias, seed 7" \
  --gate 1=fail

python3 axiom-rewrite/candidates.py list            # all candidates
python3 axiom-rewrite/candidates.py list --json
python3 axiom-rewrite/candidates.py stats           # counts + reusable total

# Coverage: pass the full benchmark list so UNATTEMPTED declarations show up.
python3 axiom-rewrite/candidates.py coverage --domains benchmark_domains.txt
```

`--domains <file>` takes one benchmark declaration per line. Declarations absent
from the ledger are reported with **zero attempts** and sorted first — that is the
whole point of the map: it is what tells proposal where to aim instead of
re-testing easy wins.

### Example coverage output

```
attempts  g3  g5 failed  domain
       0   0   0      0  a_declaration_never_tried
       2   1   0      1  decl_a
       1   0   0      1  decl_b
```

## Tests

```bash
python3 axiom-rewrite/test_candidates.py          # 16 tests
python3 axiom-rewrite/test_mutation_guard.py      # proves the above can fail
```

Both run in CI. The guard mutates the real source and restores it in a `finally`,
so a crash cannot leave the working tree dirty.

## Known limits

- **No concurrency control.** Two agents appending simultaneously could interleave.
  Fine for the current single-writer usage; a file lock would be needed for parallel
  proposal. Not built, because nothing writes here concurrently yet.
- **`domain` is a free string.** Nothing validates it against the real benchmark
  corpus, so a typo'd declaration silently creates a phantom coverage row. Worth
  tightening once the benchmark list is pinned (issue #26).
- **No schema version field.** If the record shape changes, old records are read
  as-is. Acceptable while the ledger is small; add a version tag before it matters.
