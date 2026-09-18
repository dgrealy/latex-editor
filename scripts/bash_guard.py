#!/usr/bin/env python3
"""PreToolUse guard: stop the shell being used to route around the prose guard.

The Edit/Write guard is the real gate, but a shell can write a file too.  This
hook refuses commands that would write into a .tex file the author owns.  It
looks for write *intent* rather than policing commands in general, so builds,
greps and git all pass through untouched.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as config_module  # noqa: E402
import hookio  # noqa: E402

EVENT = "PreToolUse"

#: (pattern, what it is) -- group 1 is the .tex file being written, when known.
WRITE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?<![0-9])>>?\s*([^\s;|&<>]+\.tex)\b"), "a shell redirection"),
    (re.compile(r"\btee\b(?:\s+-a)?\s+([^\s;|&<>]+\.tex)\b"), "tee"),
    (re.compile(r"\bsed\b[^;|&]*?\s-i[^;|&]*?\s([^\s;|&<>]+\.tex)\b"), "sed -i"),
    (re.compile(r"\bperl\b[^;|&]*?\s-[a-zA-Z]*i[a-zA-Z]*[^;|&]*?\s([^\s;|&<>]+\.tex)\b"), "perl -i"),
    (re.compile(r"\b(?:cp|mv|install|rsync)\b[^;|&]*?\s([^\s;|&<>]+\.tex)\s*(?:;|\||&|$)"), "a file copy or move"),
    (re.compile(r"\btruncate\b[^;|&]*?\s([^\s;|&<>]+\.tex)\b"), "truncate"),
    (re.compile(r"\bdd\b[^;|&]*?\bof=([^\s;|&<>]+\.tex)\b"), "dd"),
]

#: Commands that rewrite .tex in place without naming a redirection target.
BLANKET_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"\blatexindent\b[^;|&]*?\s-(?:w\b|-overwrite\b)"),
        "latexindent rewriting files in place",
    ),
    (
        re.compile(r"\bgit\s+(?:checkout|restore)\b[^;|&]*\.tex\b"),
        "git restoring a .tex file, which can silently undo the author's writing",
    ),
    (
        re.compile(r"\bpython[0-9.]*\b[^;|&]*\s-c\b[^;|&]*\.tex"),
        "an inline Python program touching a .tex file",
    ),
]

ADVICE = (
    "Use the Edit or Write tool instead so the prose guard can check the change, "
    "or run scripts/reflow.py if you only mean to reformat."
)


def main() -> None:
    event = hookio.read_event()
    command = (event.get("tool_input") or {}).get("command") or ""
    if ".tex" not in command:
        hookio.allow()

    cfg = config_module.load(event.get("cwd"))
    if cfg is None:
        hookio.allow()

    for pattern, description in WRITE_PATTERNS:
        for match in pattern.finditer(command):
            target = match.group(1)
            if cfg.owns(cfg.root / target) or cfg.owns(target):
                continue
            hookio.deny(
                EVENT,
                f"Blocked: this command writes to {target} through {description}, which "
                f"bypasses the prose guard protecting the author's text. {ADVICE}",
            )

    for pattern, description in BLANKET_PATTERNS:
        if pattern.search(command):
            hookio.deny(EVENT, f"Blocked: {description}. {ADVICE}")

    hookio.allow()


if __name__ == "__main__":
    main()
