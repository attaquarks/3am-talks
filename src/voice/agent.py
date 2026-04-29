"""
3AM Talks — LiveKit Voice Agent (Ella)
Real-time voice conversation agent using:
  Pipeline: Silero VAD → ElevenLabs STT → (Backend ConversationManager) → ElevenLabs TTS

Runs as a standalone process: python src/voice_agent.py dev
"""

import json
import logging
import time
from dotenv import load_dotenv
import os
import sys
import asyncio
from pathlib import Path
from typing import AsyncIterable, AsyncIterator, Optional, Tuple

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
from livekit.agents import tts as tts_mod
from livekit.agents.tts import FallbackAdapter as TTSFallbackAdapter
from livekit.agents.tokenize import blingfire

try:
    # Preferred when running as module: `python -m src.voice.agent`.
    from .tts_plugin import TTS as EdgeTTS
except ImportError:
    try:
        # Works when src/ is on PYTHONPATH.
        from voice.tts_plugin import TTS as EdgeTTS
    except ImportError:
        # Fallback for direct script execution from src/voice/.
        from tts_plugin import TTS as EdgeTTS

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
        tts_pipelines: dict,
        room: Optional[rtc.Room] = None,
    ) -> None:
        super().__init__(instructions=ELLA_SYSTEM_PROMPT)
        self._backend_base_url = backend_base_url.rstrip("/")
        self._voice_agent_secret = voice_agent_secret
        self._user_id = user_id
        self._conversation_id = conversation_id
        self._tts_pipelines = tts_pipelines
        self._room = room
        # Set by llm_node based on the user's transcribed input; read by
        # tts_node to pick the voice. Input-based routing works even when
        # the LLM replies in Roman-script Hinglish.
        self._last_user_lang: str = "en"
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=10.0)
        )
        # Feature flag for the streaming SSE path. Default off for safe rollout.
        self._streaming = os.getenv("VOICE_STREAMING_ENABLED", "false").strip().lower() == "true"
        # Tracks the most recent client-reported mic mute state. Audio is
        # already gated client-side by LiveKit when muted, so this is for
        # logging/telemetry only — the agent does not need to suppress STT
        # explicitly. Defaults to False (microphone live) until the client
        # reports otherwise.
        self._user_muted: bool = False
        if self._room is not None:
            self._register_room_handlers()

    def _extract_user_text(self, chat_ctx: ChatContext) -> str:
        """Pull the last user message out of the LiveKit ChatContext.
        Handles both the method-style `.messages()` and the attribute-style
        `.items` present across livekit-agents versions.
        """
        try:
            msgs = chat_ctx.messages() if callable(getattr(chat_ctx, "messages", None)) else getattr(chat_ctx, "messages", [])
            if not msgs:
                msgs = [it for it in getattr(chat_ctx, "items", []) if getattr(it, "role", None) == "user"]
            last = msgs[-1] if msgs else None
            if last and getattr(last, "role", None) == "user":
                if hasattr(last, "text_content"):
                    tc = last.text_content
                    return (tc() if callable(tc) else (tc or "")).strip()
                content = getattr(last, "content", "") or ""
                if isinstance(content, list):
                    content = " ".join(str(c) for c in content if isinstance(c, str))
                return content.strip()
        except Exception as e:
            logger.error(f"[_extract_user_text] {type(e).__name__}: {e}")
        return ""

    async def llm_node(
        self,
        chat_ctx: ChatContext,
        tools: list[FunctionTool],
        model_settings: ModelSettings,
    ) -> AsyncIterable[ChatChunk | str]:
        """Replace the default LLM with a backend request. Routes to the
        streaming SSE endpoint when VOICE_STREAMING_ENABLED=true, otherwise
        falls back to the one-shot /api/voice/chat path."""
        user_text = self._extract_user_text(chat_ctx)
        logger.info(f"[llm_node] user_text: {user_text!r} streaming={self._streaming}")
        if not user_text:
            logger.warning("[llm_node] Empty user_text, returning early")
            return

        # Route TTS by input language — works even when reply is Roman-script Hinglish.
        self._last_user_lang = (
            "hi"
            if any(0x0900 <= ord(c) <= 0x097F or 0x0600 <= ord(c) <= 0x06FF for c in user_text)
            else "en"
        )
        logger.info(f"[llm_node] routed_lang={self._last_user_lang}")

        if self._streaming:
            async for chunk in self._llm_node_streaming(user_text):
                yield chunk
        else:
            async for chunk in self._llm_node_oneshot(user_text):
                yield chunk

    async def _llm_node_oneshot(self, user_text: str) -> AsyncIterator[str]:
        """Legacy blocking path — one HTTP request, one yield."""
        try:
            url = f"{self._backend_base_url}/api/voice/chat"
            headers = {"Authorization": f"Bearer {self._voice_agent_secret}"}
            payload = {
                "user_id": self._user_id,
                "conversation_id": self._conversation_id,
                "message": user_text,
            }
            logger.info(f"[llm_node:oneshot] Calling backend: {url}")
            resp = await self._http.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            self._conversation_id = data.get("conversation_id") or self._conversation_id
            crisis = data.get("crisis")
            if crisis and crisis.get("detected"):
                await self._publish_crisis(crisis)
            text = (data.get("response") or "").strip()
            if not text:
                raise RuntimeError("Backend returned empty response text")
            yield text
        except Exception as e:
            logger.error(f"[llm_node:oneshot] failed: {type(e).__name__}: {e}")
            raise

    async def _llm_node_streaming(self, user_text: str) -> AsyncIterator[str]:
        """Streaming SSE path — yields sentence-sized chunks as they arrive.

        Each yield becomes its own TTS synthesize call in LiveKit, so first
        audio can play while later sentences are still being generated by
        the backend.
        """
        url = f"{self._backend_base_url}/api/voice/chat/stream"
        headers = {"Authorization": f"Bearer {self._voice_agent_secret}"}
        payload = {
            "user_id": self._user_id,
            "conversation_id": self._conversation_id,
            "message": user_text,
        }
        t0 = time.perf_counter()
        first_sentence = True
        await self._publish_agent_state("thinking")
        try:
            async with self._http.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for event, data in _parse_sse_lines(resp.aiter_lines()):
                    if event == "meta":
                        self._conversation_id = data.get("conversation_id") or self._conversation_id
                    elif event == "sentence":
                        text = (data.get("text") or "").strip()
                        if not text:
                            continue
                        if first_sentence:
                            logger.info(
                                f"[llm_node:stream] first-sentence took {time.perf_counter() - t0:.3f}s"
                            )
                            await self._publish_agent_state("speaking")
                            first_sentence = False
                        # Append a space so sentences don't run together in
                        # the TTS concatenation.
                        yield text + " "
                    elif event == "crisis":
                        if isinstance(data, dict) and data.get("detected"):
                            await self._publish_crisis(data)
                    elif event == "final":
                        # Persistence metadata — nothing to speak.
                        pass
                    elif event == "error":
                        logger.error(f"[llm_node:stream] backend error: {data}")
                        break
                    elif event == "done":
                        break
        except Exception as e:
            logger.error(f"[llm_node:stream] failed: {type(e).__name__}: {e}")
            await self._publish_agent_state("interrupted")
            raise
        finally:
            await self._publish_agent_state("listening")

    def _register_room_handlers(self) -> None:
        """Subscribe to client-side data channel events.

        Handles `voice.mute.state` payloads emitted by the frontend mute
        button. Audio is already gated client-side by LiveKit, so the
        backend role here is to log the state and surface it in the
        agent-state stream so the UI label stays consistent.
        """
        if not self._room:
            return

        def _on_data(*args) -> None:
            try:
                # livekit-rtc 1.x passes a single DataPacket; older versions
                # pass (data, participant, kind). Handle both.
                packet = args[0] if args else None
                data = getattr(packet, "data", None)
                if data is None and isinstance(packet, (bytes, bytearray)):
                    data = packet
                if not isinstance(data, (bytes, bytearray)):
                    return
                payload = json.loads(data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
                return
            except Exception as exc:
                logger.debug(
                    f"[data_received] decode error: {type(exc).__name__}: {exc}"
                )
                return

            if not isinstance(payload, dict):
                return
            if payload.get("type") != "voice.mute.state":
                return
            muted = bool(payload.get("muted"))
            if muted == self._user_muted:
                return
            self._user_muted = muted
            logger.info(f"[mute] user mute state changed: muted={muted}")
            try:
                loop = asyncio.get_event_loop()
                state = "muted" if muted else "listening"
                loop.create_task(self._publish_agent_state(state))
            except RuntimeError:
                # No running loop (rare on background callbacks); skip the
                # state echo. The frontend already updated optimistically
                # from its own track state.
                pass

        try:
            self._room.on("data_received", _on_data)
        except Exception as exc:
            logger.warning(f"Failed to register data_received handler: {exc}")

    async def _publish_agent_state(self, state: str) -> None:
        """Publish an agent-state change over the data channel so the
        frontend can show distinct 'thinking'/'speaking'/'listening' UI.
        Unreliable delivery — these are UX hints, not safety signals.
        """
        if not self._room or not getattr(self._room, "local_participant", None):
            return
        try:
            payload = json.dumps({"type": "agent.state.change", "state": state, "ts": time.time()})
            await self._room.local_participant.publish_data(
                payload.encode("utf-8"), reliable=False
            )
        except Exception as exc:
            logger.warning(f"[state] publish failed: {exc}")

    async def tts_node(self, text, model_settings):
        """Route TTS to the voice pipeline for the user's input language.
        Input-based routing means Hinglish replies in Roman script still use
        the Hindi voice as long as the user spoke Hindi/Urdu.

        Streams text chunks from llm_node INTO the TTS as they arrive while
        concurrently yielding audio frames OUT — first audio can start
        playing while later sentences are still being generated by the
        backend. Do NOT drain `text` into a list first; that batches the
        whole reply and wipes out the streaming benefit.
        """
        lang = self._last_user_lang
        chosen_tts = self._tts_pipelines[lang]
        logger.info(f"[tts_node] lang={lang} streaming-feed=1")

        wrapped_tts = chosen_tts
        if not wrapped_tts.capabilities.streaming:
            wrapped_tts = tts_mod.StreamAdapter(
                tts=wrapped_tts,
                sentence_tokenizer=blingfire.SentenceTokenizer(retain_format=True),
            )

        activity = self._get_activity_or_raise()
        conn_options = activity.session.conn_options.tts_conn_options

        async with wrapped_tts.stream(conn_options=conn_options) as stream:
            saw_any = False

            async def _feed() -> None:
                nonlocal saw_any
                try:
                    async for chunk in text:
                        if not chunk:
                            continue
                        saw_any = True
                        stream.push_text(chunk)
                finally:
                    # Always close input so the TTS knows to finish, even
                    # on feeder cancellation / exception. `end_input` is
                    # safe to call multiple times.
                    try:
                        stream.end_input()
                    except Exception:
                        pass

            feeder = asyncio.create_task(_feed(), name="ella-tts-feeder")
            try:
                async for ev in stream:
                    yield ev.frame
            finally:
                if not feeder.done():
                    feeder.cancel()
                try:
                    await feeder
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    logger.warning(f"[tts_node] feeder errored: {exc}")
                if not saw_any:
                    logger.info("[tts_node] no text received")

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
            url = f"{self._backend_base_url}/api/voice/end"
            headers = {"Authorization": f"Bearer {self._voice_agent_secret}"}
            payload = {
                "user_id": self._user_id,
                "conversation_id": self._conversation_id,
            }
            await self._http.post(url, json=payload, headers=headers)
        except Exception as e:
            logger.warning(f"[on_exit] voice/end flush failed: {type(e).__name__}: {e}")
        try:
            await self._http.aclose()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# SSE line parser used by Ella._llm_node_streaming
# ---------------------------------------------------------------------------


async def _parse_sse_lines(lines_iter) -> AsyncIterator[Tuple[str, dict]]:
    """Parse an async iterator of raw lines from an SSE response into
    `(event, data_dict)` tuples.

    Handles:
      event: <name>
      data: <json>
      <blank line terminates a frame>
    """
    event = "message"
    data_lines: list[str] = []
    async for raw in lines_iter:
        line = raw.rstrip("\r") if isinstance(raw, str) else raw
        if line == "" or line is None:
            if data_lines:
                payload = "\n".join(data_lines)
                try:
                    data = json.loads(payload) if payload else {}
                except json.JSONDecodeError:
                    data = {"_raw": payload}
                yield event, data if isinstance(data, dict) else {"value": data}
            event = "message"
            data_lines = []
            continue
        if line.startswith(":"):
            # comment / keepalive
            continue
        if line.startswith("event:"):
            event = line[len("event:"):].strip() or "message"
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].lstrip())
    # flush trailing frame
    if data_lines:
        payload = "\n".join(data_lines)
        try:
            data = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            data = {"_raw": payload}
        yield event, data if isinstance(data, dict) else {"value": data}


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


def _build_tts_pipelines() -> dict:
    """Build per-language TTS pipelines (keys: 'en', 'hi').
    ElevenLabs primary + Edge TTS fallback when a key is available, else Edge TTS only.
    """
    edge_voice = os.getenv("EDGE_TTS_VOICE", "en-US-AvaMultilingualNeural")
    edge_tts = EdgeTTS(voice=edge_voice)

    tts_key = os.getenv("ELEVEN_TTS_API_KEY") or os.getenv("ELEVEN_API_KEY")
    if not tts_key:
        logger.warning("No ElevenLabs TTS key — using Edge TTS only")
        return {"en": edge_tts, "hi": edge_tts}

    voice_en = (os.getenv("ELEVEN_VOICE_ID_EN") or "").strip()
    if not voice_en:
        raise RuntimeError(
            "ELEVEN_VOICE_ID_EN is not set. Add a valid ElevenLabs voice ID to .env "
            "(grab one from elevenlabs.io → VoiceLab → voice → 'Voice ID')."
        )
    eleven_en = elevenlabs.TTS(voice_id=voice_en, api_key=tts_key)
    en_pipe = TTSFallbackAdapter([eleven_en, edge_tts], max_retry_per_tts=1)

    voice_hi = (os.getenv("ELEVEN_VOICE_ID_HI") or "").strip()
    if voice_hi:
        eleven_hi = elevenlabs.TTS(voice_id=voice_hi, api_key=tts_key)
        hi_pipe = TTSFallbackAdapter([eleven_hi, edge_tts], max_retry_per_tts=1)
    else:
        logger.warning("ELEVEN_VOICE_ID_HI not set — Hindi replies use English voice")
        hi_pipe = en_pipe

    return {"en": en_pipe, "hi": hi_pipe}


def _build_stt():
    """Build ElevenLabs STT with optional split-key and language overrides."""
    kwargs: dict = {"model_id": "scribe_v2_realtime"}
    stt_key = os.getenv("ELEVEN_STT_API_KEY") or os.getenv("ELEVEN_API_KEY")
    if stt_key:
        kwargs["api_key"] = stt_key
    language = os.getenv("ELEVEN_STT_LANGUAGE", "").strip()
    if language:
        kwargs["language_code"] = language
    return elevenlabs.STT(**kwargs)


def build_session(tts_pipelines: dict) -> AgentSession:
    """Build an AgentSession with the full voice pipeline.

    VAD + interruption tuning filters backchannels ("mm-hmm"/"yeah") so they
    don't spawn new turns or interrupt mid-sentence.
    """
    return AgentSession(
        vad=silero.VAD.load(
            min_speech_duration=0.25,
            min_silence_duration=0.6,
            activation_threshold=0.55,
        ),
        stt=_build_stt(),
        # LLM is intentionally overridden in Ella.llm_node() to call the backend.
        llm=openai.LLM(model="psychocounsel", base_url="http://localhost", api_key="empty"),
        tts=tts_pipelines["en"],
        allow_interruptions=True,
        min_interruption_duration=0.8,
        min_endpointing_delay=0.4,
        max_endpointing_delay=3.0,
    )


# ---------------------------------------------------------------------------
# Agent entrypoint
# ---------------------------------------------------------------------------


async def entrypoint(ctx: JobContext) -> None:
    """LiveKit agent entrypoint — connects to room and starts Ella."""
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")

    tts_pipelines = _build_tts_pipelines()
    session = build_session(tts_pipelines)

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
            tts_pipelines=tts_pipelines,
            room=ctx.room,
        ),
        room=ctx.room,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
