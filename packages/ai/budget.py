"""In-memory request budget contracts for gated provider integrations."""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import date
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class BudgetModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RequestBudgetKey(BudgetModel):
    provider: str
    budget_date: date


class RequestBudgetDecision(BudgetModel):
    provider: str
    budget_date: date
    allowed: bool
    used_before: int = Field(ge=0)
    used_after: int = Field(ge=0)
    limit: int = Field(ge=0)
    reason: str = "allowed"


class RequestBudgetStore(Protocol):
    def used(self, key: RequestBudgetKey) -> int:
        """Return current used request count for the key."""

    def increment(self, key: RequestBudgetKey, amount: int) -> int:
        """Increment used request count and return the new value."""


class InMemoryRequestBudgetStore:
    """Side-effect-limited request budget store for tests and local runs."""

    def __init__(self, initial_usage: MutableMapping[RequestBudgetKey, int] | None = None) -> None:
        self._usage: dict[RequestBudgetKey, int] = dict(initial_usage or {})

    def used(self, key: RequestBudgetKey) -> int:
        return self._usage.get(key, 0)

    def increment(self, key: RequestBudgetKey, amount: int) -> int:
        if amount < 0:
            raise ValueError("budget increment amount must be non-negative")
        next_value = self.used(key) + amount
        self._usage[key] = next_value
        return next_value


class RequestBudgetService:
    """Enforce daily per-provider request limits before network calls."""

    def __init__(self, store: RequestBudgetStore | None = None) -> None:
        self._store = store or InMemoryRequestBudgetStore()

    def check_and_consume(
        self,
        *,
        provider: str,
        budget_date: date,
        limit: int,
        amount: int = 1,
    ) -> RequestBudgetDecision:
        if limit < 0:
            raise ValueError("budget limit must be non-negative")
        if amount <= 0:
            raise ValueError("budget request amount must be positive")
        key = RequestBudgetKey(provider=provider, budget_date=budget_date)
        used_before = self._store.used(key)
        if used_before + amount > limit:
            return RequestBudgetDecision(
                provider=provider,
                budget_date=budget_date,
                allowed=False,
                used_before=used_before,
                used_after=used_before,
                limit=limit,
                reason="daily_budget_exceeded",
            )
        used_after = self._store.increment(key, amount)
        return RequestBudgetDecision(
            provider=provider,
            budget_date=budget_date,
            allowed=True,
            used_before=used_before,
            used_after=used_after,
            limit=limit,
        )
