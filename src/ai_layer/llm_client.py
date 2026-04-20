"""
OpenAI-compatible LLM client with primary + fallback endpoint support.

Endpoint resolution order (priority, first that's set wins for each slot):
  Primary  : LLM_PRIMARY_URL  / LLM_PRIMARY_API_KEY
  Fallback : LLM_FALLBACK_URL / LLM_FALLBACK_API_KEY
             (falls back to COLAB_API_URL / COLAB_API_KEY for backwards compat)

If LLM_PRIMARY_URL is unset, the fallback is used as the sole endpoint — so
existing deployments that only set COLAB_API_URL keep working unchanged.

Fallback is only triggered on connection-class failures (endpoint unreachable,
DNS failure, 5xx). Read timeouts are NOT retried, so the caller's time budget
is respected — important for the crisis arbiter where a 2x wait would be bad.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("llm-client")


@dataclass
class Endpoint:
    url: str
    api_key: str
    label: str  # "primary" | "fallback"


def _resolve_endpoints() -> List[Endpoint]:
    endpoints: List[Endpoint] = []

    primary_url = (os.getenv("LLM_PRIMARY_URL") or "").strip()
    if primary_url:
        primary_key = (os.getenv("LLM_PRIMARY_API_KEY") or "ollama").strip()
        endpoints.append(Endpoint(url=primary_url, api_key=primary_key, label="primary"))

    fallback_url = (
        os.getenv("LLM_FALLBACK_URL") or os.getenv("COLAB_API_URL") or ""
    ).strip()
    if fallback_url and (not endpoints or fallback_url != endpoints[0].url):
        fallback_key = (
            os.getenv("LLM_FALLBACK_API_KEY")
            or os.getenv("COLAB_API_KEY")
            or "EMPTY"
        ).strip()
        endpoints.append(Endpoint(url=fallback_url, api_key=fallback_key, label="fallback"))

    return endpoints


# Fast-fail errors — retry the next endpoint.
_CONN_EXC = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)


def post_chat_completion(
    payload: Dict[str, Any],
    *,
    client: httpx.Client,
    extra_headers: Optional[Dict[str, str]] = None,
) -> httpx.Response:
    """POST the OpenAI-compatible chat-completion payload, failing over to the
    next endpoint on connection-class errors or 5xx.

    Returns the successful `httpx.Response` (already `raise_for_status`-checked).
    Raises the last exception if every endpoint fails, or `RuntimeError` if no
    endpoint is configured.
    """
    endpoints = _resolve_endpoints()
    if not endpoints:
        raise RuntimeError(
            "No LLM endpoint configured. Set LLM_PRIMARY_URL and/or COLAB_API_URL."
        )

    last_exc: Optional[Exception] = None
    for ep in endpoints:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ep.api_key}",
        }
        if extra_headers:
            headers.update(extra_headers)
        try:
            resp = client.post(ep.url, json=payload, headers=headers)
            resp.raise_for_status()
            if ep.label == "fallback":
                logger.info("LLM served by fallback endpoint.")
            return resp
        except _CONN_EXC as exc:
            last_exc = exc
            logger.warning(
                f"LLM {ep.label} endpoint unreachable ({exc!r}); trying next."
            )
            continue
        except httpx.HTTPStatusError as exc:
            # 5xx -> server is sick, try the next endpoint. 4xx -> our payload
            # is wrong, same request will fail on fallback; bubble up.
            if 500 <= exc.response.status_code < 600:
                last_exc = exc
                logger.warning(
                    f"LLM {ep.label} returned {exc.response.status_code}; trying next."
                )
                continue
            raise

    assert last_exc is not None
    raise last_exc
