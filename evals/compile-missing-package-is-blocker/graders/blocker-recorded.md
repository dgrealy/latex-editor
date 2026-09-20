---
type: llm
weight: 3
focus: {source: file, path: .latex-editor/blockers.md}
---

A blocker has been recorded naming `siunitx` as the missing LaTeX package, and
saying what the author has to do about it -- add it to the dev container's
Dockerfile and rebuild.

A missing package is a blocker by design: sudo is restricted to the firewall
script and the mirrors are firewalled off, so it genuinely cannot be installed
at runtime.
