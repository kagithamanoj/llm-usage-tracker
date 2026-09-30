"""Track LLM token usage and cost across providers.

A small, dependency-free library. Record usage events as they happen,
estimate cost from a built-in pricing table, and summarize or export
for reporting. Prices are per 1K tokens in USD and were last reviewed
2026-09-30; override them with your own table if they drift.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

PRICING_PER_1K_USD = {
    "openai": {
        "gpt-4o": (0.0025, 0.010),
        "gpt-4o-mini": (0.00015, 0.0006),
        "gpt-4.1": (0.002, 0.008),
        "gpt-4.1-mini": (0.0004, 0.0016),
    },
    "anthropic": {
        "claude-opus-4-1": (0.015, 0.075),
        "claude-sonnet-4-5": (0.003, 0.015),
        "claude-haiku-4-5": (0.001, 0.005),
    },
    "google": {
        "gemini-2.5-pro": (0.00125, 0.010),
        "gemini-2.5-flash": (0.0003, 0.0025),
    },
}

DEFAULT_PRICE = (0.002, 0.008)


@dataclass
class UsageEvent:
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    timestamp: float = field(default_factory=time.time)
    label: str = ""

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def cost_usd(self, pricing=PRICING_PER_1K_USD) -> float:
        prompt_price, completion_price = pricing.get(self.provider, {}).get(
            self.model, DEFAULT_PRICE
        )
        return (
            self.prompt_tokens / 1000 * prompt_price
            + self.completion_tokens / 1000 * completion_price
        )

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.cost_usd(), 6),
            "timestamp": self.timestamp,
            "label": self.label,
        }


class UsageTracker:
    """Collect usage events in memory; append to a JSONL log optionally."""

    def __init__(self, log_path: str | None = None):
        self.events: list[UsageEvent] = []
        self.log_path = log_path

    def record(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        label: str = "",
    ) -> UsageEvent:
        if prompt_tokens < 0 or completion_tokens < 0:
            raise ValueError("token counts cannot be negative")
        event = UsageEvent(
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            label=label,
        )
        self.events.append(event)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.to_dict()) + "\n")
        return event

    def summary(self) -> dict:
        total_tokens = sum(e.total_tokens for e in self.events)
        total_cost = sum(e.cost_usd() for e in self.events)
        by_model: dict[str, dict] = {}
        for e in self.events:
            key = f"{e.provider}/{e.model}"
            bucket = by_model.setdefault(
                key, {"calls": 0, "tokens": 0, "cost_usd": 0.0}
            )
            bucket["calls"] += 1
            bucket["tokens"] += e.total_tokens
            bucket["cost_usd"] = round(bucket["cost_usd"] + e.cost_usd(), 6)
        return {
            "calls": len(self.events),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "by_model": by_model,
        }


def load_events(log_path: str) -> list[dict]:
    events = []
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events
