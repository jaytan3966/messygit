"""Tests for verbose mode: the persisted setting, the `verbose` toggle command,
and `_drive` choosing live-streaming vs. the spinner.

No network or real agent run — `_drive` is exercised with a fake agent and a
fake spinner so we can assert which path was taken.
"""

import pytest

from messygit import config
from messygit.commands import agent_cmds, app_cmds
from messygit.ui.output import console, err_console


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect config to a throwaway dir so tests never touch ~/.messygit."""
    config_dir = tmp_path / ".messygit"
    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", config_dir / "config.json")
    return config_dir


# --- config: load_verbose / save_verbose ----------------------------------

def test_verbose_defaults_off():
    assert config.load_verbose() is False


def test_verbose_roundtrips():
    config.save_verbose(True)
    assert config.load_verbose() is True
    config.save_verbose(False)
    assert config.load_verbose() is False


def test_verbose_is_coerced_to_bool():
    config.save_verbose(True)
    assert config.load_verbose() is True  # stored/returned as a real bool


def test_verbose_does_not_disturb_other_keys():
    config.save_api_key("sk-ant-keep-me")
    config.save_verbose(True)
    assert config.load_api_key() == "sk-ant-keep-me"


# --- the `verbose` command ------------------------------------------------

def render_verbose(args):
    """Run handle_verbose(args), returning what it printed (stdout + stderr)."""
    with console.capture() as out, err_console.capture() as err:
        app_cmds.handle_verbose(args)
    return out.get() + err.get()


def test_bare_verbose_toggles_from_off_to_on():
    config.save_verbose(False)
    out = render_verbose([])
    assert config.load_verbose() is True
    assert "on" in out.lower()


def test_bare_verbose_toggles_from_on_to_off():
    config.save_verbose(True)
    out = render_verbose([])
    assert config.load_verbose() is False
    assert "off" in out.lower()


@pytest.mark.parametrize("word", ["on", "true", "1", "yes"])
def test_verbose_on_words(word):
    config.save_verbose(False)
    render_verbose([word])
    assert config.load_verbose() is True


@pytest.mark.parametrize("word", ["off", "false", "0", "no"])
def test_verbose_off_words(word):
    config.save_verbose(True)
    render_verbose([word])
    assert config.load_verbose() is False


def test_verbose_invalid_arg_errors_and_does_not_change_state():
    config.save_verbose(True)
    out = render_verbose(["bogus"])
    assert "Usage" in out
    assert config.load_verbose() is True  # unchanged


# --- _drive: live streaming vs. spinner -----------------------------------

class FakeAgent:
    name = "changelog_agent"

    def __init__(self):
        self.run_kwargs = None

    def run(self, prompt, on_step=None):
        self.run_kwargs = {"prompt": prompt, "on_step": on_step}
        return "RESULT"


class FakeSpinner:
    """Stand-in for ui.spinner.spinner; records whether it was entered."""

    def __init__(self):
        self.entered = False

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, *exc):
        return False


def test_drive_verbose_streams_and_skips_spinner(monkeypatch):
    monkeypatch.setattr(agent_cmds, "load_verbose", lambda: True)
    fake_spinner = FakeSpinner()
    monkeypatch.setattr(agent_cmds, "spinner", fake_spinner)

    agent = FakeAgent()
    result = agent_cmds._drive(agent, "do it")

    assert result == "RESULT"
    assert fake_spinner.entered is False           # no spinner in verbose
    assert callable(agent.run_kwargs["on_step"])   # steps are streamed


def test_drive_non_verbose_uses_spinner_and_no_callback(monkeypatch):
    monkeypatch.setattr(agent_cmds, "load_verbose", lambda: False)
    fake_spinner = FakeSpinner()
    monkeypatch.setattr(agent_cmds, "spinner", fake_spinner)

    agent = FakeAgent()
    result = agent_cmds._drive(agent, "do it")

    assert result == "RESULT"
    assert fake_spinner.entered is True            # spinner shown
    assert agent.run_kwargs["on_step"] is None     # nothing streamed
