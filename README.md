# 3AM Talks - AI Therapy System

A comprehensive AI-powered therapy and counseling system that provides personalized mental health support using personality-aware responses, RAG (Retrieval-Augmented Generation), and evidence-based therapeutic techniques.

## Architecture

The system consists of several key components:

### 1. **Personality Assessment Layer**
- Uses `bert-base-personality` model to assess Big Five personality traits
- Implements PsyCOT (Psychological Chain-of-Thought) inference for therapeutic adaptations
- Initial assessment via structured questionnaire
- Continuous updates every 30-50 conversation turns

### 2. **User Profile Management**
- Stores user profiles in Supabase database
- Maintains personality scores, conversation history, and preferences
- Updates profile after each personality assessment

### 3. **AI Layer**
- **PsychoCounsel Model**: Fine-tuned therapy model (Llama3-8B)
- **LLM4CBT Technique**: Evidence-based Cognitive Behavioral Therapy framework
- Personality-aware prompt generation using PsyCOT

### 4. **RAG Layer**
- Retrieves relevant therapeutic techniques from Pinecone vector database
- Supports CBT, DBT, ACT, and other evidence-based modalities
- Context-aware technique selection based on user issues

### 5. **Conversation Management**
- Maintains conversation history in Supabase
- Tracks conversation turns for personality updates
- Per-user customization based on personality profile

## Features

- ✅ User authentication and registration
- ✅ Initial personality assessment via questionnaire
- ✅ Personality-aware therapeutic responses
- ✅ RAG-based technique retrieval
- ✅ Continuous personality profile updates
- ✅ Per-user conversation customization
- ✅ Conversation history persistence
- ✅ Evidence-based therapeutic approaches

## Setup

### Prerequisites

1. **Python 3.8+**
2. **Supabase Account** - For database and authentication
3. **Pinecone Account** - For RAG vector database
4. **Ollama** - For running the PsychoCounsel model locally

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd 3AM
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. Set up Ollama and pull the model:
   ```bash
   ollama serve
   ollama pull psychocounsel
   ```

5. Set up Supabase database tables (see Database Schema below)

6. Set up Pinecone index with therapeutic techniques

## Configuration

### Environment Variables

Create a `.env` file with:

```env
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key
PINECONE_API_KEY=your-pinecone-api-key
```

### Database Schema

The system requires the following Supabase tables:

#### `user_profiles`
- `user_id` (UUID, primary key)
- `extroversion` (float)
- `neuroticism` (float)
- `agreeableness` (float)
- `conscientiousness` (float)
- `openness` (float)
- `total_text_analyzed` (int)
- `profile_version` (int)
- `personality_updated_at` (timestamp)
- `risk_flags` (jsonb)
- `preferences` (jsonb)

#### `conversations`
- `conversation_id` (UUID, primary key)
- `user_id` (UUID, foreign key)
- `is_active` (boolean)
- `total_turns` (int)
- `last_personality_update_turn` (int)
- `created_at` (timestamp)
- `ended_at` (timestamp)

#### `messages`
- `message_id` (UUID, primary key)
- `conversation_id` (UUID, foreign key)
- `user_id` (UUID, foreign key)
- `role` (text: 'user' or 'assistant')
- `content` (text)
- `turn_index` (int)
- `personality_scores_at_turn` (jsonb)
- `rag_techniques_used` (jsonb)
- `created_at` (timestamp)

## Usage

### Basic Example

```python
from src.conversation_manager import ConversationManager

# Initialize the system
manager = ConversationManager(
    model_name="psychocounsel",
    ollama_base_url="http://127.0.0.1:11434",
    personality_update_interval=40,  # Update every 40 turns
    enable_rag=True,
    enable_personality=True
)

# Register a new user
result = manager.register_user("user@example.com", "password123")
user_id = result["user_id"]

# Start a session (will initiate questionnaire for new users)
session = manager.start_session(user_id, start_questionnaire=True)
conversation_id = session["conversation_id"]

# Process messages
response = manager.process_message(
    user_id=user_id,
    conversation_id=conversation_id,
    user_message="I've been feeling anxious lately.",
    is_questionnaire_response=False
)

print(response["response"])

# Clean up
manager.close()
```

### Questionnaire Flow

For new users, the system automatically starts a questionnaire:

```python
# Start session (questionnaire starts automatically for new users)
session = manager.start_session(user_id, start_questionnaire=True)

if "questionnaire" in session:
    # Process questionnaire responses
    result = manager.process_message(
        user_id=user_id,
        conversation_id=conversation_id,
        user_message="I'm someone who enjoys social activities...",
        is_questionnaire_response=True
    )
    
    # Continue until questionnaire is complete
    while result.get("questionnaire", {}).get("active", False):
        # Get next question and process response
        pass
```

## Testing

Run the comprehensive test suite:

```bash
pytest tests/test_full_system.py -v
```

Or run directly:

```bash
python tests/test_full_system.py
```

See `tests/README.md` for more details.

## System Flow

1. **User Registration/Login**
   - User signs up or logs in via Supabase Auth
   - User profile is created/retrieved

2. **Initial Assessment (New Users)**
   - Questionnaire is presented
   - User responses are collected
   - BERT personality model analyzes responses
   - Initial personality profile is created

3. **Regular Conversation**
   - Each message goes through:
     - Personality profile loading
     - RAG technique retrieval
     - Personality-aware prompt generation
     - LLM response generation
     - Response storage

4. **Personality Updates**
   - After every 30-50 turns:
     - Recent conversation text is analyzed
     - Personality scores are updated
     - Profile is saved to database

5. **Per-User Customization**
   - Each response is tailored based on:
     - User's personality profile
     - Conversation history
     - Relevant therapeutic techniques

## Model Files

The system uses the following models:

- **BERT Personality Model**: `Models/bert-base-personality/`
- **PsychoCounsel Model**: `Models/psychocounsel/` (Ollama model)

Ensure these are properly set up before running the system.

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

## Support

[Add support information here]
