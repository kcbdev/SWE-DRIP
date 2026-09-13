"""httpx-based OpenRouter client (spec: LLM + image + vision).

Every node calls its routed model directly through this client — there is no
shared gateway payload/template layer. ``transport`` is injectable so tests
capture exact per-call model params with ``httpx.MockTransport``; no live
network ever runs in gates.

A missing ``OPENROUTER_API_KEY`` is a loud ``RuntimeError`` at construction,
never a silent empty key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass
class LLMResult:
    content: Any
    model: str
    tokens_in: int
    tokens_out: int
    raw: dict[str, Any]


class OpenRouterClient:
    """Thin sync client over OpenRouter's OpenAI-compatible endpoints."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 60.0,
    ) -> None:
        key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set — pass api_key explicitly or "
                "export OPENROUTER_API_KEY (see .env.example)"
            )
        self.api_key = key
        self.base_url = (
            base_url or os.environ.get("OPENROUTER_BASE_URL") or OPENROUTER_BASE_URL
        ).rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            transport=transport,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(path, json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"unexpected OpenRouter response shape: {type(data)}")
        return data

    @staticmethod
    def _usage(data: dict[str, Any]) -> tuple[int, int]:
        usage = data.get("usage") or {}
        return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)

    def chat(
        self, model: str, messages: list[dict[str, Any]], **params: Any
    ) -> LLMResult:
        """Chat completion with the EXACT model ID passed — never overridden."""
        data = self._post("/chat/completions", {"model": model, "messages": messages, **params})
        choices = data.get("choices") or [{}]
        content = (choices[0].get("message") or {}).get("content")
        tokens_in, tokens_out = self._usage(data)
        return LLMResult(content=content, model=model, tokens_in=tokens_in, tokens_out=tokens_out, raw=data)

    def vision(
        self, model: str, prompt: str, image_url: str, **params: Any
    ) -> LLMResult:
        """Vision call: text prompt + image URL as multimodal content."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]
        return self.chat(model, messages, **params)

    def image(self, model: str, prompt: str, **params: Any) -> LLMResult:
        """Image generation call with the EXACT model ID passed."""
        data = self._post("/images/generations", {"model": model, "prompt": prompt, **params})
        items = data.get("data") or [{}]
        content = items[0].get("b64_json") or items[0].get("url")
        tokens_in, tokens_out = self._usage(data)
        return LLMResult(content=content, model=model, tokens_in=tokens_in, tokens_out=tokens_out, raw=data)
