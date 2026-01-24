# Test Suite for 3AM Talks System

This directory contains comprehensive tests for the 3AM Talks therapy system.

## Running Tests

### Prerequisites

1. Set up your `.env` file with required credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase and Pinecone credentials
   ```

2. Ensure Ollama is running with the `psychocounsel` model:
   ```bash
   ollama serve
   ollama pull psychocounsel
   ```

3. Install test dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Run All Tests

```bash
# Using pytest
pytest tests/test_full_system.py -v

# Or run directly
python tests/test_full_system.py
```

### Test Coverage

The test suite covers:

1. **User Registration** - Tests user signup and profile creation
2. **User Login** - Tests authentication flow
3. **Session Management** - Tests starting sessions with questionnaire
4. **Questionnaire Flow** - Tests initial personality assessment
5. **Regular Conversation** - Tests RAG and personality-aware responses
6. **Personality Updates** - Tests automatic personality updates after 30-50 turns
7. **Per-User Customization** - Tests that agent behaves differently per user profile
8. **History Persistence** - Tests conversation history storage in Supabase
9. **End-to-End Flow** - Complete flow from signup to conversation

### Test Configuration

Tests use a reduced personality update interval (5 turns) for faster testing. In production, this should be 30-50 turns.

### Notes

- Tests create real users in your Supabase database (with unique timestamps)
- Tests require active Supabase and Pinecone connections
- Tests require Ollama to be running with the psychocounsel model
- Some tests may take several minutes to complete
