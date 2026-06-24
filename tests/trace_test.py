"""Tests for the `trace` command: how the last agent run is rendered.

We capture output from the shared rich Console (messygit.ui.output.console,
which trace.py and warn() both print to) and assert on the rendered text — no
network or real agent run involved.
"""

import pytest

from messygit.agent.agent import TraceStep
from messygit.commands import trace as tr
from messygit.ui.output import console


@pytest.fixture(autouse=True)
def reset_last_trace():
    """The last run is module-global state; clear it around every test."""
    tr._last = None
    yield
    tr._last = None


def render():
    """Run handle_trace() and return what it printed to the console."""
    with console.capture() as cap:
        tr.handle_trace()
    return cap.get()


# --- empty state ----------------------------------------------------------

def test_no_run_yet_warns():
    out = render()
    assert "No agent run to trace" in out


def test_recorded_but_empty_steps_warns():
    tr.record_trace("changelog", [])
    assert "No agent run to trace" in render()


# --- rendering ------------------------------------------------------------

def test_tool_calls_are_numbered_and_named():
    tr.record_trace("changelog", [
        TraceStep(kind="tool", name="run_git", tool_input={"args": ["tag"]}, result="v0.1.0"),
        TraceStep(kind="tool", name="read_file", tool_input={"path": "README.md"}, result="hi"),
    ])
    out = render()
    assert "1." in out and "2." in out
    assert "run_git" in out and "read_file" in out
    # input is summarized onto the call line
    assert "tag" in out and "README.md" in out


def test_title_counts_only_tool_calls_not_text():
    tr.record_trace("changelog", [
        TraceStep(kind="text", text="thinking out loud"),
        TraceStep(kind="tool", name="run_git", tool_input={"args": ["tag"]}, result="x"),
    ])
    out = render()
    assert "1 tool call" in out  # singular, and excludes the text step
    assert "thinking out loud" in out


def test_label_appears_in_title():
    tr.record_trace("suggest", [
        TraceStep(kind="tool", name="run_git", tool_input={"args": ["log"]}, result="x"),
    ])
    assert "suggest" in render()


def test_tool_result_is_not_parsed_as_markup():
    """Tool output containing rich-markup-like brackets must render literally."""
    tr.record_trace("changelog", [
        TraceStep(kind="tool", name="run_git", tool_input={"args": ["log"]},
                  result="commit abc [scope] feat: thing"),
    ])
    out = render()  # must not raise on the unbalanced/style-like '[scope]'
    assert "[scope]" in out


def test_error_step_renders_result():
    tr.record_trace("changelog", [
        TraceStep(kind="tool", name="run_git", tool_input={"args": ["push"]},
                  result="Invalid git command.", is_error=True),
    ])
    assert "Invalid git command." in render()


# --- _result_line helper --------------------------------------------------

def test_result_line_empty():
    assert tr._result_line("") == ("(no output)", "")


def test_result_line_single_line_no_note():
    assert tr._result_line("all good") == ("all good", "")


def test_result_line_multiline_adds_count_note():
    first, note = tr._result_line("line1\nline2\nline3")
    assert first == "line1"
    assert note == "(+2 more lines)"


def test_result_line_singular_note():
    _, note = tr._result_line("a\nb")
    assert note == "(+1 more line)"


def test_result_line_truncates_long_first_line():
    first, _ = tr._result_line("x" * 1000)
    assert first.endswith("…")
    assert len(first) <= tr._RESULT_LIMIT + 2
