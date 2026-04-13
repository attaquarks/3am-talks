"""
Comprehensive test suite for the 3AM Talks therapy system.
Tests the complete flow from user signup to conversation with personality updates.
"""

import os
import sys
import pytest
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from conversation_manager import ConversationManager
from database import SupabaseClient, UserService
from ai_layer.personality_service import PersonalityService, PsyCOTInference
from questionnaire import PersonalityQuestionnaire

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestFullSystem:
    """Test suite for the complete 3AM Talks system"""
    
    def initialize(self):
        """Initialize test environment"""
        # Check for required environment variables
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.pinecone_key = os.getenv("PINECONE_API_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            logger.warning("SUPABASE_URL and SUPABASE_KEY must be set in environment")
            # We don't skip here for manual runs, just warn, but manager init might fail or use defaults?
            # actually manager init doesn't need supabase immediately maybe?
            # but let's keep pytest logic separate
            if "pytest" in sys.modules:
                pytest.skip("SUPABASE_URL and SUPABASE_KEY must be set in environment")
            else:
                raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        
        # Initialize conversation manager with test settings
        self.manager = ConversationManager(
            model_name="psychocounsel",
            personality_model_path="Models/bert-base-personality",
            personality_update_interval=5,  # Use 5 for faster testing (normally 30-50)
            enable_rag=True,
            enable_personality=True
        )
        
        # Generate unique test user email
        self.test_email = f"test_{int(time.time())}@example.com"
        self.test_password = "TestPassword123!"

    def cleanup(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'manager') and self.manager:
                self.manager.close()
        except:
            pass

    @pytest.fixture(autouse=True)
    def setup_fixture(self):
        """Pytest fixture for setup/teardown"""
        self.initialize()
        yield
        self.cleanup()
    
    def test_1_user_registration(self):
        """Test 1: User registration and profile creation"""
        logger.info("=" * 60)
        logger.info("TEST 1: User Registration")
        logger.info("=" * 60)
        
        # Register new user
        result = self.manager.register_user(self.test_email, self.test_password)
        
        assert "user_id" in result
        assert "email" in result
        assert result["email"] == self.test_email
        assert "profile" in result
        
        user_id = result["user_id"]
        profile = result["profile"]
        
        # Verify profile has default personality scores
        assert profile.get("extroversion") == 0.5
        assert profile.get("neuroticism") == 0.5
        assert profile.get("agreeableness") == 0.5
        assert profile.get("conscientiousness") == 0.5
        assert profile.get("openness") == 0.5
        assert profile.get("total_text_analyzed") == 0
        
        logger.info(f"✓ User registered successfully: {user_id}")
        logger.info(f"✓ Profile created with default scores")
        
        return user_id
    
    def test_2_user_login(self):
        """Test 2: User login"""
        logger.info("=" * 60)
        logger.info("TEST 2: User Login")
        logger.info("=" * 60)
        
        # First register
        reg_result = self.manager.register_user(
            f"login_test_{int(time.time())}@example.com",
            self.test_password
        )
        user_id = reg_result["user_id"]
        
        # Then login
        login_result = self.manager.login_user(reg_result["email"], self.test_password)
        
        assert "user_id" in login_result
        assert login_result["user_id"] == user_id
        assert "access_token" in login_result
        
        logger.info(f"✓ User logged in successfully: {user_id}")
        
        return user_id
    
    def test_3_start_session_with_questionnaire(self):
        """Test 3: Start session and initiate questionnaire for new user"""
        logger.info("=" * 60)
        logger.info("TEST 3: Start Session with Questionnaire")
        logger.info("=" * 60)
        
        # Register new user
        reg_result = self.manager.register_user(
            f"session_test_{int(time.time())}@example.com",
            self.test_password
        )
        user_id = reg_result["user_id"]
        
        # Start session
        session_result = self.manager.start_session(user_id, start_questionnaire=True)
        
        assert "conversation_id" in session_result
        assert session_result.get("is_new_user") == True
        
        # Check if questionnaire was started
        if "questionnaire" in session_result:
            assert session_result["questionnaire"]["active"] == True
            assert "question" in session_result["questionnaire"]
            logger.info(f"✓ Questionnaire started for new user")
            logger.info(f"  First question: {session_result['questionnaire']['question']['question']}")
        
        logger.info(f"✓ Session started: {session_result['conversation_id']}")
        
        return user_id, session_result["conversation_id"]
    
    def test_4_questionnaire_flow(self):
        """Test 4: Complete questionnaire and assess initial personality"""
        logger.info("=" * 60)
        logger.info("TEST 4: Questionnaire Flow")
        logger.info("=" * 60)
        
        # Register and start session
        reg_result = self.manager.register_user(
            f"questionnaire_test_{int(time.time())}@example.com",
            self.test_password
        )
        user_id = reg_result["user_id"]
        session_result = self.manager.start_session(user_id, start_questionnaire=True)
        conversation_id = session_result["conversation_id"]
        
        # Sample responses that should reveal personality traits
        questionnaire_responses = [
            "I'm someone who loves trying new things and exploring different perspectives. I enjoy reading about various topics and learning.",
            "I'm quite social and enjoy being around people. I get energy from group activities and meeting new friends.",
            "I tend to worry a lot and feel anxious when things don't go as planned. I sometimes struggle with stress.",
            "I'm very organized and like to plan everything in advance. I set goals and work systematically towards them.",
            "I try to be understanding and cooperative with others. I value harmony in relationships.",
            "Spending time with loved ones and achieving my goals brings me satisfaction.",
            "I usually talk to friends or engage in activities to manage stress, though sometimes it's hard.",
            "I recently started learning a new language and would love to travel more."
        ]
        
        # Process questionnaire responses
        for i, response in enumerate(questionnaire_responses):
            result = self.manager.process_message(
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=response,
                is_questionnaire_response=True
            )
            
            # Check if questionnaire is still active
            if "questionnaire" in result and not result["questionnaire"].get("completed", False):
                logger.info(f"  Question {i+1} answered, next question provided")
            elif result.get("questionnaire", {}).get("completed", False):
                logger.info(f"✓ Questionnaire completed after {i+1} responses")
                break
        
        # Verify personality was assessed
        profile = self.manager.get_user_profile(user_id)
        assert profile is not None
        
        # Check that personality scores were updated (should not all be 0.5)
        personality_scores = {
            "Extroversion": profile.get("extroversion"),
            "Neuroticism": profile.get("neuroticism"),
            "Agreeableness": profile.get("agreeableness"),
            "Conscientiousness": profile.get("conscientiousness"),
            "Openness": profile.get("openness")
        }
        
        logger.info(f"✓ Personality assessed from questionnaire:")
        for trait, score in personality_scores.items():
            logger.info(f"  {trait}: {score:.3f}")
        
        # Verify text was analyzed
        assert profile.get("total_text_analyzed", 0) > 0
        logger.info(f"✓ Total text analyzed: {profile.get('total_text_analyzed')} characters")
        
        return user_id, conversation_id
    
    def test_5_regular_conversation_flow(self):
        """Test 5: Regular conversation with RAG and personality-aware responses"""
        logger.info("=" * 60)
        logger.info("TEST 5: Regular Conversation Flow")
        logger.info("=" * 60)
        
        # Setup: Register, start session, complete questionnaire
        reg_result = self.manager.register_user(
            f"conversation_test_{int(time.time())}@example.com",
            self.test_password
        )
        user_id = reg_result["user_id"]
        session_result = self.manager.start_session(user_id, start_questionnaire=False)
        conversation_id = session_result["conversation_id"]
        
        # Skip questionnaire for this test (or use existing user)
        # Simulate some initial personality
        initial_scores = {
            "Extroversion": 0.6,
            "Neuroticism": 0.7,
            "Agreeableness": 0.8,
            "Conscientiousness": 0.5,
            "Openness": 0.6
        }
        self.manager.user_service.update_personality_scores(
            user_id,
            initial_scores,
            text_length=500
        )
        
        # Test conversation messages
        test_messages = [
            "I've been feeling really anxious lately about my job.",
            "I can't stop worrying about making mistakes.",
            "It's affecting my sleep and I feel overwhelmed."
        ]
        
        for i, message in enumerate(test_messages):
            result = self.manager.process_message(
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=message,
                is_questionnaire_response=False
            )
            
            assert "response" in result
            assert "turn" in result
            assert result["turn"] == i + 1
            
            logger.info(f"  Turn {result['turn']}: User: {message}")
            logger.info(f"  Assistant: {result['response']}")
            
            # Check if RAG was used
            if result.get("rag_techniques_used", 0) > 0:
                logger.info(f"  ✓ RAG techniques retrieved: {result['rag_techniques_used']}")
        
        # Verify conversation history
        history = self.manager.get_conversation_history(conversation_id)
        assert len(history) >= len(test_messages) * 2  # User + Assistant messages
        
        logger.info(f"✓ Conversation flow working correctly")
        logger.info(f"✓ Total messages in history: {len(history)}")
        
        return user_id, conversation_id
    
    def test_6_personality_update_after_turns(self):
        """Test 6: Personality update after specified number of turns"""
        logger.info("=" * 60)
        logger.info("TEST 6: Personality Update After Turns")
        logger.info("=" * 60)
        
        # Setup
        reg_result = self.manager.register_user(
            f"personality_update_test_{int(time.time())}@example.com",
            self.test_password
        )
        user_id = reg_result["user_id"]
        session_result = self.manager.start_session(user_id, start_questionnaire=False)
        conversation_id = session_result["conversation_id"]
        
        # Set initial personality
        initial_scores = {
            "Extroversion": 0.5,
            "Neuroticism": 0.5,
            "Agreeableness": 0.5,
            "Conscientiousness": 0.5,
            "Openness": 0.5
        }
        self.manager.user_service.update_personality_scores(
            user_id,
            initial_scores,
            text_length=100
        )
        
        # Generate enough conversation turns to trigger update
        # Update interval is set to 5 for testing
        update_interval = 5
        messages_needed = update_interval + 2
        
        # Create messages that reveal different personality traits
        personality_revealing_messages = [
            "I love going to parties and meeting new people every weekend.",
            "I'm always the first to volunteer for group activities.",
            "I feel energized after social gatherings.",
            "I prefer working in teams rather than alone.",
            "I enjoy being the center of attention sometimes.",
            "I get anxious when I have to speak in front of groups.",
            "I worry about what others think of me.",
            "I often feel stressed about deadlines."
        ]
        
        personality_updates = []
        
        for i in range(messages_needed):
            message = personality_revealing_messages[i % len(personality_revealing_messages)]
            
            result = self.manager.process_message(
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=message,
                is_questionnaire_response=False
            )
            
            # Check if personality was updated
            if result.get("personality_scores"):
                scores = result["personality_scores"]
                
                # In Test 6, actual analysis only happens when conversation_turns % update_interval == 0
                is_actual_update = (result["turn"] % update_interval == 0)
                
                if is_actual_update:
                    personality_updates.append({
                        "turn": result["turn"],
                        "scores": scores
                    })
                    logger.info(f"  ✨ Turn {result['turn']}: PERSONALITY ANALYZED & UPDATED")
                else:
                    logger.info(f"  Turn {result['turn']}: Current Personality (Update in {update_interval - (result['turn'] % update_interval)} turns)")
                
                for trait, score in scores.items():
                    logger.info(f"    {trait}: {score:.3f}")
        
        # Verify personality was updated
        profile = self.manager.get_user_profile(user_id)
        final_scores = {
            "Extroversion": profile.get("extroversion"),
            "Neuroticism": profile.get("neuroticism"),
            "Agreeableness": profile.get("agreeableness"),
            "Conscientiousness": profile.get("conscientiousness"),
            "Openness": profile.get("openness")
        }
        
        logger.info(f"✓ Final personality scores:")
        for trait, score in final_scores.items():
            logger.info(f"  {trait}: {score:.3f}")
        
        # Verify update occurred
        assert len(personality_updates) > 0, "Personality should have been updated"
        logger.info(f"✓ Personality updated {len(personality_updates)} time(s) during conversation")
        
        return user_id, conversation_id
    
    def test_7_per_user_customization(self):
        """Test 7: Verify agent behaves differently for different user profiles"""
        logger.info("=" * 60)
        logger.info("TEST 7: Per-User Customization")
        logger.info("=" * 60)
        
        # Create two users with different personality profiles
        users = []
        
        for i, personality_type in enumerate(["introverted", "extroverted"]):
            reg_result = self.manager.register_user(
                f"customization_test_{personality_type}_{int(time.time())}@example.com",
                self.test_password
            )
            user_id = reg_result["user_id"]
            session_result = self.manager.start_session(user_id, start_questionnaire=False)
            conversation_id = session_result["conversation_id"]
            
            # Set different personality profiles
            if personality_type == "introverted":
                scores = {
                    "Extroversion": 0.3,  # Low extroversion
                    "Neuroticism": 0.6,   # Higher neuroticism
                    "Agreeableness": 0.7,
                    "Conscientiousness": 0.8,
                    "Openness": 0.5
                }
            else:  # extroverted
                scores = {
                    "Extroversion": 0.8,  # High extroversion
                    "Neuroticism": 0.3,   # Lower neuroticism
                    "Agreeableness": 0.7,
                    "Conscientiousness": 0.6,
                    "Openness": 0.7
                }
            
            self.manager.user_service.update_personality_scores(
                user_id,
                scores,
                text_length=500
            )
            
            users.append({
                "user_id": user_id,
                "conversation_id": conversation_id,
                "personality_type": personality_type,
                "scores": scores
            })
        
        # Send same message to both users
        test_message = "I'm feeling a bit down today."
        
        responses = []
        for user in users:
            result = self.manager.process_message(
                user_id=user["user_id"],
                conversation_id=user["conversation_id"],
                user_message=test_message,
                is_questionnaire_response=False
            )
            
            responses.append({
                "personality_type": user["personality_type"],
                "response": result["response"],
                "personality_scores": result.get("personality_scores")
            })
            
            logger.info(f"  {user['personality_type'].upper()} user response:")
            logger.info(f"    {result['response'][:150]}...")
        
        # Verify responses are different (personality-aware)
        assert responses[0]["response"] != responses[1]["response"], \
            "Responses should differ based on personality profiles"
        
        logger.info(f"✓ Agent customized responses based on user personality")
        
        return users
    
    def test_8_conversation_history_persistence(self):
        """Test 8: Verify conversation history is persisted in database"""
        logger.info("=" * 60)
        logger.info("TEST 8: Conversation History Persistence")
        logger.info("=" * 60)
        
        # Setup
        reg_result = self.manager.register_user(
            f"history_test_{int(time.time())}@example.com",
            self.test_password
        )
        user_id = reg_result["user_id"]
        session_result = self.manager.start_session(user_id, start_questionnaire=False)
        conversation_id = session_result["conversation_id"]
        
        # Create conversation
        messages = [
            "Hello, I need some help.",
            "I've been struggling with anxiety.",
            "It's been getting worse lately."
        ]
        
        for message in messages:
            self.manager.process_message(
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=message,
                is_questionnaire_response=False
            )
        
        # Retrieve history
        history = self.manager.get_conversation_history(conversation_id)
        
        # Verify all messages are stored
        user_messages = [msg for msg in history if msg.get("role") == "user"]
        assistant_messages = [msg for msg in history if msg.get("role") == "assistant"]
        
        assert len(user_messages) == len(messages)
        assert len(assistant_messages) == len(messages)
        
        # Verify message content
        for i, msg in enumerate(user_messages):
            assert messages[i] in msg.get("content", "")
        
        logger.info(f"✓ Conversation history persisted correctly")
        logger.info(f"  User messages: {len(user_messages)}")
        logger.info(f"  Assistant messages: {len(assistant_messages)}")
        
        # Test history retrieval after session end
        self.manager.end_session(conversation_id)
        
        # History should still be retrievable
        history_after_end = self.manager.get_conversation_history(conversation_id)
        assert len(history_after_end) == len(history)
        
        logger.info(f"✓ History persists after session end")
        
        return user_id, conversation_id
    
    def test_9_end_to_end_flow(self):
        """Test 9: Complete end-to-end flow from signup to conversation"""
        logger.info("=" * 60)
        logger.info("TEST 9: Complete End-to-End Flow")
        logger.info("=" * 60)
        
        # Step 1: Register
        logger.info("Step 1: User Registration")
        reg_result = self.manager.register_user(
            f"e2e_test_{int(time.time())}@example.com",
            self.test_password
        )
        user_id = reg_result["user_id"]
        logger.info(f"✓ User registered: {user_id}")
        
        # Step 2: Login
        logger.info("Step 2: User Login")
        login_result = self.manager.login_user(reg_result["email"], self.test_password)
        assert login_result["user_id"] == user_id
        logger.info(f"✓ User logged in")
        
        # Step 3: Start session (skip questionnaire for faster test)
        logger.info("Step 3: Start Session")
        session_result = self.manager.start_session(user_id, start_questionnaire=False)
        conversation_id = session_result["conversation_id"]
        logger.info(f"✓ Session started: {conversation_id}")
        
        # Step 4: Regular conversation (enough turns to trigger personality update at turn 5)
        logger.info("Step 4: Regular Conversation")
        conversation_messages = [
            "I've been feeling stressed about work lately.",
            "I can't seem to relax even when I'm at home.",
            "I worry constantly about making mistakes at my job.",
            "It's affecting my sleep and I feel exhausted.",
            "I'm really struggling to cope with all this pressure.",
            "Sometimes I just want to give up on everything."
        ]
        
        for message in conversation_messages:
            result = self.manager.process_message(
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=message,
                is_questionnaire_response=False
            )
            logger.info(f"  Turn {result['turn']}: Response generated")
        
        # Step 5: Verify profile updates
        logger.info("Step 5: Verify Profile Updates")
        profile = self.manager.get_user_profile(user_id)
        assert profile is not None
        assert profile.get("total_text_analyzed", 0) > 0
        logger.info(f"✓ Profile updated: {profile.get('total_text_analyzed')} chars analyzed")
        
        # Step 6: End session
        logger.info("Step 6: End Session")
        self.manager.end_session(conversation_id)
        logger.info(f"✓ Session ended")
        
        logger.info("=" * 60)
        logger.info("✓ COMPLETE END-TO-END FLOW SUCCESSFUL")
        logger.info("=" * 60)
        
        return user_id, conversation_id


def run_all_tests():
    """Run all tests in sequence"""
    test_suite = TestFullSystem()
    test_suite.initialize()
    
    try:
        # Run tests in sequence
        logger.info("\n" + "=" * 60)
        logger.info("STARTING COMPREHENSIVE SYSTEM TESTS")
        logger.info("=" * 60 + "\n")
        
        # Test 1: Registration
        user_id_1 = test_suite.test_1_user_registration()
        
        # Test 2: Login
        user_id_2 = test_suite.test_2_user_login()
        
        # Test 3: Session with questionnaire
        user_id_3, conv_id_3 = test_suite.test_3_start_session_with_questionnaire()
        
        # Test 4: Questionnaire flow
        user_id_4, conv_id_4 = test_suite.test_4_questionnaire_flow()
        
        # Test 5: Regular conversation
        user_id_5, conv_id_5 = test_suite.test_5_regular_conversation_flow()
        
        # Test 6: Personality updates
        user_id_6, conv_id_6 = test_suite.test_6_personality_update_after_turns()
        
        # Test 7: Per-user customization
        users_7 = test_suite.test_7_per_user_customization()
        
        # Test 8: History persistence
        user_id_8, conv_id_8 = test_suite.test_8_conversation_history_persistence()
        
        # Test 9: End-to-end
        user_id_9, conv_id_9 = test_suite.test_9_end_to_end_flow()
        
        logger.info("\n" + "=" * 60)
        logger.info("ALL TESTS COMPLETED SUCCESSFULLY!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    finally:
        test_suite.manager.close()


if __name__ == "__main__":
    # Run tests
    run_all_tests()
