#!/usr/bin/env python3
"""Switch the editor between UI presets without touching the build configuration.

`.vscode/settings.base.json` holds everything that makes Ctrl+S build and the PDF
refresh. A preset only adds appearance on top. Merging the two means switching can
never quietly break the build, which is what editing one combined settings.json by
hand tends to do.

    minimal  stock VS Code, just the LaTeX build and fewer popups
    writer   build artefacts hidden, no minimap or breadcrumbs
    focus    plus no activity bar, no status bar, single tab
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as config_module  # noqa: E402

BASE = "settings.base.json"
ACTIVE = "settings.json"
MARKER = "_latexEditorPreset"


def vscode_dir(root: Path) -> Path:
    return root / ".vscode"


def presets(root: Path) -> dict[str, Path]:
    directory = vscode_dir(root) / "presets"
    if not directory.is_dir():
        return {}
    return {path.stem: path for path in sorted(directory.glob("*.json"))}


def active(root: Path) -> str | None:
    path = vscode_dir(root) / ACTIVE
    try:
        return json.loads(path.read_text(encoding="utf-8")).get(MARKER)
    except (OSError, json.JSONDecodeError):
        return None


def apply(root: Path, name: str) -> Path:
    available = presets(root)
    if name not in available:
        raise SystemExit(
            f"No preset named {name!r}. Available: {', '.join(available) or 'none'}"
        )

    base_path = vscode_dir(root) / BASE
    try:
        settings = json.loads(base_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"Cannot read {base_path}: {exc}") from exc

    settings.update(json.loads(available[name].read_text(encoding="utf-8")))
    settings[MARKER] = name

    target = vscode_dir(root) / ACTIVE
    target.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("preset", nargs="?", help="minimal | writer | focus")
    parser.add_argument("--list", action="store_true", help="show the presets")
    args = parser.parse_args()

    cfg = config_module.load()
    if cfg is None:
        print("Not a latex-editor project (no .latex-editor.yml found).", file=sys.stderr)
        return 2

    if args.list or not args.preset:
        current = active(cfg.root)
        for name in presets(cfg.root):
            print(f"  {'*' if name == current else ' '} {name}")
        if not current:
            print("\nNo preset applied yet. Run: ui_preset.py writer")
        return 0

    target = apply(cfg.root, args.preset)
    print(f"Applied the {args.preset!r} preset to {target.relative_to(cfg.root)}.")
    print("VS Code picks it up immediately; reload the window if anything looks stale.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
