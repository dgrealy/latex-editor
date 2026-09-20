---
type: regex
target: trace
pattern: 'author prose reordered'
match: contains
weight: 2
---

The guard must refuse with the *reordered* reason specifically. A reorder
changes what the reader sees while leaving the word multiset identical, so
this is the case a naive word-set comparison would wave through.
