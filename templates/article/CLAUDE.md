# Working on this manuscript

## Rule 1 — the author writes every word of the prose

This is enforced by a hook, not by good intentions. An edit that adds, removes,
rewords or reorders any of the author's text is blocked before it happens.

**Yours to write:** `\cite{}`, `\ref{}`, `\label{}`, `\gls{}`, inline and
display maths, `equation`/`align`, `table`/`tabular`, `figure`, `algorithm`,
`tikzpicture`, everything in `bib/`, `figures/`, `tables/` and `frontmatter/`,
the preamble, `%` comments, and all whitespace and layout.

**The author's:** every word of running text, every section heading, every
caption, the title and the abstract.

## How to answer

Keep the console quiet. The author reads what changed in the commit diff, not in
your replies.

**Refusing.** One line. Do not volunteer a suggestion, list your capabilities, or
explain the rule:

> I can't write prose. Ask what I can do, or let's talk about what you'd write.

**After doing work.** One line naming what changed and where. No summary of your
reasoning, no list of what you considered. The commit carries the detail.

> Added smith2019 and one citation in methods.

**When a suggestion is asked for.** Put it in the manuscript as a `% SUGGEST:`
comment on the line above the sentence it concerns, so the author sees it beside
their own text and in the diff. One line. If the reasoning needs more room, write
it in `reviews/<date>.md` and end the comment with `[see review]`:

```latex
% SUGGEST: two clauses; "the device" is not introduced yet. [see review]
The sample was then cooled and it was measured with the device.
```

Run `scripts/suggestions.py --list` to see open suggestions and `--clear` to remove
ones the author has acted on.

**Blockers are the exception.** Rule 2 outranks brevity: an unreachable source, an
unverifiable value or an ambiguity gets reported in full, immediately, however long
that takes.

## Rule 2 — flag, don't guess

The moment you cannot reach a source, verify a value or resolve an ambiguity,
say so and append it to `.latex-editor/blockers.md`. Never invent a DOI, a page
range, an author list, a measurement, or a journal's requirement. A guess that
looks plausible is worse than a gap, because the author will not catch it.

## Conventions

- One sentence per line. `scripts/reflow.py` does this safely; it verifies it
  changed no words before writing.
- Label prefixes: `fig:`, `tab:`, `eq:`, `alg:`, `sec:`, `lst:`.
- Citation keys: `smith2019`, `smith2019a` for a second Smith paper that year.
- Every bib entry needs a provenance record in `.latex-editor/bib-provenance.json`.
- Commit your own changes separately from the author's, with the `[claude]`
  prefix, so the author can review each one as a diff.

## Building

`latexmk` — the `.latexmkrc` sets the output directory and bib backend. In the
editor, Ctrl+S rebuilds and refreshes the PDF tab.

## The container

Everything runs inside the dev container: the build, the hooks, Claude Code
itself. Two limits follow from that, and both are deliberate.

**A missing LaTeX package is a blocker, not an obstacle to route around.** `sudo`
is restricted to the firewall script, so it cannot be installed at runtime, and
the mirrors are firewalled off anyway. Do not substitute a different package or
work around the gap silently. Record it in `.latex-editor/blockers.md`, tell the
author which package is needed, and let them add it to
`.devcontainer/Dockerfile` and rebuild (*Dev Containers: Rebuild Container*).

**Reference lookups can stop working mid-session.** The firewall allowlists the
addresses it resolved at start-up, and Crossref and arXiv sit behind CDNs that
rotate them. If a lookup that worked earlier starts failing, say so and suggest
re-running `sudo /usr/local/bin/init-firewall.sh`. Never treat an unreachable
API as licence to write the entry from memory.

**The git hooks only run inside the container.** `.githooks/pre-commit` stands
aside on the host, where the toolchain is absent, so a commit made outside the
container is unchecked. If the author mentions committing from their laptop,
that is why they saw no output.
