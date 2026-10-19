#!/usr/bin/env python3
"""Mutation guard for phase-2 candidate dedup (#97).

Disables each part of the dedup, one at a time, and asserts the tests DETECT it.
Same convention as `test_structural_similarity_guard.py` and the other guards in
this repo: a check that cannot fail is not a check.

Run: python3 python/test_structural_similarity_dedup_guard.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tooling"))
from mutation_guard_lib import guarded_source, run_python  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "python" / "structural_similarity_dedup.py"
TEST = REPO / "python" / "test_structural_similarity_dedup.py"

MUTATIONS = [
    ("fingerprint replaced by candidate_id (duplicates never collapse)",
     '        key = s.fingerprint().key()',
     '        key = s.candidate_id'),
    ("duplicate threshold disabled (every group reported as distinct)",
     '    return sorted((sorted(ids) for ids in groups.values() if len(ids) > 1),',
     '    return sorted((sorted(ids) for ids in groups.values() if False),'),
    ("phi_graph requirement disabled (elaborated term no longer needed)",
     '    if not raw.get("phi_graph"):',
     '    if False:'),
    ("candidate-record validation disabled (any JSON accepted)",
     '    if missing:',
     '    if False:'),
]


def main() -> int:
    rows = []
    with guarded_source(SRC) as original:
        for name, old, new in MUTATIONS:
            if old not in original:
                print(f"  [MISS] {name}: anchor not found")
                rows.append((name, "ANCHOR-MISSING"))
                continue
            SRC.write_text(original.replace(old, new, 1))
            r = run_python([str(TEST)], capture_output=True,
                           text=True, cwd=str(REPO), timeout=600)
            detected = r.returncode != 0
            n = r.stdout.count("FAIL:") + r.stdout.count("ERROR:")
            status = "DETECTED" if detected else "GAP"
            print(f"  [{status:<10}] {name} (exit={r.returncode}, failures={n})")
            rows.append((name, status))

    control = run_python([str(TEST)], capture_output=True,
                         text=True, cwd=str(REPO)).returncode == 0
    print(f"\n  [{'PASS' if control else 'FAIL'}] control: unmutated tests pass")

    gaps = [n for n, s in rows if s in ("GAP", "ANCHOR-MISSING")]
    print()
    if gaps or not control:
        print(f"MUTATION GUARD FAILED: {len(gaps)} gap(s); control_ok={control}")
        for g in gaps:
            print(f"  - {g}")
        return 1
    print(f"MUTATION GUARD OK: {len(rows)}/{len(rows)} detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
