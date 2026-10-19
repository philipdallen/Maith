#!/usr/bin/env python3
"""Candidate dedup over elaborated phi terms -- phase 2 of the structural
similarity search (issue #97).

Phase 1 (`python/structural_similarity.py`) fingerprints IR graphs extracted from
*Mathlib declarations*, so a graph under a different name still matches. Phase 2
points the same machinery at each candidate's *elaborated phi definition*: two
proposals whose `phi` source text differs but whose elaborated term is structurally
the same are duplicates, which a ledger text search cannot see
(`AXIOM_DISCOVERY.md` section "Search-loop refinements").

## Why synthetic fixtures

Elaborating a `phi` definition needs a Lean toolchain. The sandbox has none, so the
issue scopes this to the pattern the #29 starter established: **synthetic fixtures
always run; real data is skipped when absent.** A fixture is a candidate record in
the `axiom-rewrite/candidates.py` shape (same required fields, validated through
that module's `Candidate`) plus `phi_graph` -- the IR graph the elaborator *would*
emit for that `phi`. Real elaborated terms would be read through the same record
shape; nothing else changes.

Two fixtures whose `phi_graph` fingerprints are equal are duplicates, however much
their `phi` text or their positional indices differ. That is the whole check.

Usage:
    python3 python/structural_similarity_dedup.py --fixtures axiom-rewrite/fixtures/dedup
    python3 python/structural_similarity_dedup.py --fixtures <dir> --json

Exit codes: 0 when the dedup ran (duplicates are data, not an error); 2 on a usage
or fixture error (missing path, unreadable or invalid record, absent `phi_graph`).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "python"))
sys.path.insert(0, str(REPO / "axiom-rewrite"))

import structural_similarity as ss  # noqa: E402
import candidates as cand_mod  # noqa: E402

# The candidate-record fields `axiom-rewrite/candidates.py` requires. A dedup
# fixture must carry all of them, so a fixture is a genuine candidate record and
# not a bespoke format.
REQUIRED_FIELDS = ("candidate_id", "target_structure", "domain", "phi", "provenance")


class FixtureError(Exception):
    """A fixture that cannot be loaded (as opposed to a usage error)."""


@dataclass(frozen=True)
class CandidatePhi:
    """A candidate record plus the IR graph of its elaborated phi term."""

    record: "cand_mod.Candidate"
    phi_graph: dict

    @property
    def candidate_id(self) -> str:
        return self.record.candidate_id

    @property
    def phi(self) -> str:
        return self.record.phi

    def fingerprint(self) -> "ss.Fingerprint":
        return ss.fingerprint(self.phi_graph)


def load_spec(path: Path) -> CandidatePhi:
    """Load one fixture: a candidate record in the candidates.py shape + `phi_graph`."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise FixtureError(f"{path}: not valid JSON: {e}") from e

    missing = [f for f in REQUIRED_FIELDS if not raw.get(f)]
    if missing:
        raise FixtureError(
            f"{path}: not a candidate record (missing {missing}); fixtures reuse "
            f"the `axiom-rewrite/candidates.py` shape"
        )
    if not raw.get("phi_graph"):
        raise FixtureError(
            f"{path}: no `phi_graph` -- phase-2 dedup needs the elaborated phi term"
        )

    fields = {k: raw[k] for k in REQUIRED_FIELDS}
    fields["gates"] = raw.get("gates", {})
    record = cand_mod.Candidate.from_json(fields)
    record.validate()
    return CandidatePhi(record=record, phi_graph=raw["phi_graph"])


def collect_fixtures(target: Path) -> list[Path]:
    if target.is_dir():
        return sorted(target.glob("*.json"))
    return [target]


def dedup(specs: list[CandidatePhi]) -> dict:
    """Group candidate ids by the fingerprint of their elaborated phi term."""
    groups: dict = {}
    for s in specs:
        key = s.fingerprint().key()
        groups.setdefault(key, []).append(s.candidate_id)
    return groups


def duplicates(groups: dict) -> list[list[str]]:
    """Groups with two or more members: the same elaborated phi, different text."""
    return sorted((sorted(ids) for ids in groups.values() if len(ids) > 1),
                  key=lambda g: g[0])


def distinct(groups: dict) -> list[str]:
    """Singletons: candidates whose elaborated phi is unique."""
    return sorted(ids[0] for ids in groups.values() if len(ids) == 1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="phase-2 candidate dedup over elaborated phi terms (#97)")
    ap.add_argument("--fixtures", required=True, help="fixture directory or one JSON file")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    target = Path(args.fixtures)
    if not target.exists():
        print(f"ERROR: no such fixture path: {target}", file=sys.stderr)
        return 2
    try:
        specs = [load_spec(p) for p in collect_fixtures(target)]
    except FixtureError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if not specs:
        print(f"ERROR: no fixtures found in {target}", file=sys.stderr)
        return 2

    groups = dedup(specs)
    dups = duplicates(groups)
    dist = distinct(groups)

    if args.json:
        print(json.dumps({"n": len(specs), "duplicates": dups, "distinct": dist},
                         indent=2))
        return 0

    print(f"loaded {len(specs)} candidate phi specs")
    print(f"\nduplicate groups ({len(dups)}):")
    for g in dups:
        print(f"  {' = '.join(g)}")
    print(f"\ndistinct phi ({len(dist)}):")
    for cid in dist:
        print(f"  {cid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
