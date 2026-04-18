"""
Questionnaire system for initial personality assessment.
Uses structured questions to gather text for BERT personality analysis.
"""

from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class PersonalityQuestionnaire:
    """
    Questionnaire system for initial personality assessment.
    Uses open-ended questions to gather text for BERT personality analysis.
    """
    
    # Questionnaire questions designed to elicit personality-revealing responses
    QUESTIONS = [
        {
            "id": 1,
            "question": "Tell me a bit about yourself. What are some things that make you who you are?",
            "category": "openness"
        },
        {
            "id": 2,
            "question": "How do you typically handle social situations? Do you enjoy meeting new people or prefer smaller groups?",
            "category": "extroversion"
        },
        {
            "id": 3,
            "question": "When you face challenges or setbacks, how do you usually respond?",
            "category": "neuroticism"
        },
        {
            "id": 4,
            "question": "How do you approach your goals and responsibilities? Are you someone who plans ahead or takes things as they come?",
            "category": "conscientiousness"
        },
        {
            "id": 5,
            "question": "In your relationships with others, how do you typically interact? Are you more focused on harmony or on being direct?",
            "category": "agreeableness"
        },
        {
            "id": 6,
            "question": "What brings you joy or satisfaction in life?",
            "category": "general"
        },
        {
            "id": 7,
            "question": "How do you deal with stress or difficult emotions?",
            "category": "neuroticism"
        },
        {
            "id": 8,
            "question": "What's something new you've tried recently, or would like to try?",
            "category": "openness"
        }
    ]
    
    def __init__(self):
        self.current_question_index = 0
        self.responses: List[Dict[str, str]] = []
        self.completed = False
    
    def get_next_question(self) -> Optional[Dict]:
        """Get the next question in the questionnaire"""
        if self.completed or self.current_question_index >= len(self.QUESTIONS):
            return None
        
        question = self.QUESTIONS[self.current_question_index].copy()
        question["progress"] = f"{self.current_question_index + 1}/{len(self.QUESTIONS)}"
        return question
    
    def submit_response(self, question_id: int, response_text: str) -> bool:
        """
        Submit a response to a question
        
        Args:
            question_id: ID of the question being answered
            response_text: User's response text
            
        Returns:
            True if response was accepted, False otherwise
        """
        if self.completed:
            return False
        
        # Validate question_id matches current question
        if self.current_question_index >= len(self.QUESTIONS):
            return False
        
        current_question = self.QUESTIONS[self.current_question_index]
        if current_question["id"] != question_id:
            logger.warning(f"Question ID mismatch: expected {current_question['id']}, got {question_id}")
            # Still accept it if it's a valid question ID
            if not any(q["id"] == question_id for q in self.QUESTIONS):
                return False
        
        # Store response
        self.responses.append({
            "question_id": question_id,
            "question": current_question["question"],
            "response": response_text,
            "category": current_question["category"]
        })
        
        # Move to next question
        self.current_question_index += 1
        
        # Check if completed
        if self.current_question_index >= len(self.QUESTIONS):
            self.completed = True
        
        return True
    
    def get_all_responses_text(self) -> str:
        """Get all responses concatenated as a single text for personality analysis"""
        if not self.responses:
            return ""
        
        # Combine all responses into a single text
        text_parts = []
        for resp in self.responses:
            text_parts.append(f"Q: {resp['question']}\nA: {resp['response']}")
        
        return "\n\n".join(text_parts)
    
    def get_progress(self) -> Dict:
        """Get questionnaire progress information"""
        total = len(self.QUESTIONS)
        answered = len(self.responses)
        
        return {
            "total_questions": total,
            "answered": answered,
            "remaining": total - answered,
            "progress_percent": (answered / total * 100) if total > 0 else 0,
            "completed": self.completed
        }
    
    def reset(self):
        """Reset the questionnaire to start over"""
        self.current_question_index = 0
        self.responses = []
        self.completed = False
    
    def skip_remaining(self) -> int:
        """
        Skip remaining questions (for users who want to proceed without full questionnaire)
        
        Returns:
            Number of questions skipped
        """
        skipped = len(self.QUESTIONS) - self.current_question_index
        self.current_question_index = len(self.QUESTIONS)
        self.completed = True
        return skipped
