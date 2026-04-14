from anthropic import (
    Anthropic,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
)

from .config import (
    ANTHROPIC_INSUFFICIENT_BALANCE_MESSAGE,
    FORBIDDEN_API_KEY_MESSAGE,
    INVALID_API_KEY_MESSAGE,
    AnthropicInsufficientBalanceError,
    InvalidAnthropicCredentialsError,
    resolve_api_key,
)
from .prompts import COMMIT_SYSTEM_PROMPT, build_user_prompt

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_TOKENS = 256

_BALANCE_ERROR_HINTS = (
    "credit balance",
    "balance too low",
    "balance is too low",
    "too low to access",
    "insufficient credit",
    "no credit",
    "out of credit",
)


def _nested_api_error_type(body: object) -> str | None:
    if not isinstance(body, dict):
        return None
    err = body.get("error")
    if isinstance(err, dict):
        t = err.get("type")
        if isinstance(t, str):
            return t
    return None


def _nested_api_error_message(body: object) -> str:
    if not isinstance(body, dict):
        return ""
    err = body.get("error")
    if isinstance(err, dict) and err.get("message"):
        return str(err["message"])
    return ""


def _combined_error_text(exc: APIStatusError) -> str:
    parts = [exc.message or "", _nested_api_error_message(exc.body)]
    return " ".join(parts).lower()


def _is_insufficient_balance_or_billing(exc: APIStatusError) -> bool:
    if exc.status_code == 402:
        return True
    if _nested_api_error_type(exc.body) == "billing_error":
        return True
    if isinstance(exc, BadRequestError):
        return any(h in _combined_error_text(exc) for h in _BALANCE_ERROR_HINTS)
    return False


def _insufficient_balance_user_message(exc: APIStatusError) -> str:
    msg = ANTHROPIC_INSUFFICIENT_BALANCE_MESSAGE
    rid = exc.request_id
    if rid:
        msg = f"{msg} Request ID for support: {rid}."
    return msg


def _text_from_message(message) -> str:
    parts: list[str] = []
    for block in message.content:
        if getattr(block, "type", None) == "text" and getattr(block, "text", None):
            parts.append(block.text)
    return "\n".join(parts).strip()


def generate_commit_message(staged_changes: str) -> str:
    """Call Claude with the compact staged changes and return a one-line commit message."""
    client = Anthropic(api_key=resolve_api_key())
    try:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=COMMIT_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": build_user_prompt(staged_changes)},
            ],
        )
    except AuthenticationError as e:
        raise InvalidAnthropicCredentialsError(INVALID_API_KEY_MESSAGE) from e
    except PermissionDeniedError as e:
        raise InvalidAnthropicCredentialsError(FORBIDDEN_API_KEY_MESSAGE) from e
    except BadRequestError as e:
        if _is_insufficient_balance_or_billing(e):
            raise AnthropicInsufficientBalanceError(
                _insufficient_balance_user_message(e)
            ) from e
        raise
    except APIStatusError as e:
        if _is_insufficient_balance_or_billing(e):
            raise AnthropicInsufficientBalanceError(
                _insufficient_balance_user_message(e)
            ) from e
        raise
    return _text_from_message(response)
