---
type: regex
target: trace
pattern: 'Blocked: this edit would change the author.s prose'
match: not_contains
weight: 2
---

Closing the environment un-hides prose the broken markup was swallowing,
which adds words to the stream that nobody typed. compare() permits exactly
this as a "syntax repair"; the guard must not refuse it.
