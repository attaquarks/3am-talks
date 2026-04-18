from typing import Dict, Optional, List
from datetime import datetime
import logging
import uuid
from .supabase_client import SupabaseClient, normalize_postgrest_value

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing user profiles, conversations, and messages"""
    
    def __init__(self, supabase_client: SupabaseClient):
        self.db = supabase_client
    
    # ==================== USER PROFILE METHODS ====================
    
    def create_user_profile(self, user_id: Optional[str] = None) -> dict:
        """Create a new user profile with default personality scores"""
        data = {
            "extroversion": 0.5,
            "neuroticism": 0.5,
            "agreeableness": 0.5,
            "conscientiousness": 0.5,
            "openness": 0.5,
            "total_text_analyzed": 0,
            "questionnaire_completed": False,
            "profile_version": 1
        }

        if user_id:
            data["user_id"] = user_id

        try:
            profile = self.db.insert("user_profiles", data)
            logger.info(f"Created user profile: {profile.get('user_id')}")
            return profile
        except Exception as e:
            logger.error(f"Failed to create user profile: {e}")
            raise

    def mark_questionnaire_completed(self, user_id: str, completed: bool = True) -> dict:
        """Mark the user's questionnaire as completed or skipped"""
        try:
            updated_profile = self.db.update(
                "user_profiles",
                {"questionnaire_completed": completed},
                {"user_id": f"eq.{user_id}"}
            )
            logger.info(f"Marked questionnaire as {'completed' if completed else 'skipped'} for user {user_id}")
            return updated_profile
        except Exception as e:
            logger.error(f"Failed to update questionnaire status: {e}")
            raise
    
    def get_user_profile(self, user_id: str) -> Optional[dict]:
        """Get user profile by user_id"""
        try:
            profiles = self.db.select(
                "user_profiles",
                filters={"user_id": f"eq.{user_id}"}
            )
            return profiles[0] if profiles else None
        except Exception as e:
            logger.error(f"Failed to get user profile {user_id}: {e}")
            return None
    
    def update_personality_scores(
        self, 
        user_id: str, 
        scores: Dict[str, float],
        text_length: int = 0
    ) -> dict:
        """Update user's personality scores"""
        try:
            profile = self.get_user_profile(user_id)
            if not profile:
                raise ValueError(f"User profile {user_id} not found")
            
            current_text_analyzed = profile.get("total_text_analyzed", 0)
            
            update_data = {
                "extroversion": scores.get("Extroversion", 0.5),
                "neuroticism": scores.get("Neuroticism", 0.5),
                "agreeableness": scores.get("Agreeableness", 0.5),
                "conscientiousness": scores.get("Conscientiousness", 0.5),
                "openness": scores.get("Openness", 0.5),
                "personality_updated_at": datetime.utcnow().isoformat(),
                "total_text_analyzed": current_text_analyzed + text_length,
                "profile_version": profile.get("profile_version", 1) + 1
            }
            
            updated_profile = self.db.update(
                "user_profiles",
                update_data,
                {"user_id": f"eq.{user_id}"}
            )
            
            logger.info(f"Updated personality scores for user {user_id}")
            return updated_profile
        except Exception as e:
            logger.error(f"Failed to update personality scores: {e}")
            raise
    
    def update_risk_flags(self, user_id: str, risk_flags: dict) -> dict:
        """Update risk flags for a user"""
        try:
            updated_profile = self.db.update(
                "user_profiles",
                {"risk_flags": risk_flags},
                {"user_id": f"eq.{user_id}"}
            )
            logger.info(f"Updated risk flags for user {user_id}")
            return updated_profile
        except Exception as e:
            logger.error(f"Failed to update risk flags: {e}")
            raise
    
    def update_preferences(self, user_id: str, preferences: dict) -> dict:
        """Update user preferences"""
        try:
            updated_profile = self.db.update(
                "user_profiles",
                {"preferences": preferences},
                {"user_id": f"eq.{user_id}"}
            )
            logger.info(f"Updated preferences for user {user_id}")
            return updated_profile
        except Exception as e:
            logger.error(f"Failed to update preferences: {e}")
            raise
    
    # ==================== CONVERSATION METHODS ====================
    
    def create_conversation(self, user_id: str) -> dict:
        """Create a new conversation for a user"""
        try:
            # First check if user profile exists
            profile = self.get_user_profile(user_id)
            if not profile:
                logger.info(f"User profile not found for {user_id}, creating new profile")
                self.create_user_profile(user_id)
            
            conversation = self.db.insert("conversations", {
                "user_id": user_id,
                "is_active": True,
                "total_turns": 0,
                "last_personality_update_turn": 0
            })
            
            logger.info(f"Created conversation: {conversation.get('conversation_id')}")
            return conversation
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            raise
    
    def get_conversation(self, conversation_id: str) -> Optional[dict]:
        """Get conversation by ID"""
        try:
            conversation_id = normalize_postgrest_value(conversation_id)
            conversations = self.db.select(
                "conversations",
                filters={"conversation_id": f"eq.{conversation_id}"}
            )
            return conversations[0] if conversations else None
        except Exception as e:
            logger.error(f"Failed to get conversation {conversation_id}: {e}")
            return None
    
    def get_active_conversation(self, user_id: str) -> Optional[dict]:
        """Get active conversation for a user"""
        try:
            conversations = self.db.select(
                "conversations",
                filters={
                    "user_id": f"eq.{user_id}",
                    "is_active": "eq.true"
                }
            )
            return conversations[0] if conversations else None
        except Exception as e:
            logger.error(f"Failed to get active conversation for user {user_id}: {e}")
            return None
    
    def end_conversation(self, conversation_id: str) -> dict:
        """Mark a conversation as ended"""
        try:
            conversation_id = normalize_postgrest_value(conversation_id)
            updated_conversation = self.db.update(
                "conversations",
                {
                    "is_active": False,
                    "ended_at": datetime.utcnow().isoformat()
                },
                {"conversation_id": f"eq.{conversation_id}"}
            )
            logger.info(f"Ended conversation: {conversation_id}")
            return updated_conversation
        except Exception as e:
            logger.error(f"Failed to end conversation: {e}")
            raise
    
    def update_conversation_turns(
        self, 
        conversation_id: str, 
        increment: int = 1,
        update_personality_turn: bool = False
    ) -> dict:
        """Update conversation turn count"""
        try:
            conversation_id = normalize_postgrest_value(conversation_id)
            conversation = self.get_conversation(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
            
            current_turns = conversation.get("total_turns", 0)
            new_turns = current_turns + increment
            
            update_data = {"total_turns": new_turns}
            
            if update_personality_turn:
                update_data["last_personality_update_turn"] = new_turns
            
            updated_conversation = self.db.update(
                "conversations",
                update_data,
                {"conversation_id": f"eq.{conversation_id}"}
            )
            
            return updated_conversation
        except Exception as e:
            logger.error(f"Failed to update conversation turns: {e}")
            raise
    
    # ==================== MESSAGE METHODS ====================
    
    def add_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        turn_index: int,
        personality_scores: Optional[dict] = None,
        rag_techniques: Optional[list] = None
    ) -> dict:
        """Add a message to a conversation"""
        try:
            conversation_id = normalize_postgrest_value(conversation_id)
            message_data = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "role": role,
                "content": content,
                "turn_index": turn_index
            }
            
            if personality_scores:
                message_data["personality_scores_at_turn"] = personality_scores
            
            if rag_techniques:
                message_data["rag_techniques_used"] = rag_techniques
            
            message = self.db.insert("messages", message_data)
            logger.info(f"Added {role} message to conversation {conversation_id}")
            return message
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            raise
    
    def get_conversation_history(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[dict]:
        """Get conversation message history"""
        try:
            conversation_id = normalize_postgrest_value(conversation_id)
            filters = {"conversation_id": f"eq.{conversation_id}"}
            
            messages = self.db.select(
                "messages",
                columns="*",
                filters=filters
            )
            
            # Sort by turn_index
            messages_sorted = sorted(messages, key=lambda x: x.get("turn_index", 0))
            
            if limit:
                messages_sorted = messages_sorted[-limit:]
            
            return messages_sorted
        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []
    
    def get_user_conversation_text(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
        last_n_turns: int = 5
    ) -> str:
        """Get recent user text for personality analysis"""
        try:
            if conversation_id:
                messages = self.get_conversation_history(conversation_id)
            else:
                # Get from active conversation
                active_conv = self.get_active_conversation(user_id)
                if not active_conv:
                    return ""
                messages = self.get_conversation_history(active_conv["conversation_id"])
            
            # Filter user messages only and get last N
            user_messages = [
                msg["content"] 
                for msg in messages 
                if msg.get("role") == "user"
            ][-last_n_turns:]
            
            return " ".join(user_messages)
        except Exception as e:
            logger.error(f"Failed to get user conversation text: {e}")
            return ""
    
    # ==================== UTILITY METHODS ====================
    
    def should_update_personality(self, conversation_id: str, update_interval: int = 40) -> bool:
        """Check if personality should be updated based on turn count"""
        try:
            conversation_id = normalize_postgrest_value(conversation_id)
            conversation = self.get_conversation(conversation_id)
            if not conversation:
                return False
            
            total_turns = conversation.get("total_turns", 0)
            last_update = conversation.get("last_personality_update_turn", 0)
            
            return (total_turns - last_update) >= update_interval
        except Exception as e:
            logger.error(f"Failed to check personality update: {e}")
            return False
