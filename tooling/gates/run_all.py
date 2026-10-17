#!/usr/bin/env python3
"""Run all Tier-1 integrity gates (mirrors .github/workflows/ci.yml).

Single entrypoint for the gate suite so it runs locally, in sandboxes, and
via the repo auditor's gate-health check. Mirrors the CI invocations; CI
remains the authority if they drift.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATES = ROOT / "tooling" / "gates"

COMMANDS = [
    [sys.executable, str(GATES / "hygiene_scan.py"),
     "--prove-stage", "Maith", "Tests", "Scripts"],
    [sys.executable, str(GATES / "vacuity_scan.py"),
     "Maith", "Tests", "Scripts"],
    [sys.executable, str(GATES / "binder_usage_scan.py"),
     "--allow-unreferenced", r"^(run(All|Env|Graph)?[A-Za-z]*|main)$",
     "Maith", "Tests", "Scripts"],
]


def main() -> int:
    failed = []
    for cmd in COMMANDS:
        label = Path(cmd[1]).name
        print(f"--- {label} ---", flush=True)
        r = subprocess.run(cmd, cwd=ROOT)
        print(f"{label}: exit {r.returncode}", flush=True)
        if r.returncode != 0:
            failed.append(label)
    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("all gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
