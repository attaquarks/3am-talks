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
from conversation.questionnaire import PersonalityQuestionnaire

logger = logging.getLogger(__name__)
class ConversationManager:
    """
    Main orchestrator for the 3AM Talks therapy system.
    Manages user profiles, personality updates, RAG retrieval, and conversation flow.
    """
    
    def __init__(
        self,
        model_name: str = "psychocounsel",
        personality_model_path: str = "Models/bert-base-personality",
        personality_update_interval: int = 40,  # Update personality every 40 turns
        enable_rag: bool = True,
        enable_personality: bool = True
    ):
        """
        Initialize the conversation manager
        
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

            # Ensure profile exists (create if missing)
            profile = self.user_service.get_user_profile(user_id)
            if not profile:
                logger.warning(f"Profile not found for {user_id}, creating one")
                self.user_service.create_user_profile(user_id)

            # Create conversation
            conversation = self.user_service.create_conversation(user_id)

            logger.info(f"Started session for user {user_id}, conv={conversation['conversation_id']}")

            return {
                "user_id": user_id,
                "conversation_id": conversation["conversation_id"],
                "message": "Session started successfully",
            }
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
            questionnaire = self.questionnaires.get(user_id)
            
            if is_questionnaire_response and questionnaire and not questionnaire.completed:
                # Get current question
                current_question = questionnaire.get_next_question()
                if current_question:
                    # Save response to the database
                    try:
                        self.db_client.insert(
                            "questionnaire_responses",
                            {
                                "user_id": user_id,
                                "question": current_question["question"],
                                "response": user_message
                            }
                        )
                    except Exception as e:
                        logger.error(f"Failed to save response to database: {e}")

                    # Submit response to in-memory system
                    questionnaire.submit_response(
                        current_question["id"],
                        user_message
                    )
                    
                    # If questionnaire is now complete, analyze personality
                    if questionnaire.completed:
                        # Get all responses text
                        questionnaire_text = questionnaire.get_all_responses_text()

                        # Analyze personality from questionnaire
                        personality_scores = None
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

                        # Mark questionnaire as completed in database
                        self.user_service.mark_questionnaire_completed(user_id, completed=True)

                        return {
                            "response": "Thank you for completing the initial assessment. I now have a better understanding of you, and we can continue our conversation.",
                            "turn": current_turn,
                            "questionnaire": {
                                "completed": True,
                                "message": "Thank you for completing the initial assessment. I now have a better understanding of you, and we can continue our conversation."
                            },
                            "personality_scores": personality_scores
                        }

                    # Questionnaire is not yet complete, return next question
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
                            "personality_scores": None
                        }
            
            # Step 2: Save user message
            self.user_service.add_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=user_message,
                turn_index=current_turn
            )
            
            # Step 3: Update personality if needed
            personality_scores = self._update_personality_if_needed(
                user_id,
                conversation_id,
                force_update=False
            )
            
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

        # 2. Personality Adaptation (only if we have valid scores and it's not the very first turn)
        if personality_scores and self.enable_personality and not (current_turn == 1 and is_new_user):
            # Adapt conversation style based on personality traits
            try:
                personality_context = self._build_personality_context(personality_scores)
                if personality_context:
                    updates.append(personality_context)
            except Exception as e:
                logger.warning(f"Failed to generate personality context: {e}")

        # 3. RAG Context - Only include if genuinely relevant
        if rag_context:
            updates.append(f"SOME RELEVANT IDEAS THAT MIGHT HELP (use naturally if appropriate):\n{rag_context}")

        return "\n\n".join(updates)

    def _build_personality_context(self, scores: Dict[str, float]) -> str:
        """
        Build personality-aware context for natural conversation adaptation.
        Uses Big Five traits to subtly adjust communication style.
        """
        adaptations = []

        # Neuroticism - Adjust emotional sensitivity
        neuroticism = scores.get("Neuroticism", 0.5)
        if neuroticism > 0.6:
            adaptations.append("They may be feeling emotionally sensitive - be especially gentle, patient, and reassuring")
        elif neuroticism < 0.4:
            adaptations.append("They tend to be emotionally steady - you can be more direct and matter-of-fact")

        # Conscientiousness - Adjust structure preference
        conscientiousness = scores.get("Conscientiousness", 0.5)
        if conscientiousness > 0.6:
            adaptations.append("They appreciate structure and organization - consider offering clear frameworks or steps when relevant")
        elif conscientiousness < 0.4:
            adaptations.append("They prefer flexibility - keep things open-ended and exploratory")

        # Openness - Adjust comfort with new ideas
        openness = scores.get("Openness", 0.5)
        if openness > 0.6:
            adaptations.append("They're open to new perspectives and ideas - feel free to offer fresh viewpoints")
        elif openness < 0.4:
            adaptations.append("They prefer familiar concepts - build on what they already know and are comfortable with")

        # Extroversion - Adjust interaction style
        extroversion = scores.get("Extroversion", 0.5)
        if extroversion > 0.6:
            adaptations.append("They enjoy interactive conversation - engage actively and ask questions")
        elif extroversion < 0.4:
            adaptations.append("They appreciate space for reflection - don't feel the need to fill every silence")

        # Agreeableness - Adjust warmth level
        agreeableness = scores.get("Agreeableness", 0.5)
        if agreeableness > 0.6:
            adaptations.append("They respond well to warmth and collaboration - be especially supportive")
        elif agreeableness < 0.4:
            adaptations.append("They appreciate directness - be straightforward and honest")

        if adaptations:
            return "PERSONALITY CONTEXT (adapt your style naturally):\n" + "\n".join(f"- {a}" for a in adaptations)
        return ""
    
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

            # Mark questionnaire as completed (skipped) in database
            self.user_service.mark_questionnaire_completed(user_id, completed=True)

            return {
                "skipped": skipped,
                "message": "Questionnaire skipped. You can proceed with regular conversation."
            }

        # Even if no active questionnaire, mark as completed in database
        # (handles case where frontend skipped after session start)
        self.user_service.mark_questionnaire_completed(user_id, completed=True)

        return {
            "skipped": 0,
            "message": "No active questionnaire found."
        }
    
    def close(self):
        """Clean up resources"""
        self.db_client.close()
        logger.info("ConversationManager closed")
