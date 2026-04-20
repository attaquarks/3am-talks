import asyncio
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

# Import all components
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_layer.llm_service import LLMService
from ai_layer.personality_service import PersonalityService
from conversation.questionnaire import PersonalityQuestionnaire
from conversation.state import ConversationState, render_state_for_prompt
from database import SupabaseClient, UserService
from rag_layer import RAGService
from voice.backchannel import is_backchannel
from voice.sentence_buffer import SentenceChunker

logger = logging.getLogger(__name__)


@dataclass
class _ConversationBufferState:
    """In-memory buffer state for a single conversation."""

    messages: List[dict] = field(default_factory=list)
    pending_turns: int = 0
    last_enqueue_at: float = field(default_factory=time.time)
    last_personality_update_turn: Optional[int] = None
    flush_in_progress: bool = False


class ConversationManager:
    """
    Main orchestrator for the 3AM Talks therapy system.
    Manages user profiles, personality updates, RAG retrieval, and conversation flow.
    """

    def __init__(
        self,
        model_name: str = "psychocounsel",
        personality_model_path: str = "Models/bert-base-personality",
        personality_update_interval: int = 40,
        enable_rag: bool = True,
        enable_personality: bool = True,
    ):
        """
        Initialize the conversation manager.

        Args:
            model_name: Model name
            personality_model_path: Path to BERT personality model
            personality_update_interval: Update personality every N turns (30-50 recommended)
            enable_rag: Enable RAG retrieval
            enable_personality: Enable personality detection
        """
        # Initialize database
        self.db_client = SupabaseClient()
        self.user_service = UserService(self.db_client)

        # Initialize AI components
        self.llm = LLMService(model_name)

        self.enable_rag = enable_rag
        self.enable_personality = enable_personality
        self.personality_update_interval = personality_update_interval

        if enable_personality:
            self.personality_detector = PersonalityService(personality_model_path)
        else:
            self.personality_detector = None

        if enable_rag:
            self.rag_service = RAGService()
        else:
            self.rag_service = None

        # Questionnaire system - one per user (stored by user_id)
        self.questionnaires: Dict[str, PersonalityQuestionnaire] = {}

        # Persistence mode controls
        self.persistence_mode = (
            os.getenv("CONVERSATION_PERSISTENCE_MODE", "buffered").strip().lower()
        )
        if self.persistence_mode not in {"immediate", "buffered"}:
            logger.warning(
                "Unknown CONVERSATION_PERSISTENCE_MODE=%s. Falling back to immediate.",
                self.persistence_mode,
            )
            self.persistence_mode = "immediate"
        self.buffered_persistence = self.persistence_mode == "buffered"

        self.flush_interval_seconds = max(
            1, int(os.getenv("CONVERSATION_FLUSH_INTERVAL_SECONDS", "20"))
        )
        self.flush_turn_threshold = max(
            1, int(os.getenv("CONVERSATION_FLUSH_TURN_THRESHOLD", "2"))
        )

        # Buffering state
        self._state_guard = threading.RLock()
        self._conversation_locks: Dict[str, threading.Lock] = {}
        # Distinct from _conversation_locks (which guards buffer mutations).
        # _turn_locks serializes full turn processing per conversation so that
        # two overlapping voice utterances cannot race through process_message
        # and corrupt history/personality state. Acquisition order is always
        # _state_guard → _turn_locks[cid] → _conversation_locks[cid]; the
        # flush thread only takes _conversation_locks[cid], so no inversion.
        self._turn_locks: Dict[str, threading.Lock] = {}
        self._buffer_states: Dict[str, _ConversationBufferState] = {}
        # In-memory conversation state snapshots (topic, mood, goal, summary).
        # Updated by a non-blocking background task every N turns from
        # crisis.integration.process_message_with_crisis. Lost on restart.
        self._conv_states: Dict[str, ConversationState] = {}
        self._flush_stop_event = threading.Event()
        self._flush_thread: Optional[threading.Thread] = None

        if self.buffered_persistence:
            self._start_flush_worker()

        logger.info(
            "ConversationManager initialized (persistence_mode=%s, flush_interval=%ss, flush_turn_threshold=%s)",
            self.persistence_mode,
            self.flush_interval_seconds,
            self.flush_turn_threshold,
        )

    # ==================== BUFFER MANAGEMENT ====================

    def _start_flush_worker(self) -> None:
        """Start periodic flush worker for buffered persistence mode."""
        if self._flush_thread is not None or self.flush_interval_seconds <= 0:
            return

        def _run() -> None:
            while not self._flush_stop_event.wait(self.flush_interval_seconds):
                try:
                    self.flush_due_buffers(reason="periodic")
                except Exception as exc:
                    logger.warning("Periodic flush loop error: %s", exc)
                try:
                    self._evict_stale_in_memory_state()
                except Exception as exc:
                    logger.warning("Stale-state eviction error: %s", exc)

        self._flush_thread = threading.Thread(
            target=_run,
            name="conversation-buffer-flusher",
            daemon=True,
        )
        self._flush_thread.start()

    # Caps for the per-process in-memory dicts so long-running servers don't
    # grow unbounded. Evicted entries are safely rebuilt on the next turn
    # (ConversationState refreshes itself every N turns; locks are lazy).
    _MAX_CONV_STATES = 2000
    _MAX_LOCK_ENTRIES = 2000
    _LOCK_IDLE_SECONDS = 3600  # 1h

    def _evict_stale_in_memory_state(self) -> None:
        """Trim `_conv_states`, `_turn_locks`, `_conversation_locks` when
        they grow too large. Keeps entries that have active buffered state.
        """
        now = time.time()
        with self._state_guard:
            # Conversation states — evict oldest by last_updated_at.
            if len(self._conv_states) > self._MAX_CONV_STATES:
                overflow = len(self._conv_states) - self._MAX_CONV_STATES
                by_age = sorted(
                    self._conv_states.items(),
                    key=lambda kv: getattr(kv[1], "last_updated_at", 0.0),
                )
                for cid, _ in by_age[:overflow]:
                    self._conv_states.pop(cid, None)

            # Locks — evict only if conversation has no buffered state AND
            # recent activity is older than the idle threshold.
            active = set(self._buffer_states.keys())
            for lock_dict in (self._turn_locks, self._conversation_locks):
                if len(lock_dict) <= self._MAX_LOCK_ENTRIES:
                    continue
                candidates = []
                for cid in list(lock_dict.keys()):
                    if cid in active:
                        continue
                    state = self._conv_states.get(cid)
                    last_touch = getattr(state, "last_updated_at", 0.0) if state else 0.0
                    if now - last_touch > self._LOCK_IDLE_SECONDS:
                        candidates.append(cid)
                for cid in candidates[: len(lock_dict) - self._MAX_LOCK_ENTRIES]:
                    lock_dict.pop(cid, None)

    def _get_conversation_lock(self, conversation_id: str) -> threading.Lock:
        with self._state_guard:
            lock = self._conversation_locks.get(conversation_id)
            if lock is None:
                lock = threading.Lock()
                self._conversation_locks[conversation_id] = lock
            return lock

    def _get_turn_lock(self, conversation_id: str) -> threading.Lock:
        with self._state_guard:
            lock = self._turn_locks.get(conversation_id)
            if lock is None:
                lock = threading.Lock()
                self._turn_locks[conversation_id] = lock
            return lock

    def get_conversation_state(self, conversation_id: str) -> Optional[ConversationState]:
        """Read the current in-memory state snapshot (may be None)."""
        with self._state_guard:
            return self._conv_states.get(conversation_id)

    def set_conversation_state(
        self, conversation_id: str, state: ConversationState
    ) -> None:
        """Replace the in-memory state snapshot for a conversation."""
        with self._state_guard:
            self._conv_states[conversation_id] = state

    def _get_or_create_buffer_state(self, conversation_id: str) -> _ConversationBufferState:
        with self._state_guard:
            state = self._buffer_states.get(conversation_id)
            if state is None:
                state = _ConversationBufferState()
                self._buffer_states[conversation_id] = state
            return state

    def _get_pending_turns(self, conversation_id: str) -> int:
        if not self.buffered_persistence:
            return 0
        with self._state_guard:
            state = self._buffer_states.get(conversation_id)
            return state.pending_turns if state else 0

    def _get_buffered_messages(self, conversation_id: str) -> List[dict]:
        if not self.buffered_persistence:
            return []
        with self._state_guard:
            state = self._buffer_states.get(conversation_id)
            if not state:
                return []
            return [dict(m) for m in state.messages]

    def _enqueue_turn_messages(
        self,
        *,
        conversation_id: str,
        user_id: str,
        turn_index: int,
        user_message: str,
        assistant_message: str,
        personality_scores: Optional[dict] = None,
        rag_techniques: Optional[list] = None,
    ) -> int:
        """Buffer one user/assistant turn for asynchronous persistence."""
        lock = self._get_conversation_lock(conversation_id)
        with lock:
            state = self._get_or_create_buffer_state(conversation_id)
            now = time.time()

            user_payload = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "role": "user",
                "content": user_message,
                "turn_index": turn_index,
            }
            assistant_payload = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "role": "assistant",
                "content": assistant_message,
                "turn_index": turn_index,
            }

            if personality_scores:
                assistant_payload["personality_scores_at_turn"] = personality_scores
            if rag_techniques:
                assistant_payload["rag_techniques_used"] = rag_techniques

            state.messages.append(user_payload)
            state.messages.append(assistant_payload)
            state.pending_turns += 1
            state.last_enqueue_at = now

            pending_turns = state.pending_turns

        if pending_turns >= self.flush_turn_threshold:
            self._trigger_async_flush(conversation_id, reason="turn-threshold")

        return pending_turns

    def _trigger_async_flush(self, conversation_id: str, reason: str) -> None:
        """Schedule an asynchronous flush for a conversation if not already running."""
        if not self.buffered_persistence:
            return

        with self._state_guard:
            state = self._buffer_states.get(conversation_id)
            if not state or state.flush_in_progress:
                return
            state.flush_in_progress = True

        def _runner() -> None:
            try:
                self.flush_conversation_buffer(conversation_id, reason=reason)
            except Exception as exc:
                logger.warning(
                    "Async flush failed for %s (reason=%s): %s",
                    conversation_id,
                    reason,
                    exc,
                )
            finally:
                with self._state_guard:
                    current = self._buffer_states.get(conversation_id)
                    if current:
                        current.flush_in_progress = False
                        if (
                            not current.messages
                            and current.pending_turns <= 0
                            and current.last_personality_update_turn is None
                        ):
                            del self._buffer_states[conversation_id]

        threading.Thread(
            target=_runner,
            name=f"flush-{conversation_id[:8]}",
            daemon=True,
        ).start()

    def flush_due_buffers(self, reason: str = "manual") -> int:
        """Schedule flush for any buffer that is due by age or turn threshold."""
        if not self.buffered_persistence:
            return 0

        now = time.time()
        to_flush: List[str] = []

        with self._state_guard:
            for conversation_id, state in self._buffer_states.items():
                if state.flush_in_progress:
                    continue
                if state.pending_turns >= self.flush_turn_threshold:
                    to_flush.append(conversation_id)
                    continue
                age = now - state.last_enqueue_at
                if state.messages and age >= self.flush_interval_seconds:
                    to_flush.append(conversation_id)

        for conversation_id in to_flush:
            self._trigger_async_flush(conversation_id, reason=reason)

        return len(to_flush)

    def flush_conversation_buffer(self, conversation_id: str, reason: str = "manual") -> dict:
        """Flush one conversation buffer to Supabase in write-order."""
        if not self.buffered_persistence:
            return {
                "conversation_id": conversation_id,
                "flushed_messages": 0,
                "flushed_turns": 0,
                "reason": reason,
                "mode": "immediate",
            }

        lock = self._get_conversation_lock(conversation_id)
        with lock:
            with self._state_guard:
                state = self._buffer_states.get(conversation_id)
                if not state:
                    return {
                        "conversation_id": conversation_id,
                        "flushed_messages": 0,
                        "flushed_turns": 0,
                        "reason": reason,
                        "mode": "buffered",
                    }

                pending_messages = [dict(m) for m in state.messages]
                pending_turns = state.pending_turns
                pending_personality_turn = state.last_personality_update_turn

            if not pending_messages and pending_turns <= 0 and pending_personality_turn is None:
                return {
                    "conversation_id": conversation_id,
                    "flushed_messages": 0,
                    "flushed_turns": 0,
                    "reason": reason,
                    "mode": "buffered",
                }

            _t0 = time.perf_counter()
            logger.info(
                "[LATENCY] flush START conv=%s reason=%s pending_messages=%s pending_turns=%s",
                conversation_id,
                reason,
                len(pending_messages),
                pending_turns,
            )

            if pending_messages:
                _ts = time.perf_counter()
                self.user_service.add_messages_batch(pending_messages)
                logger.info(
                    "[LATENCY] flush add_messages_batch took %.3fs",
                    time.perf_counter() - _ts,
                )

            if pending_turns > 0 or pending_personality_turn is not None:
                _ts = time.perf_counter()
                self.user_service.update_conversation_turns(
                    conversation_id,
                    increment=pending_turns,
                    last_personality_update_turn=pending_personality_turn,
                    touch_updated_at=True,
                )
                logger.info(
                    "[LATENCY] flush update_conversation_turns took %.3fs",
                    time.perf_counter() - _ts,
                )

            with self._state_guard:
                state = self._buffer_states.get(conversation_id)
                if state:
                    state.messages.clear()
                    state.pending_turns = 0
                    state.last_personality_update_turn = None
                    state.last_enqueue_at = time.time()
                    if not state.flush_in_progress:
                        del self._buffer_states[conversation_id]

            logger.info(
                "[LATENCY] flush TOTAL took %.3fs conv=%s",
                time.perf_counter() - _t0,
                conversation_id,
            )

            return {
                "conversation_id": conversation_id,
                "flushed_messages": len(pending_messages),
                "flushed_turns": pending_turns,
                "reason": reason,
                "mode": "buffered",
            }

    def flush_all_buffers(self, reason: str = "manual") -> int:
        """Flush all pending conversation buffers synchronously."""
        if not self.buffered_persistence:
            return 0

        with self._state_guard:
            conversation_ids = list(self._buffer_states.keys())

        flushed = 0
        for conversation_id in conversation_ids:
            try:
                result = self.flush_conversation_buffer(conversation_id, reason=reason)
                if result.get("flushed_messages") or result.get("flushed_turns"):
                    flushed += 1
            except Exception as exc:
                logger.warning("Failed to flush conversation %s: %s", conversation_id, exc)

        return flushed

    # ==================== AUTHENTICATION ====================

    def register_user(self, email: str, password: str) -> Dict:
        """Register a new user and create their profile."""
        try:
            auth_response = self.db_client.sign_up(email, password)

            user = auth_response.get("user") or auth_response
            user_id = user.get("id")

            if not user_id:
                raise ValueError("Failed to get User ID from signup response")

            logger.info("Registered user auth: %s", user_id)

            profile = self.user_service.create_user_profile(user_id)

            return {
                "user_id": user_id,
                "email": email,
                "profile": profile,
            }
        except Exception as e:
            logger.error("Registration failed: %s", e)
            raise

    def login_user(self, email: str, password: str) -> Dict:
        """Login an existing user."""
        try:
            auth_response = self.db_client.sign_in(email, password)

            user = auth_response.get("user")
            user_id = user.get("id") if user else None
            access_token = auth_response.get("access_token")

            if not user_id:
                raise ValueError("Failed to get User ID from login response")

            return {
                "user_id": user_id,
                "access_token": access_token,
            }
        except Exception as e:
            logger.error("Login failed: %s", e)
            raise

    # ==================== SESSION MANAGEMENT ====================

    def start_session(self, user_id: str) -> Dict[str, str]:
        """
        Start a new conversation session for a user.

        Args:
            user_id: Required User ID (from auth)

        Returns:
            dict with conversation_id and session info
        """
        try:
            if not user_id:
                raise ValueError("User ID is required to start a session")

            profile = self.user_service.get_user_profile(user_id)
            if not profile:
                logger.warning("Profile not found for %s, creating one", user_id)
                self.user_service.create_user_profile(user_id)

            conversation = self.user_service.create_conversation(user_id)

            logger.info(
                "Started session for user %s, conv=%s",
                user_id,
                conversation["conversation_id"],
            )

            return {
                "user_id": user_id,
                "conversation_id": conversation["conversation_id"],
                "message": "Session started successfully",
            }
        except Exception as e:
            logger.error("Failed to start session: %s", e)
            raise

    def end_session(self, conversation_id: str) -> dict:
        """End a conversation session."""
        try:
            if self.buffered_persistence:
                self.flush_conversation_buffer(conversation_id, reason="end-session")
            self.user_service.end_conversation(conversation_id)
            return {"message": "Session ended successfully"}
        except Exception as e:
            logger.error("Failed to end session: %s", e)
            raise

    # ==================== PERSONALITY MANAGEMENT ====================

    def _get_recent_user_text_for_personality(
        self,
        user_id: str,
        conversation_id: str,
        current_user_message: Optional[str] = None,
        last_n_turns: int = 5,
    ) -> str:
        """Collect recent user text from persisted + buffered messages."""
        persisted_messages = self.user_service.get_conversation_history(
            conversation_id,
            limit=max(last_n_turns * 4, 20),
        )
        user_messages = [
            msg.get("content", "")
            for msg in persisted_messages
            if msg.get("role") == "user" and msg.get("content")
        ]

        if self.buffered_persistence:
            buffered_messages = self._get_buffered_messages(conversation_id)
            user_messages.extend(
                [
                    msg.get("content", "")
                    for msg in buffered_messages
                    if msg.get("role") == "user" and msg.get("content")
                ]
            )

        if current_user_message:
            user_messages.append(current_user_message)

        return " ".join(user_messages[-last_n_turns:]).strip()

    def _get_effective_last_personality_turn(
        self,
        conversation: dict,
        conversation_id: str,
    ) -> int:
        """Get last personality update turn with buffered state considered."""
        persisted_turn = int(conversation.get("last_personality_update_turn", 0) or 0)
        if not self.buffered_persistence:
            return persisted_turn

        with self._state_guard:
            state = self._buffer_states.get(conversation_id)
            if not state or state.last_personality_update_turn is None:
                return persisted_turn
            return max(persisted_turn, int(state.last_personality_update_turn))

    def _mark_personality_updated_turn(self, conversation_id: str, turn_value: int) -> None:
        """Persist or buffer personality-update turn marker."""
        if self.buffered_persistence:
            with self._state_guard:
                state = self._get_or_create_buffer_state(conversation_id)
                state.last_personality_update_turn = int(turn_value)
            return

        self.user_service.update_conversation_turns(
            conversation_id,
            increment=0,
            last_personality_update_turn=int(turn_value),
            touch_updated_at=False,
        )

    def _update_personality_if_needed(
        self,
        user_id: str,
        conversation_id: str,
        total_turns_before_current: Optional[int] = None,
        current_user_message: Optional[str] = None,
        force_update: bool = False,
        *,
        conversation: Optional[dict] = None,
        profile: Optional[dict] = None,
    ) -> Optional[Dict[str, float]]:
        """Update personality profile if enough turns have passed.

        `conversation` and `profile` can be passed in by the caller to avoid
        redundant DB fetches — process_message already fetched both by the
        time this is called. When omitted we fall back to fetching.
        """
        if not self.enable_personality:
            return None

        try:
            if conversation is None:
                conversation = self.user_service.get_conversation(conversation_id)
            if not conversation:
                return None

            if total_turns_before_current is None:
                total_turns_before_current = int(conversation.get("total_turns", 0) or 0)

            last_personality_turn = self._get_effective_last_personality_turn(
                conversation,
                conversation_id,
            )

            should_update = force_update or (
                int(total_turns_before_current) - int(last_personality_turn)
            ) >= self.personality_update_interval

            if not should_update:
                cached = profile if profile is not None else (
                    self.user_service.get_user_profile(user_id) or {}
                )
                return {
                    "Extroversion": cached.get("extroversion", 0.5),
                    "Neuroticism": cached.get("neuroticism", 0.5),
                    "Agreeableness": cached.get("agreeableness", 0.5),
                    "Conscientiousness": cached.get("conscientiousness", 0.5),
                    "Openness": cached.get("openness", 0.5),
                }

            user_text = self._get_recent_user_text_for_personality(
                user_id,
                conversation_id,
                current_user_message=current_user_message,
                last_n_turns=5,
            )

            if not user_text or len(user_text) < 50:
                logger.info("Not enough text for personality update")
                return None

            scores = self.personality_detector.detect_personality(user_text)

            self.user_service.update_personality_scores(
                user_id,
                scores,
                len(user_text),
            )

            self._mark_personality_updated_turn(
                conversation_id,
                int(total_turns_before_current),
            )

            logger.info("Updated personality for user %s: %s", user_id, scores)
            return scores

        except Exception as e:
            logger.error("Failed to update personality: %s", e)
            return None

    # ==================== CORE CONVERSATION FLOW ====================

    def process_message(
        self,
        user_id: str,
        conversation_id: str,
        user_message: str,
        is_questionnaire_response: bool = False,
    ) -> dict:
        """
        Process a user message through the complete pipeline:
        1. Load user profile
        2. Update personality if needed
        3. Retrieve RAG techniques
        4. Generate LLM response with personality-aware prompt
        5. Persist (immediate) or enqueue (buffered)

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            user_message: User's message
            is_questionnaire_response: Whether this is a questionnaire response

        Returns:
            dict with response and metadata
        """
        turn_lock = self._get_turn_lock(conversation_id)
        turn_lock.acquire()
        try:
            prep = self._prepare_turn(
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=user_message,
                is_questionnaire_response=is_questionnaire_response,
            )
            if prep.get("early_return") is not None:
                return prep["early_return"]

            _ts = time.perf_counter()
            llm_response = self._generate_llm_response(
                user_message=prep["user_message"],
                context_updates=prep["context_updates"],
                history=prep["history"],
            )
            logger.info(
                "[LATENCY] LLM generate_response took %.3fs",
                time.perf_counter() - _ts,
            )

            assistant_message = llm_response.get("Response", "I'm here to listen.")
            return self._finalize_turn(
                prep,
                assistant_message=assistant_message,
                llm_response=llm_response,
            )
        except Exception as e:
            logger.error("Error processing message: %s", e)
            import traceback
            logger.error(traceback.format_exc())
            raise
        finally:
            turn_lock.release()

    def _prepare_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        user_message: str,
        is_questionnaire_response: bool = False,
    ) -> dict:
        """Run DB fetches, personality, RAG, context, history — everything
        needed to call the LLM. Returns a dict consumed by `_finalize_turn`.

        If the message is a questionnaire response, the dict contains an
        `early_return` key holding the final response (questionnaire path
        does not touch the LLM).
        """
        _t0 = time.perf_counter()
        logger.info(
            "[LATENCY] process_message START user=%s conv=%s mode=%s",
            user_id,
            conversation_id,
            self.persistence_mode,
        )

        _ts = time.perf_counter()
        conversation = self.user_service.get_conversation(conversation_id)
        logger.info("[LATENCY] get_conversation took %.3fs", time.perf_counter() - _ts)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        persisted_turns = int(conversation.get("total_turns", 0) or 0)
        pending_turns = self._get_pending_turns(conversation_id)
        total_turns_before_current = persisted_turns + pending_turns
        current_turn = total_turns_before_current + 1

        _ts = time.perf_counter()
        profile = self.user_service.get_user_profile(user_id)
        logger.info("[LATENCY] get_user_profile took %.3fs", time.perf_counter() - _ts)
        if not profile:
            raise ValueError(f"User profile {user_id} not found")

        questionnaire = self.questionnaires.get(user_id)

        if is_questionnaire_response and questionnaire and not questionnaire.completed:
            current_question = questionnaire.get_next_question()
            if current_question:
                try:
                    self.db_client.insert(
                        "questionnaire_responses",
                        {
                            "user_id": user_id,
                            "question": current_question["question"],
                            "response": user_message,
                        },
                    )
                except Exception as e:
                    logger.error("Failed to save response to database: %s", e)

                questionnaire.submit_response(current_question["id"], user_message)

                if questionnaire.completed:
                    questionnaire_text = questionnaire.get_all_responses_text()
                    personality_scores_q = None
                    if self.enable_personality and self.personality_detector:
                        personality_scores_q = self.personality_detector.detect_personality(
                            questionnaire_text
                        )
                        self.user_service.update_personality_scores(
                            user_id,
                            personality_scores_q,
                            len(questionnaire_text),
                        )
                        logger.info(
                            "Initial personality assessed from questionnaire for user %s",
                            user_id,
                        )
                    self.user_service.mark_questionnaire_completed(user_id, completed=True)
                    return {
                        "early_return": {
                            "response": "Thank you for completing the initial assessment. I now have a better understanding of you, and we can continue our conversation.",
                            "turn": current_turn,
                            "questionnaire": {
                                "completed": True,
                                "message": "Thank you for completing the initial assessment. I now have a better understanding of you, and we can continue our conversation.",
                            },
                            "personality_scores": personality_scores_q,
                        }
                    }

                next_question = questionnaire.get_next_question()
                if next_question:
                    return {
                        "early_return": {
                            "response": f"Thank you for sharing that. {next_question['question']}",
                            "turn": current_turn,
                            "questionnaire": {
                                "active": True,
                                "question": next_question,
                                "progress": questionnaire.get_progress(),
                            },
                            "personality_scores": None,
                        }
                    }

        if not self.buffered_persistence:
            _ts = time.perf_counter()
            self.user_service.add_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=user_message,
                turn_index=current_turn,
            )
            logger.info(
                "[LATENCY] add_message (user) took %.3fs",
                time.perf_counter() - _ts,
            )
        else:
            logger.info(
                "[LATENCY] add_message (user) skipped in buffered mode conv=%s",
                conversation_id,
            )

        _ts = time.perf_counter()
        personality_scores = self._update_personality_if_needed(
            user_id,
            conversation_id,
            total_turns_before_current=total_turns_before_current,
            current_user_message=user_message,
            force_update=False,
            conversation=conversation,
            profile=profile,
        )
        logger.info(
            "[LATENCY] _update_personality_if_needed took %.3fs",
            time.perf_counter() - _ts,
        )

        rag_context = None
        rag_techniques_metadata: List[dict] = []

        # Gate RAG: skip for short / backchannel utterances. The crisis
        # detector runs in a separate coroutine and is NOT affected.
        should_run_rag = (
            self.enable_rag
            and self.rag_service
            and len(user_message.split()) >= 4
            and not is_backchannel(user_message)
        )

        if should_run_rag:
            try:
                _ts = time.perf_counter()
                issue_tags = self._infer_issue_tags(user_message)
                techniques = self.rag_service.retrieve_relevant_techniques(
                    query=user_message,
                    issue_tags=issue_tags,
                    top_k=3,
                )
                rag_context = self.rag_service.format_techniques_for_prompt(techniques)
                rag_techniques_metadata = [
                    {
                        "id": t.get("id"),
                        "technique_name": t.get("metadata", {}).get("technique_name"),
                        "score": t.get("score"),
                    }
                    for t in techniques
                ]
                logger.info(
                    "[LATENCY] RAG retrieval (%s techniques) took %.3fs",
                    len(techniques),
                    time.perf_counter() - _ts,
                )
            except Exception as e:
                logger.error("RAG retrieval failed: %s", e)
                rag_context = None

        _ts = time.perf_counter()
        context_updates = self._build_context_updates(
            personality_scores,
            rag_context,
            current_turn,
            profile,
            conversation_id=conversation_id,
        )
        logger.info(
            "[LATENCY] _build_context_updates took %.3fs",
            time.perf_counter() - _ts,
        )

        _ts = time.perf_counter()
        if self.buffered_persistence:
            history_messages = self._get_history_with_buffer(conversation_id, limit=10)
        else:
            history_messages = self.user_service.get_conversation_history(
                conversation_id,
                limit=10,
            )
        logger.info(
            "[LATENCY] get_conversation_history took %.3fs",
            time.perf_counter() - _ts,
        )

        history: List[dict] = []
        if self.buffered_persistence:
            for msg in history_messages:
                history.append({"role": msg.get("role"), "content": msg.get("content")})
        else:
            for msg in history_messages[:-1]:
                history.append({"role": msg.get("role"), "content": msg.get("content")})

        return {
            "early_return": None,
            "t0": _t0,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "user_message": user_message,
            "current_turn": current_turn,
            "conversation": conversation,
            "profile": profile,
            "personality_scores": personality_scores,
            "rag_context": rag_context,
            "rag_techniques_metadata": rag_techniques_metadata,
            "context_updates": context_updates,
            "history": history,
        }

    def _finalize_turn(
        self,
        prep: dict,
        assistant_message: str,
        *,
        llm_response: Optional[dict] = None,
    ) -> dict:
        """Persist (or enqueue) the turn and return the final response dict.

        Safe to call with a partial assistant_message (e.g. after a voice
        interrupt) — the message is stored as-is so history stays coherent.
        """
        user_id = prep["user_id"]
        conversation_id = prep["conversation_id"]
        user_message = prep["user_message"]
        current_turn = prep["current_turn"]
        personality_scores = prep.get("personality_scores")
        rag_techniques_metadata = prep.get("rag_techniques_metadata") or []
        _t0 = prep.get("t0") or time.perf_counter()

        assistant_message = (assistant_message or "").strip() or "I'm here to listen."

        _ts = time.perf_counter()
        if self.buffered_persistence:
            pending_turns_after_enqueue = self._enqueue_turn_messages(
                conversation_id=conversation_id,
                user_id=user_id,
                turn_index=current_turn,
                user_message=user_message,
                assistant_message=assistant_message,
                personality_scores=personality_scores,
                rag_techniques=rag_techniques_metadata if rag_techniques_metadata else None,
            )
            logger.info(
                "[LATENCY] enqueue_turn_messages took %.3fs (pending_turns=%s)",
                time.perf_counter() - _ts,
                pending_turns_after_enqueue,
            )
        else:
            self.user_service.add_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="assistant",
                content=assistant_message,
                turn_index=current_turn,
                personality_scores=personality_scores,
                rag_techniques=rag_techniques_metadata if rag_techniques_metadata else None,
            )
            logger.info(
                "[LATENCY] add_message (assistant) took %.3fs",
                time.perf_counter() - _ts,
            )

            _ts = time.perf_counter()
            self.user_service.update_conversation_turns(
                conversation_id,
                increment=1,
                touch_updated_at=True,
            )
            logger.info(
                "[LATENCY] update_conversation_turns took %.3fs",
                time.perf_counter() - _ts,
            )

        logger.info(
            "[LATENCY] process_message TOTAL took %.3fs",
            time.perf_counter() - _t0,
        )

        return {
            "response": assistant_message,
            "turn": current_turn,
            "personality_scores": personality_scores,
            "rag_techniques_used": len(rag_techniques_metadata),
            "metadata": {
                "llm_raw_response": llm_response,
                "rag_techniques": rag_techniques_metadata,
                "persistence_mode": self.persistence_mode,
            },
        }

    async def process_message_streaming(
        self,
        *,
        user_id: str,
        conversation_id: str,
        user_message: str,
    ) -> AsyncIterator[dict]:
        """Async generator that streams a turn as sentence-level events.

        Yields dicts of shape {"type": "sentence"|"final", "data": {...}}.
        The turn lock is held across the whole generator so overlapping
        voice utterances cannot race. If the consumer cancels mid-stream
        (e.g. user interrupted), whatever partial text we have is still
        persisted so the next turn's history stays coherent.
        """
        turn_lock = self._get_turn_lock(conversation_id)
        await asyncio.to_thread(turn_lock.acquire)
        prep: Optional[dict] = None
        full_text = ""
        try:
            prep = await asyncio.to_thread(
                self._prepare_turn,
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=user_message,
                is_questionnaire_response=False,
            )
            if prep.get("early_return") is not None:
                er = prep["early_return"]
                if er.get("response"):
                    yield {"type": "sentence", "data": {"text": er["response"]}}
                yield {"type": "final", "data": er}
                return

            chunker = SentenceChunker()
            try:
                async for delta in self.llm.generate_response_streaming(
                    patient_utterance=prep["user_message"],
                    history=prep["history"],
                    context_updates=prep["context_updates"],
                ):
                    full_text += delta
                    for sentence in chunker.push(delta):
                        yield {"type": "sentence", "data": {"text": sentence}}
                for sentence in chunker.flush():
                    yield {"type": "sentence", "data": {"text": sentence}}
            except (asyncio.CancelledError, GeneratorExit):
                # Consumer went away (e.g. user barged in). Persist partial
                # text, re-raise so the outer task sees cancellation.
                if prep is not None:
                    try:
                        await asyncio.to_thread(
                            self._finalize_turn,
                            prep,
                            full_text.strip(),
                        )
                    except Exception as exc:
                        logger.warning("partial-persist failed: %s", exc)
                raise

            final = await asyncio.to_thread(
                self._finalize_turn,
                prep,
                full_text.strip(),
            )
            yield {"type": "final", "data": final}
        except Exception as e:
            logger.error("Error in process_message_streaming: %s", e)
            import traceback
            logger.error(traceback.format_exc())
            yield {"type": "error", "data": {"message": str(e)}}
        finally:
            turn_lock.release()

    # ==================== HELPER METHODS ====================

    def _get_history_with_buffer(self, conversation_id: str, limit: int = 10) -> List[dict]:
        """Return merged persisted + buffered history in chronological order."""
        persisted = self.user_service.get_conversation_history(
            conversation_id,
            limit=max(limit * 3, 30),
        )
        buffered = self._get_buffered_messages(conversation_id)
        combined = persisted + buffered
        if limit:
            combined = combined[-limit:]
        return combined

    def _infer_issue_tags(self, user_message: str) -> List[str]:
        """Infer issue tags from user message for RAG filtering."""
        keywords_map = {
            "anxiety": ["anxious", "worried", "nervous", "panic", "fear"],
            "depression": ["sad", "depressed", "hopeless", "empty", "down"],
            "stress": ["stress", "overwhelmed", "pressure", "burden"],
            "anger": ["angry", "frustrated", "mad", "irritated"],
            "relationships": ["relationship", "partner", "friend", "family"],
            "self-esteem": ["worthless", "inadequate", "failure", "not good enough"],
            "trauma": ["trauma", "ptsd", "flashback", "triggered"],
        }

        user_lower = user_message.lower()
        tags = []

        for tag, keywords in keywords_map.items():
            if any(kw in user_lower for kw in keywords):
                tags.append(tag)

        return tags[:3]

    def _build_context_updates(
        self,
        personality_scores: Optional[Dict[str, float]],
        rag_context: Optional[str],
        current_turn: int,
        user_profile: Dict,
        conversation_id: Optional[str] = None,
    ) -> str:
        """
        Build dynamic context updates (State + Personality + RAG + Onboarding)
        to be appended to the LLM's base persona.
        """
        updates = []

        # Prepend the rolling conversation state first so the model treats it
        # as the anchor for coherence rather than an afterthought.
        if conversation_id:
            state_block = render_state_for_prompt(
                self.get_conversation_state(conversation_id)
            )
            if state_block:
                updates.append(state_block)

        is_new_user = user_profile.get("total_text_analyzed", 0) < 100

        if current_turn == 1 and is_new_user:
            updates.append(
                "CONTEXT: This is a new conversation. Introduce yourself warmly as Ella. "
                "Be genuinely curious about them - ask what brings them here today or what's on their mind. "
                "Start building a connection naturally, like meeting a new friend."
            )
        elif current_turn <= 5 and is_new_user:
            updates.append(
                "CONTEXT: You're still getting to know this person. "
                "Be curious and warm. Ask thoughtful follow-up questions. "
                "Focus on understanding them, not analyzing them."
            )

        if personality_scores and self.enable_personality and not (
            current_turn == 1 and is_new_user
        ):
            try:
                personality_context = self._build_personality_context(personality_scores)
                if personality_context:
                    updates.append(personality_context)
            except Exception as e:
                logger.warning("Failed to generate personality context: %s", e)

        if rag_context:
            updates.append(
                f"SOME RELEVANT IDEAS THAT MIGHT HELP (use naturally if appropriate):\n{rag_context}"
            )

        return "\n\n".join(updates)

    def _build_personality_context(self, scores: Dict[str, float]) -> str:
        """
        Build personality-aware context for natural conversation adaptation.
        Uses Big Five traits to subtly adjust communication style.
        """
        adaptations = []

        neuroticism = scores.get("Neuroticism", 0.5)
        if neuroticism > 0.6:
            adaptations.append(
                "They may be feeling emotionally sensitive - be especially gentle, patient, and reassuring"
            )
        elif neuroticism < 0.4:
            adaptations.append(
                "They tend to be emotionally steady - you can be more direct and matter-of-fact"
            )

        conscientiousness = scores.get("Conscientiousness", 0.5)
        if conscientiousness > 0.6:
            adaptations.append(
                "They appreciate structure and organization - consider offering clear frameworks or steps when relevant"
            )
        elif conscientiousness < 0.4:
            adaptations.append(
                "They prefer flexibility - keep things open-ended and exploratory"
            )

        openness = scores.get("Openness", 0.5)
        if openness > 0.6:
            adaptations.append(
                "They're open to new perspectives and ideas - feel free to offer fresh viewpoints"
            )
        elif openness < 0.4:
            adaptations.append(
                "They prefer familiar concepts - build on what they already know and are comfortable with"
            )

        extroversion = scores.get("Extroversion", 0.5)
        if extroversion > 0.6:
            adaptations.append(
                "They enjoy interactive conversation - engage actively and ask questions"
            )
        elif extroversion < 0.4:
            adaptations.append(
                "They appreciate space for reflection - don't feel the need to fill every silence"
            )

        agreeableness = scores.get("Agreeableness", 0.5)
        if agreeableness > 0.6:
            adaptations.append(
                "They respond well to warmth and collaboration - be especially supportive"
            )
        elif agreeableness < 0.4:
            adaptations.append("They appreciate directness - be straightforward and honest")

        if adaptations:
            return "PERSONALITY CONTEXT (adapt your style naturally):\n" + "\n".join(
                f"- {a}" for a in adaptations
            )
        return ""

    def _generate_llm_response(
        self,
        user_message: str,
        context_updates: str,
        history: List[dict],
    ) -> dict:
        """Generate LLM response with custom context updates."""
        try:
            return self.llm.generate_response(
                patient_utterance=user_message,
                history=history,
                context_updates=context_updates,
            )
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            return {
                "Response": "I'm having trouble processing your message right now. Could you please rephrase?",
                "error": str(e),
            }

    # ==================== UTILITY METHODS ====================

    def get_user_profile(self, user_id: str) -> Optional[dict]:
        """Get complete user profile."""
        return self.user_service.get_user_profile(user_id)

    def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[dict]:
        """Get persisted conversation history."""
        return self.user_service.get_conversation_history(conversation_id, limit)

    def get_questionnaire_status(self, user_id: str) -> Optional[dict]:
        """Get current questionnaire status for a user."""
        questionnaire = self.questionnaires.get(user_id)
        if questionnaire:
            return questionnaire.get_progress()
        return None

    def skip_questionnaire(self, user_id: str) -> dict:
        """Skip the questionnaire and proceed to regular conversation."""
        questionnaire = self.questionnaires.get(user_id)
        if questionnaire:
            skipped = questionnaire.skip_remaining()

            self.user_service.mark_questionnaire_completed(user_id, completed=True)

            return {
                "skipped": skipped,
                "message": "Questionnaire skipped. You can proceed with regular conversation.",
            }

        self.user_service.mark_questionnaire_completed(user_id, completed=True)

        return {
            "skipped": 0,
            "message": "No active questionnaire found.",
        }

    def close(self):
        """Clean up resources."""
        if self.buffered_persistence:
            self._flush_stop_event.set()
            if self._flush_thread and self._flush_thread.is_alive():
                self._flush_thread.join(timeout=2.0)
            self.flush_all_buffers(reason="shutdown")

        self.db_client.close()
        logger.info("ConversationManager closed")
