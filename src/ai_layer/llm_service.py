import json
import httpx
import logging
import os
from typing import Dict, Optional, List
from dotenv import load_dotenv
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


class LLMService:
    """
    Service for interacting with the LLM.
    Handles prompt construction and API communication using OpenAI compatible style endpoints.
    """

    def __init__(self, model_name: str = "psychocounsel"):
        self.model_name = model_name
        self.colab_api_url = os.getenv("COLAB_API_URL")
        if not self.colab_api_url:
            logger.warning("COLAB_API_URL is not set in environment variables.")
        self.client = httpx.Client(timeout=180.0)

    # Core Persona - Warm, empathetic counselor who builds genuine connections
    SYSTEM_PERSONA = (
        "You are Ella, a warm and supportive AI companion trained in counseling and emotional support. "
        "Your primary goal is to build genuine emotional connections with people, making them feel heard, "
        "understood, and valued. You're here to have real conversations - not to diagnose or treat mental illness. "
        "Most people you talk to are dealing with normal life challenges: work stress, relationship ups and downs, "
        "big decisions, difficult emotions, or just need someone to talk to. Treat everyone as a normal person "
        "navigating life, not as a patient with a condition to fix."
    )

    SYSTEM_CONCEPTS = """
YOUR COMMUNICATION STYLE:
- Be warm, genuine, and conversational - like talking to a trusted friend who happens to have professional training
- Use natural, multi-sentence responses that show you're truly listening and engaged
- Mirror the user's emotional tone and energy level
- Share brief relevant observations or reflections that show you understand
- Ask follow-up questions that feel natural, not clinical
- Use the person's name occasionally if shared, and warm language when appropriate

BUILDING CONNECTION:
- Start by truly understanding what's on their mind before offering any guidance
- Validate their feelings genuinely - "That sounds really tough" or "I can see why that would be frustrating"
- Share thoughtful observations about their situation
- Build trust through genuine empathy, not therapeutic techniques
- Let the conversation flow naturally - don't force it toward any particular topic

WHEN TO USE THERAPEUTIC APPROACHES:
- When someone shows clear signs of being stuck in negative thought patterns
- When they specifically ask for help with deeper issues
- After you've built rapport and they seem comfortable
- Use techniques gently and naturally, not as obvious interventions
- Frame suggestions as observations or questions, not prescriptions

REMEMBER:
- You're having a conversation, not conducting a therapy session
- Most people just need to feel heard and understood
- Sometimes the best support is simply being present and listening
- Don't pathologize normal human experiences
- Don't assume everyone has a problem that needs "fixing"
"""

    def _construct_prompt(
        self, patient_utterance: str, context_updates: Optional[str] = None
    ) -> Dict:
        # Start with the Canonical LLM4CBT Persona
        full_system_prompt = f"{self.SYSTEM_PERSONA}\n\n{self.SYSTEM_CONCEPTS}"

        # Merge dynamic updates (RAG context, Personality instructions) if provided
        if context_updates:
            full_system_prompt += (
                f"\n\n--- CURRENT SESSION CONTEXT ---\n{context_updates}"
            )

        user_task_instructions = f"""Your task is to write a warm, empathetic response as Ella in JSON format.
Your output must always be a JSON object only, with no additional text or explanation.
The JSON object must contain a key 'Response' with your message as the value.

Here is the person's message:
"{patient_utterance}"

Guidelines for your response:
- Try to reflect the patient's mind and normalize his situation rather than providing a solution. 
- Respond naturally, as if talking to a friend who trusts you
- Use 2-4 sentences typically or more if needed - enough to show you're engaged and thoughtful
- If they're sharing something difficult, acknowledge it genuinely before anything else
- Ask thoughtful follow-up questions that feel natural to the conversation
- Don't try to solve everything - sometimes listening is enough
- Match their emotional tone and energy

Remember: You're having a real conversation. Be natural, be human, be caring.
"""

        return {"system": full_system_prompt, "user": user_task_instructions}

    def generate_response(
        self,
        patient_utterance: str,
        history: Optional[List[Dict]] = None,
        context_updates: Optional[str] = None,
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
            "response_format": {"type": "json_object"},
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
                "Authorization": f"Bearer {os.getenv('COLAB_API_KEY', 'EMPTY')}",
            }

            response = self.client.post(
                self.colab_api_url, json=payload, headers=headers
            )
            response.raise_for_status()

            result = response.json()
            # OpenAI compatible response structure
            content = (
                result.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

            logger.info("=" * 80)
            logger.info("LLM RESPONSE:")
            logger.info("-" * 80)
            logger.info(content)
            logger.info("=" * 80)

            try:
                # Parse JSON output from model
                parsed = json.loads(content)

                # Handle case where Response might be an object instead of string
                response_value = parsed.get("Response", "")
                if isinstance(response_value, dict):
                    # Extract text from nested object
                    response_value = response_value.get("text", str(response_value))

                parsed["Response"] = response_value
                return parsed
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON: {content}")
                return {"Response": content, "error": "JSON parse failed"}

        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return {
                "Response": "I encountered an error. Please try again.",
                "error": str(e),
            }
