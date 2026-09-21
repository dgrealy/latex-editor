#!/usr/bin/env python3
"""PostToolUse hook: notice author prose that changed without passing the guard.

Runs after every tool call that could touch a file.  A changed file is not by
itself evidence of anything: the author may be typing in their editor while
Claude works, which is entirely their right.  So each change is placed:

  * it matches what the guard approved      -- the gate did its job, say nothing
  * the tool wrote this file, and it doesn't -- something landed that the guard
                                                did not see; Claude explains it
  * the tool was Bash, which names no file   -- same, conservatively
  * nothing here touched it                  -- the author typed; record and move on

Everything is written to the audit log either way.  Only the unexplained goes
into `pending`, because a Stop hook that blocks on every keystroke is a Stop
hook the author turns off.
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

    tool = event.get("tool_name", "a tool")
    tool_input = event.get("tool_input") or {}
    written = session_state.relative(cfg, tool_input.get("file_path") or "")

    # Nothing calls hookio.allow() inside the transaction: it exits the process,
    # which would abandon the block before the state is written back.
    with session_state.transaction(cfg) as state:
        current = session_state.snapshot(cfg)
        if not state:
            state.update({"prose": current, "pending": [], "approved": {}})
        else:
            approved = state.setdefault("approved", {})
            unexplained = []

            for name in session_state.drifted(cfg, state, current):
                if approved.get(name) is not None and approved[name] == current.get(name):
                    continue  # exactly what the guard permitted
                if name == written or tool == "Bash":
                    session_state.log(cfg, f"author prose changed in {name} around a {tool} call")
                    unexplained.append(name)
                else:
                    session_state.log(cfg, f"author edited {name} in their editor")

            # A tool call settles the approval for the file it named, whether the
            # write landed or not -- a stale digest must never excuse a later edit.
            if written:
                approved.pop(written, None)

            if unexplained:
                state["pending"] = sorted(set(state.get("pending", [])) | set(unexplained))
            state["prose"] = current

    hookio.allow()


if __name__ == "__main__":
    main()
