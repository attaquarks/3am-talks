#!/usr/bin/env python3
"""
Example usage of the 3AM Talks therapy system.
This demonstrates the complete flow from user registration to conversation.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file first
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from conversation_manager import ConversationManager
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Example usage of the 3AM Talks system"""
    
    print("=" * 60)
    print("3AM Talks - Example Usage")
    print("=" * 60)
    print()
    
    # Initialize the conversation manager
    print("Initializing ConversationManager...")
    manager = ConversationManager(
        model_name="psychocounsel",
        ollama_base_url="http://127.0.0.1:11434",
        personality_update_interval=40,  # Update every 40 turns
        enable_rag=True,
        enable_personality=True
    )
    print("✓ ConversationManager initialized\n")
    
    try:
        # Step 1: Register a new user
        print("Step 1: Registering new user...")
        email = f"example_user_{int(__import__('time').time())}@example.com"
        password = "SecurePassword123!"
        
        reg_result = manager.register_user(email, password)
        user_id = reg_result["user_id"]
        print(f"✓ User registered: {user_id}")
        print(f"  Email: {email}\n")
        
        # Step 2: Start a session
        print("Step 2: Starting session...")
        session_result = manager.start_session(user_id, start_questionnaire=True)
        conversation_id = session_result["conversation_id"]
        print(f"✓ Session started: {conversation_id}")
        
        # Check if questionnaire was initiated
        if "questionnaire" in session_result and session_result["questionnaire"]["active"]:
            print("  Questionnaire initiated for new user\n")
            
            # Step 3: Complete questionnaire (simplified - just a few questions)
            print("Step 3: Completing questionnaire...")
            questionnaire_responses = [
                "I'm someone who enjoys trying new things and learning. I'm creative and open-minded.",
                "I'm moderately social - I enjoy being with people but also need my alone time.",
                "I handle stress reasonably well, though I do get anxious sometimes, especially about work.",
                "I'm fairly organized and like to plan ahead, but I can also be flexible when needed.",
                "I try to be understanding and cooperative with others, and I value harmony in relationships."
            ]
            
            for i, response in enumerate(questionnaire_responses[:3], 1):  # Just 3 for demo
                print(f"  Answering question {i}...")
                result = manager.process_message(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    user_message=response,
                    is_questionnaire_response=True
                )
                
                if result.get("questionnaire", {}).get("completed", False):
                    print("  ✓ Questionnaire completed!")
                    print(f"  Initial personality assessed\n")
                    break
                elif "questionnaire" in result:
                    print(f"  Next question: {result['questionnaire']['question']['question'][:60]}...")
        
        # Step 4: Regular conversation
        print("Step 4: Starting regular conversation...")
        conversation_messages = [
            "I've been feeling really anxious about my job lately.",
            "I can't stop worrying about making mistakes and what my boss thinks of me.",
            "It's affecting my sleep and I feel overwhelmed."
        ]
        
        for i, message in enumerate(conversation_messages, 1):
            print(f"\nTurn {i}:")
            print(f"  User: {message}")
            
            result = manager.process_message(
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=message,
                is_questionnaire_response=False
            )
            
            print(f"  Assistant: {result['response']}")
            
            if result.get("rag_techniques_used", 0) > 0:
                print(f"  (Used {result['rag_techniques_used']} RAG techniques)")
            
            if result.get("personality_scores"):
                print(f"  (Personality scores updated)")
        
        # Step 5: Check user profile
        print("\nStep 5: Checking user profile...")
        profile = manager.get_user_profile(user_id)
        if profile:
            print(f"  Total text analyzed: {profile.get('total_text_analyzed', 0)} characters")
            print(f"  Personality scores:")
            print(f"    Extroversion: {profile.get('extroversion', 0):.3f}")
            print(f"    Neuroticism: {profile.get('neuroticism', 0):.3f}")
            print(f"    Agreeableness: {profile.get('agreeableness', 0):.3f}")
            print(f"    Conscientiousness: {profile.get('conscientiousness', 0):.3f}")
            print(f"    Openness: {profile.get('openness', 0):.3f}")
        
        # Step 6: Check conversation history
        print("\nStep 6: Checking conversation history...")
        history = manager.get_conversation_history(conversation_id, limit=10)
        print(f"  Total messages: {len(history)}")
        print(f"  User messages: {len([m for m in history if m.get('role') == 'user'])}")
        print(f"  Assistant messages: {len([m for m in history if m.get('role') == 'assistant'])}")
        
        # Step 7: End session
        print("\nStep 7: Ending session...")
        manager.end_session(conversation_id)
        print("✓ Session ended")
        
        print("\n" + "=" * 60)
        print("Example completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"Error in example: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        manager.close()


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in .env file")
        print("Please create a .env file with your credentials.")
        sys.exit(1)
    
    main()
