#!/usr/bin/env python3
"""SessionStart hook: record the prose baseline and remind Claude of the rules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as config_module  # noqa: E402
import hookio  # noqa: E402
import session_state  # noqa: E402

BRIEFING = """This is a latex-editor project. Two rules are enforced, not advisory:

1. The author writes every word of the prose. You may add, edit and remove
   \\cite{}, \\ref{}, \\label{}, maths, tables, figures, algorithms, comments and
   anything in the preamble, and you may reformat freely -- but you may not add,
   delete, reword or reorder a single word of the running text, a heading, a
   caption or the title. A hook blocks any edit that would. When the text should
   change, report it with file:line, the current sentence and your proposed
   replacement, and let the author type it.

2. Flag, don't guess. If a source is unreachable, a value unverifiable or a
   requirement unclear, say so the moment you hit it and append it to
   .latex-editor/blockers.md. Never invent a DOI, page range, author list,
   measurement or journal requirement to fill a gap."""


def main() -> None:
    event = hookio.read_event()
    cfg = config_module.load(event.get("cwd"))
    if cfg is None:
        hookio.allow()

    state = session_state.load_state(cfg)
    state["prose"] = session_state.snapshot(cfg)
    state.setdefault("pending", [])
    session_state.save_state(cfg, state)

    blockers = cfg.root / ".latex-editor" / "blockers.md"
    context = BRIEFING
    if blockers.is_file() and blockers.read_text(encoding="utf-8").strip():
        context += f"\n\nThere are open blockers recorded in {blockers}. Read them before starting."

    json.dump(
        {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}},
        sys.stdout,
    )


if __name__ == "__main__":
    main()
