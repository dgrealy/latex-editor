---
name: cite
description: Manage references - add entries to the .bib file from a DOI, arXiv id or title, verify and normalise their metadata, keep citation keys consistent, fill in \cite{} commands, and find cited-but-missing or defined-but-uncited entries. Use for anything about references, citations, bibliography or the .bib file.
---

# Manage the bibliography

You own the `.bib` file and every `\cite{}` argument. You do not own the
sentence the citation sits in.

## The rule that matters most here

**Never invent metadata.** If you cannot reach Crossref, arXiv, OpenAlex or the
publisher, you do not write the entry. A fabricated DOI or page range survives
into a submitted manuscript and is worse than a missing reference. When a lookup
fails:

1. Say so in chat, immediately, naming what you tried.
2. Append to `.latex-editor/blockers.md`: the date, the identifier you were
   given, what failed, and what you need from the author.
3. Write no entry, or — if the author explicitly asks for a placeholder — write
   it with a `% UNVERIFIED` comment and a provenance record marked
   `"verified": false`, so `review` keeps flagging it.

## Adding an entry

1. Resolve the identifier: `https://api.crossref.org/works/<doi>`,
   `http://export.arxiv.org/api/query?id_list=<id>`, or OpenAlex by title.
2. Check the returned title and authors actually match what the author asked
   for. A near-miss from a title search is a blocker, not a result.
3. Key it `<FirstAuthorLastname>.<year><disambiguator>`, e.g. `Smith.2019`, and
   `Smith.2019a` for a second Smith paper that year.
4. Normalise: `--` in page ranges, `{}` around acronyms and proper nouns in the
   title so the style cannot lowercase them, journal names spelled consistently
   with the rest of the file, DOI present for anything published.
5. Record provenance in `.latex-editor/bib-provenance.json`:
   `{"Smith.2019": {"source": "crossref", "url": "...", "fetched": "<date>", "verified": true}}`

## Filling citations

You may put `\cite{key}` where the author left `\cite{}` empty, or add one at
the end of a clause. You may not replace the author's words with a citation —
turning "as Smith showed" into "as shown in \cite{Smith.2019}" deletes their
prose and the guard will refuse it.

## Checking

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bib_lint.py <bib> --provenance .latex-editor/bib-provenance.json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ref_check.py --root . --bib <bib>
```

## Finishing

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/claude_commit.py "cite: add Smith.2019, fill 2 citations in methods" <bib> <tex files>
```
