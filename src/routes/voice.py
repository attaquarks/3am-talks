"""
routes/voice.py — Voice agent endpoints
"""
from __future__ import annotations

import datetime as dt
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.helpers import (
    require_user,
    require_voice_agent,
    get_manager,
    _get_profile_persistent,
    _resume_or_start_conversation,
)
from crisis.integration import process_message_with_crisis
from database.supabase_client import SupabaseClient

logger = logging.getLogger("3am-voice")
router = APIRouter()
_sb = SupabaseClient()

class VoiceBootstrapRequest(BaseModel):
    user_id: str

class VoiceChatRequest(BaseModel):
    user_id: str
    message: str
    conversation_id: Optional[str] = None


class VoiceEndRequest(BaseModel):
    user_id: str
    conversation_id: Optional[str] = None


@router.post("/api/livekit/token")
def livekit_token(request: Request):
    """Generate a LiveKit access token for a voice session."""
    user = require_user(request)
    user_id = str(user["id"])

    lk_api_key = os.getenv("LIVEKIT_API_KEY")
    lk_api_secret = os.getenv("LIVEKIT_API_SECRET")
    lk_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")

    if not lk_api_key or not lk_api_secret:
        raise HTTPException(
            status_code=503,
            detail="LiveKit credentials not configured on the server.",
        )

    try:
        from livekit import api as lk_api

        room_name = f"ella-voice-{user_id}"

        token = (
            lk_api.AccessToken(api_key=lk_api_key, api_secret=lk_api_secret)
            .with_identity(f"user-{user_id}")
            .with_name(user.get("username", "User"))
            .with_grants(
                lk_api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
            .with_ttl(dt.timedelta(minutes=30))
            .to_jwt()
        )

        return {
            "serverUrl": lk_url,
            "roomName": room_name,
            "participantName": user.get("username", "User"),
            "participantToken": token,
        }

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="livekit-api package not installed. Run: pip install livekit-api",
        )
    except Exception as e:
        logger.error(f"LiveKit token generation failed: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to generate voice session token."
        )


@router.post("/api/voice/bootstrap")
def voice_bootstrap(body: VoiceBootstrapRequest, request: Request):
    """
    Server-to-server endpoint used by the LiveKit voice agent.
    Resolves the conversation_id to resume (or starts one) for the given user.
    """
    require_voice_agent(request)
    mgr = get_manager()

    _get_profile_persistent(body.user_id)
    conv_id = _resume_or_start_conversation(mgr, body.user_id)
    return {"conversation_id": conv_id}


@router.post("/api/voice/chat")
async def voice_chat(body: VoiceChatRequest, request: Request):
    """
    Server-to-server endpoint used by the LiveKit voice agent.
    Routes the message through the full ConversationManager pipeline so voice
    shares the exact same persona, memory, RAG, and personality adaptation.

    Crisis detection runs in parallel with the therapy LLM. When HIGH/CRITICAL,
    the response contains a `crisis` field; the voice agent forwards it as a
    LiveKit data-channel event so the frontend modal can open alongside TTS.
    """
    require_voice_agent(request)
    mgr = get_manager()

    _get_profile_persistent(body.user_id)
    conv_id = body.conversation_id or _resume_or_start_conversation(mgr, body.user_id)

    result, crisis_payload = await process_message_with_crisis(
        mgr=mgr,
        sb=_sb,
        user_id=body.user_id,
        conversation_id=conv_id,
        message=body.message,
    )

    response = {
        "conversation_id": conv_id,
        "response": result.get("response", "I'm here to listen."),
        "turn": result.get("turn"),
        "personality_scores": result.get("personality_scores"),
        "rag_techniques_used": result.get("rag_techniques_used", 0),
        "persistence_mode": result.get("metadata", {}).get("persistence_mode"),
    }


@router.post("/api/voice/end")
def voice_end(body: VoiceEndRequest, request: Request):
    """Server-to-server endpoint used by the voice worker when a call ends."""
    require_voice_agent(request)
    mgr = get_manager()

    _get_profile_persistent(body.user_id)
    conv_id = body.conversation_id or _resume_or_start_conversation(mgr, body.user_id)

    flush_result = mgr.flush_conversation_buffer(conv_id, reason="voice-end")

    try:
        mgr.db_client.update(
            "conversations",
            {"is_active": False, "ended_at": dt.datetime.utcnow().isoformat()},
            {"conversation_id": f"eq.{conv_id}", "user_id": f"eq.{body.user_id}"},
        )
    except Exception as e:
        logger.warning(f"Failed to mark conversation inactive on voice end ({conv_id}): {e}")

    return {
        "conversation_id": conv_id,
        "flushed": True,
        "result": flush_result,
    }
    if crisis_payload:
        response["crisis"] = crisis_payload
    return response
