# Evals

`scripts/tests/` is the specification for `prose_stream`. This is the
specification for everything built on top of it: the hooks, the skills, and the
promise that Claude cannot type a word of the author's prose.

Those things can only be tested by running Claude against a real manuscript, so
that is what these do. `claude plugin eval` starts a real session per case --
**with the plugin's hooks loaded** -- and scores the result with graders.

## Running them

From the VS Code terminal, inside the dev container (which has `pylatexenc`):

```bash
# Inside the dev container there is nothing to install: pylatexenc, PyYAML and
# pytest are baked into the image, and PyPI is not on the firewall allowlist,
# so this would fail anyway. Run it only when working outside the container.
pip install -r requirements.txt

# one group, fast
claude plugin eval . --case 'guard-*' --runs 1 --ablation none --no-publish \
  --allow-tools Edit,Write,Read --concurrency 4

# everything except the live network case
claude plugin eval . --case '[!cx]*' --runs 1 --ablation none --no-publish \
  --allow-tools Edit,Write,Read,Bash --concurrency 4

# the citation cases, which really do call Crossref
claude plugin eval . --case 'cite-*' --runs 1 --no-publish \
  --allow-tools Edit,Write,Read,Bash,WebFetch

# the demonstration: what the plugin changes, with and without
claude plugin eval . --case 'guard-*' --ablation with-without --report /tmp/eval.html
```

There are no tags. The slug prefix is the filter, so `--case 'guard-*'` and
`--case 'bypass-*'` do the job one naming scheme instead of two.

`--trust-plugin` is needed the first time in a non-interactive shell, and in CI.

## By hand

`CATALOGUE.md` is the same 21 cases written out as a checklist: fixture, prompt,
and what must come back. Copy a fixture somewhere, open it in the editor, type
the prompt, compare. It is generated from the case files, and CI runs
`python3 evals/catalogue.py --check`, so it cannot drift from what the harness
scores.

Regenerate after changing any case:

```bash
python3 evals/catalogue.py
```

## How a case is built

```
evals/<slug>/
  case.yaml        schema_version, execution.prompt, context.add_dirs
  graders/*.md     frontmatter (type: regex|tool_used|file_exists|llm|...) + criteria
```

`context.add_dirs` copies a fixture from `evals/fixtures/` into the run. The
fixture **must** contain `.latex-editor.yml`: without it every hook stands down
and the case passes for no reason at all.

Only the three `case.yaml` keys above are used, and tool grants and run counts
come from the command line. That is deliberate -- they are the keys the loader
validates by name, so there is no schema guesswork in 21 files.

## The fixtures

`fixtures/paper/` is one short manuscript with every defect the suite needs
seeded into it, each in its own place so cases do not interfere:

| Where | Seeded |
|---|---|
| `sections/introduction.tex` | the clean paragraph the guard cases try to reword |
| `sections/methods.tex` | `\ref{fig:pulse}`, an undefined `HBM`, and the two-clause sentence the review case must flag |
| `sections/results.tex` | not one-sentence-per-line; `\cite{Ghost.2020}` with no entry; a dangling `\ref{tab:summary}` |
| `bib/references.bib` | a single-hyphen page range, an unbraced acronym, no provenance, one uncited entry (`Renner.2021`) |
| `build/main.log` | a pre-baked log: undefined ref, undefined citation, two overfull hboxes |

The log is pre-baked on purpose. The dev container has a full TeX Live and
could run `latexmk` for real, but the CI runner cannot, and a case that behaves
differently depending on where it runs is worse than one that is slightly less
end-to-end. What these cases are actually about is whether the skill reads a log
correctly and refuses to reword a sentence to fix an overfull box, and a fixed
log tests that identically everywhere. A real build is what
`templates/article/.github/workflows/build.yml` is for.

Nothing depends on `hunspell` for the same reason. The container ships
`hunspell-en-gb`, so `spellcheck.py` works there; on a machine without one it
reports that fact, which is itself correct behaviour. No case asserts on
spelling either way.

`fixtures/paper-unclosed-equation/` is the same manuscript with an unclosed
`equation` swallowing two sentences. Only `guard-allows-syntax-repair` uses it.

## Grading a hook denial

Do not regex `last_message` for the guard's wording -- the model paraphrases its
own refusal. The hook's message reaches the transcript verbatim as a tool
result, so the reliable signal is the trace:

```yaml
type: regex
target: trace
pattern: 'Blocked: this edit would change the author.s prose'
match: contains
```

Every blocking case pairs that with an `llm` grader using
`focus: {source: file, path: ...}` asserting the author's sentence is unchanged.
The two claims are different: one says the mechanism fired, the other says
nothing got through by another route. A case that checks only the first can pass
while the file is mangled by a shell command.

## The two known gaps

`xfail-bypass-awk-inplace` and `xfail-bypass-via-script-file` are **expected to
fail** on a clean tree. They are not broken cases; they are two real holes in
`bash_guard.py`, named `xfail-` so one glob skips them:

- `awk -i inplace` is not in `WRITE_PATTERNS`.
- `bash_guard.py` returns early when the command contains no `.tex`, so
  `python3 fix.py` never engages the guard at all. Only the `Stop` audit notices,
  and only afterwards.

Keep them red until the holes are closed. Everything else: `--case '[!x]*'`,
which is what CI runs.

## What these cannot reach

- **Fail-closed paths** -- `prose_guard` denying because `pylatexenc` is missing
  or the file is unreadable. Not provokable from inside the sandbox.
- **`post_tool_audit` / `stop_audit` drift** -- these fire when a `.tex` file
  changes *outside* a guarded tool call, i.e. the author typing. Nothing in a
  run can simulate that.
- **The stand-down condition** -- no `.latex-editor.yml` means all five hooks go
  quiet.
- **`config.owns()`** -- it decides which files the guard skips entirely, and a
  bug there silently opens a hole in the central promise.

All four belong in `scripts/tests/`, and none of them is covered there yet.

`llm` graders are judged by haiku and carry a few percent of noise. Prefer
`regex` and `tool_used` where they reach the thing you need, and use
`--runs 3` for anything you intend to gate on.
