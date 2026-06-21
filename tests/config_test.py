import json

import pytest

from messygit import config


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect config/todo files to a temp dir and clear the API-key env var.

    autouse=True means every test in this module runs against a throwaway
    directory instead of the real ~/.messygit, and never sees a key that
    happens to be exported in the developer's (or CI runner's) environment.
    """
    config_dir = tmp_path / ".messygit"
    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(config, "TODO_FILE", config_dir / "todo.md")
    monkeypatch.delenv(config.ANTHROPIC_ENV_VAR, raising=False)
    return config_dir


# --- save_api_key / load_api_key ------------------------------------------

def test_save_then_load_api_key_roundtrips():
    config.save_api_key("sk-ant-secret")
    assert config.load_api_key() == "sk-ant-secret"


def test_save_api_key_strips_surrounding_whitespace():
    config.save_api_key("  sk-ant-secret\n")
    assert config.load_api_key() == "sk-ant-secret"


@pytest.mark.parametrize("bad", ["", "   ", "\n\t"])
def test_save_api_key_rejects_blank(bad):
    with pytest.raises(ValueError):
        config.save_api_key(bad)


def test_load_api_key_returns_none_when_unset():
    assert config.load_api_key() is None


def test_save_api_key_preserves_other_keys():
    config.save_theme("midnight")
    config.save_api_key("sk-ant-secret")
    assert config.load_theme() == "midnight"
    assert config.load_api_key() == "sk-ant-secret"


# --- resolve_api_key ------------------------------------------------------

def test_resolve_prefers_env_over_file(monkeypatch):
    config.save_api_key("file-key")
    monkeypatch.setenv(config.ANTHROPIC_ENV_VAR, "env-key")
    assert config.resolve_api_key() == "env-key"


def test_resolve_falls_back_to_file_when_env_absent():
    config.save_api_key("file-key")
    assert config.resolve_api_key() == "file-key"


def test_resolve_raises_when_env_set_but_blank(monkeypatch):
    monkeypatch.setenv(config.ANTHROPIC_ENV_VAR, "   ")
    with pytest.raises(config.MissingApiKeyError) as exc:
        config.resolve_api_key()
    assert exc.value.args[0] == config.EMPTY_ENV_API_KEY_MESSAGE


def test_resolve_raises_when_nothing_configured():
    with pytest.raises(config.MissingApiKeyError) as exc:
        config.resolve_api_key()
    assert exc.value.args[0] == config.MISSING_API_KEY_MESSAGE


# --- theme / model --------------------------------------------------------

def test_theme_roundtrips():
    config.save_theme("midnight")
    assert config.load_theme() == "midnight"


def test_model_roundtrips():
    config.save_model("claude-haiku-4-5")
    assert config.load_model() == "claude-haiku-4-5"


# --- todo -----------------------------------------------------------------

def test_todo_roundtrips():
    config.save_todo("- ship outbox command\n")
    assert config.load_todo() == "- ship outbox command\n"


def test_load_todo_empty_when_missing():
    assert config.load_todo() == ""


# --- corrupt / malformed config ------------------------------------------

def test_corrupt_config_is_ignored(isolated_config):
    isolated_config.mkdir(parents=True, exist_ok=True)
    (isolated_config / "config.json").write_text("{not valid json")
    # _read_config swallows the error and returns {}, so loads are None.
    assert config.load_api_key() is None
    # ...and a subsequent save overwrites the garbage cleanly.
    config.save_api_key("sk-ant-secret")
    assert json.loads((isolated_config / "config.json").read_text()) == {
        "api_key": "sk-ant-secret"
    }


# --- mask_api_key ---------------------------------------------------------

def test_mask_api_key_hides_middle():
    assert config.mask_api_key("sk-ant-abcdefghijklmnop") == "sk-ant-a...mnop"


@pytest.mark.parametrize("value,expected", [
    (None, "(not set)"),
    ("", "(not set)"),
    ("short", "(set)"),
])
def test_mask_api_key_edge_cases(value, expected):
    assert config.mask_api_key(value) == expected
