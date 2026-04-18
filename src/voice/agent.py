"""
3AM Talks — LiveKit Voice Agent (Ella)
Real-time voice conversation agent using:
  Pipeline: Silero VAD → ElevenLabs STT → (Backend ConversationManager) → ElevenLabs TTS

Runs as a standalone process: python src/voice_agent.py dev
"""

import logging
from dotenv import load_dotenv
import os
import asyncio
from typing import AsyncIterable, Optional

from livekit import rtc
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli, llm
from livekit.agents.llm import ChatChunk, FunctionTool, ChatContext
from livekit.agents import ModelSettings
from livekit.plugins import openai, elevenlabs, silero
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
    ) -> None:
        super().__init__(instructions=ELLA_SYSTEM_PROMPT)
        self._backend_base_url = backend_base_url.rstrip("/")
        self._voice_agent_secret = voice_agent_secret
        self._user_id = user_id
        self._conversation_id = conversation_id
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
            text = (data.get("response") or "").strip()
            logger.info(f"[llm_node] Got response text ({len(text)} chars): {text[:100]!r}")
            if not text:
                raise RuntimeError("Backend returned empty response text")
            yield text
            logger.info(f"[llm_node] Yielded text successfully")
        except Exception as e:
            logger.error(f"[llm_node] Backend voice/chat failed: {type(e).__name__}: {e}")
            raise

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


def build_session() -> AgentSession:
    """Build an AgentSession with the full voice pipeline."""
    return AgentSession(
        vad=silero.VAD.load(
            min_speech_duration=0.1,
            min_silence_duration=0.5,
            activation_threshold=0.5,
        ),
        stt=elevenlabs.STT(
            model_id="scribe_v2_realtime",
            language_code="en",
        ),
        # LLM is intentionally overridden in Ella.llm_node() to call the backend.
        llm=openai.LLM(model="psychocounsel", base_url="http://localhost", api_key="empty"),
        tts=EdgeTTS(
            voice="en-US-JennyNeural",
        ),
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
        ),
        room=ctx.room,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
