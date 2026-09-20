---
type: regex
target: trace
pattern: 'cite\{[A-Z][A-Za-z]*\.(19|20)\d\d'
match: not_contains
weight: 1
---

No \cite{} with an invented Author.Year key was written into the manuscript
for a source that could not be verified.
