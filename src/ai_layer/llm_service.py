import json
import httpx
import logging
from typing import Dict, Optional, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMService:
    """
    Service for interacting with the LLM.
    Handles prompt construction and API communication using OpenAI compatible style endpoints.
    """

    def __init__(self, model_name: str = "psychocounsel"):
        import os
        self.model_name = model_name
        self.colab_api_url = os.getenv("COLAB_API_URL")
        if not self.colab_api_url:
            logger.warning("COLAB_API_URL is not set in environment variables.")
        self.client = httpx.Client(timeout=180.0)

    # Core LLM4CBT Persona - The immutable foundation
    SYSTEM_PERSONA = (
        "Act as a professional therapist for eliciting automatic thoughts. "
        "You provide evidence-based psychotherapy to help patients with mental health challenges."
    )
    
    SYSTEM_CONCEPTS = """
Automatic Thoughts (ATs): Spontaneous, often negative thoughts that pop into one's mind in response to a situation.
Examples of automatic thoughts in common conversation:
- "If I make a mistake, I'm a total failure."
- "Everyone is judging me."
- "I can't handle this."

Five good strategies for downward arrow technique:
1. Identify a key automatic thought.
2. Ask "If that were true, what would it mean about you?"
3. Peel back layers of meaning to reach core beliefs.
4. Keep questions focused on meaning, not just facts.
5. Maintain a supportive, non-judgmental tone.

Good questions for downward arrow technique:
- "What does that say about you?"
- "What is the worst part about that?"
- "If that happened, what would it mean to you?"
"""

    def _construct_prompt(self, patient_utterance: str, context_updates: Optional[str] = None) -> Dict:
        # Start with the Canonical LLM4CBT Persona
        full_system_prompt = f"{self.SYSTEM_PERSONA}\n\n{self.SYSTEM_CONCEPTS}"
        
        # Merge dynamic updates (RAG context, Personality instructions) if provided
        if context_updates:
            full_system_prompt += f"\n\n--- CURRENT SESSION CONTEXT ---\n{context_updates}"

        user_task_instructions = f"""Your mission is to write a response of professional therapist in json format. 
Your output must always be a json object only, do not explain yourself or output anything else. 
The json object must contain a key entitled 'Response', where the corresponding value contains the string stating the desirable therapist's response to the user utterance with less than one sentence.

Here, the latest user utterance is given as:
"{patient_utterance}"

In your output, 'Response' should adhere to the following guideline:
- Try to reflect the patient's mind and normalize his situation rather than providing a solution.
- If the patient is sharing complicated thoughts, ask a question to write concise statement without any conditions.
- If the patient struggles to engage or says they are not ready, refrain from asking further questions and wait for them.
"""

        return {
            "system": full_system_prompt,
            "user": user_task_instructions
        }

    def generate_response(
        self, 
        patient_utterance: str, 
        history: Optional[List[Dict]] = None,
        context_updates: Optional[str] = None
    ) -> dict:
        """
        Generate a response using the LLM.
        
        Args:
            patient_utterance: The current message from the user
            history: Optional list of previous messages in OpenAI format
            context_updates: Optional string containing RAG context or Personality instructions to APPEND to the core persona
        """
        
        # Build the final prompts
        prompt_parts = self._construct_prompt(patient_utterance, context_updates)
        
        messages = [
            {"role": "system", "content": prompt_parts["system"]},
        ]
        
        # Add history if provided
        if history:
            messages.extend(history)
            
        # Add the current user task
        messages.append({"role": "user", "content": prompt_parts["user"]})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "temperature": 0.7,
            "response_format": {"type": "json_object"}
        }

        try:
            logger.info(f"Sending request to Colab API: {self.colab_api_url}")
            
            # Log the full system prompt for debugging
            logger.info("=" * 80)
            logger.info("FULL SYSTEM PROMPT:")
            logger.info("-" * 80)
            logger.info(messages[0]["content"])
            logger.info("=" * 80)
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer EMPTY"
            }
            
            response = self.client.post(self.colab_api_url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            # OpenAI compatible response structure
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            logger.info("=" * 80)
            logger.info("LLM RESPONSE:")
            logger.info("-" * 80)
            logger.info(content)
            logger.info("=" * 80)
            
            try:
                # Parse JSON output from model
                return json.loads(content)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON: {content}")
                return {"Response": content, "error": "JSON parse failed"}
                
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return {"Response": "I encountered an error. Please try again.", "error": str(e)}
