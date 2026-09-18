---
name: compile
description: Build a LaTeX document with latexmk, read the log, and fix LaTeX syntax errors - missing braces, unclosed environments, undefined control sequences, missing packages. Use when the document fails to build, when the author reports an error, or when a PDF is needed.
---

# Build the document and fix what breaks

## Build

```
latexmk -pdf -interaction=nonstopmode -file-line-error -outdir=build <main>.tex
```

Use the engine from `.latex-editor.yml` (`pdflatex`, `xelatex` or `lualatex`);
`latexmk -pdfxe` and `-pdflua` select the other two. The `.latexmkrc` in the
project already sets the output directory and the bib backend, so prefer a plain
`latexmk` invocation when one is present.

## Read the log

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log_parse.py build/<main>.log
```

Work the list top down: errors, then missing packages, then undefined
references and citations, then overfull boxes.

## Fix

You may fix anything structural: unbalanced braces, unclosed environments,
misspelled macro names, a missing `\usepackage`, a wrong float placement, a
broken table column spec, a `\label` that does not match its `\ref`.

You may **not** fix an error by rewriting the author's sentence. If a line
overflows because a long word will not break, add `\hyphenation{}` or an
explicit `\-` hint; if that is not enough, report it as a suggestion and let the
author reword. The same goes for an overfull box caused by a long sentence.

A missing package is a blocker, not something to work around by substituting a
different package — record it in `.latex-editor/blockers.md` and tell the author
what to install.

## Finishing

Report what you changed and what is still failing. If the build is clean, say
so plainly and give the page count. Commit structural fixes:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/claude_commit.py "compile: fix <what>" <files>
```
