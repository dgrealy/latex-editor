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

When the text should change, do not try to change it. Report it:

```
sections/methods.tex:42
  now:      <the sentence as it stands>
  suggest:  <your proposed replacement>
  why:      <one line>
```

## Rule 2 — flag, don't guess

The moment you cannot reach a source, verify a value or resolve an ambiguity,
say so and append it to `.latex-editor/blockers.md`. Never invent a DOI, a page
range, an author list, a measurement, or a journal's requirement. A guess that
looks plausible is worse than a gap, because the author will not catch it.

## Conventions

- One sentence per line. `scripts/reflow.py` does this safely; it verifies it
  changed no words before writing.
- Label prefixes: `fig:`, `tab:`, `eq:`, `alg:`, `sec:`, `lst:`.
- Citation keys: `Smith.2019`, `Smith.2019a` for a second Smith paper that year.
- Every bib entry needs a provenance record in `.latex-editor/bib-provenance.json`.
- Commit your own changes separately from the author's, with the `[claude]`
  prefix, so the author can review each one as a diff.

## Building

`latexmk` — the `.latexmkrc` sets the output directory and bib backend. In the
editor, Ctrl+S rebuilds and refreshes the PDF tab.
