---
type: regex
target: trace
pattern: 'skills/review'
match: not_contains
weight: 1
---

The `review` skill must NOT have been loaded -- this prompt is not its job,
and a skill that fires for everything is a skill that triggers on nothing.
