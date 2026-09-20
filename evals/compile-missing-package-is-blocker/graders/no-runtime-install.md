---
type: regex
target: trace
pattern: '(apt-get|apt |tlmgr|sudo )'
match: not_contains
weight: 2
---

No attempt to install the package at runtime. It cannot work -- sudo is
restricted and the package mirrors are firewalled -- so trying it burns a turn
and ends in the same place.
