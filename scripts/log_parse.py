#!/usr/bin/env python3
"""Turn a LaTeX log into a short list of things that actually need attention."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ERROR = re.compile(r"^! (.+)$", re.MULTILINE)
_LINE = re.compile(r"^l\.(\d+)", re.MULTILINE)
_UNDEFINED_REF = re.compile(r"Reference `([^']+)' on page \d+ undefined")
_UNDEFINED_CITE = re.compile(r"Citation `([^']+)' on page \d+ undefined")
_MULTIPLY = re.compile(r"Label `([^']+)' multiply defined")
_BOX = re.compile(r"^(Overfull|Underfull) \\([hv])box \(([^)]*)\)[^\n]*?at lines? (\d+)", re.MULTILINE)
_MISSING_FILE = re.compile(r"File `([^']+)' not found")
_MISSING_PKG = re.compile(r"LaTeX Error: File `([^']+\.sty)' not found")
_WARNING = re.compile(r"^(?:LaTeX|Package (\w+)) Warning: (.+)$", re.MULTILINE)


def parse(text: str) -> dict:
    errors = []
    for match in _ERROR.finditer(text):
        tail = text[match.end() : match.end() + 400]
        line = _LINE.search(tail)
        errors.append({"message": match.group(1).strip(), "line": int(line.group(1)) if line else None})

    boxes = [
        {
            "kind": kind.lower(),
            "direction": direction,
            "amount": amount.strip(),
            "line": int(line),
        }
        for kind, direction, amount, line in _BOX.findall(text)
    ]
    # Overfull boxes are the ones that show up as text running into the margin.
    boxes.sort(key=lambda box: (box["kind"] != "overfull", -_points(box["amount"])))

    return {
        "errors": errors,
        "undefined_references": sorted(set(_UNDEFINED_REF.findall(text))),
        "undefined_citations": sorted(set(_UNDEFINED_CITE.findall(text))),
        "duplicate_labels": sorted(set(_MULTIPLY.findall(text))),
        "missing_packages": sorted(set(_MISSING_PKG.findall(text))),
        "missing_files": sorted(set(_MISSING_FILE.findall(text))),
        "boxes": boxes,
        "warnings": sorted({(pkg or "LaTeX", msg.strip()) for pkg, msg in _WARNING.findall(text)}),
    }


def _points(amount: str) -> float:
    match = re.search(r"([\d.]+)pt", amount)
    return float(match.group(1)) if match else 0.0


def summarise(result: dict, limit: int = 8) -> str:
    lines = []
    for error in result["errors"]:
        where = f" (line {error['line']})" if error["line"] else ""
        lines.append(f"ERROR{where}: {error['message']}")
    for package in result["missing_packages"]:
        lines.append(f"ERROR: package not installed: {package}")
    for name in result["undefined_references"]:
        lines.append(f"undefined reference: {name}")
    for name in result["undefined_citations"]:
        lines.append(f"undefined citation: {name}")
    for name in result["duplicate_labels"]:
        lines.append(f"label defined twice: {name}")
    overfull = [box for box in result["boxes"] if box["kind"] == "overfull"]
    for box in overfull[:limit]:
        lines.append(f"overfull \\{box['direction']}box ({box['amount']}) at line {box['line']}")
    if len(overfull) > limit:
        lines.append(f"...and {len(overfull) - limit} more overfull boxes")
    return "\n".join(lines) or "No errors or warnings worth reporting."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.log.is_file():
        print(f"No log at {args.log} -- the document has not been built yet.", file=sys.stderr)
        return 2

    result = parse(args.log.read_text(encoding="utf-8", errors="replace"))
    if args.json:
        json.dump(result, sys.stdout, indent=2)
        print()
    else:
        print(summarise(result))
    return 1 if result["errors"] or result["missing_packages"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
