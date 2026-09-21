"""The parts of the guard no eval run can reach.

An eval case drives Claude against a real manuscript, which covers the gate's
behaviour but not its edges: what happens when a dependency is missing, when the
marker file is absent, or when the author changes a file outside a tool call.
Those are reachable only by calling the hooks directly, which is what this does.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import config as config_module  # noqa: E402
import session_state  # noqa: E402

SECTION = """\\section{Methods}
The sample was cooled and measured with a thermometer.
"""


def run_hook(name: str, event: dict, cwd: Path, env: dict | None = None):
    """Run a hook the way Claude Code does: JSON on stdin, JSON or nothing out."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / name)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, payload


def decision(payload: dict) -> str | None:
    return (payload.get("hookSpecificOutput") or {}).get("permissionDecision")


def reason(payload: dict) -> str:
    return (payload.get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")


def read_state(project: Path) -> dict:
    return json.loads((project / ".latex-editor" / "state.json").read_text())


def audit_log(project: Path) -> str:
    return (project / ".latex-editor" / "audit.log").read_text()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A minimal latex-editor project: the marker file is what switches hooks on."""
    (tmp_path / ".latex-editor.yml").write_text("project:\n  main: main.tex\n")
    (tmp_path / "sections").mkdir()
    (tmp_path / "sections" / "methods.tex").write_text(SECTION)
    (tmp_path / "bib").mkdir()
    (tmp_path / "bib" / "references.bib").write_text("")
    return tmp_path


def edit_event(path: Path, old: str, new: str, cwd: Path) -> dict:
    return {
        "tool_name": "Edit",
        "cwd": str(cwd),
        "tool_input": {"file_path": str(path), "old_string": old, "new_string": new},
    }


# --- the gate itself, at the hook boundary ----------------------------------

def test_reword_is_denied(project):
    target = project / "sections" / "methods.tex"
    _, out = run_hook("prose_guard.py", edit_event(target, "cooled", "chilled", project), project)
    assert decision(out) == "deny"
    assert "would change the author's prose" in reason(out)


def test_citation_insert_is_allowed(project):
    target = project / "sections" / "methods.tex"
    _, out = run_hook(
        "prose_guard.py",
        edit_event(target, "thermometer.", "thermometer~\\cite{Smith.2019}.", project),
        project,
    )
    assert decision(out) != "deny"


# --- stand-down: no marker file, no opinions --------------------------------

def test_hooks_stand_down_without_the_marker(tmp_path):
    """Outside a latex-editor project the plugin must be inert, so it is safe to
    leave installed everywhere."""
    (tmp_path / "notes.tex").write_text(SECTION)
    _, out = run_hook(
        "prose_guard.py",
        edit_event(tmp_path / "notes.tex", "cooled", "chilled", tmp_path),
        tmp_path,
    )
    assert decision(out) != "deny"

    _, out = run_hook(
        "bash_guard.py",
        {"tool_name": "Bash", "cwd": str(tmp_path),
         "tool_input": {"command": "sed -i s/a/b/ notes.tex"}},
        tmp_path,
    )
    assert decision(out) != "deny"


# --- fail closed ------------------------------------------------------------

def test_missing_pylatexenc_denies_rather_than_waving_through(project, monkeypatch):
    """The guard must fail closed. If it failed open, a machine without the
    dependency would silently stop protecting the manuscript."""
    target = project / "sections" / "methods.tex"
    blocker = project / "sitecustomize.py"
    blocker.write_text(
        "import sys\n"
        "class _Block:\n"
        "    def find_module(self, name, path=None):\n"
        "        if name == 'pylatexenc' or name.startswith('pylatexenc.'):\n"
        "            raise ImportError('pylatexenc blocked for the test')\n"
        "sys.meta_path.insert(0, _Block())\n"
    )
    import os
    env = dict(os.environ, PYTHONPATH=str(project))
    _, out = run_hook("prose_guard.py", edit_event(target, "cooled", "chilled", project),
                      project, env=env)
    assert decision(out) == "deny"
    assert "pip install pylatexenc" in reason(out)


def test_unreadable_file_denies(project):
    target = project / "sections" / "methods.tex"
    target.chmod(0o000)
    try:
        try:
            target.read_text()
        except OSError:
            pass
        else:  # root reads anything, so there is nothing to test here
            pytest.skip("this user can read a mode-000 file")
        _, out = run_hook("prose_guard.py",
                          edit_event(target, "cooled", "chilled", project), project)
    finally:
        target.chmod(0o644)
    assert decision(out) == "deny"
    assert "could not read" in reason(out)


@pytest.mark.parametrize(
    "tool_input, expected",
    [
        ({"file_path": "X", "new_string": "x"}, "no old_string/new_string"),
        ({"file_path": "X", "old_string": "", "new_string": "x"}, "empty old_string"),
    ],
)
def test_undecidable_edits_are_denied(project, tool_input, expected):
    """An edit the guard cannot reconstruct is refused, not guessed at."""
    tool_input = dict(tool_input, file_path=str(project / "sections" / "methods.tex"))
    _, out = run_hook("prose_guard.py",
                      {"tool_name": "Edit", "cwd": str(project), "tool_input": tool_input},
                      project)
    assert decision(out) == "deny"
    assert expected in reason(out)


def test_write_without_content_is_denied(project):
    """With parallel writing off, Write is evaluated again -- and still fails closed."""
    (project / ".latex-editor.yml").write_text("prose:\n  parallel: false\n")
    _, out = run_hook(
        "prose_guard.py",
        {"tool_name": "Write", "cwd": str(project),
         "tool_input": {"file_path": str(project / "sections" / "methods.tex")}},
        project,
    )
    assert decision(out) == "deny"
    assert "carried no file content" in reason(out)


# --- config.owns: which files the guard skips entirely ----------------------

@pytest.mark.parametrize(
    "path, owned",
    [
        ("bib/references.bib", True),
        ("frontmatter/glossary.tex", True),
        ("figures/out/plot.pdf", True),
        ("build/main.log", True),
        ("sections/methods.tex", False),
        ("main.tex", False),
        # A path that merely starts with an owned prefix is not owned.
        ("bibliography/notes.tex", False),
        ("sections/bib/notes.tex", False),
        # Outside the project root entirely.
        ("../elsewhere/methods.tex", False),
    ],
)
def test_config_owns(project, path, owned):
    """owns() decides which files the guard waves through without looking. A bug
    here opens a hole in the plugin's central promise and nothing else notices."""
    cfg = config_module.load(project)
    assert cfg is not None
    assert cfg.owns(project / path) is owned, path


def test_claude_owned_tex_is_not_guarded(project):
    """frontmatter/ is Claude's, so prose there is Claude's to change."""
    frontmatter = project / "frontmatter"
    frontmatter.mkdir()
    target = frontmatter / "glossary.tex"
    target.write_text("Some words that would otherwise be protected.\n")
    _, out = run_hook("prose_guard.py",
                      edit_event(target, "Some words", "Other words", project), project)
    assert decision(out) != "deny"


# --- drift detection: the author typing in their editor ---------------------

def test_drift_is_detected_and_blocks_the_stop(project):
    """post_tool_audit notices prose that changed without passing the gate, and
    stop_audit will not let the turn end with that unexplained."""
    session_state.reset(config_module.load(project))

    # The author edits the file outside any tool call.
    target = project / "sections" / "methods.tex"
    target.write_text(SECTION.replace("cooled", "chilled"))

    run_hook("post_tool_audit.py",
             {"tool_name": "Bash", "cwd": str(project), "tool_input": {"command": "ls"}},
             project)

    state = json.loads((project / ".latex-editor" / "state.json").read_text())
    assert "sections/methods.tex" in state["pending"]
    assert "author prose changed" in (project / ".latex-editor" / "audit.log").read_text()

    _, out = run_hook("stop_audit.py", {"cwd": str(project)}, project)
    assert out.get("decision") == "block"
    assert "sections/methods.tex" in out.get("reason", "")


def test_stop_audit_does_not_loop(project):
    """stop_hook_active means we already blocked once; blocking again would trap
    the session."""
    session_state.reset(config_module.load(project))
    (project / "sections" / "methods.tex").write_text(SECTION.replace("cooled", "chilled"))
    run_hook("post_tool_audit.py",
             {"tool_name": "Bash", "cwd": str(project), "tool_input": {"command": "ls"}}, project)
    assert read_state(project)["pending"], "nothing pending; the test would pass for free"

    _, out = run_hook("stop_audit.py", {"cwd": str(project), "stop_hook_active": True}, project)
    assert out.get("decision") != "block"


# --- writing in parallel with Claude ----------------------------------------

def test_whole_file_write_to_author_tex_is_refused(project):
    """A Write is checked against the file as it is and applied a moment later,
    so anything typed in between is lost. Edit is anchored; Write is not."""
    _, out = run_hook(
        "prose_guard.py",
        {"tool_name": "Write", "cwd": str(project),
         "tool_input": {"file_path": str(project / "sections" / "methods.tex"),
                        "content": SECTION}},
        project,
    )
    assert decision(out) == "deny"
    assert "Use Edit instead" in reason(out)


def test_whole_file_write_is_allowed_when_parallel_is_off(project):
    """An author who never types while Claude works keeps the old behaviour."""
    (project / ".latex-editor.yml").write_text("prose:\n  parallel: false\n")
    _, out = run_hook(
        "prose_guard.py",
        {"tool_name": "Write", "cwd": str(project),
         "tool_input": {"file_path": str(project / "sections" / "methods.tex"),
                        "content": SECTION}},
        project,
    )
    assert decision(out) != "deny"


def test_write_to_a_claude_owned_tex_is_untouched(project):
    """frontmatter/ is Claude's; parallel writing does not narrow that."""
    (project / "frontmatter").mkdir()
    target = project / "frontmatter" / "glossary.tex"
    target.write_text("Some words.\n")
    _, out = run_hook(
        "prose_guard.py",
        {"tool_name": "Write", "cwd": str(project),
         "tool_input": {"file_path": str(target), "content": "Other words.\n"}},
        project,
    )
    assert decision(out) != "deny"


def test_write_to_a_new_tex_is_untouched(project):
    """A file that does not exist has no author prose to lose."""
    _, out = run_hook(
        "prose_guard.py",
        {"tool_name": "Write", "cwd": str(project),
         "tool_input": {"file_path": str(project / "sections" / "results.tex"),
                        "content": SECTION}},
        project,
    )
    assert decision(out) != "deny"


def test_author_typing_elsewhere_does_not_block_the_stop(project):
    """The author edits discussion.tex while Claude cites methods.tex. That is
    the whole point of the feature, and it must not end the turn in a block."""
    (project / "sections" / "discussion.tex").write_text(SECTION)
    session_state.reset(config_module.load(project))

    # The author types, outside any tool call.
    (project / "sections" / "discussion.tex").write_text(
        SECTION.replace("cooled", "cooled slowly")
    )
    run_hook("post_tool_audit.py",
             {"tool_name": "Edit", "cwd": str(project),
              "tool_input": {"file_path": str(project / "sections" / "methods.tex")}},
             project)

    state = read_state(project)
    assert state["pending"] == []
    assert "author edited sections/discussion.tex" in audit_log(project)

    _, out = run_hook("stop_audit.py", {"cwd": str(project)}, project)
    assert out.get("decision") != "block"


def test_prose_landing_in_the_file_a_tool_wrote_still_blocks(project):
    """The audit must not have been softened into uselessness: prose that appears
    in the very file a tool just wrote is exactly what it exists to catch."""
    session_state.reset(config_module.load(project))
    target = project / "sections" / "methods.tex"
    target.write_text(SECTION.replace("cooled", "chilled"))

    run_hook("post_tool_audit.py",
             {"tool_name": "Edit", "cwd": str(project),
              "tool_input": {"file_path": str(target)}},
             project)

    assert "sections/methods.tex" in read_state(project)["pending"]
    _, out = run_hook("stop_audit.py", {"cwd": str(project)}, project)
    assert out.get("decision") == "block"


def test_guard_approved_repair_is_not_reported_as_drift(project):
    """compare() allows a syntax repair, which recovers author words from markup
    that was swallowing them. The prose fingerprint changes, legitimately."""
    target = project / "sections" / "methods.tex"
    broken = "\\section{Methods}\nThe sample was cooled \\begin{equation} x = 1 and measured.\n"
    repaired = broken.replace("x = 1 ", "x = 1 \\end{equation} ")
    target.write_text(broken)
    session_state.reset(config_module.load(project))

    _, out = run_hook("prose_guard.py",
                      edit_event(target, "x = 1 ", "x = 1 \\end{equation} ", project), project)
    assert decision(out) != "deny", reason(out)

    target.write_text(repaired)  # the tool applies the edit the guard just approved
    run_hook("post_tool_audit.py",
             {"tool_name": "Edit", "cwd": str(project), "tool_input": {"file_path": str(target)}},
             project)

    assert read_state(project)["pending"] == []
    _, out = run_hook("stop_audit.py", {"cwd": str(project)}, project)
    assert out.get("decision") != "block"


def test_a_file_with_no_baseline_digest_is_still_watched(project, monkeypatch):
    """fingerprint() returns None for a file it cannot read or parse -- and when
    pylatexenc is missing, for every file. Such a file used to be left out of the
    baseline, where `previous.get(name, digest)` made it compare equal to itself
    forever: prose appearing in it was invisible to the audit from then on."""
    cfg = config_module.load(project)
    monkeypatch.setattr(session_state, "prose_digest", lambda cfg, text: None)
    session_state.reset(cfg)
    monkeypatch.undo()
    assert read_state(project)["prose"]["sections/methods.tex"] == session_state.UNPARSEABLE

    # The file becomes readable again and the audit must now see its prose.
    run_hook("post_tool_audit.py",
             {"tool_name": "Bash", "cwd": str(project), "tool_input": {"command": "ls"}},
             project)
    assert "sections/methods.tex" in read_state(project)["pending"]


@pytest.mark.parametrize(
    "path, transient",
    [
        (".latex-editor/state.json", True),
        (".latex-editor/state.lock", True),
        (".latex-editor/.state.json.4321.tmp", True),
        # The author's and Claude's real work in the same directory.
        (".latex-editor/blockers.md", False),
        (".latex-editor/audit.log", False),
        (".latex-editor/dictionary.txt", False),
        ("sections/methods.tex", False),
        # Same names, wrong place.
        ("state.lock", False),
        ("a/.latex-editor/state.lock", False),
    ],
)
def test_is_transient(path, transient):
    """autocommit asks this before deciding a file is something the author wrote.
    Projects scaffolded before the lock file existed do not gitignore it, so a
    wrong answer here puts the guard's bookkeeping in an [author] commit."""
    assert session_state.is_transient(path) is transient, path


def test_autocommit_does_not_record_the_guards_bookkeeping(project):
    """The provenance record is the point of the whole design: what lands in an
    [author] commit must be the author's writing and nothing else."""
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)

    # A session runs, leaving a lock file and state behind beside a real edit.
    session_state.reset(config_module.load(project))
    session_state.log(config_module.load(project), "something happened")
    (project / "sections" / "methods.tex").write_text(SECTION.replace("cooled", "cooled slowly"))

    run_hook("autocommit.py", {"cwd": str(project)}, project)

    # autocommit makes a separate commit per group, so look at all of them.
    listed = subprocess.run(["git", "log", "--name-only", "--format=", "--all"],
                            cwd=project, capture_output=True, text=True).stdout.split()
    assert "sections/methods.tex" in listed
    assert ".latex-editor/state.json" not in listed
    assert ".latex-editor/state.lock" not in listed

    messages = subprocess.run(["git", "log", "--format=%s"], cwd=project,
                              capture_output=True, text=True).stdout
    assert "[author]" in messages and "[claude]" in messages, messages


def test_concurrent_audits_do_not_corrupt_the_state(project):
    """Two sessions can be open on one manuscript, and three hooks write this file."""
    session_state.reset(config_module.load(project))
    (project / "sections" / "methods.tex").write_text(SECTION.replace("cooled", "chilled"))

    event = json.dumps({"tool_name": "Bash", "cwd": str(project),
                        "tool_input": {"command": "ls"}})
    running = [
        subprocess.Popen([sys.executable, str(SCRIPTS / "post_tool_audit.py")],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, cwd=project)
        for _ in range(8)
    ]
    for proc in running:
        proc.communicate(event)
        assert proc.returncode == 0

    state = read_state(project)  # parses at all, and still holds every key
    assert set(state) >= {"prose", "pending", "approved"}
    assert "sections/methods.tex" in state["pending"]
