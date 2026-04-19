"""
3AM Talks — LiveKit Voice Agent (Ella)
Real-time voice conversation agent using:
  Pipeline: Silero VAD → ElevenLabs STT → (Backend ConversationManager)
            → ElevenLabs TTS (primary) with Edge TTS fallback

Runs as a standalone process: python src/voice_agent.py dev
"""

import json
import logging
from dotenv import load_dotenv
import os
import sys
import asyncio
from pathlib import Path
from typing import AsyncIterable, Optional

# When launched as `python src/voice/agent.py dev`, Python puts src/voice/ on
# sys.path instead of src/, so `from voice.tts_plugin` can't resolve. Add src/
# to sys.path so the import works regardless of invocation style.
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from livekit import rtc
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli, llm
from livekit.agents.llm import ChatChunk, FunctionTool, ChatContext
from livekit.agents import ModelSettings
from livekit.plugins import openai, elevenlabs, silero
from livekit.agents.tts import FallbackAdapter as TTSFallbackAdapter
from voice.tts_plugin import TTS as EdgeTTS
import httpx

load_dotenv()

logger = logging.getLogger("ella-voice")

# ---------------------------------------------------------------------------
# Voice-worker instructions
# ---------------------------------------------------------------------------

ELLA_SYSTEM_PROMPT = (
    "You are the voice transport worker for Ella. "
    "Do not implement independent therapy logic here. "
    "All response generation must come from backend ConversationManager."
)


class Ella(Agent):
    """
    Ella — voice interface around the backend ConversationManager.

    Important: All "thinking" (persona, history, RAG, personality adaptation, persistence)
    must happen in the backend, not in this worker.
    """

    def __init__(
        self,
        *,
        backend_base_url: str,
        voice_agent_secret: str,
        user_id: str,
        conversation_id: str,
        room: Optional[rtc.Room] = None,
    ) -> None:
        super().__init__(instructions=ELLA_SYSTEM_PROMPT)
        self._backend_base_url = backend_base_url.rstrip("/")
        self._voice_agent_secret = voice_agent_secret
        self._user_id = user_id
        self._conversation_id = conversation_id
        self._room = room
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=10.0)
        )

    async def llm_node(
        self,
        chat_ctx: ChatContext,
        tools: list[FunctionTool],
        model_settings: ModelSettings,
    ) -> AsyncIterable[ChatChunk | str]:
        """
        Replace the default LLM call with a backend request.

        The backend routes this through ConversationManager.process_message(), ensuring
        the same persona/history/RAG/personality logic is applied for voice.
        """
        user_text = ""
        try:
            # chat_ctx.messages is a method in newer livekit-agents versions.
            # Fall back to .items filtered by role if needed.
            msgs = chat_ctx.messages() if callable(getattr(chat_ctx, "messages", None)) else getattr(chat_ctx, "messages", [])
            if not msgs:
                msgs = [it for it in getattr(chat_ctx, "items", []) if getattr(it, "role", None) == "user"]
            last = msgs[-1] if msgs else None
            if last and getattr(last, "role", None) == "user":
                if hasattr(last, "text_content"):
                    tc = last.text_content
                    user_text = tc() if callable(tc) else (tc or "")
                else:
                    user_text = getattr(last, "content", "") or ""
                    if isinstance(user_text, list):
                        user_text = " ".join(str(c) for c in user_text if isinstance(c, str))
        except Exception as e:
            logger.error(f"[llm_node] Failed to extract user_text: {type(e).__name__}: {e}")
            user_text = ""

        user_text = (user_text or "").strip()
        logger.info(f"[llm_node] Called with user_text: {user_text!r}")
        if not user_text:
            logger.warning("[llm_node] Empty user_text, returning early")
            return

        try:
            url = f"{self._backend_base_url}/api/voice/chat"
            headers = {"Authorization": f"Bearer {self._voice_agent_secret}"}
            payload = {
                "user_id": self._user_id,
                "conversation_id": self._conversation_id,
                "message": user_text,
            }
            logger.info(f"[llm_node] Calling backend: {url}")
            resp = await self._http.post(url, json=payload, headers=headers)
            logger.info(f"[llm_node] Backend responded: status={resp.status_code}")
            resp.raise_for_status()
            data = resp.json()

            self._conversation_id = data.get("conversation_id") or self._conversation_id

            crisis = data.get("crisis")
            if crisis and crisis.get("detected"):
                await self._publish_crisis(crisis)

            text = (data.get("response") or "").strip()
            logger.info(f"[llm_node] Got response text ({len(text)} chars): {text[:100]!r}")
            if not text:
                raise RuntimeError("Backend returned empty response text")
            yield text
            logger.info(f"[llm_node] Yielded text successfully")
        except Exception as e:
            logger.error(f"[llm_node] Backend voice/chat failed: {type(e).__name__}: {e}")
            raise

    async def _publish_crisis(self, crisis: dict) -> None:
        """Send a crisis event over the LiveKit data channel so the frontend
        can open the same CrisisCountdownModal used by /api/chat."""
        if not self._room or not getattr(self._room, "local_participant", None):
            logger.warning("[crisis] no room/local_participant — cannot publish")
            return
        try:
            payload = json.dumps({"type": "crisis.countdown.start", **crisis})
            await self._room.local_participant.publish_data(
                payload.encode("utf-8"), reliable=True
            )
            logger.info(
                f"[crisis] published risk_level={crisis.get('risk_level')} "
                f"event_id={crisis.get('event_id')}"
            )
        except Exception as exc:
            logger.error(f"[crisis] publish_data failed: {exc}")

    async def on_exit(self) -> None:
        try:
            await self._http.aclose()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Voice pipeline configuration
# ---------------------------------------------------------------------------

def _extract_user_id(identity: str) -> Optional[str]:
    if not identity:
        return None
    if identity.startswith("user-"):
        return identity[len("user-") :]
    return None


async def _wait_for_user(ctx: JobContext, timeout_s: float = 20.0) -> str:
    logger.info(f"[_wait_for_user] Waiting for user to join (timeout={timeout_s}s)")
    deadline = asyncio.get_event_loop().time() + timeout_s
    last_log = 0.0
    while asyncio.get_event_loop().time() < deadline:
        participants = list(ctx.room.remote_participants.values())
        for p in participants:
            identity = getattr(p, "identity", "")
            uid = _extract_user_id(identity)
            logger.info(f"[_wait_for_user] Found participant: identity={identity!r} extracted_uid={uid!r}")
            if uid:
                return uid
            # Fallback: accept any participant identity if not starting with "user-"
            if identity and not identity.startswith("agent"):
                logger.warning(f"[_wait_for_user] Using raw identity as user_id: {identity}")
                return identity
        now = asyncio.get_event_loop().time()
        if now - last_log > 2.0:
            logger.info(f"[_wait_for_user] Still waiting... participants={len(participants)}")
            last_log = now
        await asyncio.sleep(0.2)
    raise TimeoutError("Timed out waiting for a user to join the room")


async def _bootstrap_conversation(backend_base_url: str, voice_agent_secret: str, user_id: str) -> str:
    url = f"{backend_base_url.rstrip('/')}/api/voice/bootstrap"
    headers = {"Authorization": f"Bearer {voice_agent_secret}"}
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
    ) as client:
        resp = await client.post(url, json={"user_id": user_id}, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        conv_id = data.get("conversation_id")
        if not conv_id:
            raise RuntimeError("Backend bootstrap did not return conversation_id")
        return conv_id


def _build_tts():
    """Build TTS with ElevenLabs primary + Edge TTS fallback.

    Key resolution: ELEVEN_TTS_API_KEY → ELEVEN_API_KEY. If neither is set,
    skip ElevenLabs entirely and use Edge alone. Otherwise wrap both in
    FallbackAdapter: the adapter retries ElevenLabs max_retry_per_tts
    times (connection errors / 5xx / auth rejections on exhausted credits)
    before switching to Edge for the remainder of the utterance.
    """
    edge_voice = os.getenv("EDGE_TTS_VOICE", "en-US-JennyNeural")
    edge_tts = EdgeTTS(voice=edge_voice)

    tts_key = os.getenv("ELEVEN_TTS_API_KEY") or os.getenv("ELEVEN_API_KEY")
    if not tts_key:
        logger.warning("No ElevenLabs TTS key set; using Edge TTS only")
        return edge_tts

    eleven_voice_id = os.getenv("ELEVEN_VOICE_ID", "l7kNoIfnJKPg7779LI2t")
    primary = elevenlabs.TTS(voice_id=eleven_voice_id, api_key=tts_key)
    return TTSFallbackAdapter([primary, edge_tts], max_retry_per_tts=1)


def _build_stt():
    """Build ElevenLabs STT with optional language + split-key overrides.

    Key resolution: ELEVEN_STT_API_KEY → ELEVEN_API_KEY. ELEVEN_STT_LANGUAGE
    accepts an ISO 639-1 code (e.g. 'en', 'ur', 'hi'); when unset the
    model auto-detects the spoken language.
    """
    kwargs: dict = {"model_id": "scribe_v2_realtime"}
    stt_key = os.getenv("ELEVEN_STT_API_KEY") or os.getenv("ELEVEN_API_KEY")
    if stt_key:
        kwargs["api_key"] = stt_key
    language = os.getenv("ELEVEN_STT_LANGUAGE", "en").strip()
    if language:
        kwargs["language_code"] = language
    return elevenlabs.STT(**kwargs)


def build_session() -> AgentSession:
    """Build an AgentSession with the full voice pipeline."""
    return AgentSession(
        vad=silero.VAD.load(
            min_speech_duration=0.1,
            min_silence_duration=0.5,
            activation_threshold=0.5,
        ),
        stt=_build_stt(),
        # LLM is intentionally overridden in Ella.llm_node() to call the backend.
        llm=openai.LLM(model="psychocounsel", base_url="http://localhost", api_key="empty"),
        tts=_build_tts(),
        allow_interruptions=True,
        min_interruption_duration=0.5,
        min_endpointing_delay=0.5,
        max_endpointing_delay=3.0,
    )


# ---------------------------------------------------------------------------
# Agent entrypoint
# ---------------------------------------------------------------------------


async def entrypoint(ctx: JobContext) -> None:
    """LiveKit agent entrypoint — connects to room and starts Ella."""
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")

    session = build_session()

    backend_base_url = os.getenv("BACKEND_API_URL", "http://127.0.0.1:5050")
    voice_agent_secret = os.getenv("VOICE_AGENT_SECRET", "dev-voice-agent-secret")

    user_id = await _wait_for_user(ctx)
    conversation_id = await _bootstrap_conversation(backend_base_url, voice_agent_secret, user_id)

    await session.start(
        agent=Ella(
            backend_base_url=backend_base_url,
            voice_agent_secret=voice_agent_secret,
            user_id=user_id,
            conversation_id=conversation_id,
            room=ctx.room,
        ),
        room=ctx.room,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
