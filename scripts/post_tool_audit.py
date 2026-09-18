#!/usr/bin/env python3
"""PostToolUse hook: notice author prose that changed without passing the guard.

Runs after every tool call that could touch a file.  A change here means either
the author typed something in their editor -- which is entirely their right --
or something wrote prose without going through the guard.  Either way it is
recorded, and the Stop hook makes Claude account for it before finishing.
"""

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
    if not state:
        session_state.reset(cfg)
        hookio.allow()

    changed = session_state.drifted(cfg, state)
    if changed:
        tool = event.get("tool_name", "a tool")
        for name in changed:
            session_state.log(cfg, f"author prose changed in {name} around a {tool} call")
        pending = set(state.get("pending", [])) | set(changed)
        state["pending"] = sorted(pending)
        state["prose"] = session_state.snapshot(cfg)
        session_state.save_state(cfg, state)

    hookio.allow()


if __name__ == "__main__":
    main()
