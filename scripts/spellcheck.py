#!/usr/bin/env python3
"""Spell-check the author's prose, and nothing else.

Feeding a .tex file straight to a spell checker produces noise: macro names,
citation keys and maths all come back as misspellings.  This checks the prose
stream instead, so every hit is a real word in a real sentence.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as config_module  # noqa: E402
import session_state  # noqa: E402
from prose_stream import classify  # noqa: E402

_STRIP = re.compile(r"^[^\w]+|[^\w]+$")


def _checker() -> list[str] | None:
    for name, args in (
        ("hunspell", ["-l", "-i", "utf-8"]),
        ("aspell", ["list", "--encoding=utf-8"]),
    ):
        if shutil.which(name):
            return [name, *args]
    return None


def check(cfg) -> dict:
    tool = _checker()
    if tool is None:
        return {
            "available": False,
            "blocker": (
                "No spell checker is installed, so the spelling section could not run. "
                "Install one with: apt-get install hunspell hunspell-en-gb"
            ),
            "misspellings": {},
        }

    dictionary = cfg.root / cfg.get("review", "dict")
    personal = set()
    if dictionary.is_file():
        personal = {
            line.strip()
            for line in dictionary.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }

    findings: dict[str, list[dict]] = {}
    for path in session_state.author_tex_files(cfg):
        stream = classify(path.read_text(encoding="utf-8", errors="replace"), cfg.captions_are_prose)
        words = {}
        for token in stream.prose:
            word = _STRIP.sub("", token.text)
            if len(word) > 1 and not word.isdigit():
                words.setdefault(word, token.line)
        if not words:
            continue
        result = subprocess.run(
            tool, input="\n".join(words), capture_output=True, text=True, timeout=120
        )
        bad = [
            {"word": word, "line": words[word]}
            for word in dict.fromkeys(result.stdout.split())
            if word in words and word not in personal
        ]
        if bad:
            findings[path.relative_to(cfg.root).as_posix()] = bad

    return {"available": True, "blocker": None, "misspellings": findings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cfg = config_module.load()
    if cfg is None:
        print("Not a latex-editor project (no .latex-editor.yml found).", file=sys.stderr)
        return 2

    result = check(cfg)
    if args.json:
        json.dump(result, sys.stdout, indent=2)
        print()
        return 0

    if not result["available"]:
        print(result["blocker"], file=sys.stderr)
        return 2
    for path, items in result["misspellings"].items():
        for item in items:
            print(f"{path}:{item['line']}  {item['word']}")
    if not result["misspellings"]:
        print("No spelling problems found in the author's prose.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
