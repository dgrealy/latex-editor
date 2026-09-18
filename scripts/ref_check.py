#!/usr/bin/env python3
"""Cross-reference integrity: labels, references and citation keys.

Reports rather than fixes, so the caller decides what to do.  Everything here
is mechanical -- no judgement, no guessing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

#: The prefix each kind of label should carry, keyed by the environment or
#: sectioning command it labels.
PREFIXES = {
    "figure": "fig:", "subfigure": "fig:", "wrapfigure": "fig:",
    "table": "tab:", "longtable": "tab:",
    "equation": "eq:", "align": "eq:", "gather": "eq:", "multline": "eq:",
    "algorithm": "alg:", "algorithm2e": "alg:",
    "section": "sec:", "subsection": "sec:", "subsubsection": "sec:",
    "chapter": "ch:", "lstlisting": "lst:",
}

_LABEL = re.compile(r"\\label\s*\{([^}]*)\}")
_REF = re.compile(r"\\(?:page|auto|eq|name|v)?[Rr]ef(?:range)?\s*\*?\s*\{([^}]*)\}")
_CITE = re.compile(r"\\(?:no)?cite[a-zA-Z]*\s*\*?\s*(?:\[[^\]]*\]\s*)*\{([^}]*)\}")
_BIB_KEY = re.compile(r"^\s*@\s*\w+\s*\{\s*([^,\s]+)", re.MULTILINE)
_BEGIN = re.compile(r"\\begin\s*\{([^}]*)\}")
_SECTION = re.compile(r"\\(chapter|section|subsection|subsubsection)\s*\*?\s*\{")


def _tex_files(root: Path, skip: set[str]) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*.tex"))
        if not any(part in skip for part in path.relative_to(root).parts)
    ]


def _context_for(text: str, position: int) -> str | None:
    """The innermost environment or sectioning command a label sits in."""
    depth_stack: list[str] = []
    for match in re.finditer(r"\\(begin|end)\s*\{([^}]*)\}", text[:position]):
        if match.group(1) == "begin":
            depth_stack.append(match.group(2).rstrip("*"))
        elif depth_stack:
            depth_stack.pop()
    for name in reversed(depth_stack):
        if name in PREFIXES:
            return name
    sections = list(_SECTION.finditer(text[:position]))
    if sections and position - sections[-1].end() < 120:
        return sections[-1].group(1)
    return None


def scan(root: Path, bib: Path | None, skip: set[str] | None = None) -> dict:
    skip = skip or {".git", "build", "node_modules", ".latex-editor"}
    labels: dict[str, list[str]] = defaultdict(list)
    label_context: dict[str, str | None] = {}
    refs: dict[str, list[str]] = defaultdict(list)
    cites: dict[str, list[str]] = defaultdict(list)

    for path in _tex_files(root, skip):
        text = path.read_text(encoding="utf-8", errors="replace")
        where = path.relative_to(root).as_posix()
        for match in _LABEL.finditer(text):
            name = match.group(1).strip()
            line = text.count("\n", 0, match.start()) + 1
            labels[name].append(f"{where}:{line}")
            label_context.setdefault(name, _context_for(text, match.start()))
        for match in _REF.finditer(text):
            for name in match.group(1).split(","):
                if name.strip():
                    refs[name.strip()].append(where)
        for match in _CITE.finditer(text):
            for name in match.group(1).split(","):
                if name.strip():
                    cites[name.strip()].append(where)

    bib_keys: set[str] = set()
    if bib and bib.is_file():
        bib_keys = set(_BIB_KEY.findall(bib.read_text(encoding="utf-8", errors="replace")))

    wrong_prefix = []
    for name, context in label_context.items():
        expected = PREFIXES.get(context or "")
        if expected and not name.startswith(expected):
            wrong_prefix.append({"label": name, "expected": expected, "at": labels[name][0]})

    return {
        "broken_refs": sorted(name for name in refs if name not in labels),
        "unused_labels": sorted(name for name in labels if name not in refs),
        "duplicate_labels": sorted(name for name, places in labels.items() if len(places) > 1),
        "missing_citations": sorted(name for name in cites if bib_keys and name not in bib_keys),
        "uncited_entries": sorted(bib_keys - set(cites)) if bib_keys else [],
        "wrong_prefix": wrong_prefix,
        "bib_found": bool(bib_keys),
        "counts": {"labels": len(labels), "refs": len(refs), "cites": len(cites)},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--bib", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    bib = args.bib or next(iter(sorted(args.root.rglob("*.bib"))), None)
    result = scan(args.root.resolve(), bib)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        print()
        return 0

    problems = 0
    for key, title in [
        ("broken_refs", "References with no matching \\label"),
        ("missing_citations", "Cited keys missing from the .bib"),
        ("duplicate_labels", "Labels defined more than once"),
        ("unused_labels", "Labels never referenced"),
        ("uncited_entries", "Bib entries never cited"),
    ]:
        items = result[key]
        if items:
            hard = key in {"broken_refs", "missing_citations", "duplicate_labels"}
            problems += len(items) if hard else 0
            print(f"{title}: {', '.join(items)}")
    for item in result["wrong_prefix"]:
        print(f"Label {item['label']} at {item['at']} should start with {item['expected']!r}")
    if not problems and not result["wrong_prefix"]:
        print("Cross-references are consistent.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
