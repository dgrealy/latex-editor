# latex-editor

A Claude Code plugin for writing scientific LaTeX, built on one rule:

> **The author writes every word of the prose. Claude writes everything else.**

Claude handles citations, cross-references, maths, tables, figures, algorithms,
nomenclature, LaTeX syntax and the build. It reviews the writing and suggests
improvements. It cannot type a sentence into the manuscript — not because it has
been asked not to, but because a hook inspects every edit and blocks any that
would change the author's words.

## Why a hook and not an instruction

A rule in `CLAUDE.md` drifts over a long document. This one is mechanical: every
`.tex` edit is parsed, the author's prose is extracted from it, and the edit is
refused unless that prose comes out identical. Adding `\cite{}` mid-sentence,
reflowing a paragraph, inserting an equation and rewriting the preamble all pass
through. Adding a word, deleting a word, rewording a caption or reordering two
sentences does not.

## Install

```bash
/plugin marketplace add dgrealy/latex-editor
/plugin install latex-editor
```

The guards only activate in a directory containing `.latex-editor.yml`, so the
plugin is safe to leave installed everywhere.

## Start a document

```bash
python3 ~/.claude/plugins/*/latex-editor/scripts/new_project.py my-paper
cd my-paper && git init && git config core.hooksPath .githooks
```

Or just ask Claude to set up a new paper — the `newproject` skill does the same
thing and then asks the questions that matter (journal, engine, guidelines).

Open the folder in VS Code and reopen it in the dev container. Then **Ctrl+S**
builds the document and refreshes the PDF in the next tab, the way Overleaf
does; **Ctrl+Alt+J** jumps the PDF to wherever your cursor is.

## What Claude may and may not touch

| Claude writes | The author writes |
|---|---|
| `\cite{}`, `\ref{}`, `\label{}`, `\gls{}` | every word of running text |
| inline and display maths | every section heading |
| `table`, `tabular`, `figure`, `algorithm`, `tikzpicture` | every caption |
| `bib/`, `figures/`, `tables/`, `frontmatter/` | the title and abstract |
| the preamble, `%` comments, all layout and whitespace | |

Captions can be handed to Claude with `prose.captions: claude` in
`.latex-editor.yml`. Which files Claude owns outright is `prose.claude_paths`.

## The second rule: flag, don't guess

When Claude cannot reach a source, verify a value or resolve an ambiguity, it
says so immediately and records it in `.latex-editor/blockers.md`, which every
review report reprints at the top. It never invents a DOI, a page range, an
author list or a journal requirement to fill a gap. Every bibliography entry
carries a provenance record, and unverified entries are reported as errors until
the author clears them.

## Skills

| Skill | What it does |
|---|---|
| `newproject` | Scaffolds the folder structure, dev container, editor settings, CI and git hooks |
| `compile` | Builds with `latexmk`, reads the log, fixes LaTeX syntax errors |
| `cite` | Owns the `.bib`: adds and verifies entries, normalises them, fills `\cite{}` |
| `glossary` | Maintains the acronym and nomenclature indexes and reports gaps |
| `review` | Build, syntax, citations, references, spelling, grammar, layout, notation — into `reviews/<date>.md` |

## Reviewing what Claude did

Each skill commits its own changes with a `[claude]` prefix, so Claude's
structural edits and the author's writing stay in separate commits. Review them
in VS Code's Source Control view or with `git diff HEAD~1`, and undo any of them
with `git revert`. Over a thesis this is a provenance record: every word the
author wrote sits in a commit the author made.

Turn it off with `git.auto_commit: false`.

## Tools

Standalone, usable outside a Claude session:

```bash
scripts/ref_check.py --root .            # labels, references, citation keys
scripts/bib_lint.py bib/references.bib   # bibliography hygiene and provenance
scripts/glossary_check.py                # undefined and unused acronyms
scripts/spellcheck.py                    # spelling, prose only
scripts/wordcount.py --record            # author word count, excluding maths and floats
scripts/reflow.py sections/*.tex         # one sentence per line, verified word-safe
scripts/log_parse.py build/main.log      # what actually went wrong
```

## Development

```bash
pip install -r requirements.txt
python3 -m pytest scripts/tests -q
```

The test suite is the specification for the guard: each case asks whether one
particular edit would change what a reader sees. Add a case before changing the
classification tables in `scripts/prose_stream.py`.

## Not built yet

Deliberately deferred until needed: the standalone figure/pgfplots pipeline,
table and equation conventions, journal guideline ingestion, style comparison
against a journal corpus, literature-review suggestions, a submission packager,
`latexdiff` revisions, and deterministic application of approved grammar fixes.
