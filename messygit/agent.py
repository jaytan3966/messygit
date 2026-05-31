from .tool import Tool
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
from .llm import _is_insufficient_balance_or_billing, _insufficient_balance_user_message, _text_from_message

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_TOKENS = 256

class Agent:
    def __init__(self, name: str, system_prompt: str, user_prompt: str, max_iterations: int, tools: list[Tool]):
        self.name = name
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.max_iterations = max_iterations
        self.tools = tools
        self.messages = []

    def run(self, input: str) -> str:
        """Run the agent."""
        client = Anthropic(api_key=resolve_api_key())
        try:
            self.messages.append({"role": "user", "content": input})
            response = None
            for i in range(self.max_iterations):
                response = client.messages.create(
                    model=DEFAULT_MODEL,
                    max_tokens=DEFAULT_MAX_TOKENS,
                    tools=[t.to_schema() for t in self.tools],
                    tool_choice="auto",
                    system=self.system_prompt,
                    messages=self.messages,
                )
                self.messages.append({"role": "assistant", "content": response.content})

                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                if not tool_use_blocks:
                    break

                tool_results = []
                for block in tool_use_blocks:
                    tool = next(t for t in self.tools if t.name == block.name)
                    result = tool.run(**block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
                self.messages.append({"role": "user", "content": tool_results})
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