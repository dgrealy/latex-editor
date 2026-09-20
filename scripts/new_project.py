#!/usr/bin/env python3
"""Scaffold a document repo from the stored default structure."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def available() -> list[str]:
    return sorted(path.name for path in TEMPLATES.iterdir() if path.is_dir())


def scaffold(target: Path, template: str, force: bool = False) -> list[Path]:
    source = TEMPLATES / template
    if not source.is_dir():
        raise SystemExit(f"No template named {template!r}. Available: {', '.join(available())}")

    written = []
    for path in sorted(source.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(source)
        destination = target / relative
        if destination.exists() and not force:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        written.append(relative)

    # The git hook needs to find the plugin's scripts at commit time, when no
    # Claude Code session is running to set CLAUDE_PLUGIN_ROOT.
    marker = target / ".latex-editor" / "scripts-path"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(Path(__file__).resolve().parent) + "\n", encoding="utf-8")

    hook = target / ".githooks" / "pre-commit"
    if hook.exists():
        hook.chmod(0o755)

    # The template ships presets rather than a settings.json, so apply one.
    if not (target / ".vscode" / "settings.json").exists():
        try:
            import ui_preset

            ui_preset.apply(target, "writer")
        except Exception:
            pass  # the author can run ui_preset.py themselves

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument("--template", default="article", help=f"one of: {', '.join(available())}")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args()

    target = args.target.resolve()
    target.mkdir(parents=True, exist_ok=True)
    written = scaffold(target, args.template, args.force)

    print(f"Scaffolded {len(written)} files into {target} from the {args.template!r} template.")
    if not written:
        print("Everything was already in place; nothing was overwritten.")
    print("\nNext:")
    print("  git init && git config core.hooksPath .githooks")
    print("  open the folder in VS Code and reopen in the dev container")
    print("  put your title in main.tex and start writing in sections/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
