#!/usr/bin/env python3
"""Candidate ledger + coverage map for the axiom-discovery track (issue #27).

Two data structures, per `docs/experiments/AXIOM_DISCOVERY.md` §"Tracking
candidates and search space":

1. **Candidate ledger** (`candidates.jsonl`) — append-only, one record per
   candidate φ. Failed candidates are KEPT: the search history is itself data
   (which regions of the space are exhausted).

2. **Coverage map** — derived, not stored. Per benchmark declaration, how many
   candidate φ's have been tried and with what outcome. Used to bias proposal
   toward under-explored, high-proof-size declarations instead of re-testing the
   same easy wins.

The coverage map is *derived from the ledger* on every read rather than kept as a
second file. That is deliberate: a stored copy would be a second source of truth
that can drift, and the ledger is append-only so the derivation is cheap and
always consistent.

## Gate rules encoded here (not just documented)

`AXIOM_DISCOVERY.md` §"Validation pipeline" states two rules that a naive ledger
would let you violate silently, so they are **enforced on append**:

- **Only candidates surviving gate 3 get a compression number.** Compression is
  bookkeeping on a result that already exists; recording it for a candidate that
  failed the transfer test would present bookkeeping as evidence.
- **Only candidates surviving gate 5 may be marked `reusable`.** Gate 5 is the
  breadth check (a second, unrelated sub-domain); a one-off hit is logged but is
  not validated infrastructure.

A record whose `gates` contradict either rule is rejected with a nonzero exit
rather than written, so the violation cannot enter the ledger.

Usage:
    python3 axiom-rewrite/candidates.py add --target-structure ... --domain ... \\
        --phi ... --provenance ... [--gate 1=pass --gate 2=fail ...]
    python3 axiom-rewrite/candidates.py list [--status ...] [--json]
    python3 axiom-rewrite/candidates.py coverage [--json]
    python3 axiom-rewrite/candidates.py stats

Exit codes: 0 ok, 1 rejected/invalid record or read error, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER = REPO / "axiom-rewrite" / "candidates.jsonl"

VALID_GATES = (1, 2, 3, 4, 5)
VALID_OUTCOMES = ("pass", "fail", "skip")

# Gate names, for readable reporting (AXIOM_DISCOVERY.md §Validation pipeline).
GATE_NAMES = {
    1: "homomorphism",
    2: "faithfulness",
    3: "transfer",
    4: "compression",
    5: "breadth",
}

# Failure modes (issue #32): a *fixed* enum, not free text, so failures are
# groupable across candidates. Each value is keyed to the gate that produces it,
# and a record carries the mode of its FIRST failed gate (`failed_gate` is the
# min of failed gates — the pipeline is admission-controlled, so later failures
# are never reached). Gate 4 has no mode on purpose: compression accounting is
# bookkeeping on a result that already exists, so gate 4 is declared
# explicitly non-failing (see `validate`).
FAILURE_MODES = {
    1: "not_homomorphism",
    2: "degenerate_collapse",
    3: "target_too_weak",
    5: "no_replication",
}
VALID_FAILURE_MODES = tuple(FAILURE_MODES.values())


class LedgerError(Exception):
    """A record that cannot be accepted (as opposed to a usage error)."""


@dataclass
class Candidate:
    """One candidate φ.

    `gates` maps gate number (int) to outcome ("pass"/"fail"/"skip"). Gates are
    recorded independently because the pipeline is ordered: a candidate that
    fails gate 2 never reaches gate 3, and the ledger should show that rather
    than collapsing to a single pass/fail.
    """

    candidate_id: str
    target_structure: str
    domain: str
    phi: str
    provenance: str
    gates: dict[int, str] = field(default_factory=dict)
    compression: Optional[dict] = None
    reusable: bool = False
    note: str = ""
    failure_mode: Optional[str] = None

    # -- derived ------------------------------------------------------------
    @property
    def highest_gate_passed(self) -> int:
        """Highest gate reached with outcome `pass`, or 0 if none."""
        passed = [g for g, o in self.gates.items() if o == "pass"]
        return max(passed) if passed else 0

    @property
    def status(self) -> str:
        """Where the candidate died (or how far it got)."""
        if self.failed_gate is not None:
            return f"failed_gate_{self.failed_gate}"
        return f"passed_gate_{self.highest_gate_passed}" if self.highest_gate_passed else "proposed"

    @property
    def failed_gate(self) -> Optional[int]:
        """Lowest gate with outcome `fail`, or None."""
        failed = [g for g, o in self.gates.items() if o == "fail"]
        return min(failed) if failed else None

    @property
    def expected_failure_mode(self) -> Optional[str]:
        """The mode implied by the first failed gate, or None if nothing failed."""
        return FAILURE_MODES.get(self.failed_gate) if self.failed_gate else None

    # -- validation ---------------------------------------------------------
    def validate(self) -> None:
        """Enforce the gate rules. Raises LedgerError on violation."""
        if not self.candidate_id:
            raise LedgerError("candidate_id is required")
        for req in ("target_structure", "domain", "phi", "provenance"):
            if not getattr(self, req):
                raise LedgerError(f"{req} is required")

        for g, outcome in self.gates.items():
            if g not in VALID_GATES:
                raise LedgerError(f"unknown gate {g!r} (valid: {list(VALID_GATES)})")
            if outcome not in VALID_OUTCOMES:
                raise LedgerError(
                    f"gate {g}: outcome {outcome!r} not in {list(VALID_OUTCOMES)}"
                )

        # Rule 1: compression only for candidates that passed the transfer gate.
        if self.compression is not None and self.gates.get(3) != "pass":
            raise LedgerError(
                "compression recorded, but gate 3 (transfer) did not pass — "
                "compression is bookkeeping on an existing result and must never "
                "be recorded for a candidate that failed the transfer test "
                "(AXIOM_DISCOVERY.md §Validation pipeline)"
            )

        # Rule 2: `reusable` only past the breadth check.
        if self.reusable and self.gates.get(5) != "pass":
            raise LedgerError(
                "reusable=True, but gate 5 (breadth) did not pass — a one-off hit "
                "is logged but is not validated infrastructure "
                "(AXIOM_DISCOVERY.md §Validation pipeline)"
            )

        # Consistency: cannot pass a later gate while failing an earlier one.
        for g in sorted(self.gates):
            if self.gates[g] == "pass":
                earlier_fails = [k for k in sorted(self.gates)
                                 if k < g and self.gates[k] == "fail"]
                if earlier_fails:
                    raise LedgerError(
                        f"gate {g} passed while earlier gate(s) {earlier_fails} "
                        f"failed — the pipeline is ordered and admission-controlled"
                    )

        # Rule 3: gate 4 (compression accounting) is declared explicitly
        # non-failing. It is bookkeeping on a result that already exists, so it
        # has no failure mode and the schema must not permit `fail` for it
        # (issue #32 decision).
        if self.gates.get(4) == "fail":
            raise LedgerError(
                "gate 4 (compression) recorded as `fail`, but gate 4 is declared "
                "explicitly non-failing — compression accounting is bookkeeping on "
                "a result that already exists, so it carries no failure_mode "
                "(issue #32)"
            )

        # Rule 4: `failure_mode` is required whenever a gate failed, forbidden
        # otherwise, and must be the fixed mode of the FIRST failed gate. One
        # guard, because the mode is fully determined by the first failure: a
        # missing value, a free-text value, and a value naming the wrong gate are
        # all "not the expected mode" (issue #32).
        expected = self.expected_failure_mode
        if expected is None:
            if self.failure_mode is not None:
                raise LedgerError(
                    f"failure_mode {self.failure_mode!r} recorded, but no gate "
                    "failed — failure_mode is required only on failure (issue #32)"
                )
        elif self.failure_mode != expected:
            if self.failure_mode is None:
                raise LedgerError(
                    f"gate {self.failed_gate} failed but failure_mode is missing — "
                    f"it is required on failure and must be {expected!r} "
                    "(issue #32)"
                )
            raise LedgerError(
                f"failure_mode {self.failure_mode!r} does not match the first failed "
                f"gate {self.failed_gate} (expected {expected!r}) — the pipeline is "
                "admission-controlled, so the first failure is the meaningful one, "
                "and the enum is fixed so modes stay groupable (issue #32)"
            )

    def to_json(self) -> dict:
        d = asdict(self)
        # JSON object keys must be strings; keep gates as "1".."5" on disk.
        d["gates"] = {str(k): v for k, v in sorted(self.gates.items())}
        d["status"] = self.status
        return d

    @classmethod
    def from_json(cls, d: dict) -> "Candidate":
        return cls(
            candidate_id=d["candidate_id"],
            target_structure=d["target_structure"],
            domain=d["domain"],
            phi=d["phi"],
            provenance=d["provenance"],
            gates={int(k): v for k, v in d.get("gates", {}).items()},
            compression=d.get("compression"),
            reusable=bool(d.get("reusable", False)),
            note=d.get("note", ""),
            failure_mode=d.get("failure_mode"),
        )


# ---------------------------------------------------------------------------
# Ledger I/O
# ---------------------------------------------------------------------------

def read_ledger(path: Path) -> list[Candidate]:
    if not path.exists():
        return []
    out: list[Candidate] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(Candidate.from_json(json.loads(line)))
        except (json.JSONDecodeError, KeyError) as e:
            raise LedgerError(f"{path}:{lineno}: unreadable record: {e}") from e
    return out


def next_candidate_id(existing: list[Candidate]) -> str:
    """Sequential id, `C-001`, `C-002`, ... — stable and orderable."""
    n = 0
    for c in existing:
        if c.candidate_id.startswith("C-"):
            try:
                n = max(n, int(c.candidate_id[2:]))
            except ValueError:
                pass
    return f"C-{n + 1:03d}"


def append_candidate(path: Path, cand: Candidate) -> None:
    """Append one record. Creates the dir/file if absent. Never rewrites."""
    cand.validate()
    existing = read_ledger(path)
    if any(c.candidate_id == cand.candidate_id for c in existing):
        raise LedgerError(f"candidate_id {cand.candidate_id!r} already present "
                          f"(the ledger is append-only; ids must be unique)")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(cand.to_json(), sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# Coverage map (derived)
# ---------------------------------------------------------------------------

def coverage(ledger_path: Path, domains: Optional[list[str]] = None) -> list[dict]:
    """Per benchmark declaration, how many candidates were tried and how they fared.

    A candidate's `domain` field names the benchmark declaration (or subset) it
    was tested against. When `domains` is supplied (the full benchmark list), any
    declaration with no attempts appears with zeros — that is the whole point of
    the map: un-attempted declarations are the ones to bias proposal toward.
    """
    cands = read_ledger(ledger_path)
    by_domain: dict[str, dict] = {}

    def bucket(d: str) -> dict:
        if d not in by_domain:
            by_domain[d] = {"domain": d, "attempts": 0, "passed_gate3": 0,
                            "passed_gate5": 0, "failed": 0, "candidates": []}
        return by_domain[d]

    for c in cands:
        b = bucket(c.domain)
        b["attempts"] += 1
        b["candidates"].append(c.candidate_id)
        if c.gates.get(3) == "pass":
            b["passed_gate3"] += 1
        if c.gates.get(5) == "pass":
            b["passed_gate5"] += 1
        if c.failed_gate is not None:
            b["failed"] += 1

    for d in domains or []:
        bucket(d)

    rows = sorted(by_domain.values(), key=lambda r: (r["attempts"], r["domain"]))
    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_gate(spec: str) -> tuple[int, str]:
    if "=" not in spec:
        raise argparse.ArgumentTypeError(f"--gate expects N=outcome, got {spec!r}")
    g, outcome = spec.split("=", 1)
    try:
        return int(g), outcome
    except ValueError:
        raise argparse.ArgumentTypeError(f"--gate number must be an int, got {g!r}")


def cmd_add(args) -> int:
    path = Path(args.ledger)
    existing = read_ledger(path)
    gates = dict(args.gate or [])
    if args.reusable and 5 not in gates:
        # Explicit and early: better than a confusing validation error later.
        print("error: --reusable requires --gate 5=pass", file=sys.stderr)
        return 1
    # On failure the mode is determined by the first failed gate, so derive it
    # rather than making the caller repeat a fact the record already encodes.
    # An explicit --failure-mode still wins, and a mismatch is rejected below.
    failure_mode = args.failure_mode
    if failure_mode is None:
        failed = [g for g, o in gates.items() if o == "fail"]
        if failed:
            failure_mode = FAILURE_MODES.get(min(failed))
    cand = Candidate(
        candidate_id=args.id or next_candidate_id(existing),
        target_structure=args.target_structure,
        domain=args.domain,
        phi=args.phi,
        provenance=args.provenance,
        gates=gates,
        compression=json.loads(args.compression) if args.compression else None,
        reusable=bool(args.reusable),
        note=args.note or "",
        failure_mode=failure_mode,
    )
    try:
        append_candidate(path, cand)
    except LedgerError as e:
        print(f"REJECTED: {e}", file=sys.stderr)
        return 1
    print(f"appended {cand.candidate_id} (status: {cand.status})")
    return 0


def cmd_list(args) -> int:
    cands = read_ledger(Path(args.ledger))
    if args.status:
        cands = [c for c in cands if c.status == args.status]
    if args.json:
        print(json.dumps([c.to_json() for c in cands], indent=2))
        return 0
    if not cands:
        print("(ledger empty)")
        return 0
    for c in cands:
        gates = ", ".join(f"g{g}:{o}" for g, o in sorted(c.gates.items())) or "(no gates run)"
        print(f"{c.candidate_id}  [{c.status}]  {c.target_structure}")
        print(f"    domain: {c.domain}")
        print(f"    gates:  {gates}")
        if c.failure_mode:
            print(f"    failure_mode: {c.failure_mode} (gate {c.failed_gate})")
        if c.compression is not None:
            print(f"    compression: {c.compression}")
        if c.reusable:
            print("    REUSABLE")
    return 0


def cmd_coverage(args) -> int:
    domains = None
    if args.domains:
        domains = [d.strip() for d in Path(args.domains).read_text(
            encoding="utf-8").splitlines() if d.strip()]
    rows = coverage(Path(args.ledger), domains)
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("(no domains — pass --domains <file> with one declaration per line, "
              "or add candidates)")
        return 0
    print(f"{'attempts':>8} {'g3':>3} {'g5':>3} {'failed':>6}  domain")
    for r in rows:
        print(f"{r['attempts']:>8} {r['passed_gate3']:>3} {r['passed_gate5']:>3} "
              f"{r['failed']:>6}  {r['domain']}")
    unattempted = [r["domain"] for r in rows if r["attempts"] == 0]
    if unattempted:
        print(f"\n{len(unattempted)} declaration(s) with no attempts "
              f"(bias proposal here):")
        for d in unattempted[:20]:
            print(f"  {d}")
        if len(unattempted) > 20:
            print(f"  ... and {len(unattempted) - 20} more")
    return 0


def cmd_stats(args) -> int:
    cands = read_ledger(Path(args.ledger))
    print(f"candidates: {len(cands)}")
    by_status: dict[str, int] = {}
    for c in cands:
        by_status[c.status] = by_status.get(c.status, 0) + 1
    for s in sorted(by_status):
        print(f"  {s}: {by_status[s]}")
    print(f"reusable: {sum(1 for c in cands if c.reusable)}"
          f" (gate 5 survivors — promoted structures)")
    print(f"with compression recorded: {sum(1 for c in cands if c.compression is not None)}")
    by_mode: dict[str, int] = {}
    for c in cands:
        if c.failure_mode:
            by_mode[c.failure_mode] = by_mode.get(c.failure_mode, 0) + 1
    if by_mode:
        print("failure modes (groupable — the point of the enum):")
        for m in sorted(by_mode, key=lambda k: (-by_mode[k], k)):
            print(f"  {m}: {by_mode[m]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="axiom-discovery candidate ledger")
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER),
                    help=f"ledger path (default: {DEFAULT_LEDGER})")
    sub = ap.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="append a candidate")
    p_add.add_argument("--id", default=None, help="candidate id (default: auto C-NNN)")
    p_add.add_argument("--target-structure", required=True)
    p_add.add_argument("--domain", required=True,
                       help="benchmark declaration/subset this candidate is tested against")
    p_add.add_argument("--phi", required=True, help="the proposed map, as a Lean definition")
    p_add.add_argument("--provenance", required=True,
                       help="how it was proposed (heuristic, seed, model prompt)")
    p_add.add_argument("--gate", action="append", type=_parse_gate, default=[],
                       metavar="N=pass|fail|skip",
                       help="repeatable, e.g. --gate 1=pass --gate 2=fail")
    p_add.add_argument("--compression", default=None,
                       help="JSON, e.g. '{\"nodes_before\":10,\"nodes_after\":7}' "
                            "(only valid when gate 3 passed)")
    p_add.add_argument("--failure-mode", default=None, choices=VALID_FAILURE_MODES,
                       help="fixed failure enum; required on failure (derived from "
                            "the first failed gate when omitted)")
    p_add.add_argument("--reusable", action="store_true",
                       help="promote to reusable (requires --gate 5=pass)")
    p_add.add_argument("--note", default="")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="list candidates")
    p_list.add_argument("--status", default=None, help="filter by status")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_cov = sub.add_parser("coverage", help="coverage map over the benchmark domain")
    p_cov.add_argument("--domains", default=None,
                       help="file with one benchmark declaration per line "
                            "(unattempted ones are shown — that is the point)")
    p_cov.add_argument("--json", action="store_true")
    p_cov.set_defaults(func=cmd_coverage)

    p_stats = sub.add_parser("stats", help="summary counts")
    p_stats.set_defaults(func=cmd_stats)

    args = ap.parse_args()
    try:
        return args.func(args)
    except LedgerError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())