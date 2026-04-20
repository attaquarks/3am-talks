"""Per-conversation state engine.

Stores a compact, structured snapshot (topic, emotional tone, user goal,
rolling summary) that is injected into every LLM turn so the model stays
coherent across long conversations instead of rediscovering context from
flat message history.

State lives in-memory on ConversationManager._conv_states. Updated every
4 turns by a non-blocking background asyncio task (`update_conv_state_bg`).
On server restart state is lost; Phase 2b rebuilds it within 4 turns.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from conversation.summary import _call_llm, _extract_json

logger = logging.getLogger(__name__)


@dataclass
class ConversationState:
    conversation_id: str
    topic: str = ""
    emotional_state: str = ""
    user_goal: str = ""
    rolling_summary: str = ""
    last_updated_turn: int = 0
    last_updated_at: float = field(default_factory=time.time)

    def has_any(self) -> bool:
        return bool(self.topic or self.emotional_state or self.user_goal or self.rolling_summary)


_STATE_SYSTEM = (
    "You are a clinical documentation assistant that produces compact "
    "conversation-state snapshots. Output valid JSON only — no markdown "
    "fences, no commentary, no extra keys."
)

_STATE_USER_TEMPLATE = """Read this therapy conversation and produce a compact state snapshot.

Return JSON with EXACTLY these keys (all strings):
{{
  "topic": "1-6 words on the main thing they're discussing (e.g. 'work burnout', 'breakup grief').",
  "emotional_state": "1-4 words on their current emotional tone (e.g. 'anxious', 'calm resignation', 'relieved').",
  "user_goal": "1-8 words on what they seem to want right now (e.g. 'vent', 'get concrete advice', 'feel heard').",
  "rolling_summary": "2-4 sentences summarizing the arc so far. Preserve emotional + topic continuity."
}}

Rules:
- Be concise. Prefer specificity over generic labels.
- If it is very early and you do not know a field, use an empty string.
- Never diagnose; use hedged language in the summary.

CONVERSATION:
{transcript}
"""


def _messages_to_transcript(messages: List[Dict[str, Any]], max_chars: int = 3500) -> str:
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


def compute_conversation_state(
    messages: List[Dict[str, Any]],
    *,
    previous: Optional[ConversationState] = None,
    turn: int = 0,
    conversation_id: str = "",
) -> Optional[ConversationState]:
    """Call the LLM to build (or refresh) a ConversationState for `messages`.

    Returns None on empty transcript or LLM failure. On parse failure, tries
    to keep the previous state rather than wiping it.
    """
    transcript = _messages_to_transcript(messages)
    if not transcript.strip():
        return None

    try:
        raw = _call_llm(
            _STATE_SYSTEM,
            _STATE_USER_TEMPLATE.format(transcript=transcript),
            max_tokens=250,
            temperature=0.2,
        )
    except Exception as exc:
        logger.warning("conv-state LLM call failed: %s", exc)
        return None

    parsed = _extract_json(raw or "")
    if not parsed:
        return previous

    return ConversationState(
        conversation_id=conversation_id or (previous.conversation_id if previous else ""),
        topic=str(parsed.get("topic") or "")[:80],
        emotional_state=str(parsed.get("emotional_state") or "")[:40],
        user_goal=str(parsed.get("user_goal") or "")[:80],
        rolling_summary=str(parsed.get("rolling_summary") or "")[:700],
        last_updated_turn=int(turn or 0),
        last_updated_at=time.time(),
    )


def render_state_for_prompt(state: Optional[ConversationState]) -> str:
    """Build the prompt block that is prepended to context_updates.

    Returns empty string when state is None or has no meaningful fields.
    """
    if state is None or not state.has_any():
        return ""
    topic = state.topic or "unclear"
    emotion = state.emotional_state or "unclear"
    goal = state.user_goal or "unclear"
    summary = state.rolling_summary or "early in the conversation"
    return (
        "CURRENT CONVERSATION STATE (use these to stay coherent — do not "
        "restart the topic or ignore continuity):\n"
        f"- Topic: {topic}\n"
        f"- Emotional tone: {emotion}\n"
        f"- What they seem to want: {goal}\n"
        f"- Summary so far: {summary}"
    )
