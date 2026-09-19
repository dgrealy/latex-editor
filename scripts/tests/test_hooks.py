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
             {"tool_name": "Edit", "cwd": str(project), "tool_input": {}}, project)

    _, out = run_hook("stop_audit.py", {"cwd": str(project), "stop_hook_active": True}, project)
    assert out.get("decision") != "block"
