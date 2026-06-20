"""Session-local token usage tracking.

The Anthropic API does not expose an account credit/balance endpoint, so we
cannot show "tokens remaining". Instead we accumulate the token usage reported
on each API response (`response.usage`) for the life of the process.
"""

from dataclasses import dataclass

BILLING_URL = "https://console.anthropic.com/settings/billing"


@dataclass
class _SessionUsage:
    input: int = 0
    output: int = 0
    requests: int = 0
    cost: float = 0.0  # accumulated USD estimate, priced per call at the model used

    @property
    def total(self) -> int:
        return self.input + self.output

    @property
    def estimated_cost(self) -> float:
        return self.cost

    def record(self, usage, model=None) -> None:
        """Add one API response's usage (input + cache + output tokens).

        If `model` (a models.ModelInfo) is given, accumulate its cost at that
        model's rates, so the estimate stays accurate across model switches.
        """
        if usage is None:
            return
        inp = (
            (getattr(usage, "input_tokens", 0) or 0)
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
            + (getattr(usage, "cache_read_input_tokens", 0) or 0)
        )
        out = getattr(usage, "output_tokens", 0) or 0
        self.input += inp
        self.output += out
        self.requests += 1
        if model is not None:
            self.cost += inp * model.input_cost_per_token + out * model.output_cost_per_token


# Single process-wide tracker.
SESSION_USAGE = _SessionUsage()
