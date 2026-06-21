from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    """A tool that an Agent can invoke, wrapping a plain Python function."""

    name: str
    description: str
    function: Callable[..., Any]
    parameters: dict[str, Any] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)

    def run(self, **kwargs: Any) -> Any:
        return self.function(**kwargs)

    def to_schema(self) -> dict[str, Any]:
        """Return an Anthropic-compatible tool schema for API calls."""
        input_schema: dict[str, Any] = {
            "type": "object",
            "properties": self.parameters,
        }
        if self.required:
            input_schema["required"] = self.required
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": input_schema,
        }
