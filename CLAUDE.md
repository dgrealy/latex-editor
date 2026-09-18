# latex-editor — working on the plugin itself

This repository is the tooling, not a manuscript. The prose guard does not
apply here; it applies in the document repos that install this plugin.

## The thing to understand first

`scripts/prose_stream.py` is the whole design. It turns a `.tex` file into the
ordered stream of words that belong to the *author*, discarding maths, float
bodies, citation and reference arguments, comments and the preamble. Two files
with the same prose stream say the same thing to a reader. Every guard, the word
count, the spell checker and the reflow tool are built on that one function.

Before changing what counts as prose, add a test. `scripts/tests/` is the
specification: each case asks whether one specific edit would change what a
reader sees. If you widen `CLAUDE_ENVS` or `SKIP_MACROS`, you are handing the
author's words to Claude — be sure that is what you mean.

## How the guard fits together

| Hook | Script | Role |
|---|---|---|
| `SessionStart` | `session_start.py` | Records the prose baseline, states the two rules |
| `PreToolUse` on Edit/Write/MultiEdit | `prose_guard.py` | The real gate: reconstructs the edit and refuses it if prose changes |
| `PreToolUse` on Bash | `bash_guard.py` | Blocks shell writes into `.tex` that would route around the gate |
| `PostToolUse` | `post_tool_audit.py` | Notices prose that changed without passing the gate |
| `Stop` | `stop_audit.py` | Won't let a turn finish with that unexplained |

Guards fail **closed**: if a dependency is missing or a file cannot be parsed,
the edit is refused with an actionable message rather than waved through.

## Conventions

- Scripts are standalone CLIs as well as library modules, with `--json` where a
  skill needs to consume the output.
- Findings are reported, never silently fixed.
- `templates/article/` is copied verbatim by `new_project.py`; anything added
  there ships to every new document.
