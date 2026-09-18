"""Tracks the author's prose across a session, as a backstop to the guards.

The Edit/Write guard sees every edit Claude proposes and the Bash guard blocks
the obvious shell bypasses.  This records a fingerprint of every author-owned
.tex file so that anything which slips past both is still noticed before Claude
finishes its turn.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from config import Config

STATE_FILE = "state.json"
AUDIT_LOG = "audit.log"
SKIP_DIRS = {".git", "build", "node_modules", ".latex-editor", ".devcontainer"}


def author_tex_files(cfg: Config) -> list[Path]:
    """Every .tex file whose prose belongs to the author."""
    found = []
    for path in sorted(cfg.root.rglob("*.tex")):
        if any(part in SKIP_DIRS for part in path.relative_to(cfg.root).parts[:-1]):
            continue
        if cfg.owns(path):
            continue
        found.append(path)
    return found


def fingerprint(cfg: Config, path: Path) -> str | None:
    """A hash of the author's words in one file, ignoring all markup and layout."""
    try:
        from prose_stream import classify

        stream = classify(path.read_text(encoding="utf-8"), cfg.captions_are_prose)
    except Exception:
        return None
    if not stream.parse_ok:
        return None
    return hashlib.sha256(stream.text.encode("utf-8")).hexdigest()


def snapshot(cfg: Config) -> dict[str, str]:
    out = {}
    for path in author_tex_files(cfg):
        digest = fingerprint(cfg, path)
        if digest:
            out[path.relative_to(cfg.root).as_posix()] = digest
    return out


def _state_path(cfg: Config) -> Path:
    return cfg.state_dir() / STATE_FILE


def load_state(cfg: Config) -> dict:
    try:
        return json.loads(_state_path(cfg).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(cfg: Config, state: dict) -> None:
    _state_path(cfg).write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def reset(cfg: Config) -> dict:
    state = {"prose": snapshot(cfg), "pending": []}
    save_state(cfg, state)
    return state


def drifted(cfg: Config, state: dict) -> list[str]:
    """Files whose author prose differs from the recorded fingerprint."""
    previous = state.get("prose", {})
    current = snapshot(cfg)
    changed = [name for name, digest in current.items() if previous.get(name, digest) != digest]
    changed += [name for name in previous if name not in current]
    return sorted(set(changed))


def log(cfg: Config, message: str) -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    with open(cfg.state_dir() / AUDIT_LOG, "a", encoding="utf-8") as handle:
        handle.write(f"{stamp}  {message}\n")
