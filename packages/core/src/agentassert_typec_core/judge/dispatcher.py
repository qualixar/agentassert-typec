from __future__ import annotations

import os
import random
import threading
from typing import Any


class JudgeDispatcher:
    """Async LLM-as-judge evaluator for judge_predicate contract operators.

    Architecture:
    - Sampled: only evaluates when random roll < sample_rate (statistical quality control)
    - Cost-capped: per-session cost ceiling, disables sampling when exceeded
    - Fail-safe: ALL failures return (True, 0.0) — never disrupt agent flow
    - Model routing: ds-flash-free (free via OpenRouter) or haiku (cheapest paid)
    - Thread-safe: _lock guards _spent_usd

    Reference: This pattern follows MLflow's BuiltInEvaluator dispatch model
    (mlflow/models/evaluation/default_evaluator.py L275) — isolated evaluator
    classes with fail-safe defaults, dispatched by metric type.
    """

    def __init__(self, cost_ceiling: float = 0.10, model: str = "haiku") -> None:
        self._ceiling = cost_ceiling
        self._model = model
        self._spent_usd: float = 0.0
        self._lock = threading.Lock()
        self._sample_count = 0
        self._failure_count = 0

    def should_sample(self, sample_rate: float) -> bool:
        with self._lock:
            if self._spent_usd >= self._ceiling:
                return False
            self._sample_count += 1
        return random.random() < sample_rate

    async def evaluate(
        self, rubric: str, content: str, session_id: str
    ) -> tuple[bool, float]:
        prompt = (
            f"You are an evaluator. Evaluate if the following response meets the rubric.\n\n"
            f"Rubric: {rubric}\n\n"
            f"Response:\n{content}\n\n"
            f"Answer only: PASS or FAIL"
        )

        try:
            if self._model in ("ds-flash-free", "free"):
                result, cost = await self._call_openrouter_free(prompt)
            else:
                result, cost = await self._call_anthropic_haiku(prompt)

            with self._lock:
                self._spent_usd += cost

            if not result:
                self._failure_count += 1

            return result, cost
        except Exception:
            return True, 0.0

    async def _call_anthropic_haiku(self, prompt: str) -> tuple[bool, float]:
        try:
            import httpx
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                return True, 0.0

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-3-5-haiku-20241022",
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                data = response.json()
                usage = data.get("usage", {})
                input_tokens = usage.get("input_tokens", len(prompt) // 4)
                output_tokens = usage.get("output_tokens", 5)
                cost = (input_tokens * 0.00000025) + (output_tokens * 0.00000125)

                content_text = ""
                for block in data.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "text":
                        content_text += block.get("text", "")
                return ("PASS" in content_text.upper()), cost
        except Exception:
            return True, 0.0

    async def _call_openrouter_free(self, prompt: str) -> tuple[bool, float]:
        try:
            import httpx
            api_key = os.environ.get("OPENROUTER_API_KEY", "")
            if not api_key:
                return True, 0.0

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek/deepseek-chat-v3-0324:free",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 10,
                    },
                )
                data = response.json()
                text = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                    .upper()
                )
                return ("PASS" in text), 0.0
        except Exception:
            return True, 0.0

    @property
    def total_spent(self) -> float:
        with self._lock:
            return self._spent_usd

    @property
    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "samples": self._sample_count,
                "failures": self._failure_count,
                "spent_usd": self._spent_usd,
                "ceiling": self._ceiling,
            }
