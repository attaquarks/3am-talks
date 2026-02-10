"""
3AM Talks — LiveKit Voice Agent (Ella)
Real-time voice conversation agent using:
  Pipeline: Silero VAD → ElevenLabs Scribe v2 STT → Ollama LLM (psychocounsel) → ElevenLabs TTS

Runs as a standalone process: python src/voice_agent.py dev
"""

import logging
from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import openai, elevenlabs, silero
import httpx

load_dotenv()

logger = logging.getLogger("ella-voice")

# ---------------------------------------------------------------------------
# Ella's therapy persona — matches the text-based LLM persona
# ---------------------------------------------------------------------------

ELLA_SYSTEM_PROMPT = """You are Ella, a warm and empathetic AI therapist for 3AM Talks.
You provide evidence-based psychotherapy to help patients with mental health challenges.

Your approach:
- Use Cognitive Behavioral Therapy (CBT) techniques, especially the downward arrow technique.
- Reflect the patient's feelings and normalize their situation rather than jumping to solutions.
- If the patient shares complicated thoughts, ask a clarifying question to help them articulate concisely.
- If the patient struggles to engage or says they are not ready, give them space without pressing further.
- Be warm, calm, supportive, and non-judgmental at all times.

Therapeutic techniques you know:
- Identify automatic thoughts (spontaneous negative thoughts in response to situations).
- Use the downward arrow technique: ask "If that were true, what would it mean about you?"
- Peel back layers of meaning to reach core beliefs.
- Keep questions focused on meaning, not just facts.

Voice-specific guidelines:
- Keep responses concise — one to two sentences at most.
- Speak naturally and conversationally, as if in a real therapy session.
- Avoid complex formatting, lists, bullet points, or symbols.
- Use a gentle, calm tone. Pause naturally between thoughts.
- Never say you are an AI. You are Ella, a supportive therapist."""


class Ella(Agent):
    """Ella — the 3AM Talks voice therapy agent."""

    def __init__(self) -> None:
        super().__init__(instructions=ELLA_SYSTEM_PROMPT)


# ---------------------------------------------------------------------------
# Voice pipeline configuration
# ---------------------------------------------------------------------------


def build_session() -> AgentSession:
    """Build an AgentSession with the full voice pipeline."""
    return AgentSession(
        vad=silero.VAD.load(),
        stt=elevenlabs.STT(
            model_id="scribe_v2_realtime",
            language_code="en",
        ),
        llm=openai.LLM(
            model="llama3.2:3b",
            base_url="http://127.0.0.1:11434/v1",
            api_key="ollama",
            timeout=httpx.Timeout(connect=30.0, read=120.0, write=10.0, pool=10.0),
        ),
        tts=elevenlabs.TTS(
            model="eleven_multilingual_v2",
        ),
        allow_interruptions=True,
        min_interruption_duration=0.5,
    )


# ---------------------------------------------------------------------------
# Agent entrypoint
# ---------------------------------------------------------------------------


async def entrypoint(ctx: JobContext) -> None:
    """LiveKit agent entrypoint — connects to room and starts Ella."""
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")

    session = build_session()

    await session.start(
        agent=Ella(),
        room=ctx.room,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
