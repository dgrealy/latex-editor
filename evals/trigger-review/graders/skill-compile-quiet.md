---
type: regex
target: trace
pattern: 'skills/compile'
match: not_contains
weight: 1
---

The `compile` skill must NOT have been loaded -- this prompt is not its job,
and a skill that fires for everything is a skill that triggers on nothing.
