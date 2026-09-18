"""Shared plumbing for the hook entry points."""

from __future__ import annotations

import json
import sys
from typing import Any


def read_event() -> dict[str, Any]:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def allow() -> None:
    """Say nothing and let the normal permission flow continue."""
    sys.exit(0)


def deny(event_name: str, reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": event_name,
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.exit(0)


def block_stop(reason: str) -> None:
    """Keep Claude working -- a Stop hook cannot use exit codes to do this."""
    json.dump({"decision": "block", "reason": reason}, sys.stdout)
    sys.exit(0)
