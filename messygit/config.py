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
INVALID_API_KEY_MESSAGE = (
    "Anthropic rejected this API key (invalid, expired, or revoked). "
    "Check that ANTHROPIC_API_KEY is correct, or update the key saved with "
    "`messygit config --key <key>`. Create or rotate keys at "
    "https://console.anthropic.com/settings/keys. "
    "If the key still fails in the console, see https://docs.anthropic.com/en/api/errors "
    "and contact https://support.anthropic.com/."
)

FORBIDDEN_API_KEY_MESSAGE = (
    "Anthropic denied access with this API key (forbidden). "
    "The key may be disabled, lack required permissions, or your account may be restricted. "
    "Review your key and billing at https://console.anthropic.com/. "
    "For access or account issues, see https://docs.anthropic.com/en/api/errors and "
    "https://support.anthropic.com/."
)

class InvalidAnthropicCredentialsError(RuntimeError):
    """Raised when Anthropic returns 401 or 403 for the configured API key."""

ANTHROPIC_INSUFFICIENT_BALANCE_MESSAGE = (
    "Your Anthropic API key is accepted, but the account cannot run API requests right now "
    "because of billing or credit balance. This often means credits are exhausted, a free "
    "tier limit was hit, or payment details need attention—not that the key string is wrong. "
    "Open Plans & Billing to add credits or update payment: https://platform.claude.com/ "
    "If you just purchased credits, wait a few minutes and try again. "
    "For persistent issues, contact Anthropic support at https://support.anthropic.com/ "
    "and include your request ID if one appears below (see "
    "https://docs.anthropic.com/en/api/errors)."
)

class AnthropicInsufficientBalanceError(RuntimeError):
    """Raised when Anthropic returns billing_error, 402, or low-credit style 400 responses."""

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

