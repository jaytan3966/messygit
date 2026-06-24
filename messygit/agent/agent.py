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
from ..models import current_model
from ..usage import SESSION_USAGE

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
        model = current_model()
        messages = []
        try:
            messages.append({"role": "user", "content": user_input})
            response = None
            completed = False
            for i in range(self.max_iterations):
                response = client.messages.create(
                    model=model.id,
                    max_tokens=DEFAULT_MAX_TOKENS,
                    tools=[t.to_schema() for t in self.tools],
                    tool_choice={"type": "auto"},
                    system=self.system_prompt,
                    messages=messages,
                )
                SESSION_USAGE.record(response.usage, model)
                messages.append({"role": "assistant", "content": response.content})

                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                if not tool_use_blocks:
                    completed = True
                    break

                tool_results = []
                for block in tool_use_blocks:
                    tool = next((t for t in self.tools if t.name == block.name), None)
                    if tool is None:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Unknown tool: {block.name!r}.",
                            "is_error": True,
                        })
                        continue
                    try:
                        result = tool.run(**block.input)
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Error running tool {block.name!r}: {e}",
                            "is_error": True,
                        })
                        continue
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
        text = _text_from_message(response)
        if not completed:
            warning = (
                f"⚠️ Stopped after reaching the {self.max_iterations}-iteration "
                "limit before finishing. The task is incomplete — any file the "
                "agent was meant to write may be missing or partial. Try again, "
                "and consider raising the iteration limit if this recurs."
            )
            return f"{warning}\n\n{text}" if text else warning
        return text