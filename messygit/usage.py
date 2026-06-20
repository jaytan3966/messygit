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

    @property
    def total(self) -> int:
        return self.input + self.output

    def record(self, usage) -> None:
        """Add one API response's usage (input + cache + output tokens)."""
        if usage is None:
            return
        self.input += getattr(usage, "input_tokens", 0) or 0
        self.input += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.input += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.output += getattr(usage, "output_tokens", 0) or 0
        self.requests += 1


# Single process-wide tracker.
SESSION_USAGE = _SessionUsage()
