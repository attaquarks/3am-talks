"""
Crisis detection — two-stage engine.

Stage 1 (fast, always-on): keyword/regex matcher that scans text for acute
risk markers. High recall by design (false positives are caught in stage 2).

Stage 2 (when stage 1 fires): LLM arbiter call against the existing Colab
endpoint to judge intent vs. hyperbole. Kills false positives like "this
exam is killing me" without losing true positives.

Two entry points:
- `scan_messages(messages)` — legacy bulk scan used by therapist SOAP summaries.
  Unchanged behavior — do not modify.
- `detect_crisis(text, ...)` — single-message real-time detector used by
  `/api/chat` and (later) the voice agent.

Design principles:
- False positives on SHOWING helplines are acceptable. False positives on
  SENDING SMS to contacts are not — the LLM arbiter gates CRITICAL.
- If the LLM is unreachable AND stage 1 found CRITICAL keywords, we fail
  to CRITICAL (safer to over-alert than miss a real crisis).
- Keyword-only path is <10ms. Full pipeline with LLM is <2s typical.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SUICIDAL_PATTERNS = [
    r"\bkill(ing)?\s+my\s*self\b",
    r"\bsuicid(e|al)\b",
    r"\bend(ing)?\s+(my|it\s+all)\s+life\b",
    r"\bwant\s+to\s+die\b",
    r"\bno\s+reason\s+to\s+live\b",
    r"\btake\s+my\s+(own\s+)?life\b",
    r"\bcan'?t\s+go\s+on\b",
    r"\bbetter\s+off\s+(dead|without\s+me)\b",
    r"\bgoodbye\s+(forever|world)\b",
]

SELF_HARM_PATTERNS = [
    r"\bcut(ting)?\s+my\s*self\b",
    r"\bself\s*[- ]?harm(ing)?\b",
    r"\bhurt(ing)?\s+my\s*self\b",
    r"\bburn(ing)?\s+my\s*self\b",
]

ABUSE_PATTERNS = [
    r"\bhe\s+hits\s+me\b",
    r"\bshe\s+hits\s+me\b",
    r"\bthey\s+hit\s+me\b",
    r"\bbeat(en|ing)?\s+(me|up)\b",
    r"\babus(es|ed|ing)\s+me\b",
    r"\bafraid\s+of\s+(him|her|them)\b",
]

SUBSTANCE_PATTERNS = [
    r"\boverdos(e|ing)\b",
    r"\bcan'?t\s+stop\s+drinking\b",
    r"\brelapsed\b",
    r"\btoo\s+many\s+pills\b",
]

HARM_OTHERS_PATTERNS = [
    r"\bkill(ing)?\s+(him|her|them|someone)\b",
    r"\bhurt(ing)?\s+(him|her|them|someone)\b",
]

CATEGORIES = [
    ("suicidal_ideation", SUICIDAL_PATTERNS, "critical"),
    ("self_harm", SELF_HARM_PATTERNS, "high"),
    ("abuse", ABUSE_PATTERNS, "high"),
    ("substance_risk", SUBSTANCE_PATTERNS, "medium"),
    ("harm_to_others", HARM_OTHERS_PATTERNS, "critical"),
]

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def scan_messages(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Scan messages for risk markers. Returns:
      {
        "flagged": bool,
        "severity": "low"|"medium"|"high"|"critical",
        "categories": { "suicidal_ideation": [...snippets], ... },
        "snippets": [first few matched text fragments, <=3 per category]
      }
    """
    categories: Dict[str, List[str]] = {}
    worst_severity = "low"

    for msg in messages:
        role = msg.get("role") or ("user" if msg.get("is_user") else "assistant")
        if role != "user":
            continue
        text = (msg.get("content") or "").lower()
        if not text:
            continue

        for name, patterns, severity in CATEGORIES:
            for pat in patterns:
                m = re.search(pat, text, flags=re.IGNORECASE)
                if m:
                    snippet = _excerpt(text, m.start(), m.end())
                    cat_list = categories.setdefault(name, [])
                    if len(cat_list) < 3:
                        cat_list.append(snippet)
                    if SEVERITY_RANK[severity] > SEVERITY_RANK[worst_severity]:
                        worst_severity = severity
                    break  # one match per category per message is enough

    return {
        "flagged": bool(categories),
        "severity": worst_severity if categories else "low",
        "categories": categories,
        "snippets": [s for arr in categories.values() for s in arr[:2]][:6],
    }


def _excerpt(text: str, start: int, end: int, window: int = 60) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    prefix = "..." if left > 0 else ""
    suffix = "..." if right < len(text) else ""
    return f"{prefix}{text[left:right].strip()}{suffix}"


# =============================================================================
# Real-time crisis detection (stage 1 keyword + stage 2 LLM arbiter)
# =============================================================================


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


_RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}


# --- Tiered keyword dictionaries (per original plan + extensions) -----------
# Phrases are matched case-insensitively as regex. Keep these as regex strings
# so we can allow word-boundaries and minor inflection. Grouping by severity.

CRITICAL_PHRASES = [
    # --- Bare core phrases (always dangerous, LLM arbiter handles edge cases) ---
    r"\bkill\s+my\s*self\b",
    r"\bend\s+my\s*self\b",
    r"\bend\s+my\s+life\b",
    r"\btake\s+my\s+(own\s+)?life\b",
    r"\bi\s+want\s+to\s+die\b",
    r"\bwant\s+to\s+end\s+(it|things)\b",
    r"\bbetter\s+off\s+dead\b",
    r"\b(no|any)\s+reason\s+to\s+live\b",
    r"\bno\s+point\s+in\s+(living|going\s+on|being\s+alive)\b",
    # --- "about to" / "going to" variants ---
    r"\babout\s+to\s+(kill|end|hurt)\s+(my\s*self|my\s+life|it\s+all|it)\b",
    r"\bi'?m?\s+going\s+to\s+die\b",
    r"\bgoing\s+to\s+end\s+(it|my\s+life)\b",
    r"\bgoing\s+to\s+hurt\s+my\s*self\b",
    # --- Explicit intent with "I" ---
    r"\bi\s+don'?t\s+want\s+to\s+live\s*(anymore|any\s*more)?\b",
    r"\bi\s+don'?t\s+want\s+to\s+(be\s+here|exist|wake\s+up)\s*(anymore|any\s*more)?\b",
    r"\bi\s+wish\s+i\s+(didn'?t|did\s+not)\s+exist\b",
    r"\bi\s+wish\s+i\s+was\s+never\s+born\b",
    r"\bplanning\s+to\s+(take|end)\s+my\s+(own\s+)?life\b",
    r"\bi\s+have\s+a\s+plan\s+to\s+(die|kill\s+my\s*self)\b",
    r"\bi'?ve\s+decided\s+to\s+end\s+(it|things|my\s+life)\b",
    r"\bthis\s+is\s+(it|the\s+end)\s+for\s+me\b",
    # --- Imminent / temporal ---
    r"\bi\s+won'?t\s+be\s+(here|around|alive)\s+(tomorrow|much\s+longer|anymore|any\s*more)\b",
    r"\bafter\s+tonight\s+(it\s+)?won'?t\s+matter\b",
    r"\bi'?ll\s+do\s+it\s+(tonight|today|now)\b",
    r"\bi'?m\s+ending\s+it\s+(tonight|today|now)\b",
    # --- Method-specific intent ---
    r"\bi'?m\s+going\s+to\s+(jump|hang|shoot|drown)\s*(my\s*self)?\b",
    r"\bi'?m\s+(standing\s+)?on\s+the\s+(bridge|ledge|roof|edge)\b",
    r"\bi\s+have\s+(pills|a\s+rope|a\s+gun|a\s+knife)\s+(and|ready)\b",
    # --- Active attempt (past tense = already happening!) ---
    r"\bi\s+(just\s+)?(took|swallowed|drank)\s+(all\s+)?(the\s+)?(pills|medicine|bleach|poison)\b",
    r"\bi\s+already\s+(cut|hurt|harmed)\s+(my\s*self)\b",
    r"\bi\s+already\s+(took|swallowed)\b",
    r"\bi\s+already\s+(wrote|have)\s+(my\s+)?(goodbye|suicide)\s+(letter|note)\b",
    # --- Farewell / escape / leaving ---
    r"\btell\s+(my|them|everyone).{0,30}(i\s+love|goodbye|i'?m\s+sorry)\b",
    r"\bfree\s+from\s+this\s+(world|life|pain)\b",
    r"\bfinally\s+(be\s+)?free\s+from\s+(this|it\s+all|everything|all\s+this)\b",
    r"\bgetting\s+away\s+from\s+this\s+(life|world)\b",
    r"\bleave\s+this\s+(world|life|earth|place)\b",
    r"\b(go|going)\s+to\s+heaven\b(?!.{0,20}(vacation|trip|movie|show|book|song))",
    r"\bwhen\s+i\s+die\b(?!.*old|.*someday|.*eventually)",
    r"\bready\s+to\s+(go|die|leave)\b(?!.*work|.*home|.*school|.*bed|.*sleep|.*party|.*out)",
    # --- "put me out of my misery" / mercy phrasing ---
    r"\bput\s+me\s+out\s+of\s+my\s+\w*\s*misery\b",
    r"\bend\s+my\s+(suffering|misery|pain)\b",
]

HIGH_PHRASES = [
    r"\bi\s+can'?t\s+take\s+(this|it)\s+anymore\b",
    r"\bnobody\s+would\s+miss\s+me\b",
    r"\bno\s+one\s+(will|would)\s+miss\s+me\b",
    r"\bi'?m\s+a\s+burden\s+to\s+everyone\b",
    r"\bthe\s+world\s+(would\s+be|is)\s+better\s+without\s+me\b",
    r"\bi\s+don'?t\s+deserve\s+to\s+(live|be\s+alive|exist)\b",
    r"\bwhat'?s\s+the\s+point\s+of\s+(living|life|anything)\b",
    r"\bi\s+wish\s+i\s+(was|were)\s+dead\b",
    r"\blife\s+isn'?t\s+worth\s+(it|living)\b",
    r"\bthinking\s+about\s+suicide\b",
    r"\b(been\s+)?thinking\s+of\s+ending\s+(it|my\s+life)\b",
    r"\bcut(ting)?\s+my\s*self\b",
    r"\bself[-\s]?harm(ing)?\b",
    r"\boverdos(e|ing)\b(?!.*prevention)",
    r"\bi\s+(just\s+)?want\s+the\s+pain\s+to\s+stop\s+forever\b",
    r"\bwant\s+the\s+pain\s+to\s+stop\s+forever\b",
    r"\bnobody\s+will\s+miss\s+me\s+when\s+i'?m\s+gone\b",
    r"\bnothing\s+matters\s*(anymore|any\s*more)\b",
    r"\bi\s+can'?t\s+see\s+a\s+future\b",
    r"\bthere'?s?\s+no\s+future\s+for\s+me\b",
    r"\bgiving\s+away\s+(my|all\s+my)\s+(things|stuff|belongings|possessions)\b",
    # --- Desperation / giving up on life ---
    r"\bi'?ve\s+given\s+up+\s+(on\s+)?(life|living|everything|hope)\b",
    r"\bsick\s+of\s+(living|feeling|being\s+alive|this\s+life)\b",
    r"\btired\s+of\s+(living|being\s+alive|existing|this\s+life)\b",
    r"\btake\s+(this|it)\s+all\s+away\b",
    r"\bi\s+can'?t\s+(keep|go\s+on)\s+living\b",
    r"\bthere'?s?\s+no\s+escape\b",
]

MEDIUM_PHRASES = [
    r"\bi\s+feel\s+hopeless\b",
    r"\bi\s+can'?t\s+go\s+on\b",
    r"\beverything\s+is\s+pointless\b",
    r"\bi'?m\s+so\s+tired\s+of\s+(life|living)\b",
    r"\bi\s+just\s+want\s+the\s+pain\s+to\s+stop\b",
    r"\bnobody\s+cares\s+about\s+me\b",
    r"\bi'?m\s+worthless\b",
    r"\bi'?ll\s+never\s+get\s+better\b",
    r"\bgoodbye\s+(forever|world)\b",
    r"\bthere'?s?\s+no\s+(way\s+out|hope)\b",
    r"\bwhy\s+am\s+i\s+even\s+here\b",
    r"\bi\s+have\s+no\s+one\b",
    r"\bi'?m\s+(completely\s+)?alone\s+in\s+this\b",
    # --- Escalating distress ---
    r"\bi'?ve\s+given\s+up+\b",
    r"\bi\s+give\s+up\b",
    r"\bwhat'?s\s+wrong\s+with\s+me\b",
    r"\bi\s+can'?t\s+do\s+this\s+anymore\b",
    r"\bi'?m\s+suffocating\b",
]

# Contextual modifiers — their presence alongside HIGH/MEDIUM phrases bumps
# severity one tier. Things like "tonight", method words, and preparation cues.
CONTEXTUAL_MODIFIERS = [
    r"\btonight\b",
    r"\btoday\b",
    r"\bright\s+now\b",
    r"\balready\s+(have|bought|got)\b",
    r"\bmethod\b",
    r"\bpills\b",
    r"\bbridge\b",
    r"\brope\b",
    r"\bgun\b",
    r"\brazor\b",
    r"\bblade\b",
    r"\bplan\b",
    r"\bgoodbye\s+letter\b",
    r"\bsuicide\s+note\b",
    r"\bgiving\s+away\s+my\s+(things|stuff|belongings)\b",
]

_CRITICAL_RE = [re.compile(p, re.IGNORECASE) for p in CRITICAL_PHRASES]
_HIGH_RE = [re.compile(p, re.IGNORECASE) for p in HIGH_PHRASES]
_MEDIUM_RE = [re.compile(p, re.IGNORECASE) for p in MEDIUM_PHRASES]
_MODIFIER_RE = [re.compile(p, re.IGNORECASE) for p in CONTEXTUAL_MODIFIERS]


@dataclass
class CrisisResult:
    risk_level: RiskLevel
    severity_score: float
    keyword_matches: List[str] = field(default_factory=list)
    ml_scores: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    keyword_tier: str = "none"  # which tier the keyword layer hit
    llm_verdict: Optional[str] = None  # 'intent' | 'hyperbole' | 'unavailable'
    detection_ms: float = 0.0

    @property
    def requires_intervention(self) -> bool:
        return self.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    @property
    def requires_emergency_alert(self) -> bool:
        return self.risk_level == RiskLevel.CRITICAL

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_level"] = self.risk_level.value
        d["timestamp"] = self.timestamp.isoformat()
        d["requires_intervention"] = self.requires_intervention
        d["requires_emergency_alert"] = self.requires_emergency_alert
        return d


def _match_all(regexes: List[re.Pattern], text: str) -> List[str]:
    hits: List[str] = []
    for rx in regexes:
        m = rx.search(text)
        if m:
            hits.append(m.group(0))
    return hits


def keyword_scan(text: str) -> Dict[str, Any]:
    """Stage 1: fast keyword/regex pass. Target <10ms."""
    text = (text or "").strip()
    if not text:
        return {"tier": "none", "matches": [], "modifiers": []}

    crit = _match_all(_CRITICAL_RE, text)
    if crit:
        modifiers = _match_all(_MODIFIER_RE, text)
        return {"tier": "critical", "matches": crit, "modifiers": modifiers}

    high = _match_all(_HIGH_RE, text)
    modifiers = _match_all(_MODIFIER_RE, text)
    if high:
        # High + a contextual modifier (e.g. "tonight", "pills") → escalates
        if modifiers:
            return {"tier": "critical", "matches": high, "modifiers": modifiers}
        return {"tier": "high", "matches": high, "modifiers": modifiers}

    med = _match_all(_MEDIUM_RE, text)
    if med:
        if modifiers:
            return {"tier": "high", "matches": med, "modifiers": modifiers}
        return {"tier": "medium", "matches": med, "modifiers": modifiers}

    return {"tier": "none", "matches": [], "modifiers": modifiers}


# --- Stage 2: LLM arbiter ---------------------------------------------------

_LLM_ARBITER_SYSTEM = (
    "You are a safety classifier for a mental health chatbot. Your ONLY job "
    "is to judge whether a message expresses real self-harm/suicide intent "
    "versus hyperbole, metaphor, third-party discussion, or past-tense "
    "resolved distress. You are NOT a therapist. You do not respond to the "
    "user. Output strict JSON only."
)

_LLM_ARBITER_USER_TEMPLATE = """Analyze this message for self-harm/suicide risk.

Message: {text}

Return strict JSON with these keys:
- intent: boolean — true if the speaker expresses first-person intent, plan, or active desire to harm themselves
- imminence: one of "none", "low", "medium", "high" — how imminent is the risk
- is_hyperbole: boolean — true if the phrasing is figurative ("exam is killing me", "dying of laughter", "traffic was murder")
- is_third_party: boolean — true if talking about someone else, a movie, or news
- reasoning: one short sentence

Examples:
Message: "This exam is killing me"
{{"intent": false, "imminence": "none", "is_hyperbole": true, "is_third_party": false, "reasoning": "Common idiom for academic stress"}}

Message: "I want to kill myself tonight"
{{"intent": true, "imminence": "high", "is_hyperbole": false, "is_third_party": false, "reasoning": "First-person direct statement with timeframe"}}

Message: "My friend is going through a tough time"
{{"intent": false, "imminence": "none", "is_hyperbole": false, "is_third_party": true, "reasoning": "Speaker is discussing someone else"}}

Now classify the message above. Respond with JSON only."""

_LLM_ARBITER_CONTEXT_TEMPLATE = """Analyze the LATEST message for self-harm/suicide risk, considering the conversation history for context.

Conversation history (most recent last):
{history}

LATEST message to classify: {text}

IMPORTANT: Evaluate the latest message in the CONTEXT of the full conversation.
A message like "goodbye", "this is it", "ok thanks", "nvm", "i'm fine now", or
"it feels like freedom" may be benign on its own but extremely dangerous after
expressions of suicidal ideation. Look for escalation patterns: increasing
hopelessness, farewell language, sense of calm after expressing intent to die.

ESCALATION DETECTION RULES:
1. If history contains prior ideation cues (hopelessness, goodbye, plan-making,
   "can't go on", method talk) AND the latest message is short, resigned, or
   eerily calm ("ok", "nvm", "thanks for everything", "goodbye", "i get it now",
   "i feel better") — set escalating=true and classification intent=true.
   Calm resignation AFTER prior ideation is a severity signal, not reassurance.
2. If history shows progression (mild sadness → hopelessness → plan/method talk)
   across recent turns — set escalating=true even if the latest message is mild.
3. A sudden shift to peace/acceptance after deep distress ("it'll all be over
   soon", "i know what i need to do now") is a HIGH-imminence escalation signal.
4. Resume-of-topic: if the user previously mentioned a method (pills, bridge,
   gun, rope) and returns to it casually in the latest message, that is intent
   even if phrased indirectly.

Return strict JSON with these keys:
- intent: boolean — true if, IN CONTEXT, the speaker is expressing or continuing first-person intent/desire to harm themselves
- imminence: one of "none", "low", "medium", "high"
- is_hyperbole: boolean — true only if clearly figurative
- is_third_party: boolean — true if about someone else
- escalating: boolean — true if the conversation shows a worsening trajectory OR calm resignation following prior ideation
- reasoning: one short sentence

Respond with JSON only."""


def _format_history(history: List[Dict[str, str]], max_messages: int = 10) -> str:
    """Format conversation history for the LLM arbiter prompt."""
    recent = history[-max_messages:] if len(history) > max_messages else history
    lines = []
    for msg in recent:
        role = msg.get("role", "user").upper()
        content = (msg.get("content") or "")[:300]
        lines.append(f"[{role}]: {content}")
    return "\n".join(lines)


def llm_arbitrate(
    text: str,
    *,
    history: Optional[List[Dict[str, str]]] = None,
    timeout_seconds: float = 8.0,
) -> Dict[str, Any]:
    """Stage 2: call the existing Colab LLM to judge intent vs. hyperbole.

    When `history` is provided, uses the context-aware template that lets the
    LLM evaluate escalation patterns across the conversation.

    Returns a dict with keys: intent, imminence, is_hyperbole, is_third_party,
    reasoning, available (and `escalating` when history is used). If the LLM is
    unreachable, available=False — caller should treat that as "fail to the
    keyword tier" (safer default).
    """
    import os
    import httpx
    from ai_layer.llm_client import post_chat_completion, _resolve_endpoints

    if not _resolve_endpoints():
        return {"available": False, "reason": "no LLM endpoint configured"}

    if history:
        user_content = _LLM_ARBITER_CONTEXT_TEMPLATE.format(
            history=_format_history(history),
            text=text,
        )
    else:
        user_content = _LLM_ARBITER_USER_TEMPLATE.format(text=text)

    payload = {
        "model": os.getenv("CRISIS_ARBITER_MODEL", "psychocounsel"),
        "messages": [
            {"role": "system", "content": _LLM_ARBITER_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            r = post_chat_completion(payload, client=client)
            data = r.json()
        content = (
            data.get("choices", [{}])[0].get("message", {}).get("content", "")
        )
        parsed = json.loads(content)
        result = {
            "available": True,
            "intent": bool(parsed.get("intent", False)),
            "imminence": str(parsed.get("imminence", "none")).lower(),
            "is_hyperbole": bool(parsed.get("is_hyperbole", False)),
            "is_third_party": bool(parsed.get("is_third_party", False)),
            "reasoning": str(parsed.get("reasoning", ""))[:300],
        }
        if history:
            result["escalating"] = bool(parsed.get("escalating", False))
        return result
    except Exception as exc:
        logger.warning(f"Crisis LLM arbiter unreachable: {exc}")
        return {"available": False, "reason": str(exc)[:200]}


_ROBERTA_GATE = 0.35  # below this, RoBERTa alone does not justify calling the LLM
_ROBERTA_MID = 0.60
_ROBERTA_HIGH = 0.85


def _bump_one_tier(level: RiskLevel) -> RiskLevel:
    order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
    idx = order.index(level)
    return order[min(idx + 1, len(order) - 1)]


def detect_crisis(
    text: str,
    *,
    use_llm: bool = True,
    history: Optional[List[Dict[str, str]]] = None,
    session_has_prior_risk: bool = False,
    roberta_score: Optional[float] = None,
    arbiter_timeout: float = 8.0,
) -> CrisisResult:
    """Run the three-stage pipeline on a single user message.

    Stages:
      1. keyword_scan  — <10ms regex tiers.
      2. RoBERTa       — suicide-class probability (computed if not passed in).
      3. LLM arbiter   — called only when (keyword != none) OR (roberta >= 0.35)
                         OR (session_has_prior_risk). Uses the context-aware
                         template when history is provided.

    Fusion rules are ported from test_crisis_flow.py where the flow hit F1 0.78
    on 132 labeled real messages.

    session_has_prior_risk lifts the fast-exit for follow-up messages in a
    conversation that already fired HIGH/CRITICAL — plugs the escalation FN
    gap (6 of 8 FNs were fast-exits on calm resignation after prior ideation).
    """
    started = time.perf_counter()
    stage1 = keyword_scan(text)
    tier = stage1["tier"]
    matches = stage1["matches"]

    # --- Stage 1.5: RoBERTa (optional; caller may pre-compute) ----------------
    # When the caller disables the LLM entirely (`use_llm=False` — e.g. unit
    # tests or keyword-only mode) we also skip RoBERTa so the result reflects
    # keyword-layer behavior only. RoBERTa without an LLM arbiter produces too
    # many false positives on benign phrases like "goodbye ella".
    if not use_llm and roberta_score is None:
        rob = 0.0
    elif roberta_score is None:
        try:
            from crisis import roberta_client
            rob = roberta_client.score(text)
        except Exception as exc:
            logger.warning(f"RoBERTa score lookup failed: {exc}")
            rob = 0.0
    else:
        rob = float(roberta_score)

    # --- Gate: skip LLM entirely when nothing meaningful triggered ------------
    needs_llm = (
        use_llm
        and (tier != "none" or rob >= _ROBERTA_GATE or session_has_prior_risk)
    )
    llm: Dict[str, Any] = {"available": False}
    if needs_llm:
        llm = llm_arbitrate(text, history=history, timeout_seconds=arbiter_timeout)

    llm_ok = bool(llm.get("available"))
    intent = bool(llm.get("intent")) if llm_ok else False
    hyperbole = bool(llm.get("is_hyperbole")) if llm_ok else False
    third = bool(llm.get("is_third_party")) if llm_ok else False
    escalating = bool(llm.get("escalating")) if llm_ok else False
    imminence = str(llm.get("imminence", "none")).lower() if llm_ok else "none"
    high_imminence = imminence in ("medium", "high")

    final, score, verdict = _fuse(
        tier=tier,
        rob=rob,
        llm_ok=llm_ok,
        intent=intent,
        hyperbole=hyperbole,
        third=third,
        escalating=escalating,
        high_imminence=high_imminence,
        session_has_prior_risk=session_has_prior_risk,
    )

    ml_scores: Dict[str, Any] = {"roberta_suicide": rob}
    if llm_ok:
        ml_scores["llm"] = {
            "intent": intent,
            "imminence": imminence,
            "is_hyperbole": hyperbole,
            "is_third_party": third,
            "escalating": escalating,
            "reasoning": llm.get("reasoning"),
        }
    elif needs_llm:
        ml_scores["llm"] = {"available": False, "reason": llm.get("reason")}

    return CrisisResult(
        risk_level=final,
        severity_score=score,
        keyword_matches=matches,
        ml_scores=ml_scores,
        keyword_tier=tier,
        llm_verdict=verdict,
        detection_ms=(time.perf_counter() - started) * 1000.0,
    )


def _fuse(
    *,
    tier: str,
    rob: float,
    llm_ok: bool,
    intent: bool,
    hyperbole: bool,
    third: bool,
    escalating: bool,
    high_imminence: bool,
    session_has_prior_risk: bool,
) -> tuple[RiskLevel, float, str]:
    """Fusion rule table ported from test_crisis_flow.py.

    Returns (risk_level, severity_score, verdict_tag).
    """
    # ---- Keyword CRITICAL ----------------------------------------------------
    if tier == "critical":
        if llm_ok and (hyperbole or third) and not intent:
            return RiskLevel.HIGH, 0.75, "kw_critical_downgraded_hyperbole"
        verdict = "kw_critical_confirmed" if llm_ok else "kw_critical_llm_unavailable"
        return RiskLevel.CRITICAL, 1.0, verdict

    # ---- Keyword HIGH --------------------------------------------------------
    if tier == "high":
        if llm_ok and intent and high_imminence:
            return RiskLevel.CRITICAL, 0.95, "kw_high_plus_imminent_intent"
        if llm_ok and (hyperbole or third) and not intent:
            return RiskLevel.MEDIUM, 0.35, "kw_high_downgraded_hyperbole"
        if rob >= _ROBERTA_MID:
            if llm_ok and intent:
                return RiskLevel.CRITICAL, 0.9, "kw_high_roberta_mid_intent"
            return RiskLevel.HIGH, 0.75, "kw_high_roberta_mid"
        return RiskLevel.HIGH, 0.7, "kw_high"

    # ---- Keyword MEDIUM ------------------------------------------------------
    if tier == "medium":
        if llm_ok and intent and high_imminence:
            return RiskLevel.HIGH, 0.65, "kw_medium_plus_imminent_intent"
        if llm_ok and (hyperbole or third) and not intent:
            return RiskLevel.LOW, 0.1, "kw_medium_downgraded_hyperbole"
        if rob >= _ROBERTA_HIGH:
            return RiskLevel.HIGH, 0.6, "kw_medium_roberta_high"
        if rob >= _ROBERTA_MID:
            return RiskLevel.MEDIUM, 0.5, "kw_medium_roberta_mid"
        return RiskLevel.MEDIUM, 0.45, "kw_medium"

    # ---- Keyword NONE: RoBERTa-led + sticky session elevation ---------------
    # Sticky elevation: prior HIGH/CRITICAL in this conversation + LLM says
    # escalating/intent → do not fast-exit. This closes the calm-resignation
    # FN gap measured on data.txt.
    if session_has_prior_risk and llm_ok and (intent or escalating):
        level = RiskLevel.CRITICAL if (intent and high_imminence) else RiskLevel.HIGH
        return level, 0.85, "session_escalation"

    if rob >= _ROBERTA_HIGH:
        if llm_ok and intent:
            return RiskLevel.CRITICAL, 0.9, "roberta_high_intent"
        if llm_ok and (hyperbole or third):
            return RiskLevel.LOW, 0.1, "roberta_high_but_hyperbole"
        return RiskLevel.HIGH, 0.7, "roberta_high_no_llm"

    if rob >= _ROBERTA_MID:
        if llm_ok and intent:
            return RiskLevel.HIGH, 0.65, "roberta_mid_intent"
        return RiskLevel.MEDIUM, 0.45, "roberta_mid"

    if rob >= _ROBERTA_GATE:
        if llm_ok and intent and high_imminence:
            return RiskLevel.HIGH, 0.6, "roberta_gate_imminent"
        if llm_ok and intent:
            return RiskLevel.MEDIUM, 0.4, "roberta_gate_intent"
        return RiskLevel.LOW, 0.15, "roberta_gate_no_intent"

    # kw=none, rob<0.35, no prior risk → LOW (fast-exit path; FN-safe due to
    # sticky elevation above).
    return RiskLevel.LOW, 0.0, "fast_exit"


# =============================================================================
# Pre-scripted crisis response (never let the LLM write this)
# =============================================================================

CRISIS_RESPONSE_PK = (
    "I hear you, and I want you to know that what you're feeling right now matters. "
    "You don't have to go through this alone.\n\n"
    "Please consider reaching out to someone who can help:\n\n"
    "📞 Umang Helpline: 0311-7786264 (24/7)\n"
    "📞 Rozan Counseling: 0304-1111741\n"
    "📞 Pakistan Emergency: 1122\n\n"
    "If you've enabled emergency contacts, your loved ones are being notified "
    "so they can support you.\n\n"
    "Would you like to continue talking with me, or would you prefer I help you "
    "connect with a professional?"
)


def crisis_response(country_code: str = "PK", alerts_being_sent: bool = False) -> str:
    """Return the pre-scripted crisis response. Country-specific helplines."""
    # MVP: single PK-focused string. Extend with locale map later — the
    # helplines.json file already supports multi-country lookup if callers
    # want to compose a custom string.
    text = CRISIS_RESPONSE_PK
    if not alerts_being_sent:
        text = text.replace(
            "If you've enabled emergency contacts, your loved ones are being notified "
            "so they can support you.\n\n",
            "",
        )
    return text


def emergency_resources(locale: str = "US") -> Dict[str, Any]:
    """Return crisis hotlines and resources. Locale-scoped."""
    locale = (locale or "US").upper()
    resources = {
        "US": [
            {"label": "988 Suicide & Crisis Lifeline", "contact": "988", "type": "call_text"},
            {"label": "Crisis Text Line", "contact": "Text HOME to 741741", "type": "text"},
            {"label": "SAMHSA National Helpline", "contact": "1-800-662-4357", "type": "call"},
        ],
        "PK": [
            {"label": "Umang Helpline (Pakistan)", "contact": "0311-7786264", "type": "call"},
            {"label": "Rozan Counseling", "contact": "0304-1111741", "type": "call"},
        ],
        "UK": [
            {"label": "Samaritans", "contact": "116 123", "type": "call"},
            {"label": "Shout Crisis Text", "contact": "Text SHOUT to 85258", "type": "text"},
        ],
    }
    return {
        "locale": locale,
        "resources": resources.get(locale, resources["US"]),
        "global": [
            {"label": "International Association for Suicide Prevention", "url": "https://www.iasp.info/resources/Crisis_Centres/"},
        ],
    }
