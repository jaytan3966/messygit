import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".messygit"
CONFIG_FILE = CONFIG_DIR / "config.json"
ANTHROPIC_ENV_VAR = "ANTHROPIC_API_KEY"

MISSING_API_KEY_MESSAGE = (
    "No Anthropic API key found. Set the ANTHROPIC_API_KEY environment variable, "
    f"or save a key with: messygit config --key <key> (stored in {CONFIG_FILE})."
)


class MissingApiKeyError(RuntimeError):
    """Raised when no API key is available from the environment or config file."""


def save_api_key(key: str):
    CONFIG_DIR.mkdir(exist_ok=True)
    config = {"api_key": key}
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def load_api_key():
    if not CONFIG_FILE.exists():
        return None
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    return config.get("api_key")


def resolve_api_key() -> str:
    """Return API key from ANTHROPIC_API_KEY or ~/.messygit/config.json."""
    env_key = (os.environ.get(ANTHROPIC_ENV_VAR) or "").strip()
    if env_key:
        return env_key
    file_key = load_api_key()
    if file_key and str(file_key).strip():
        return str(file_key).strip()
    raise MissingApiKeyError(MISSING_API_KEY_MESSAGE)


def mask_api_key(key: str | None) -> str:
    """Mask a key for display (e.g. sk-ant-a...x3f2)."""
    if not key:
        return "(not set)"
    key = str(key).strip()
    if len(key) <= 12:
        return "(set)"
    return f"{key[:8]}...{key[-4:]}"

