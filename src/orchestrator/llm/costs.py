"""Running cost estimate per run and the human-confirmed cost ceiling."""

from __future__ import annotations

import threading
from collections.abc import Callable

from orchestrator.config.models import Pricing


class BudgetStop(Exception):
    """The human declined to continue after the run reached its cost ceiling."""


class CostTracker:
    def __init__(
        self,
        pricing: Pricing,
        ceiling_usd: float,
        confirm: Callable[[str], bool],
    ) -> None:
        self.pricing = pricing
        self.ceiling = ceiling_usd
        self.confirm = confirm
        self.total_usd = 0.0
        self._next_threshold = ceiling_usd
        self._lock = threading.Lock()

    def estimate(self, model: str, usage: dict[str, int]) -> float:
        price = self.pricing.models[model]
        per_token = 1_000_000
        return (
            usage.get("input_tokens", 0) * price.input
            + usage.get("output_tokens", 0) * price.output
            + usage.get("cache_creation_input_tokens", 0) * price.cache_write
            + usage.get("cache_read_input_tokens", 0) * price.cache_read
        ) / per_token

    def add(self, model: str, usage: dict[str, int]) -> float:
        cost = self.estimate(model, usage)
        with self._lock:
            self.total_usd += cost
        return cost

    def check_ceiling(self) -> None:
        """Ask the human each time the run crosses another multiple of the ceiling."""
        with self._lock:
            crossed = self.total_usd >= self._next_threshold
            total = self.total_usd
        if not crossed:
            return
        if not self.confirm(f"Run has used ${total:.2f} (ceiling ${self.ceiling:.2f}). Continue?"):
            raise BudgetStop(f"stopped by human at ${total:.2f}")
        with self._lock:
            while self._next_threshold <= self.total_usd:
                self._next_threshold += self.ceiling
