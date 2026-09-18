#!/usr/bin/env python3
"""Count the author's words -- only the author's.

Because the count comes from the prose stream, maths, citation keys, table
bodies and comments are all excluded, which makes it a fair figure to hold
against a journal's limit and an honest one to track over a thesis.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as config_module  # noqa: E402
import session_state  # noqa: E402
from prose_stream import classify  # noqa: E402


def counts(cfg) -> dict[str, int]:
    out = {}
    for path in session_state.author_tex_files(cfg):
        stream = classify(path.read_text(encoding="utf-8", errors="replace"), cfg.captions_are_prose)
        out[path.relative_to(cfg.root).as_posix()] = len(stream.text.split())
    return out


def record(cfg, per_file: dict[str, int]) -> Path:
    path = cfg.state_dir() / "progress.csv"
    is_new = not path.exists()
    try:
        commit = subprocess.run(
            ["git", "-C", str(cfg.root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = ""
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(["date", "commit", "file", "words"])
        for name, count in sorted(per_file.items()):
            writer.writerow([date.today().isoformat(), commit, name, count])
        writer.writerow([date.today().isoformat(), commit, "TOTAL", sum(per_file.values())])
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true", help="append to progress.csv")
    args = parser.parse_args()

    cfg = config_module.load()
    if cfg is None:
        print("Not a latex-editor project (no .latex-editor.yml found).", file=sys.stderr)
        return 2

    per_file = counts(cfg)
    width = max((len(name) for name in per_file), default=10)
    for name, count in sorted(per_file.items()):
        print(f"{name:<{width}}  {count:>7,}")
    print(f"{'TOTAL':<{width}}  {sum(per_file.values()):>7,}")

    if args.record:
        print(f"\nAppended to {record(cfg, per_file)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
