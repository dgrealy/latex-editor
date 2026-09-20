---
type: regex
target: trace
pattern: 'Blocked: this edit would change the author.s prose'
match: not_contains
weight: 2
---

Reflowing moves whitespace only, so the guard must allow it.
