"""Project settings for a latex-editor document repo.

The presence of `.latex-editor.yml` is what marks a directory as a document
this plugin governs.  Without it the guards stand down entirely, so installing
the plugin globally never interferes with an unrelated repository.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any

CONFIG_NAME = ".latex-editor.yml"

DEFAULTS: dict[str, Any] = {
    "project": {
        "main": "main.tex",
        "engine": "pdflatex",
        "bib": "bib/references.bib",
        "bib_backend": "biber",
    },
    "figures": {"format": "pdf", "src": "figures/src", "out": "figures/out", "width": "8.4cm"},
    "prose": {
        "captions": "author",
        # Files Claude owns outright: generated or purely structural .tex.
        "claude_paths": [
            "bib/**", "figures/**", "tables/**", "frontmatter/**", "build/**",
        ],
        "sentence_per_line": True,
    },
    "git": {"auto_commit": True, "prefix": "[claude]"},
    "review": {"spellcheck": "hunspell", "dict": ".latex-editor/dictionary.txt"},
}


class Config:
    def __init__(self, root: Path, data: dict[str, Any]):
        self.root = root
        self.data = data

    # -- lookups ----------------------------------------------------------
    def get(self, section: str, key: str) -> Any:
        return self.data.get(section, {}).get(key, DEFAULTS[section][key])

    @property
    def captions_are_prose(self) -> bool:
        return str(self.get("prose", "captions")).lower() != "claude"

    @property
    def claude_paths(self) -> list[str]:
        return list(self.get("prose", "claude_paths"))

    def owns(self, path: str | Path) -> bool:
        """True when Claude may write the file freely, prose and all."""
        try:
            rel = Path(path).resolve().relative_to(self.root).as_posix()
        except ValueError:
            return False
        return any(
            fnmatch.fnmatch(rel, pattern) or rel.startswith(pattern.rstrip("*").rstrip("/") + "/")
            for pattern in self.claude_paths
        )

    def state_dir(self) -> Path:
        path = self.root / ".latex-editor"
        path.mkdir(parents=True, exist_ok=True)
        return path


def _merge(base: dict, extra: dict) -> dict:
    out = {key: dict(value) if isinstance(value, dict) else value for key, value in base.items()}
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key].update(value)
        else:
            out[key] = value
    return out


def find_root(start: str | Path | None = None) -> Path | None:
    """Walk up from `start` looking for the project marker."""
    begin = Path(start or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()).resolve()
    if begin.is_file():
        begin = begin.parent
    for directory in [begin, *begin.parents]:
        if (directory / CONFIG_NAME).is_file():
            return directory
    return None


def load(start: str | Path | None = None) -> Config | None:
    """Settings for the document repo containing `start`, or None if there isn't one."""
    root = find_root(start)
    if root is None:
        return None
    data: dict[str, Any] = {}
    try:
        import yaml  # optional: without it we simply use the stricter defaults

        with open(root / CONFIG_NAME, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception:
        data = {}
    return Config(root, _merge(DEFAULTS, data))
