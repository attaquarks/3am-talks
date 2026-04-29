"""
Session summary service — generates SOAP-style summaries of therapy conversations.
Runs inline on session end using a direct call to the Colab OpenAI-compatible
LLM endpoint (not via the therapy-persona LLMService).
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("summary-service")


SOAP_SYSTEM = (
    "You are a clinical documentation assistant that produces concise, careful "
    "therapy session summaries in SOAP format. You output valid JSON only, with "
    "no markdown fences and no commentary."
)

SOAP_USER_TEMPLATE = """Produce a SOAP-style summary of the therapy conversation below.

Return JSON with EXACTLY these keys:
{{
  "subjective": "2-4 sentences on what the patient reported.",
  "objective": "2-4 sentences on observable data: mood, engagement, behavior.",
  "assessment": "2-4 sentences of clinical impression. Use hedged language.",
  "plan": "2-4 sentences on recommended next steps / techniques / follow-ups.",
  "themes": ["short", "tag", "list"],
  "action_items": ["short actionable items"],
  "mood_trajectory": "improving | stable | declining | mixed"
}}

Rules:
- Never diagnose; use "reports", "appears", "may indicate".
- Preserve confidentiality — no invented details.

CONVERSATION:
{transcript}
"""


PREP_SYSTEM = (
    "You are a clinical prep assistant that produces concise pre-consult briefs. "
    "You output valid JSON only, with no markdown fences and no commentary."
)

PREP_USER_TEMPLATE = """From the patient data below, write a one-page pre-consult brief for the therapist.

Return JSON:
{{
  "top_concerns": ["..."],
  "recent_shifts": "1-2 sentences on what changed",
  "unresolved_topics": ["..."],
  "suggested_focus": "1-2 sentences",
  "risk_notes": "1 sentence; 'none noted' if clean"
}}

PATIENT DATA:
{context}
"""


def _messages_to_transcript(messages: List[Dict[str, Any]], max_chars: int = 6000) -> str:
    lines: List[str] = []
    for m in messages:
        role = m.get("role") or ("user" if m.get("is_user") else "assistant")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        label = "Patient" if role == "user" else "Ella"
        lines.append(f"{label}: {content}")
    transcript = "\n".join(lines)
    if len(transcript) > max_chars:
        transcript = transcript[-max_chars:]
    return transcript


def _extract_json(raw: str) -> Optional[dict]:
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


from ai_layer.llm_client import post_chat_completion, _resolve_endpoints


# Module-level HTTP client with connection pooling (reused across calls)
_llm_client: Optional[httpx.Client] = None


def _get_llm_client() -> httpx.Client:
    global _llm_client
    if _llm_client is None:
        _llm_client = httpx.Client(timeout=60.0)
    return _llm_client


def _call_llm(system_prompt: str, user_prompt: str, *, max_tokens: int = 700, temperature: float = 0.2) -> str:
    if not _resolve_endpoints():
        raise RuntimeError("No LLM endpoint configured (LLM_PRIMARY_URL / COLAB_API_URL)")
    payload = {
        "model": "psychocounsel",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    resp = post_chat_completion(payload, client=_get_llm_client())
    body = resp.json()
    return body.get("choices", [{}])[0].get("message", {}).get("content", "") or ""


def generate_soap_summary(llm_service, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a SOAP summary. `llm_service` is accepted for API compatibility but
    the call goes direct to Colab since this is non-persona documentation.
    Never raises — returns a skeleton on failure.
    """
    transcript = _messages_to_transcript(messages)
    if not transcript.strip():
        return _empty_summary("empty-conversation")

    try:
        raw = _call_llm(SOAP_SYSTEM, SOAP_USER_TEMPLATE.format(transcript=transcript), max_tokens=700, temperature=0.2)
    except Exception as exc:
        logger.warning(f"Summary LLM call failed: {exc}")
        return _empty_summary(f"llm-error")

    parsed = _extract_json(raw or "")
    if not parsed:
        return {
            "subjective": None,
            "objective": None,
            "assessment": (raw or "")[:2000] or "AI summary unavailable.",
            "plan": None,
            "themes": [],
            "action_items": [],
            "mood_trajectory": None,
            "generated_by": "psychocounsel",
            "generated_at": datetime.utcnow().isoformat(),
        }
    return {
        "subjective": parsed.get("subjective"),
        "objective": parsed.get("objective"),
        "assessment": parsed.get("assessment"),
        "plan": parsed.get("plan"),
        "themes": list(parsed.get("themes") or [])[:12],
        "action_items": list(parsed.get("action_items") or [])[:12],
        "mood_trajectory": parsed.get("mood_trajectory"),
        "generated_by": "psychocounsel",
        "generated_at": datetime.utcnow().isoformat(),
    }


def _empty_summary(reason: str) -> Dict[str, Any]:
    return {
        "subjective": None,
        "objective": None,
        "assessment": f"Summary not generated ({reason}).",
        "plan": None,
        "themes": [],
        "action_items": [],
        "mood_trajectory": None,
        "generated_by": "none",
        "generated_at": datetime.utcnow().isoformat(),
    }


def generate_prep_brief(llm_service, context: str) -> Dict[str, Any]:
    try:
        raw = _call_llm(PREP_SYSTEM, PREP_USER_TEMPLATE.format(context=context[:5000]), max_tokens=500, temperature=0.3)
    except Exception as exc:
        logger.warning(f"Prep brief LLM call failed: {exc}")
        return {"top_concerns": [], "recent_shifts": "", "unresolved_topics": [], "suggested_focus": "", "risk_notes": "unavailable"}

    parsed = _extract_json(raw or "")
    if not parsed:
        return {"top_concerns": [], "recent_shifts": (raw or "")[:400], "unresolved_topics": [], "suggested_focus": "", "risk_notes": ""}
    return {
        "top_concerns": list(parsed.get("top_concerns") or [])[:6],
        "recent_shifts": parsed.get("recent_shifts") or "",
        "unresolved_topics": list(parsed.get("unresolved_topics") or [])[:6],
        "suggested_focus": parsed.get("suggested_focus") or "",
        "risk_notes": parsed.get("risk_notes") or "",
    }
