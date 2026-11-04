"""Claude (Anthropic) adapter for the WESAL assistant.

- Manual tool loop over `messages.create`; the tools are the caller's scoped data
  functions, so the model can never read data the user can't.
- No tool can place, approve or modify orders, prices or commissions.
- Server-side refusal fallback (`fallbacks="default"`) is enabled.
- Not exercised against the live API in this repository (no key was provided);
  covered by unit tests with a mocked client. Set AI_PROVIDER=anthropic and
  ANTHROPIC_API_KEY to enable.
"""
from __future__ import annotations

import json
import logging
from typing import Callable

from app.core.config import settings
from app.core.errors import IntegrationUnavailable

log = logging.getLogger("wesal.ai")

SYSTEM_PROMPT = """You are the WESAL assistant, helping users of a Saudi B2B marketplace for groceries and distribution
(stores, sales representatives and supplier companies). Answer in the user's language ({locale}).

Rules:
- Use only the tools to get facts. Never invent prices, stock levels, orders, commissions or numbers.
- If the tools do not provide the answer, say you don't have that information.
- You cannot place, approve, cancel or change orders, prices, authorizations or commissions. When the user wants
  that, explain which screen in WESAL they should use.
- Mention which data you used (for example "based on your orders in the last 30 days").
- Keep answers short and practical. Format amounts in SAR."""


class ClaudeAssistant:
    def __init__(self, client=None):
        if client is None:
            if not settings.anthropic_api_key:
                raise IntegrationUnavailable("ai_not_configured")
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=60, max_retries=2)
        self.client = client

    def ask(self, question: str, locale: str, tools: list[dict], executor: Callable[[str, dict], dict],
            max_rounds: int = 6) -> dict:
        import anthropic

        messages: list = [{"role": "user", "content": question}]
        used_tools: list[str] = []
        for _ in range(max_rounds):
            try:
                response = self.client.beta.messages.create(
                    model=settings.ai_model,
                    max_tokens=settings.ai_max_tokens,
                    system=SYSTEM_PROMPT.format(locale=locale),
                    tools=tools,
                    messages=messages,
                    output_config={"effort": "low"},
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
            except anthropic.RateLimitError:
                raise IntegrationUnavailable("ai_rate_limited")
            except anthropic.AuthenticationError:
                raise IntegrationUnavailable("ai_not_configured")
            except anthropic.APIStatusError as e:
                log.warning("anthropic error %s: %s", e.status_code, e.message)
                raise IntegrationUnavailable("ai_provider_error")
            except anthropic.APIConnectionError:
                raise IntegrationUnavailable("ai_provider_unreachable")

            if response.stop_reason == "refusal":
                return {"answer": None, "refused": True, "tools_used": used_tools}
            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
                continue
            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not tool_calls:
                text = "".join(b.text for b in response.content if b.type == "text").strip()
                return {"answer": text, "refused": False, "tools_used": used_tools,
                        "truncated": response.stop_reason == "max_tokens"}
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for call in tool_calls:
                used_tools.append(call.name)
                try:
                    data = executor(call.name, dict(call.input or {}))
                    results.append({"type": "tool_result", "tool_use_id": call.id,
                                    "content": json.dumps(data, ensure_ascii=False, default=str)[:20000]})
                except Exception as exc:  # noqa: BLE001
                    results.append({"type": "tool_result", "tool_use_id": call.id, "content": f"Error: {exc}", "is_error": True})
            messages.append({"role": "user", "content": results})
        return {"answer": None, "refused": False, "tools_used": used_tools, "truncated": True}


def tool(name: str, description: str, properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {"name": name, "description": description, "strict": True,
            "input_schema": {"type": "object", "properties": properties or {}, "required": required or [],
                             "additionalProperties": False}}
