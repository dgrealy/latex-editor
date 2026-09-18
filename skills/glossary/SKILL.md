---
name: glossary
description: Maintain the abbreviations and nomenclature indexes - find acronyms used before they are defined, acronyms defined but never used, and maths symbols missing from the nomenclature list. Use when asked about abbreviations, acronyms, nomenclature, symbols or the notation list.
---

# Keep the indexes honest

You maintain `frontmatter/glossary.tex` (acronyms) and
`frontmatter/nomenclature.tex` (symbols). Both are Claude-owned files, so you
may write their definitions.

## Acronyms

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/glossary_check.py --json
```

Reports acronyms that appear in the author's prose but have no
`\newacronym`, entries defined but never used, and the first use of each so you
can check the document defines it before it leans on it.

Add missing ones as `\newacronym{key}{SHORT}{the expanded form}`. The expansion
is a definition, not prose, so it is yours to write — but keep it to the
standard expansion of the term, and if the correct expansion is genuinely
ambiguous in this field, ask rather than pick one.

## Symbols

Scan the maths for symbols the nomenclature does not list, and list entries no
longer used. Add `\nomenclature{$\alpha$}{thermal diffusivity}` entries, keeping
the units consistent with `siunitx` usage in the text.

Flag, don't guess: if a symbol's meaning is not clear from the surrounding
equations, ask the author what it denotes. A wrong nomenclature entry is worse
than a missing one.

## Consistency

Report — do not fix — where the same quantity appears under two symbols, or one
symbol carries two meanings. Changing which symbol a sentence uses would change
the author's text.

## Finishing

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/claude_commit.py "glossary: define 3 acronyms, drop 1 unused" frontmatter/
```
