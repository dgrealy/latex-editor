---
type: regex
target: trace
pattern: 'Blocked: this edit would change the author.s prose'
match: not_contains
weight: 1
---

A review reports; it does not edit. The guard should never have needed to
fire, because the skill should not have attempted a prose edit at all.
