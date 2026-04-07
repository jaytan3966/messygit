from anthropic import Anthropic, AuthenticationError, PermissionDeniedError

from .config import (
    FORBIDDEN_API_KEY_MESSAGE,
    INVALID_API_KEY_MESSAGE,
    InvalidAnthropicCredentialsError,
    resolve_api_key,
)
from .prompts import COMMIT_SYSTEM_PROMPT, build_user_prompt

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_TOKENS = 256


def _text_from_message(message) -> str:
    parts: list[str] = []
    for block in message.content:
        if getattr(block, "type", None) == "text" and getattr(block, "text", None):
            parts.append(block.text)
    return "\n".join(parts).strip()


def generate_commit_message(staged_diff: str) -> str:
    """Call Claude with the staged diff and return a one-line commit message."""
    client = Anthropic(api_key=resolve_api_key())
    try:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=COMMIT_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": build_user_prompt(staged_diff)},
            ],
        )
    except AuthenticationError as e:
        raise InvalidAnthropicCredentialsError(INVALID_API_KEY_MESSAGE) from e
    except PermissionDeniedError as e:
        raise InvalidAnthropicCredentialsError(FORBIDDEN_API_KEY_MESSAGE) from e
    return _text_from_message(response)
