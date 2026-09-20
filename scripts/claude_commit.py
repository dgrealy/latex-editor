#!/usr/bin/env python3
"""Commit what a skill just changed, so the author can review it as a diff.

Claude's structural edits and the author's writing stay in separate commits.
Over a thesis that is a provenance record: every word the author wrote sits in
a commit they made.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as config_module  # noqa: E402


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=60
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message", help="what changed, e.g. 'cite: add Smith.2019'")
    parser.add_argument("paths", nargs="+", help="only these paths are staged")
    args = parser.parse_args()

    cfg = config_module.load()
    if cfg is None:
        print("Not a latex-editor project (no .latex-editor.yml found).", file=sys.stderr)
        return 2
    if not cfg.get("git", "auto_commit"):
        print("auto_commit is off; leaving the changes unstaged for you to review.")
        return 0

    root = cfg.root
    if git(root, "rev-parse", "--git-dir").returncode != 0:
        print("Not a git repository; skipping the commit.", file=sys.stderr)
        return 0

    add = git(root, "add", "--", *args.paths)
    if add.returncode != 0:
        print(add.stderr.strip(), file=sys.stderr)
        return 1

    staged = git(root, "diff", "--cached", "--name-only", "--", *args.paths).stdout.split()
    if not staged:
        print("Nothing changed; no commit made.")
        return 0

    prefix = cfg.get("git", "prefix")
    result = git(root, "commit", "-m", f"{prefix} {args.message}", "--", *args.paths)
    if result.returncode != 0:
        print(result.stderr.strip() or result.stdout.strip(), file=sys.stderr)
        return 1

    print(f"Committed {len(staged)} file(s): {prefix} {args.message}")
    print("Review it with: git show --stat HEAD && git diff HEAD~1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
