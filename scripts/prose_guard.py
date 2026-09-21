#!/usr/bin/env python3
"""PreToolUse guard: refuse any edit that would change the author's words.

Claude may restructure, cite, reference, typeset and annotate a .tex file
freely.  It may not add, remove, reword or reorder a single word of the running
text.  This hook reconstructs what the file would look like after the proposed
edit and compares the author's prose stream before and after; if they differ,
the tool call never happens.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as config_module  # noqa: E402
import hookio  # noqa: E402
import session_state  # noqa: E402

EVENT = "PreToolUse"

SUGGEST = (
    "You cannot write the author's prose. If the text should change, put the "
    "suggestion in the review report (reviews/) or say it in chat with the "
    "exact file:line, the current sentence and your proposed replacement, and "
    "let the author type it. You may still add or edit \\cite{}, \\ref{}, "
    "\\label{}, maths, tables, figures, algorithms, comments and the preamble."
)


ANCHORLESS = (
    "You cannot replace a whole .tex file the author writes in. The guard checks "
    "your content against the file as it is now, but the write lands a moment "
    "later -- so anything the author typed in between is gone, and neither of you "
    "would see it happen. Use Edit instead: it is anchored to text you have read, "
    "so it fails safely if that text has moved. To relayout a whole file, run "
    "scripts/reflow.py, which verifies it changed no words before writing. Set "
    "prose.parallel: false in .latex-editor.yml if the author never writes while "
    "you work."
)


def _new_content(tool_name: str, tool_input: dict, current: str) -> tuple[str | None, str | None]:
    """The file content this tool call would produce, or a reason we can't tell."""
    if tool_name == "Write":
        for key in ("file_text", "content", "new_string"):
            if key in tool_input:
                return tool_input[key], None
        return None, "the Write call carried no file content"

    edits = tool_input.get("edits")
    if edits is None:
        edits = [tool_input]

    text = current
    for edit in edits:
        old = edit.get("old_string")
        new = edit.get("new_string")
        if old is None or new is None:
            return None, "the edit carried no old_string/new_string"
        if old == "":
            return None, "an empty old_string cannot be applied deterministically"
        if old not in text:
            # Let the tool itself report the mismatch.
            return None, None
        if edit.get("replace_all"):
            text = text.replace(old, new)
        else:
            text = text.replace(old, new, 1)
    return text, None


def _describe(verdict, path: str) -> str:
    parts = [f"Blocked: this edit would change the author's prose in {path} ({verdict.reason})."]
    if verdict.removed:
        parts.append("Words it would remove: " + ", ".join(repr(w) for w in verdict.removed[:12]))
    if verdict.added:
        parts.append("Words it would introduce: " + ", ".join(repr(w) for w in verdict.added[:12]))
    parts.append(SUGGEST)
    return " ".join(parts)


def main() -> None:
    event = hookio.read_event()
    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    raw_path = tool_input.get("file_path")
    if not raw_path or not str(raw_path).endswith(".tex"):
        hookio.allow()

    cfg = config_module.load(event.get("cwd") or raw_path)
    if cfg is None:
        hookio.allow()  # not a latex-editor project
    if cfg.owns(raw_path):
        hookio.allow()  # a file Claude writes outright

    path = Path(raw_path)
    if not path.exists():
        hookio.allow()  # a new file has no author prose to protect

    if tool_name == "Write" and cfg.parallel:
        hookio.deny(EVENT, ANCHORLESS)

    try:
        from prose_stream import compare
    except ImportError as exc:
        hookio.deny(
            EVENT,
            f"The prose guard cannot run ({exc}), so .tex edits are refused rather than "
            "waved through. Install its dependency with: pip install pylatexenc",
        )

    try:
        current = path.read_text(encoding="utf-8")
    except OSError as exc:
        hookio.deny(EVENT, f"The prose guard could not read {raw_path} ({exc}); refusing the edit.")

    proposed, problem = _new_content(tool_name, tool_input, current)
    if proposed is None:
        if problem:
            hookio.deny(EVENT, f"The prose guard could not evaluate this edit: {problem}.")
        hookio.allow()

    verdict = compare(current, proposed, captions_are_prose=cfg.captions_are_prose)
    if verdict.allowed:
        # Tell the audit what we permitted, so what lands on disk can be checked
        # against it rather than merely noticed as different.
        session_state.approve(cfg, path, proposed)
        hookio.allow()
    hookio.deny(EVENT, _describe(verdict, raw_path))


if __name__ == "__main__":
    main()
