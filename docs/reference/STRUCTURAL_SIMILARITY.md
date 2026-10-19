# Structural similarity over IR graphs (`#28`, phase 1)

`Maith/GraphEquivalence.lean` is exact **equality** for testing. This is
**similarity** for candidate discovery: canonical structural fingerprints over IR
graphs, so graphs that are the same shape under different names can be found, plus
a graded score for ranking.

## What "similar" means (the decision this rests on)

`AXIOM_DISCOVERY.md` needs a search mechanism over candidate target structures.
That requires deciding what "match" means. Three candidates:

| Notion | Status |
|---|---|
| Exact identity | trivial, and already `GraphEquivalence.lean`'s job |
| **Alpha-equivalence modulo naming/ordering** | **decidable — implemented here** |
| Semantic similarity | needs human judgement; no ground truth exists yet |

This module implements the second, plus a graded score for ranking (the issue asks
for "ranked proposals", not only a boolean). **No semantic-similarity claim is made
anywhere** — per `AXIOM_DISCOVERY.md`'s filter-not-generator constraint, this ranks
and prunes; it never asserts that two graphs mean the same thing.

## The fingerprint is invariant to (presentation)

- the declaration name
- **bound-scope strings and positional indices** — `FVAR_0` in one graph has no
  relation to `FVAR_2` in another; the index is local per graph (`GLOSSARY.md`)
- entity / relation / operation **ordering**
- **`polarity`** — dropped by C1 in v2 and carrying no signal (99.8% `neut`)

## ...and sensitive to (content)

- row kinds and counts (`E` / `A` / `R` / `O`)
- **relation direction** (`R src tgt op` is ordered; swapping src/tgt is a change)
- relation operator identity (`eq`, `lt`, …)
- attribute keys and non-reference values (e.g. `typeclass Ring`)
- **operation identity** (`op:<shortName>`) and **operation arity**
- **free-variable names** (`Eq`, `HMul.hMul`) — `ENCODER_FORMAT.md` calls these
  "semantically stable… real vocab", so they are content, not presentation

> **The boundary is deliberate and pinned by a test.** Abstracting `var` names away
> would make the fingerprint blind to the main thing distinguishing otherwise
> identical graphs. `test_free_variable_name_change_must_not_match` exists so a
> future reader does not "fix" that into a regression.

## Cost function

```
sim(a, b) = 0.7 * weighted_jaccard(a.facts, b.facts) + 0.3 * set_jaccard(a.ops, b.ops)
```

- **facts term (0.7)**: weighted Jaccard over the structural-fact multisets —
  `Σ min(counts) / Σ max(counts)`. Multiset rather than set, so arity/count
  differences degrade similarity continuously instead of falling off a cliff.
- **op term (0.3)**: Jaccard over operation identities. Separated out because op
  identity is the axis module-mode bucketing destroys, so a lossy corpus shows up
  as *suspiciously high* similarity among unlike graphs rather than as an invisible
  error.
- Identical fingerprints score exactly **1.0**; the function is symmetric, total
  (never raises), and bounded in [0, 1].

It is a **heuristic for ranking**, never a claim about semantic relevance.

## Extraction mode is load-bearing (`--per-operator`)

In the default `module` mode every generic op collapses to one of ~10 `GEN_*`
buckets, so structural search matches *shape* but not *which operation* — two
graphs differing only in operator identity look identical. This module therefore
**errors** on a module-bucketed corpus (`assert_per_operator_corpus`) rather than
warning, because a silent quality loss is the failure this issue exists to prevent.

How much it matters, measured on two unrelated real graphs:

| Mode | Similarity |
|---|---|
| `--per-operator` | **0.18** |
| module-bucketed (ops collapsed) | **0.54** |

Nearly 3× inflation, from losing operator identity alone.

## Usage

```bash
# Corpus/corpus*.jsonl is gitignored — build it first (the per-operator mode):
lake env ./.lake/build/bin/buildCorpus --per-operator

# The default already points at the per-operator corpus (#35 encodes the mode in
# the filename), so --corpus is optional here:
python3 python/structural_similarity.py --query CancelMonoid --top 10
python3 python/structural_similarity.py --pairs --top 20
```

## Results on the current corpus (4,029 graphs)

| Measure | Value |
|---|---|
| Graphs indexed | 4,029 |
| Distinct fingerprints | 3,167 |
| Fingerprints shared by >1 graph | 539 |
| Graphs in a shared-fingerprint group | 1,401 |

Largest groups include `CancelMonoid` / `CommMonoid` / `SubNegMonoid` (51×) and
several `_private…match_1_1` families — i.e. the abstraction finds real structural
families, not noise.

## Known limits

- **No ground truth for semantic similarity.** Structural identity is decidable and
  tested; "these two graphs mean related things" is not claimed and is not tested.
  Any future semantic notion needs its own labelled data.
- **Ledger integration not exercised.** The issue's framing mentions "consuming
  candidate specs from the ledger", but the ledger has 0 candidates, so that path
  cannot be tested. This is phase-1 scope: similarity over corpus graphs.
- **Phase 2 (candidate dedup) is synthetic-fixture only.** `python/structural_similarity_dedup.py`
  (#97) groups candidate φ specs by the phase-1 fingerprint of their elaborated
  term, using fixtures in the `axiom-rewrite/candidates.py` record shape. The
  real-candidate path stays blocked: it needs φ to exist as elaborated Lean terms
  (#29) and the second corpus's input format defined.
- **O(n²) for the `--pairs` sweep.** Fine at 4k graphs (the sweep is what produced
  the table above); an index would be needed at 100k+.
- **`_operation_identity` handles several serialization shapes** (str / dict with
  `name`/`op`/`generic`/`tag`). Verified against the real per-operator corpus, but a
  new shape would silently fall through to `str(op)`.

## Tests

```bash
python3 python/test_structural_similarity.py        # 19 tests
python3 python/test_structural_similarity_guard.py  # 9/9 mutations detected

# phase 2 (candidate dedup over elaborated φ terms, #97)
python3 python/structural_similarity_dedup.py --fixtures axiom-rewrite/fixtures/dedup
python3 python/test_structural_similarity_dedup.py         # 9 tests
python3 python/test_structural_similarity_dedup_guard.py   # 4/4 mutations detected
```

The guard disables each invariance in turn and asserts the tests catch it. It found
two genuine holes in the first fixture set — **relation direction** and **operation
arity** were unprotected — which is why those now have isolating fixtures.