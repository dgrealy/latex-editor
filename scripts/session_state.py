"""Tracks the author's prose across a session, as a backstop to the guards.

The Edit/Write guard sees every edit Claude proposes and the Bash guard blocks
the obvious shell bypasses.  This records a fingerprint of every author-owned
.tex file so that anything which slips past both is still noticed before Claude
finishes its turn.

The author may be typing in their editor the whole time, so a changed file is
not on its own evidence of anything.  The guard records the content it approved;
the audit compares against that, and only what fails to match is Claude's to
explain.  State is written under a lock and replaced atomically, because two
sessions can be open on the same manuscript.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from config import Config

try:  # POSIX only; without it the locking degrades to nothing, never to an error
    import fcntl
except ImportError:  # pragma: no cover - not reachable on the supported platforms
    fcntl = None

STATE_DIR_NAME = ".latex-editor"
STATE_FILE = "state.json"
AUDIT_LOG = "audit.log"
LOCK_FILE = "state.lock"
SKIP_DIRS = {".git", "build", "node_modules", ".latex-editor", ".devcontainer"}

# Recorded in place of a digest for a file that will not parse. Omitting it
# instead would make the file compare equal to itself forever after, which is
# how prose in a briefly-broken file used to become invisible to the audit.
UNPARSEABLE = "unparseable"


def is_transient(relative_path: str) -> bool:
    """True for the bookkeeping this module writes, which is never the author's work.

    The template gitignores these, but a project scaffolded before they existed
    does not -- and autocommit would then record the lock file as something the
    author wrote.
    """
    parts = Path(relative_path).as_posix().split("/")
    if len(parts) != 2 or parts[0] != STATE_DIR_NAME:
        return False
    name = parts[1]
    return name in {STATE_FILE, LOCK_FILE} or (
        name.startswith(f".{STATE_FILE}.") and name.endswith(".tmp")
    )


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


def prose_digest(cfg: Config, text: str) -> str | None:
    """A hash of the author's words in some .tex source, ignoring markup and layout."""
    try:
        from prose_stream import classify

        stream = classify(text, cfg.captions_are_prose)
    except Exception:
        return None
    if not stream.parse_ok:
        return None
    return hashlib.sha256(stream.text.encode("utf-8")).hexdigest()


def fingerprint(cfg: Config, path: Path) -> str | None:
    """A hash of the author's words in one file, ignoring all markup and layout."""
    try:
        return prose_digest(cfg, path.read_text(encoding="utf-8"))
    except OSError:
        return None


def relative(cfg: Config, path: str | Path) -> str | None:
    """The project-relative name used as a key throughout the state file."""
    try:
        return Path(path).resolve().relative_to(cfg.root).as_posix()
    except ValueError:
        return None


def snapshot(cfg: Config) -> dict[str, str]:
    out = {}
    for path in author_tex_files(cfg):
        out[path.relative_to(cfg.root).as_posix()] = fingerprint(cfg, path) or UNPARSEABLE
    return out


def _state_path(cfg: Config) -> Path:
    return cfg.state_dir() / STATE_FILE


def load_state(cfg: Config) -> dict:
    try:
        return json.loads(_state_path(cfg).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(cfg: Config, state: dict) -> None:
    """Replace the state file atomically, so a concurrent reader never sees half of it."""
    path = _state_path(cfg)
    tmp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


# flock is held per file descriptor, so a second `locked()` inside the first
# would open a new one and wait on a lock this process already holds. Count the
# depth instead: the outermost block owns the lock.
_depth = 0


@contextmanager
def locked(cfg: Config):
    """Hold the project's state lock, or carry on unlocked if the platform has none.

    A hook that cannot lock should still do its job: losing the lock costs us a
    racing write, refusing to run costs the author their guard.
    """
    global _depth
    if _depth:
        _depth += 1
        try:
            yield
        finally:
            _depth -= 1
        return

    handle = None
    try:
        handle = open(cfg.state_dir() / LOCK_FILE, "w", encoding="utf-8")
        if fcntl is not None:
            fcntl.flock(handle, fcntl.LOCK_EX)
    except OSError:
        if handle is not None:
            handle.close()
        handle = None
    _depth = 1
    try:
        yield
    finally:
        _depth = 0
        if handle is not None:
            try:
                if fcntl is not None:
                    fcntl.flock(handle, fcntl.LOCK_UN)
            except OSError:
                pass
            handle.close()


@contextmanager
def transaction(cfg: Config):
    """Load, modify and save the state file with nothing else writing in between."""
    with locked(cfg):
        state = load_state(cfg)
        yield state
        save_state(cfg, state)


def reset(cfg: Config) -> dict:
    state = {"prose": snapshot(cfg), "pending": [], "approved": {}}
    with locked(cfg):
        save_state(cfg, state)
    return state


def approve(cfg: Config, path: str | Path, proposed: str) -> None:
    """Record the content the guard is about to permit for `path`.

    The audit compares what lands on disk against this.  Without it a legitimate
    syntax repair -- which the guard allows precisely because it recovers the
    author's words from markup that was swallowing them -- reads as prose that
    appeared from nowhere.
    """
    name = relative(cfg, path)
    digest = prose_digest(cfg, proposed)
    if name is None or digest is None:
        return
    try:
        with transaction(cfg) as state:
            state.setdefault("approved", {})[name] = digest
    except OSError:
        # Deciding is the guard's job; recording is a convenience for the audit.
        # A read-only or full state directory must not turn an allow into a crash.
        # The cost is one drift report the author explains, not a lost refusal.
        pass


def drifted(cfg: Config, state: dict, current: dict[str, str] | None = None) -> list[str]:
    """Files whose author prose differs from the recorded fingerprint.

    Pass `current` when the caller already has a snapshot: taking one parses
    every .tex in the project, and the audit needs it for other reasons too.
    """
    previous = state.get("prose", {})
    current = snapshot(cfg) if current is None else current
    changed = [name for name, digest in current.items() if previous.get(name, digest) != digest]
    changed += [name for name in previous if name not in current]
    return sorted(set(changed))


def log(cfg: Config, message: str) -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    with locked(cfg):
        with open(cfg.state_dir() / AUDIT_LOG, "a", encoding="utf-8") as handle:
            handle.write(f"{stamp}  {message}\n")
