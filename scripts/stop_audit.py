#!/usr/bin/env python3
"""Stop hook: don't finish a turn with unexplained changes to the author's prose."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as config_module  # noqa: E402
import hookio  # noqa: E402
import session_state  # noqa: E402


def main() -> None:
    event = hookio.read_event()
    cfg = config_module.load(event.get("cwd"))
    if cfg is None:
        hookio.allow()

    state = session_state.load_state(cfg)
    pending = state.get("pending") or []
    if not pending or event.get("stop_hook_active"):
        if pending:
            state["pending"] = []
            session_state.save_state(cfg, state)
        hookio.allow()

    state["pending"] = []
    state["prose"] = session_state.snapshot(cfg)
    session_state.save_state(cfg, state)

    files = ", ".join(pending)
    hookio.block_stop(
        f"The author's prose changed during this turn in: {files}. That change did not go "
        "through the prose guard. If the author was typing in their editor, this is fine -- "
        "say so and carry on. If anything you ran caused it, check `git diff` on those files "
        "and restore the author's wording before you finish. Details are in "
        ".latex-editor/audit.log."
    )


if __name__ == "__main__":
    main()
