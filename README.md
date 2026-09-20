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

## The container

Each document gets its own dev container, scaffolded into the repo and **owned by
it from then on** — a plugin update never rewrites a project's build environment,
so a thesis started in 2026 still builds the way it always did.

It is built on Anthropic's Claude Code sandbox: a `node:20` base, and an
iptables firewall that drops all outbound traffic except GitHub, npm, Anthropic,
the VS Code marketplace and the reference APIs (Crossref, arXiv, OpenAlex,
Semantic Scholar). Only the repo is mounted — no home directory, no other
projects. On top of that sits TeX Live with the journal classes, `latexmk`,
`biber`, `chktex`, `latexindent`, `latexdiff`, hunspell, and the prose guard's
Python dependencies.

Two consequences worth knowing:

- **`sudo` is restricted to the firewall script.** A LaTeX package that is not in
  the image cannot be installed mid-session. Claude reports it as a blocker; you
  add it to the Dockerfile and rebuild. The build environment stays in git rather
  than accumulating undocumented state.
- **The firewall allowlists IP addresses resolved at start-up**, and the reference
  APIs sit behind CDNs that rotate them, so lookups can start failing during a
  long session. Re-run `sudo /usr/local/bin/init-firewall.sh`. If one of those
  APIs is unreachable at start-up the container still comes up — `cite` reports a
  blocker rather than inventing a DOI.

The first build takes 10–20 minutes and a few GB; after that it is cached.

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

You never run `git commit` yourself. A hook commits whatever you have written
before each prompt, labelled `[author]`, so your prose and Claude's edits can
never land in the same commit. Turn the whole thing off with
`git.auto_commit: false`.

## The editor

Three UI presets, switched with `scripts/ui_preset.py <name>`:

| Preset | What it does |
|---|---|
| `minimal` | Stock VS Code, just the LaTeX build and fewer popups |
| `writer` | Build artefacts hidden from the explorer, no minimap or breadcrumbs (default) |
| `focus` | Plus no activity bar, no status bar, a single tab — close to a writing app |

Build settings live in `.vscode/settings.base.json` and are merged into every
preset, so switching cannot break the build. `Ctrl+Alt+V` opens the PDF beside
your source; VS Code restores that tab afterwards, so it is a one-time step.
`.vscode/keybindings-snippet.json` has shorter bindings to paste into your own
keyboard shortcuts — VS Code has no workspace keybindings, so that part cannot
be automated.

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
python3 -m pytest scripts/tests -q          # the guard, at the unit and hook level
claude plugin eval . --case 'guard-*' --runs 1 --allow-tools Edit,Write,Read
```

`scripts/tests/` is the specification for the guard: each case asks whether one
particular edit would change what a reader sees. Add a case before changing the
classification tables in `scripts/prose_stream.py`.

`evals/` is the specification for everything built on top of it. Each case runs
a real Claude session against a seeded manuscript, hooks and all, and scores
what comes back — that the guard refuses a reword and allows a citation, that
`cite` never invents a DOI it could not reach, that `review` writes findings the
author can act on. `evals/CATALOGUE.md` is the same cases as a checklist you can
work through by hand in the editor; it is generated, and CI checks it has not
drifted. See `evals/README.md`.

## Not built yet

Deliberately deferred until needed: the standalone figure/pgfplots pipeline,
table and equation conventions, journal guideline ingestion, style comparison
against a journal corpus, literature-review suggestions, a submission packager,
`latexdiff` revisions, and deterministic application of approved grammar fixes.
