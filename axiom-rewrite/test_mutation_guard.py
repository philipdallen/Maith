#!/usr/bin/env python3
"""Mutation guard for the candidate-ledger validation (issue #27).

A test that passes on a broken validator is not a test. This disables each
validation rule in `candidates.py` one at a time, asserts the test suite DETECTS
it, and restores the file. If a fixture is ever weakened, this fails in CI instead
of silently regressing.

The mutation is applied to the real source; `guarded_source` restores it and
purges the bytecode cache on EVERY exit path (normal, exception, timeout), so a
crash cannot leave a stale mutated `.pyc` for a later process to load -- the
hazard that once truncated the ledger (DEC-048, issue #36).

Run: python3 axiom-rewrite/test_mutation_guard.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tooling"))
from mutation_guard_lib import guarded_source, run_python  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SRC = HERE / "candidates.py"
TEST = HERE / "test_candidates.py"

MUTATIONS = [
    ("compression gate-3 rule disabled",
     'if self.compression is not None and self.gates.get(3) != "pass":',
     'if False:'),
    ("reusable gate-5 rule disabled",
     'if self.reusable and self.gates.get(5) != "pass":',
     'if False:'),
    ("ordered-pipeline check disabled",
     'if earlier_fails:',
     'if False:'),
    ("invalid gate outcome accepted",
     'if outcome not in VALID_OUTCOMES:',
     'if False:'),
    ("duplicate-id check disabled",
     'if any(c.candidate_id == cand.candidate_id for c in existing):',
     'if False:'),
    ("required-field check disabled",
     'if not getattr(self, req):',
     'if False:'),
    ("failure_mode required/matched check disabled",
     'elif self.failure_mode != expected:',
     'elif False:'),
    ("failure_mode forbidden-without-failure check disabled",
     'if self.failure_mode is not None:',
     'if False:'),
    ("gate-4 non-failing rule disabled",
     'if self.gates.get(4) == "fail":',
     'if False:'),
    ("append-only broken (file reopened for write)",
     'with path.open("a", encoding="utf-8") as f:',
     'with path.open("w", encoding="utf-8") as f:'),
]


def main() -> int:
    results = []
    with guarded_source(SRC) as original:
        for name, old, new in MUTATIONS:
            if old not in original:
                print(f"  [MISS] {name}: mutation anchor not found")
                results.append((name, False))
                continue
            SRC.write_text(original.replace(old, new, 1))
            r = run_python([str(TEST)], capture_output=True, text=True,
                           cwd=str(REPO))
            detected = r.returncode != 0
            n = r.stdout.count("FAIL:") + r.stdout.count("ERROR:")
            print(f"  [{'DETECTED' if detected else 'MISSED'}] {name} "
                  f"(exit={r.returncode}, failures={n})")
            results.append((name, detected))

    missed = [n for n, ok in results if not ok]
    print()
    if missed:
        print(f"MUTATION GUARD FAILED: {len(missed)} mutation(s) not detected:")
        for m in missed:
            print(f"  - {m}")
        print("The ledger validation tests are vacuous for these rules.")
        return 1
    print(f"MUTATION GUARD OK: {len(results)}/{len(results)} mutations detected "
          f"-- validation fixtures are not vacuous.")
    return 0


if __name__ == "__main__":
    sys.exit(main())