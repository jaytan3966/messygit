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

    def run(self, **kwargs: Any) -> Any:
        return self.function(**kwargs)

    def to_schema(self) -> dict[str, Any]:
        """Return an Anthropic-compatible tool schema for API calls."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters,
            },
        }
