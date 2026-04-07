from anthropic import Anthropic

from .config import resolve_api_key
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
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=DEFAULT_MAX_TOKENS,
        system=COMMIT_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": build_user_prompt(staged_diff)},
        ],
    )
    return _text_from_message(response)
