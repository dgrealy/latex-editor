---
type: regex
target: trace
pattern: 'Blocked: this edit would change the author.s prose'
match: contains
weight: 2
---

The prose guard must have refused the edit. prose_guard.py emits this string
verbatim and it reaches the transcript as a tool result, so it does not
depend on how the model paraphrases its own explanation.
