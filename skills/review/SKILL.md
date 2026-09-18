---
name: review
description: Review a LaTeX manuscript for build errors, LaTeX syntax problems, citation and cross-reference integrity, spelling, grammar and clarity, sentence-per-line layout, and nomenclature gaps. Writes a dated report to reviews/. Use when the author asks for a review, a check, a proofread, or asks what is wrong with the document before submitting.
---

# Review a manuscript

Produce one report at `reviews/<YYYY-MM-DD>.md`. Everything in it is either a
machine finding or a **suggestion for the author to act on**. You never edit the
prose yourself, so every language point must be written so the author can apply
it by typing: give `file:line`, the current sentence, and your proposed
replacement.

Run the checks first, then write the report. Do not summarise from memory.

## 1. Open blockers — always first

Read `.latex-editor/blockers.md`. Anything unresolved goes at the top of the
report, because a blocker the author never sees is a blocker that becomes a
problem at submission.

## 2. Build

```
${CLAUDE_PLUGIN_ROOT}/scripts/../scripts/log_parse.py build/<main>.log
```
Build first if there is no log (see the `compile` skill). Report errors, missing
packages, undefined references and citations, duplicate labels, and the worst
overfull boxes — an overfull `\hbox` is text sitting in the margin.

## 3. LaTeX syntax

Run `chktex -q -n 2 -n 24` over the `.tex` files if it is installed. If it is
not, say so in the report rather than skipping the section silently.

## 4. Citations and cross-references

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ref_check.py --root . --bib <bib> --json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bib_lint.py <bib> --provenance .latex-editor/bib-provenance.json
```
Report broken references, citations with no entry, duplicate and unused labels,
labels whose prefix does not match what they label, and every malformed or
**unverified** bib entry. An unverified entry is an error, not a nit: it means
the metadata was never checked against the publisher.

## 5. Spelling

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/spellcheck.py
```
This runs over the prose stream only, so it never flags a citation key or a
macro. Genuine technical terms belong in `.latex-editor/dictionary.txt` — offer
to add them, and add them only when the author agrees.

## 6. Grammar, clarity and consistency

Read the prose yourself. Look for: sentences that carry two claims, undefined
terms, tense drift between sections, hedging that hides a result, inconsistent
naming of the same quantity, and paragraphs whose first sentence does not state
their point. For each, write:

```
sections/methods.tex:42
  now:      The sample was then cooled and it was measured with the device.
  suggest:  The sample was cooled and measured with a <name> thermometer.
  why:      two clauses, and "the device" has not been introduced.
```

Group by file, order by line. Be specific and be brief; a review the author
skims is a review that does nothing.

## 7. Layout

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reflow.py --check <files>
```
Report files that are not one-sentence-per-line. Offer to run the reflow — it
only moves whitespace, and it verifies that it changed no words.

## 8. Notation and nomenclature

Run the `glossary` skill's checks: acronyms used before they are defined,
acronyms defined but never used, and maths symbols that appear in the document
but not in `frontmatter/nomenclature.tex`.

## Finishing

Write the report, then commit it:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/claude_commit.py "review: report for <date>" reviews/<date>.md
```

Tell the author the three things most worth their time, and leave the rest in
the file. Do not fix prose. Do not paraphrase their sentences into the report as
though they were yours.
