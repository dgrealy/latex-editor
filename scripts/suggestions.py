#!/usr/bin/env python3
"""List and clear the inline `% SUGGEST:` comments Claude leaves in the manuscript.

A suggestion lives beside the sentence it concerns, so the author reads it in the
editor and in the diff rather than in a wall of console output.  Because it is a
LaTeX comment it never reaches the reader, and adding or removing one leaves the
author's prose stream untouched -- which this verifies before writing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as config_module  # noqa: E402

MARKER = "SUGGEST:"
#: A whole-line comment. Trailing comments on a code line are left alone, since
#: removing them would disturb the line they sit on.
_SUGGESTION = re.compile(r"^[ \t]*%+[ \t]*SUGGEST:[ \t]*(.*)$")
SKIP_DIRS = {".git", "build", "node_modules", ".latex-editor", ".devcontainer"}


class Suggestion:
    def __init__(self, path: Path, line: int, text: str):
        self.path, self.line, self.text = path, line, text


def tex_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*.tex"))
        if not any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1])
    ]


def find(root: Path, paths: list[Path] | None = None) -> list[Suggestion]:
    found = []
    for path in paths or tex_files(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, start=1):
            match = _SUGGESTION.match(line)
            if match:
                found.append(Suggestion(path, number, match.group(1).strip()))
    return found


def clear(root: Path, paths: list[Path] | None = None, captions_are_prose: bool = True) -> int:
    """Remove suggestion comments. Refuses to write if the author's words would move."""
    from prose_stream import compare

    removed = 0
    for path in paths or tex_files(root):
        original = path.read_text(encoding="utf-8")
        kept = [line for line in original.splitlines(keepends=True) if not _SUGGESTION.match(line.rstrip("\n"))]
        updated = "".join(kept)
        if updated == original:
            continue

        verdict = compare(original, updated, captions_are_prose)
        if not verdict.allowed:
            print(
                f"error: clearing {path} would change the author's prose "
                f"({verdict.reason}); nothing written",
                file=sys.stderr,
            )
            return -1

        removed += len(original.splitlines()) - len(kept)
        path.write_text(updated, encoding="utf-8")
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="show open suggestions")
    parser.add_argument("--clear", action="store_true", help="remove suggestion comments")
    parser.add_argument("paths", nargs="*", type=Path, help="limit to these files")
    args = parser.parse_args()

    cfg = config_module.load()
    if cfg is None:
        print("Not a latex-editor project (no .latex-editor.yml found).", file=sys.stderr)
        return 2

    paths = [p.resolve() for p in args.paths] or None

    if args.clear:
        removed = clear(cfg.root, paths, cfg.captions_are_prose)
        if removed < 0:
            return 1
        print(f"Removed {removed} suggestion{'' if removed == 1 else 's'}.")
        return 0

    items = find(cfg.root, paths)
    for item in items:
        where = item.path.relative_to(cfg.root).as_posix()
        print(f"{where}:{item.line}  {item.text}")
    if not items:
        print("No open suggestions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
