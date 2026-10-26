#!/usr/bin/env python3
"""Circuits inventory pass (BENCHMARK_CORPUS_PLAN.md Part 1, step 1).

Enumerates every declaration already formalized in PleaNP's circuit-complexity
modules and renders a plain-English list grouped by sub-area. This is the
mechanical extraction step the corpus plan calls for; correctness is never
"does this Lean look right" but "does the artifact match the source tree" --
which is what ``--check`` decides.

Usage::

    python3 tooling/circuits_inventory.py                 # write the artifact
    python3 tooling/circuits_inventory.py --check         # verify, exit 1 on drift

The PleaNP checkout defaults to ``../PleaNP`` (sibling of this repo) and can be
overridden with ``--pleanp`` or ``$PLEANP_DIR``.

Exit codes: 0 = ok, 1 = drift (``--check`` only), 2 = source tree not found.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import pathlib
import re
import subprocess
import sys

MODULES = [
    "Basic",
    "AC0",
    "Monotone",
    "MonotoneApprox",
    "MustRefute",
    "Restriction",
    "Switching",
]

# Sub-area labels, keyed by module. These are sub-areas *within* circuit
# complexity -- the scope the maintainer narrowed #31 to on 2026-10-25.
SUBAREA = {
    "Basic": "Circuit basics (gate model, size/depth, P/poly shape, natural properties)",
    "AC0": "AC0 lower bounds (parity not-in AC0; the depth ladder)",
    "Monotone": "Monotone circuits (Razborov direction)",
    "MonotoneApprox": "Monotone approximation reducer (Razborov counting)",
    "MustRefute": "Validation / must-refute suite (non-vacuity)",
    "Restriction": "Random restrictions (Hastad switching-lemma substrate)",
    "Switching": "Switching lemma / decision-tree depth (measure + statement)",
}

DECL = re.compile(
    r"^(theorem|lemma|def|abbrev|structure|inductive|instance)\s+([A-Za-z_][\w.']*)"
)
DOC_OPEN = re.compile(r"^\s*(/--|/-!)")
SORRY = re.compile(r"\b(sorry|admit)\b")
AXIOM = re.compile(r"^\s*axiom\b")
ARTIFACT_MARKER = "<!-- circuits-inventory:data"

# `def NAME : Prop` with no binders is a frozen statement target, not a
# predicate definition. The two switching-lemma `Prop`s take arguments but are
# likewise stated-not-proven (the module says so), so they are listed by name.
STATEMENT_TARGETS = {"SwitchingLemmaStatement", "SwitchingLemmaExists"}
NO_BINDER_PROP = re.compile(r"^def\s+([A-Za-z_][\w.']*)\s*:\s*Prop\b")


def strip_comments(lines: list[str]) -> list[str]:
    """Return the lines with `/- ... -/` and `--` comment text removed."""
    out, depth = [], 0
    for line in lines:
        s, i = "", 0
        while i < len(line):
            if depth == 0 and line.startswith("--", i):
                break
            if depth == 0 and line.startswith("/-", i):
                depth, i = depth + 1, i + 2
                continue
            if depth > 0:
                if line.startswith("-/", i):
                    depth, i = depth - 1, i + 2
                    continue
                i += 1
                continue
            s += line[i]
            i += 1
        out.append(s)
    return out


def first_sentence(text: str, limit: int = 200) -> str:
    text = " ".join(text.split())
    if not text:
        return ""
    for sep in (". ", " - ", " -- "):
        idx = text.find(sep)
        if 0 < idx < limit:
            text = text[: idx + 1]
            break
    return text[:limit].strip()


def doc_above(lines: list[str], i: int) -> str:
    """Return the doc comment immediately above line ``i`` (0-based), if any."""
    j = i - 1
    while j >= 0 and lines[j].strip() == "":
        j -= 1
    if j < 0 or not lines[j].rstrip().endswith("-/"):
        return ""
    end = j
    while j >= 0 and not DOC_OPEN.match(lines[j]):
        j -= 1
    if j < 0:
        return ""
    block = lines[j : end + 1]
    # Drop the marker line and any leading '-' continuation markers.
    body = []
    for k, raw in enumerate(block):
        s = raw.strip()
        if k == 0:
            s = re.sub(r"^/\-{1,2}!?", "", s)
        s = re.sub(r"^-\s?", "", s)
        if s.endswith("-/"):
            s = s[: -len("-/")].strip()
        body.append(s)
    return first_sentence(" ".join(body))


def parse_module(path: pathlib.Path) -> dict:
    lines = path.read_text().splitlines()
    code = strip_comments(lines)
    decls = []
    for i, line in enumerate(code):
        m = DECL.match(line)
        if not m:
            continue
        kind, name = m.group(1), m.group(2)
        # A `def NAME : Prop` with no binders is a frozen statement target (a
        # stated-but-unproven claim), not a predicate definition. Predicates
        # like `IsPPoly`/`Largeness` take binders and are real definitions.
        prop_target = (kind == "def" and name in STATEMENT_TARGETS) or (
            kind == "def" and bool(NO_BINDER_PROP.match(line))
        )
        decls.append(
            {
                "kind": kind,
                "name": name,
                "line": i + 1,
                "doc": doc_above(lines, i),
                "prop_target": prop_target,
            }
        )
    return {
        "module": path.stem,
        "lines": len(lines),
        "decls": decls,
        "sorries": sum(1 for l in code if SORRY.search(l)),
        "axioms": sum(1 for l in code if AXIOM.match(l)),
    }


def git_rev(repo: pathlib.Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def collect(pleanp: pathlib.Path) -> dict:
    circ = pleanp / "lean" / "PleaNP" / "Circuits"
    if not circ.is_dir():
        print(f"error: no Circuits directory at {circ}", file=sys.stderr)
        sys.exit(2)
    mods = [parse_module(circ / f"{m}.lean") for m in MODULES]
    total = sum(len(m["decls"]) for m in mods)
    return {
        "revision": git_rev(pleanp),
        "modules": mods,
        "totals": {
            "modules": len(mods),
            "declarations": total,
            "theorems_and_lemmas": sum(
                1 for m in mods for d in m["decls"] if d["kind"] in ("theorem", "lemma")
            ),
            "definitions": sum(
                1
                for m in mods
                for d in m["decls"]
                if d["kind"] in ("def", "abbrev", "structure", "inductive")
            ),
            "unproved_prop_targets": sum(
                1 for m in mods for d in m["decls"] if d["prop_target"]
            ),
            "sorries": sum(m["sorries"] for m in mods),
            "axioms": sum(m["axioms"] for m in mods),
        },
    }


def render(data: dict) -> str:
    t = data["totals"]
    out = []
    out.append("# Circuits inventory (PleaNP.Circuits, plain English)")
    out.append("")
    out.append(
        "Generated by `tooling/circuits_inventory.py` "
        "(BENCHMARK_CORPUS_PLAN.md Part 1, step 1). "
        "Do not hand-edit; re-run the script."
    )
    out.append("")
    out.append(f"- **Source:** `philipdallen/PleaNP`, `lean/PleaNP/Circuits/`")
    out.append(f"- **Revision:** `{data['revision']}`")
    out.append(
        f"- **Totals:** {t['modules']} modules, {t['declarations']} declarations "
        f"({t['theorems_and_lemmas']} theorem/lemma, {t['definitions']} def/abbrev/structure/inductive), "
        f"{t['unproved_prop_targets']} unproved `Prop` targets, "
        f"{t['sorries']} sorry/admit, {t['axioms']} axiom"
    )
    out.append("")
    out.append(
        "> **Scope note.** All seven modules sit inside one field, circuit "
        "complexity. The sub-area labels below are sub-areas *within* that field. "
        "The maintainer narrowed issue #31 to circuit-complexity-only on "
        "2026-10-25, so this single-field breadth satisfies the plan's "
        "domain-breadth check within the narrowed scope."
    )
    out.append("")
    for m in data["modules"]:
        out.append(f"## {m['module']}.lean -- {SUBAREA[m['module']]}")
        out.append("")
        out.append(f"_{m['lines']} lines, {len(m['decls'])} declarations._")
        out.append("")
        for d in m["decls"]:
            tag = " *(unproved Prop target)*" if d["prop_target"] else ""
            doc = f" -- {d['doc']}" if d["doc"] else ""
            out.append(f"- `{d['name']}` ({d['kind']}){tag}{doc}")
        out.append("")
    payload = {
        "revision": data["revision"],
        "modules": {
            m["module"]: {
                "declarations": len(m["decls"]),
                "names": [d["name"] for d in m["decls"]],
            }
            for m in data["modules"]
        },
        "totals": t,
    }
    out.append(ARTIFACT_MARKER)
    out.append(json.dumps(payload, sort_keys=True))
    out.append("-->")
    out.append("")
    return "\n".join(out)


def load_embedded(path: pathlib.Path) -> dict | None:
    text = path.read_text()
    start = text.find(ARTIFACT_MARKER)
    if start < 0:
        return None
    start = text.find("\n", start) + 1
    end = text.find("-->", start)
    if end < 0:
        return None
    return json.loads(text[start:end].strip())


def check(data: dict, artifact: pathlib.Path) -> int:
    if not artifact.exists():
        print(f"FAIL: artifact missing: {artifact}", file=sys.stderr)
        return 1
    if load_embedded(artifact) is None:
        print(f"FAIL: no machine-readable block in {artifact}", file=sys.stderr)
        return 1
    fresh = render(data)
    current = artifact.read_text()
    if fresh == current:
        print(f"OK: inventory matches PleaNP.Circuits @ {data['revision']}")
        return 0
    # The whole file is compared, not just the embedded block, so a stale
    # plain-English list is caught too -- that list is the artifact a human
    # reviews in the corpus plan's step 2.
    print("FAIL: inventory is stale against the source tree", file=sys.stderr)
    for line in list(
        difflib.unified_diff(
            current.splitlines(), fresh.splitlines(), "artifact", "fresh", lineterm=""
        )
    )[:40]:
        print(f"  {line}", file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    default_pleanp = os.environ.get("PLEANP_DIR", str(pathlib.Path(__file__).resolve().parents[2] / "PleaNP"))
    ap.add_argument("--pleanp", default=default_pleanp, help="PleaNP checkout (default: ../PleaNP)")
    ap.add_argument("--out", default="docs/experiments/CIRCUITS_INVENTORY.md")
    ap.add_argument("--check", action="store_true", help="verify the artifact, do not write")
    args = ap.parse_args()

    data = collect(pathlib.Path(args.pleanp))
    artifact = pathlib.Path(args.out)
    if args.check:
        return check(data, artifact)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(render(data))
    print(f"wrote {artifact} ({data['totals']['declarations']} declarations @ {data['revision']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
