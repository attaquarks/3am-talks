import logging
from typing import Dict, Optional, List
import sys
from pathlib import Path

# Import all components
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SupabaseClient, UserService
from ai_layer.personality_service import PersonalityService, PsyCOTInference
from ai_layer.llm_service import LLMService
from rag_layer import RAGService
from questionnaire import PersonalityQuestionnaire

logger = logging.getLogger(__name__)
class ConversationManager:
    """
    Main orchestrator for the 3AM Talks therapy system.
    Manages user profiles, personality updates, RAG retrieval, and conversation flow.
    """
    
    def __init__(
        self,
        model_name: str = "psychocounsel",
        ollama_base_url: str = "http://127.0.0.1:11434",
        personality_model_path: str = "Models/bert-base-personality",
        personality_update_interval: int = 40,  # Update personality every 40 turns
        enable_rag: bool = True,
        enable_personality: bool = True
    ):
        """
        Initialize the conversation manager
        
        Args:
            model_name: Ollama model name
            ollama_base_url: Ollama API URL
            personality_model_path: Path to BERT personality model
            personality_update_interval: Update personality every N turns (30-50 recommended)
            enable_rag: Enable RAG retrieval
            enable_personality: Enable personality detection
        """
        # Initialize database
        self.db_client = SupabaseClient()
        self.user_service = UserService(self.db_client)
        
        # Initialize AI components
        self.llm = LLMService(model_name, ollama_base_url)
        
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
        
        logger.info("ConversationManager initialized")
    
    # ==================== SESSION MANAGEMENT ====================
    
    # ==================== AUTHENTICATION ====================
    
    def register_user(self, email: str, password: str) -> Dict:
        """Register a new user and create their profile"""
        try:
            # 1. Sign up with Supabase Auth
            auth_response = self.db_client.sign_up(email, password)
            
            # Extract user ID (handle different response structures)
            user = auth_response.get("user") or auth_response
            user_id = user.get("id")
            
            if not user_id:
                raise ValueError("Failed to get User ID from signup response")
            
            logger.info(f"Registered user auth: {user_id}")
            
            # 2. Create local user profile
            profile = self.user_service.create_user_profile(user_id)
            
            return {
                "user_id": user_id,
                "email": email,
                "profile": profile
            }
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            raise

    def login_user(self, email: str, password: str) -> Dict:
        """Login an existing user"""
        try:
            auth_response = self.db_client.sign_in(email, password)
            
            # Extract user/session
            user = auth_response.get("user")
            user_id = user.get("id") if user else None
            access_token = auth_response.get("access_token")
            
            if not user_id:
                raise ValueError("Failed to get User ID from login response")
                
            return {
                "user_id": user_id,
                "access_token": access_token
            }
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise

    # ==================== SESSION MANAGEMENT ====================
    
    def start_session(self, user_id: str, start_questionnaire: bool = True) -> Dict[str, str]:
        """
        Start a new conversation session for a user
        
        Args:
            user_id: Required User ID (from auth)
            start_questionnaire: Whether to start with personality questionnaire for new users
        
        Returns:
            dict with session info and optionally first questionnaire question
        """
        try:
            if not user_id:
                 raise ValueError("User ID is required to start a session")
            
            # Verify profile exists
            profile = self.user_service.get_user_profile(user_id)
            is_new_user = False
            if not profile:
                logger.warning(f"Profile not found for {user_id}, attempting to create")
                profile = self.user_service.create_user_profile(user_id)
                is_new_user = True
            elif profile.get("total_text_analyzed", 0) == 0:
                # If profile exists but has no analysis history, treat as new user
                is_new_user = True
            
            # Check if user needs questionnaire (new user with minimal text analyzed)
            needs_questionnaire = (
                start_questionnaire and 
                is_new_user and 
                profile.get("total_text_analyzed", 0) < 100
            )
            
            # Create conversation
            conversation = self.user_service.create_conversation(user_id)
            
            result = {
                "user_id": user_id,
                "conversation_id": conversation["conversation_id"],
                "message": "Session started successfully",
                "is_new_user": is_new_user
            }
            
            # If new user, start questionnaire
            if needs_questionnaire:
                # Create questionnaire for this user
                self.questionnaires[user_id] = PersonalityQuestionnaire()
                first_question = self.questionnaires[user_id].get_next_question()
                result["questionnaire"] = {
                    "active": True,
                    "question": first_question
                }
            
            logger.info(f"Started session for user {user_id}")
            
            return result
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            raise
    
    def end_session(self, conversation_id: str) -> dict:
        """End a conversation session"""
        try:
            self.user_service.end_conversation(conversation_id)
            return {"message": "Session ended successfully"}
        except Exception as e:
            logger.error(f"Failed to end session: {e}")
            raise
    
    # ==================== PERSONALITY MANAGEMENT ====================
    
    def _update_personality_if_needed(
        self, 
        user_id: str, 
        conversation_id: str,
        force_update: bool = False
    ) -> Optional[Dict[str, float]]:
        """Update personality profile if enough turns have passed"""
        if not self.enable_personality:
            return None
        
        try:
            # Check if update is needed
            should_update = force_update or self.user_service.should_update_personality(
                conversation_id, 
                self.personality_update_interval
            )
            
            if not should_update:
                # Return current personality scores
                profile = self.user_service.get_user_profile(user_id)
                return {
                    "Extroversion": profile.get("extroversion", 0.5),
                    "Neuroticism": profile.get("neuroticism", 0.5),
                    "Agreeableness": profile.get("agreeableness", 0.5),
                    "Conscientiousness": profile.get("conscientiousness", 0.5),
                    "Openness": profile.get("openness", 0.5)
                }
            
            # Get recent user text
            user_text = self.user_service.get_user_conversation_text(
                user_id, 
                conversation_id,
                last_n_turns=5
            )
            
            if not user_text or len(user_text) < 50:
                logger.info("Not enough text for personality update")
                return None
            
            # Detect personality
            scores = self.personality_detector.detect_personality(user_text)
            
            # Update in database
            self.user_service.update_personality_scores(
                user_id,
                scores,
                len(user_text)
            )
            
            # Mark that personality was updated
            self.user_service.update_conversation_turns(
                conversation_id,
                increment=0,
                update_personality_turn=True
            )
            
            logger.info(f"Updated personality for user {user_id}: {scores}")
            return scores
            
        except Exception as e:
            logger.error(f"Failed to update personality: {e}")
            return None
    
    # ==================== CORE CONVERSATION FLOW ====================
    
    def process_message(
        self,
        user_id: str,
        conversation_id: str,
        user_message: str,
        is_questionnaire_response: bool = False
    ) -> dict:
        """
        Process a user message through the complete pipeline:
        1. Load user profile
        2. Update personality if needed
        3. Retrieve RAG techniques
        4. Generate LLM response with personality-aware prompt
        5. Save conversation to database
        
        Args:
            user_id: User ID
            conversation_id: Conversation ID
            user_message: User's message
            is_questionnaire_response: Whether this is a response to a questionnaire question
        
        Returns:
            dict with response and metadata
        """
        try:
            # Get current conversation state
            conversation = self.user_service.get_conversation(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
            
            current_turn = conversation.get("total_turns", 0) + 1
            
            # Step 1: Get user profile
            profile = self.user_service.get_user_profile(user_id)
            if not profile:
                raise ValueError(f"User profile {user_id} not found")
            
            # Handle questionnaire responses
            questionnaire_completed = False
            questionnaire = self.questionnaires.get(user_id)
            
            if is_questionnaire_response and questionnaire and not questionnaire.completed:
                # Get current question
                current_question = questionnaire.get_next_question()
                if current_question:
                    # Submit response
                    questionnaire.submit_response(
                        current_question["id"],
                        user_message
                    )
                    
                    # If questionnaire is now complete, analyze personality
                    if questionnaire.completed:
                        questionnaire_completed = True
                        # Get all responses text
                        questionnaire_text = questionnaire.get_all_responses_text()
                        
                        # Analyze personality from questionnaire
                        if self.enable_personality and self.personality_detector:
                            personality_scores = self.personality_detector.detect_personality(
                                questionnaire_text
                            )
                            # Update profile with initial personality
                            self.user_service.update_personality_scores(
                                user_id,
                                personality_scores,
                                len(questionnaire_text)
                            )
                            logger.info(f"Initial personality assessed from questionnaire for user {user_id}")
            
            # Step 2: Save user message
            self.user_service.add_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=user_message,
                turn_index=current_turn
            )
            
            # Step 3: Update personality if needed (or get current if questionnaire just completed)
            if not questionnaire_completed:
                personality_scores = self._update_personality_if_needed(
                    user_id,
                    conversation_id,
                    force_update=False
                )
            
            # If questionnaire is active and not completed, return next question
            if is_questionnaire_response and questionnaire and not questionnaire.completed:
                next_question = questionnaire.get_next_question()
                if next_question:
                    return {
                        "response": f"Thank you for sharing that. {next_question['question']}",
                        "turn": current_turn,
                        "questionnaire": {
                            "active": True,
                            "question": next_question,
                            "progress": questionnaire.get_progress()
                        },
                        "personality_scores": personality_scores if questionnaire_completed else None
                    }
            
            # Step 4: Retrieve RAG techniques
            rag_context = None
            rag_techniques_metadata = []
            
            if self.enable_rag and self.rag_service:
                try:
                    # Infer issue tags from user message
                    issue_tags = self._infer_issue_tags(user_message)
                    
                    # Retrieve relevant techniques
                    techniques = self.rag_service.retrieve_relevant_techniques(
                        query=user_message,
                        issue_tags=issue_tags,
                        top_k=3
                    )
                    
                    # Format for prompt
                    rag_context = self.rag_service.format_techniques_for_prompt(techniques)
                    
                    # Store metadata
                    rag_techniques_metadata = [
                        {
                            "id": t.get("id"),
                            "technique_name": t.get("metadata", {}).get("technique_name"),
                            "score": t.get("score")
                        }
                        for t in techniques
                    ]
                    
                    logger.info(f"Retrieved {len(techniques)} RAG techniques")
                except Exception as e:
                    logger.error(f"RAG retrieval failed: {e}")
                    rag_context = None
            
            # Step 5: Build context updates (Personality + RAG + Onboarding)
            context_updates = self._build_context_updates(
                personality_scores, 
                rag_context, 
                current_turn, 
                profile
            )
            
            # Step 6: Get conversation history context
            history_messages = self.user_service.get_conversation_history(
                conversation_id,
                limit=10
            )
            
            # Format history for LLM
            history = []
            for msg in history_messages[:-1]:  # Exclude the current user message
                history.append({
                    "role": msg.get("role"),
                    "content": msg.get("content")
                })
            
            # Step 7: Generate LLM response
            llm_response = self._generate_llm_response(
                user_message=user_message,
                context_updates=context_updates,
                history=history
            )
            
            # Step 8: Save assistant response
            assistant_message = llm_response.get("Response", "I'm here to listen.")
            
            self.user_service.add_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="assistant",
                content=assistant_message,
                turn_index=current_turn,
                personality_scores=personality_scores,
                rag_techniques=rag_techniques_metadata if rag_techniques_metadata else None
            )
            
            # Step 9: Update conversation turn count
            self.user_service.update_conversation_turns(
                conversation_id,
                increment=1
            )
            
            # Return response
            result = {
                "response": assistant_message,
                "turn": current_turn,
                "personality_scores": personality_scores,
                "rag_techniques_used": len(rag_techniques_metadata),
                "metadata": {
                    "llm_raw_response": llm_response,
                    "rag_techniques": rag_techniques_metadata
                }
            }
            
            # Add questionnaire completion message if just completed
            if questionnaire_completed:
                result["questionnaire"] = {
                    "completed": True,
                    "message": "Thank you for completing the initial assessment. I now have a better understanding of you, and we can continue our conversation."
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    # ==================== HELPER METHODS ====================
    
    def _infer_issue_tags(self, user_message: str) -> List[str]:
        """Infer issue tags from user message for RAG filtering"""
        keywords_map = {
            "anxiety": ["anxious", "worried", "nervous", "panic", "fear"],
            "depression": ["sad", "depressed", "hopeless", "empty", "down"],
            "stress": ["stress", "overwhelmed", "pressure", "burden"],
            "anger": ["angry", "frustrated", "mad", "irritated"],
            "relationships": ["relationship", "partner", "friend", "family"],
            "self-esteem": ["worthless", "inadequate", "failure", "not good enough"],
            "trauma": ["trauma", "ptsd", "flashback", "triggered"]
        }
        
        user_lower = user_message.lower()
        tags = []
        
        for tag, keywords in keywords_map.items():
            if any(kw in user_lower for kw in keywords):
                tags.append(tag)
        
        return tags[:3]  # Return top 3 tags
    
    def _build_context_updates(
        self,
        personality_scores: Optional[Dict[str, float]],
        rag_context: Optional[str],
        current_turn: int,
        user_profile: Dict
    ) -> str:
        """
        Build dynamic context updates (Personality + RAG + Onboarding) 
        to be appended to the LLM's base persona.
        """
        updates = []
        
        # 1. Onboarding / New User Logic
        is_new_user = user_profile.get("total_text_analyzed", 0) < 100
        
        if current_turn == 1 and is_new_user:
            updates.append(
                "NOTICE: This is a NEW patient. Start by briefly introducing yourself as a supportive CBT therapist. "
                "Then, politely ask a simple opening question to get to know them and their communication style. "
                "Do not dive into deep therapy yet."
            )
        elif current_turn <= 5 and is_new_user:
             updates.append(
                "NOTICE: You are still in the initial assessment phase. "
                "Continue to ask open-ended questions to gather text for personality analysis. "
                "Be warm and encouraging."
            )

        # 2. Personality Adaptation (only if we have valid scores and it's not the very first turn)
        if personality_scores and self.enable_personality and not (current_turn == 1 and is_new_user):
            # Only use inference if we have enough data (handled by should_update logic, but beneficial to check here too)
            # PsyCOTInference creates strings like "Use a warm tone..."
            try:
                # We pass an empty string as base because we only want the instructions
                personality_instructions = PsyCOTInference.create_personality_aware_system_prompt("", personality_scores)
                updates.append(personality_instructions.strip())
            except Exception as e:
                logger.warning(f"Failed to generate personality instructions: {e}")
        
        # 3. RAG Context
        if rag_context:
            updates.append(f"RELEVANT THERAPEUTIC TECHNIQUES:\n{rag_context}")
        
        return "\n\n".join(updates)
    
    def _generate_llm_response(
        self,
        user_message: str,
        context_updates: str,
        history: List[dict]
    ) -> dict:
        """Generate LLM response with custom context updates"""
        try:
            # Call the LLM with the context updates
            return self.llm.generate_response(
                patient_utterance=user_message,
                history=history,
                context_updates=context_updates
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return {
                "Response": "I'm having trouble processing your message right now. Could you please rephrase?",
                "error": str(e)
            }
    
    # ==================== UTILITY METHODS ====================
    
    def get_user_profile(self, user_id: str) -> Optional[dict]:
        """Get complete user profile"""
        return self.user_service.get_user_profile(user_id)
    
    def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[dict]:
        """Get conversation history"""
        return self.user_service.get_conversation_history(conversation_id, limit)
    
    def get_questionnaire_status(self, user_id: str) -> Optional[dict]:
        """Get current questionnaire status for a user"""
        questionnaire = self.questionnaires.get(user_id)
        if questionnaire:
            return questionnaire.get_progress()
        return None
    
    def skip_questionnaire(self, user_id: str) -> dict:
        """Skip the questionnaire and proceed to regular conversation"""
        questionnaire = self.questionnaires.get(user_id)
        if questionnaire:
            skipped = questionnaire.skip_remaining()
            return {
                "skipped": skipped,
                "message": "Questionnaire skipped. You can proceed with regular conversation."
            }
        return {
            "skipped": 0,
            "message": "No active questionnaire found."
        }
    
    def close(self):
        """Clean up resources"""
        self.db_client.close()
        logger.info("ConversationManager closed")
