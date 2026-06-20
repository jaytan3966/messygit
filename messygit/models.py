"""Selectable Claude models and their approximate first-party token pricing.

Pricing is USD per million tokens (input / output), used only for the rough
cost estimate shown in the UI. Keyed by a short name used in the `model` command.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    id: str
    label: str
    input_per_mtok: float
    output_per_mtok: float

    @property
    def input_cost_per_token(self) -> float:
        return self.input_per_mtok / 1_000_000

    @property
    def output_cost_per_token(self) -> float:
        return self.output_per_mtok / 1_000_000


MODELS: dict[str, ModelInfo] = {
    "haiku": ModelInfo("claude-haiku-4-5", "Haiku 4.5", 1.0, 5.0),
    "sonnet": ModelInfo("claude-sonnet-4-6", "Sonnet 4.6", 3.0, 15.0),
    "opus": ModelInfo("claude-opus-4-8", "Opus 4.8", 5.0, 25.0),
}
DEFAULT_MODEL_KEY = "haiku"


def resolve_model_key() -> str:
    """Return the saved model key, falling back to the default if unset/invalid."""
    from .config import load_model

    key = load_model()
    return key if key in MODELS else DEFAULT_MODEL_KEY


def current_model() -> ModelInfo:
    return MODELS[resolve_model_key()]
