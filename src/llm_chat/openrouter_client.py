"""Thin OpenRouter client for the LLM chat feature.

Stage 0: minimal wrapper around the OpenRouter chat-completions endpoint
(OpenAI-compatible). No streaming, no JSON-mode, no retries beyond a single
network timeout. The goal is to prove the API key + model slug + network path
work end-to-end inside the Streamlit dashboard.
"""

from __future__ import annotations

import logging
import os
from typing import Iterable, Optional

import requests

try:
    import streamlit as st
except Exception:  # pragma: no cover - allows import in non-Streamlit contexts
    st = None  # type: ignore

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Default free model. Override via env var OPENROUTER_MODEL or by passing
# `model=` to chat(). Verify the exact slug at https://openrouter.ai/models
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

# Optional ranking headers recommended by OpenRouter for free-tier traffic.
_APP_REFERER = os.environ.get("OPENROUTER_REFERER", "http://localhost:8501")
_APP_TITLE = os.environ.get("OPENROUTER_TITLE", "Energy Market Analysis")


class OpenRouterError(RuntimeError):
    """Raised for any failure talking to OpenRouter."""


def _get_api_key() -> str | None:
    """Fetch the OpenRouter API key from Streamlit secrets or environment."""
    if st is not None:
        try:
            key = st.secrets.get("OPENROUTER_API_KEY")
            if key:
                return key
        except Exception as e:  # secrets file may simply not exist
            logger.debug("st.secrets lookup failed: %s", e)
    return os.environ.get("OPENROUTER_API_KEY")


def chat(
    messages: Iterable[dict],
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 512,
    timeout: float = 60.0,
    json_mode: bool = False,
    max_retries: int = 2,
) -> str:
    """Send a chat-completion request to OpenRouter and return the assistant text.

    Parameters
    ----------
    messages : iterable of {"role", "content"}
        Standard OpenAI-style chat messages.
    model : str, optional
        OpenRouter model slug. Defaults to ``DEFAULT_MODEL``.
    temperature, max_tokens, timeout
        Standard generation / network knobs.
    json_mode : bool
        When True, request ``response_format={"type": "json_object"}``.
        Some free models ignore this; callers must still parse defensively.
    max_retries : int
        Retries on HTTP 429 / 5xx with exponential backoff. Applies per call.
    """
    import time as _time

    api_key = _get_api_key()
    if not api_key:
        raise OpenRouterError(
            "OPENROUTER_API_KEY is not configured. Set it as an environment "
            "variable or in .streamlit/secrets.toml."
        )

    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": list(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": _APP_REFERER,
        "X-Title": _APP_TITLE,
    }

    last_err: Optional[str] = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout,
            )
        except requests.RequestException as e:
            last_err = f"Network error: {e}"
            if attempt < max_retries:
                _time.sleep(1.5 * (2 ** attempt))
                continue
            raise OpenRouterError(last_err) from e

        if resp.status_code == 200:
            try:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, ValueError) as e:
                raise OpenRouterError(
                    f"Unexpected response shape: {resp.text!r}"
                ) from e

        # Retry on rate limit / server error.
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
            logger.warning(
                "OpenRouter HTTP %d (attempt %d/%d), backing off",
                resp.status_code,
                attempt + 1,
                max_retries + 1,
            )
            _time.sleep(1.5 * (2 ** attempt))
            continue

        try:
            err_body = resp.json()
        except Exception:
            err_body = resp.text
        raise OpenRouterError(f"HTTP {resp.status_code}: {err_body}")

    raise OpenRouterError(last_err or "Unknown error")
