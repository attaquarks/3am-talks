import torch
from transformers import BertTokenizer, BertForSequenceClassification
from typing import Dict
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class PersonalityService:
    """
    Service for detecting Big Five personality traits from text.
    Wraps the BERT personality model.
    """
    def __init__(self, model_path: str = "Models/bert-base-personality"):
        # Resolve relative paths against the project root
        p = Path(model_path)
        if not p.is_absolute():
            # Project root is 3 levels up from this file: src/ai_layer/personality_service.py
            project_root = Path(__file__).parent.parent.parent
            resolved_path = project_root / model_path
            if resolved_path.exists():
                model_path = str(resolved_path)
                
        self.model_path = model_path
        self.model = None
        self.tokenizer = None
        self._load_model()
    
    def _load_model(self):
        try:
            logger.info(f"Loading personality model from {self.model_path}")
            self.tokenizer = BertTokenizer.from_pretrained(self.model_path, do_lower_case=True)
            self.model = BertForSequenceClassification.from_pretrained(self.model_path, num_labels=5)
            
            self.model.config.label2id = {
                "Extroversion": 0,
                "Neuroticism": 1,
                "Agreeableness": 2,
                "Conscientiousness": 3,
                "Openness": 4,
            }
            self.model.config.id2label = {
                "0": "Extroversion",
                "1": "Neuroticism",
                "2": "Agreeableness",
                "3": "Conscientiousness",
                "4": "Openness",
            }
            
            self.model.eval()
            logger.info("Personality model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load personality model: {e}")
            raise
    
    def detect_personality(self, text: str) -> Dict[str, float]:
        if not text or len(text) == 0:
            return {
                "Extroversion": 0.5,
                "Neuroticism": 0.5,
                "Agreeableness": 0.5,
                "Conscientiousness": 0.5,
                "Openness": 0.5,
            }
        
        try:
            inputs = self.tokenizer(
                text,
                max_length=512,
                padding=True,
                truncation=True,
                return_tensors="pt"
            )
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                predictions = torch.sigmoid(logits).squeeze()
            
            result = {
                "Extroversion": float(predictions[0]),
                "Neuroticism": float(predictions[1]),
                "Agreeableness": float(predictions[2]),
                "Conscientiousness": float(predictions[3]),
                "Openness": float(predictions[4]),
            }
            
            logger.info(f"Personality detected: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error during personality detection: {e}")
            return {
                "Extroversion": 0.5,
                "Neuroticism": 0.5,
                "Agreeableness": 0.5,
                "Conscientiousness": 0.5,
                "Openness": 0.5,
            }


class PsyCOTInference:
    """
    Helper class for inferring therapeutic adaptations based on personality scores.
    """
    @staticmethod
    def generate_personality_profile(scores: Dict[str, float]) -> str:
        profile_parts = []
        
        # Openness to Experience
        o_score = scores.get("Openness", 0.5)
        if o_score > 0.6:
            profile_parts.append("intellectually curious and open to new ideas")
        elif o_score < 0.4:
            profile_parts.append("prefers routine and familiar approaches")
        
        # Conscientiousness
        c_score = scores.get("Conscientiousness", 0.5)
        if c_score > 0.6:
            profile_parts.append("organized and goal-oriented")
        elif c_score < 0.4:
            profile_parts.append("flexible and spontaneous")
        
        # Extroversion
        e_score = scores.get("Extroversion", 0.5)
        if e_score > 0.6:
            profile_parts.append("energized by social interaction")
        elif e_score < 0.4:
            profile_parts.append("values quiet reflection")
        
        # Agreeableness
        a_score = scores.get("Agreeableness", 0.5)
        if a_score > 0.6:
            profile_parts.append("cooperative and empathetic")
        elif a_score < 0.4:
            profile_parts.append("values directness and objectivity")
        
        # Neuroticism
        n_score = scores.get("Neuroticism", 0.5)
        if n_score > 0.6:
            profile_parts.append("may experience heightened emotional sensitivity")
        elif n_score < 0.4:
            profile_parts.append("emotionally stable")
        
        if not profile_parts:
            return "with a balanced personality profile"
        
        return ", ".join(profile_parts)
    
    @staticmethod
    def adapt_therapeutic_approach(scores: Dict[str, float]) -> Dict[str, str]:
        approach = {
            "tone": "warm and supportive",
            "pacing": "moderate",
            "guidance_level": "balanced",
            "interaction_style": "collaborative"
        }
        
        # Adjust based on Neuroticism
        n_score = scores.get("Neuroticism", 0.5)
        if n_score > 0.6:
            approach["tone"] = "especially gentle and reassuring"
            approach["pacing"] = "slower, allowing processing time"
        elif n_score < 0.4:
            approach["tone"] = "direct and matter-of-fact"
        
        # Adjust based on Conscientiousness
        c_score = scores.get("Conscientiousness", 0.5)
        if c_score > 0.6:
            approach["guidance_level"] = "structured with clear goals"
            approach["interaction_style"] = "systematic and organized"
        elif c_score < 0.4:
            approach["guidance_level"] = "flexible and exploratory"
            approach["interaction_style"] = "open-ended and adaptive"
        
        # Adjust based on Openness
        o_score = scores.get("Openness", 0.5)
        if o_score > 0.6:
            approach["interaction_style"] = "encourages exploration of new perspectives"
        elif o_score < 0.4:
            approach["interaction_style"] = "builds on familiar concepts"
        
        # Adjust based on Extroversion
        e_score = scores.get("Extroversion", 0.5)
        if e_score > 0.6:
            approach["pacing"] = "more interactive and conversational"
        elif e_score < 0.4:
            approach["pacing"] = "allows silence and reflection"
        
        return approach
    
    @staticmethod
    def create_personality_aware_system_prompt(
        base_prompt: str,
        personality_scores: Dict[str, float]
    ) -> str:
        personality_profile = PsyCOTInference.generate_personality_profile(personality_scores)
        therapeutic_approach = PsyCOTInference.adapt_therapeutic_approach(personality_scores)
        
        adaptation_instructions = f"""
You are speaking with someone who appears to be {personality_profile}.

Adapt your therapeutic approach accordingly:
- Use a {therapeutic_approach['tone']} tone
- Maintain {therapeutic_approach['pacing']} pacing
- Provide {therapeutic_approach['guidance_level']} guidance
- Engage in a {therapeutic_approach['interaction_style']} manner

Remember: These personality insights are not diagnostic labels but guides to tailor your communication style for better therapeutic rapport.
"""
        
        combined_prompt = f"{base_prompt}\n\n{adaptation_instructions}"
        return combined_prompt
