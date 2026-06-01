from .tool import Tool
from anthropic import (
    Anthropic,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
)

from ..config import (
    FORBIDDEN_API_KEY_MESSAGE,
    INVALID_API_KEY_MESSAGE,
    AnthropicInsufficientBalanceError,
    InvalidAnthropicCredentialsError,
    resolve_api_key,
)
from ..llm import _is_insufficient_balance_or_billing, _insufficient_balance_user_message, _text_from_message

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_TOKENS = 4096

class Agent:
    def __init__(self, name: str, system_prompt: str, max_iterations: int, tools: list[Tool]):
        self.name = name
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.tools = tools

    def run(self, user_input: str) -> str:
        """Run the agent."""
        client = Anthropic(api_key=resolve_api_key())
        messages = []
        try:
            messages.append({"role": "user", "content": user_input})
            response = None
            for i in range(self.max_iterations):
                response = client.messages.create(
                    model=DEFAULT_MODEL,
                    max_tokens=DEFAULT_MAX_TOKENS,
                    tools=[t.to_schema() for t in self.tools],
                    tool_choice={"type": "auto"},
                    system=self.system_prompt,
                    messages=messages,
                )
                messages.append({"role": "assistant", "content": response.content})

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
                messages.append({"role": "user", "content": tool_results})
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
        if not response:
            return "No response from the agent."
        return _text_from_message(response)