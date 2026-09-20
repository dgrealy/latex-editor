---
type: regex
target: trace
pattern: 'Blocked: this edit would change the author.s prose'
match: not_contains
weight: 2
---

The guard must NOT have refused this edit. Inserting a citation leaves the
prose stream identical, so a refusal here is a false positive.

This case is also the suite's canary: if pylatexenc is missing, prose_guard
fails closed and refuses every .tex edit, and this is the case that catches
it.
