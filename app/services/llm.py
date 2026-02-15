"""Shared LLM client with Anthropic / OpenAI / Modal fallback.

Detection order:
1. ANTHROPIC_API_KEY set → "anthropic" (Claude)
2. OPENAI_API_KEY set   → "openai"   (GPT)
3. MODAL_ENDPOINT_URL set → "modal"  (vLLM, OpenAI-compatible)
4. else → "none" (returns empty/existing records)

Modal's vLLM serves an OpenAI-compatible API, so OpenAI and Modal backends
reuse ``openai.AsyncOpenAI``; only ``base_url``, ``api_key``, and ``model`` differ.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from pydantic import BaseModel

from app.config import (
    ANTHROPIC_API_KEY,
    MODAL_ENDPOINT_URL,
    MODAL_MODEL_NAME,
    OPENAI_API_KEY,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# --- backend detection & client init ---

BACKEND: str
_model: str

if ANTHROPIC_API_KEY:
    from anthropic import AsyncAnthropic

    BACKEND = "anthropic"
    _anthropic_client: AsyncAnthropic | None = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    _openai_client = None
    _model = "claude-sonnet-4-5"
elif OPENAI_API_KEY:
    from openai import AsyncOpenAI

    BACKEND = "openai"
    _anthropic_client = None
    _openai_client: Any = AsyncOpenAI(api_key=OPENAI_API_KEY)
    _model = "gpt-5.2"
elif MODAL_ENDPOINT_URL:
    from openai import AsyncOpenAI

    BACKEND = "modal"
    _anthropic_client = None
    _openai_client = AsyncOpenAI(base_url=MODAL_ENDPOINT_URL, api_key="modal")
    _model = MODAL_MODEL_NAME
else:
    BACKEND = "none"
    _anthropic_client = None
    _openai_client = None
    _model = ""

logger.info("LLM backend: %s (model=%s)", BACKEND, _model or "n/a")


def is_available() -> bool:
    """Return True when a real LLM backend is configured."""
    return BACKEND != "none"


def _strip_markdown_fence(raw: str) -> str:
    """Strip optional markdown code fences from LLM output."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return raw


async def raw_structured_completion(
    messages: list[dict[str, Any]],
    schema: dict[str, Any],
    schema_name: str = "response",
) -> str:
    """Request a JSON-schema-constrained completion and return the raw JSON string.

    Use this when the caller does its own parsing/merging (e.g. nemsis_extractor).
    """
    if BACKEND == "anthropic" and _anthropic_client:
        # Claude: embed schema in system prompt, ask for JSON-only response
        system_msg = ""
        user_msgs = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_msgs.append(msg)

        system_with_schema = (
            f"{system_msg}\n\nJSON Schema:\n{json.dumps(schema, indent=2)}"
        )

        response = await _anthropic_client.messages.create(
            model=_model,
            max_tokens=4096,
            system=system_with_schema,
            messages=user_msgs,
        )

        raw = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw += block.text  # type: ignore[union-attr]
        return _strip_markdown_fence(raw)

    if _openai_client is None:
        raise RuntimeError(f"raw_structured_completion called with no client (backend={BACKEND})")

    if BACKEND == "openai":
        response_format: dict[str, Any] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        }
    else:
        # Modal / vLLM
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": schema,
            },
        }

    response = await _openai_client.chat.completions.create(
        model=_model,
        messages=messages,
        response_format=response_format,  # type: ignore[arg-type]
    )
    return response.choices[0].message.content or "{}"


async def structured_completion(
    messages: list[dict[str, Any]],
    response_model: type[T],
    schema_name: str = "response",
) -> T | None:
    """Request a structured completion and return a parsed Pydantic model.

    - Anthropic: embeds schema in prompt, parses raw JSON response
    - OpenAI: uses ``client.beta.chat.completions.parse(response_format=Model)``
    - Modal:  uses JSON-schema constraint + manual ``model_validate_json()``
    """
    if BACKEND == "anthropic" and _anthropic_client:
        raw = await raw_structured_completion(
            messages=messages,
            schema=response_model.model_json_schema(),
            schema_name=schema_name,
        )
        try:
            return response_model.model_validate_json(raw)
        except Exception as e:
            logger.error("Failed to parse %s from Anthropic response: %s", schema_name, e)
            logger.debug("Raw response: %s", raw)
            return None

    if _openai_client is None:
        raise RuntimeError(f"structured_completion called with no client (backend={BACKEND})")

    if BACKEND == "openai":
        response = await _openai_client.beta.chat.completions.parse(
            model=_model,
            messages=messages,
            response_format=response_model,
        )
        return response.choices[0].message.parsed

    # Modal / vLLM path
    raw = await raw_structured_completion(
        messages=messages,
        schema=response_model.model_json_schema(),
        schema_name=schema_name,
    )
    try:
        return response_model.model_validate_json(raw)
    except Exception as e:
        logger.error("Failed to parse %s from Modal response: %s", schema_name, e)
        logger.debug("Raw response: %s", raw)
        return None
