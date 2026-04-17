"""
Tests for the real-time crisis detection pipeline.

We run the KEYWORD LAYER ONLY (use_llm=False) so these tests don't require
the Colab endpoint or network. LLM-arbitrated behavior is tested separately
in an integration test with live Colab.
"""
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crisis_service import detect_crisis, keyword_scan, RiskLevel  # noqa: E402


CRITICAL_MESSAGES = [
    # Direct intent — bare core phrases
    "I want to kill myself tonight",
    "im almost about to kill myself",
    "i really think its best i end myself",
    "about to end it all",
    "I've been planning to end my life",
    "I want to die",
    "I'm going to end it tonight",
    "im going to die",
    "this is the end for me",
    "this is it for me",
    "it feels good finally ill be free from this world",
    # Existence / presence
    "i don't want to be here anymore",
    "i don't want to exist",
    "i wish i didn't exist",
    "i wish i was never born",
    # Resolved intent
    "i've decided to end things",
    "i've decided to end it",
    "i want to end it",
    "i want to end things",
    # Imminent
    "i won't be here tomorrow",
    "i won't be around much longer",
    "I'll do it now",
    "i'm ending it tonight",
    # Method-specific
    "i'm going to jump",
    "i'm going to hang myself",
    "i'm on the bridge right now",
    "i'm standing on the ledge",
    # Active attempt (past tense!)
    "i took all the pills",
    "i just swallowed all the medicine",
    "i already cut myself",
    "I already wrote my goodbye letter",
    "I have pills and I'm going to take them all",
    # Farewell / escape
    "tell my family i love them",
    "tell everyone im sorry",
    "getting away from this life",
    # No reason
    "there's no point in living",
    "i have no reason to live",
    "better off dead",
    "free from this pain",
    # Real user phrasing (from testing)
    "Yes thats why i really think its best i end myself",
    "take my life",
    # Leaving / heaven / ready to go
    "im just gonna go leave this world and ill be in heaven",
    "im ready to leave this world",
    "i'm going to heaven",
    "put me out of my misery",
    "put me out of my fucking misery!!",
    "end my suffering",
    "end my pain",
]

# Messages that are ambiguous without context — keyword layer won't catch these.
# They require LLM + conversation history (tested in integration tests).
CONTEXT_DEPENDENT_MESSAGES = [
    "i guess this is it",
    "this is it",
    "goodbye",
    "i feel at peace now",
]

HIGH_RISK_MESSAGES = [
    "I can't take this anymore, what's the point of living",
    "I've been thinking about suicide a lot lately",
    "I just want the pain to stop forever",
    "I'm a burden to everyone around me",
    "I wish I was dead",
    "I've been cutting myself",
    "the world would be better without me",
    "i don't deserve to live",
    "i don't deserve to be alive",
    "nothing matters anymore",
    "i can't see a future",
    "there's no future for me",
    "i'm giving away all my stuff",
    "Nobody will miss me when I'm gone, I'll do it tonight",
    # Desperation / giving up (from testing)
    "ive given up on life",
    "im sick of feeling",
    "im sick of living",
    "theres no escape",
    "take this all away",
    "i can't keep living like this",
    "tired of being alive",
]

SAFE_MESSAGES = [
    "goodbye ella",
    "goodbye",
    "I'm having a bad day at work",
    "This exam is killing me, so stressed",
    "I'm dying of laughter right now",
    "I could kill for a pizza right now",
    "My friend is going through a tough time",
    "I watched a movie about suicide prevention",
    "The traffic was murder today",
    "Work is crushing me lately",
    "I feel tired today",
    "I had a great session with my therapist",
    # False positive guards — must NOT trigger
    "my phone battery is going to die",
    "this show is going to end soon",
    "this is the end of the semester",
    "I'm finally free from exams!",
    "I'm giving away free samples at work",
    "nothing matters in the grand scheme of things",
    # New guards for heaven/leaving/misery patterns
    "i'm going to heaven on a vacation trip",
    "i'm ready to go home",
    "i'm ready to go to bed",
    "im ready to leave school",
    "i give up on this homework",
    "what's wrong with me, I keep forgetting my keys",
    "i can't do this anymore, this math is impossible",
]


# -----------------------------------------------------------------------------
# Keyword layer — CRITICAL messages
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("msg", CRITICAL_MESSAGES)
def test_critical_keyword_detection(msg):
    result = detect_crisis(msg, use_llm=False)
    assert result.risk_level == RiskLevel.CRITICAL, (
        f"Expected CRITICAL for {msg!r}, got {result.risk_level.value} "
        f"(tier={result.keyword_tier}, matches={result.keyword_matches})"
    )
    assert result.severity_score >= 0.9
    assert result.requires_intervention
    assert result.requires_emergency_alert


# -----------------------------------------------------------------------------
# Keyword layer — HIGH messages
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("msg", HIGH_RISK_MESSAGES)
def test_high_keyword_detection(msg):
    result = detect_crisis(msg, use_llm=False)
    assert result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL), (
        f"Expected HIGH or CRITICAL for {msg!r}, got {result.risk_level.value}"
    )
    assert result.severity_score >= 0.6
    assert result.requires_intervention


# -----------------------------------------------------------------------------
# Keyword layer — SAFE messages must NOT trigger intervention
# "goodbye" alone is safe at the keyword level — session escalation (in api.py)
# handles it when there's a prior CRITICAL in the same conversation.
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("msg", SAFE_MESSAGES)
def test_safe_messages_no_intervention(msg):
    result = detect_crisis(msg, use_llm=False)
    assert not result.requires_intervention, (
        f"False positive: {msg!r} flagged as {result.risk_level.value} "
        f"(tier={result.keyword_tier}, matches={result.keyword_matches})"
    )
    assert result.severity_score < 0.5


# -----------------------------------------------------------------------------
# Performance — keyword layer must be <10ms
# -----------------------------------------------------------------------------


def test_keyword_layer_performance():
    """Run 100 keyword scans across mixed messages; p95 should be <10ms."""
    samples = CRITICAL_MESSAGES + HIGH_RISK_MESSAGES + SAFE_MESSAGES
    timings = []
    for _ in range(10):  # 10 passes over the whole set
        for msg in samples:
            start = time.perf_counter()
            keyword_scan(msg)
            timings.append((time.perf_counter() - start) * 1000.0)

    timings.sort()
    p95 = timings[int(len(timings) * 0.95)]
    avg = sum(timings) / len(timings)
    assert p95 < 10.0, f"Keyword layer p95 too slow: {p95:.2f}ms (avg {avg:.2f}ms)"


# -----------------------------------------------------------------------------
# Result shape
# -----------------------------------------------------------------------------


def test_result_serialization():
    r = detect_crisis("I want to kill myself tonight", use_llm=False)
    d = r.to_dict()
    assert d["risk_level"] == "CRITICAL"
    assert d["requires_intervention"] is True
    assert d["requires_emergency_alert"] is True
    assert "timestamp" in d
    assert d["keyword_tier"] == "critical"


def test_empty_message_is_low():
    r = detect_crisis("", use_llm=False)
    assert r.risk_level == RiskLevel.LOW
    assert not r.requires_intervention


# -----------------------------------------------------------------------------
# Contextual modifier escalation
# -----------------------------------------------------------------------------


def test_high_phrase_with_modifier_escalates_to_critical():
    """'I want the pain to stop forever' + 'pills' should escalate HIGH→CRITICAL."""
    r = detect_crisis(
        "I want the pain to stop forever, I have pills ready",
        use_llm=False,
    )
    assert r.risk_level == RiskLevel.CRITICAL


def test_medium_phrase_with_modifier_escalates_to_high():
    r = detect_crisis("I feel hopeless and I have a plan", use_llm=False)
    assert r.risk_level == RiskLevel.HIGH


# -----------------------------------------------------------------------------
# Context-dependent messages — keyword layer correctly returns LOW
# (LLM + history needed; tested in integration tests with live Colab)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("msg", CONTEXT_DEPENDENT_MESSAGES)
def test_context_dependent_messages_are_low_without_history(msg):
    """Ambiguous messages should be LOW when no conversation history is available."""
    r = detect_crisis(msg, use_llm=False)
    assert r.risk_level == RiskLevel.LOW, (
        f"Expected LOW for ambiguous {msg!r} without history, got {r.risk_level.value}"
    )


def test_history_parameter_accepted():
    """Verify detect_crisis accepts history param without error (keyword-only)."""
    history = [
        {"role": "user", "content": "I've been feeling really down lately"},
        {"role": "assistant", "content": "I hear you. Tell me more about what you're experiencing."},
        {"role": "user", "content": "I just don't see a point anymore"},
    ]
    r = detect_crisis("this is it", use_llm=False, history=history)
    assert r.risk_level == RiskLevel.LOW
