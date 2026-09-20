#!/usr/bin/env python3
"""UserPromptSubmit hook: commit whatever is uncommitted before Claude sees the prompt.

The author writes in their editor and then asks Claude something. Without this,
their prose sits uncommitted and the next skill's commit sweeps it up, mixing the
author's words with Claude's structural edits -- which is precisely the separation
the whole design exists to keep.

So: every prompt starts from a clean tree. Author files commit as [author],
Claude-owned files as [claude] wip, so an interrupted task is never mistaken for
the author's writing.

Silent on success. It speaks only when a commit fails, because a provenance record
that quietly stops recording is worse than no record at all.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as config_module  # noqa: E402
import hookio  # noqa: E402

AUTHOR_PREFIX = "[author]"


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=60
    )


def _dirty(root: Path) -> list[str]:
    """Paths with uncommitted changes, staged or not, including new files."""
    result = git(root, "status", "--porcelain", "--untracked-files=all")
    if result.returncode != 0:
        return []
    paths = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        # Renames read "old -> new"; the new name is what we commit.
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path.strip().strip('"'))
    return paths


def _word_delta(root: Path, relative: str, captions_are_prose: bool) -> int | None:
    """How many author words this file gained or lost since the last commit."""
    try:
        from prose_stream import classify
    except ImportError:
        return None

    path = root / relative
    if path.suffix != ".tex" or not path.is_file():
        return None
    try:
        now = len(classify(path.read_text(encoding="utf-8"), captions_are_prose).text.split())
    except Exception:
        return None

    previous = git(root, "show", f"HEAD:{relative}")
    if previous.returncode != 0:
        before = 0  # a new file
    else:
        try:
            before = len(classify(previous.stdout, captions_are_prose).text.split())
        except Exception:
            return None
    return now - before


def _message(root: Path, cfg, group: str, paths: list[str]) -> str:
    prefix = AUTHOR_PREFIX if group == "author" else f"{cfg.get('git', 'prefix')} wip"

    if group == "author":
        deltas = {}
        for relative in paths:
            delta = _word_delta(root, relative, cfg.captions_are_prose)
            if delta:
                deltas[relative] = delta
        if deltas:
            parts = [f"{d:+d} words in {name}" for name, d in sorted(deltas.items())]
            return f"{prefix} {', '.join(parts[:3])}" + (
                f" and {len(parts) - 3} more" if len(parts) > 3 else ""
            )

    shown = ", ".join(sorted(paths)[:3])
    more = f" and {len(paths) - 3} more" if len(paths) > 3 else ""
    return f"{prefix} {shown}{more}"


def main() -> None:
    event = hookio.read_event()
    cfg = config_module.load(event.get("cwd"))
    if cfg is None or not cfg.get("git", "auto_commit"):
        hookio.allow()

    root = cfg.root
    if git(root, "rev-parse", "--git-dir").returncode != 0:
        hookio.allow()  # not a repository; nothing to record

    changed = _dirty(root)
    if not changed:
        hookio.allow()

    groups: dict[str, list[str]] = {"author": [], "claude": []}
    for relative in changed:
        groups["claude" if cfg.owns(root / relative) else "author"].append(relative)

    problems = []
    for group, paths in groups.items():
        if not paths:
            continue
        if git(root, "add", "--", *paths).returncode != 0:
            problems.append(f"could not stage {len(paths)} {group} file(s)")
            continue
        if not git(root, "diff", "--cached", "--name-only", "--", *paths).stdout.strip():
            continue
        result = git(root, "commit", "-m", _message(root, cfg, group, paths), "--", *paths)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            problems.append(f"{group}: {detail[0] if detail else 'commit failed'}")

    if problems:
        # Worth breaking the silence for: the provenance record just stopped.
        print(
            "Could not auto-commit your work before this prompt: "
            + "; ".join(problems)
            + ". Your changes are safe but uncommitted.",
            file=sys.stderr,
        )
    hookio.allow()


if __name__ == "__main__":
    main()
