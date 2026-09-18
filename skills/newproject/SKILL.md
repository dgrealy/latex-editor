---
name: newproject
description: Set up a new paper or thesis repository with the standard folder structure, dev container, editor settings, build configuration, CI and git hooks. Use when starting a new article, chapter or thesis, or when asked to set up a LaTeX project.
---

# Start a new document

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/new_project.py <target-dir> --template article
```

Existing files are never overwritten unless `--force` is passed, so this is safe
to run inside a repository that already has some content.

## What it lays down

| Path | Whose | For |
|---|---|---|
| `main.tex`, `sections/*.tex` | the author | the manuscript |
| `bib/references.bib` | Claude | references |
| `frontmatter/` | Claude | acronyms and nomenclature |
| `tables/`, `figures/` | Claude | floats and plot sources |
| `.latex-editor.yml` | shared | engine, paths, figure format, caption policy |
| `.vscode/` | — | Ctrl+S builds and refreshes the PDF |
| `.devcontainer/` | — | TeX Live and Claude Code, with only this repo mounted |
| `.github/workflows/build.yml` | — | compiles on push, fails on unresolved refs |
| `.githooks/pre-commit` | — | fast reference and bibliography checks |

## After scaffolding

1. `git init` if needed, then `git config core.hooksPath .githooks`.
2. Tell the author to reopen the folder in the dev container (VS Code will
   offer). The first build takes a few minutes; after that it is cached.
3. Ask which journal or university guidelines apply, and whether the engine
   should be `pdflatex`, `xelatex` or `lualatex` — then set them in
   `.latex-editor.yml`. Do not guess a journal's requirements; if the author
   does not have the guidelines to hand, record it in
   `.latex-editor/blockers.md`.
4. Confirm the build works: `latexmk -pdf main.tex`.

## Adapting the structure

The author owns the layout. If they want chapters instead of sections, or a
different split, change `main.tex` and the folders to match and update
`prose.author_paths` / `prose.claude_paths` in `.latex-editor.yml` so the guard
protects the right files. A file under `claude_paths` is one where you may write
freely — put only generated or purely structural files there.
