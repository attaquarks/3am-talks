# CLAUDE.md

This file provides comprehensive guidance for Claude Code when working with code in this repository.

## Project Overview

**Ella Speaks Calmly** (formerly 3AM Talks) is an AI-powered therapy and counseling system that provides personalized mental health support through evidence-based therapeutic techniques.

### Core Features

- **Personality-Aware Responses**: BERT-based personality detection (Big Five model) that adapts therapeutic approach to individual users
- **Retrieval-Augmented Generation (RAG)**: Pinecone-powered retrieval of therapeutic techniques (CBT, DBT, ACT)
- **Evidence-Based Therapy**: Implements CBT downward arrow technique, automatic thought elicitation, and structured interventions
- **Real-Time Voice Conversations**: LiveKit + ElevenLabs integration for natural voice-based therapy sessions
- **Multi-Platform Authentication**: Email/password + OAuth (Google, Facebook) via Supabase

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Frontend (React 18 + Vite + TypeScript)                  │
│                           localhost:5173                                     │
│  Pages: Landing, Auth, Dashboard, Therapist, History, Profile, About        │
│  State: TanStack Query + React Context (AuthContext)                         │
│  UI: Radix UI + Tailwind CSS + Framer Motion                                 │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ HTTP/REST + Cookie Sessions
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI + Python)                              │
│                           localhost:5050                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ api.py (1433 lines) - REST Endpoints                                  │   │
│  │   /api/register, /api/login, /api/logout                              │   │
│  │   /api/auth/oauth/{provider}/start, /api/oauth/session                │   │
│  │   /api/chat - Main conversation endpoint                              │   │
│  │   /api/data/{table} - Generic CRUD                                    │   │
│  │   /api/livekit/token, /api/voice/bootstrap, /api/voice/chat           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                      │                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ conversation_manager.py (592 lines) - Core Orchestration              │   │
│  │   Coordinates: Auth → Profile → Personality → RAG → LLM → Storage     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │                    │                    │                    │
          ▼                    ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   AI Layer      │  │   RAG Layer     │  │ Database Layer  │  │  External LLM   │
│ (ai_layer/)     │  │ (rag_layer/)    │  │ (database/)     │  │ (Colab API)     │
│                 │  │                 │  │                 │  │                 │
│ LLMService      │  │ RAGService      │  │ SupabaseClient  │  │ psychocounsel   │
│ PersonalitySvc  │  │ PineconeEngine  │  │ UserService     │  │ model           │
└─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ BERT Model      │  │ Pinecone Index  │  │ Supabase        │
│ bert-base-      │  │ llama-text-     │  │ PostgreSQL +    │
│ personality     │  │ embed-v2        │  │ Auth            │
└─────────────────┘  └─────────────────┘  └─────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    Voice Agent (Separate Process)                            │
│                           voice_agent.py                                     │
│  Pipeline: Silero VAD → ElevenLabs STT → Backend API → ElevenLabs TTS       │
│  Runs independently, connects to LiveKit server                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
C:\Users\Atta\Desktop\3AM\
├── .env                          # Environment variables (secrets)
├── .env.example                  # Environment template
├── .gitignore                    # Git ignore rules
├── CLAUDE.md                     # This file
├── README.md                     # Project readme
├── requirements.txt              # Python dependencies
├── techniques.json               # Therapeutic techniques data (525KB) for Pinecone
├── start.bat                     # Windows startup script
├── start.sh                      # Linux/Mac startup script
│
├── Docs/                         # Documentation
│   ├── SRS Document for 3AM Talks.pdf
│   ├── LLM4CBT.pdf              # Research paper on LLM for CBT
│   └── PsyCoT.pdf               # PsychoCounsel model paper
│
├── Models/                       # ML Model Files
│   ├── bert-base-personality/   # Fine-tuned BERT for Big Five detection
│   │   ├── config.json
│   │   ├── model.safetensors
│   │   ├── pytorch_model.bin
│   │   ├── tokenizer_config.json
│   │   └── vocab.txt
│   └── psychocounsel/           # PsychoCounsel LLM (GGUF format)
│       └── PsychoCounsel-Llama3-8B-Q4_K_M.gguf
│
├── src/                          # Python Backend (~3,200 lines)
│   ├── __init__.py
│   ├── api.py                    # FastAPI server entry point (1433 lines)
│   ├── conversation_manager.py   # Core orchestration layer (592 lines)
│   ├── voice_agent.py            # LiveKit voice agent (205 lines)
│   ├── questionnaire.py          # Personality questionnaire system (160 lines)
│   │
│   ├── ai_layer/                 # AI/ML Services
│   │   ├── __init__.py
│   │   ├── llm_service.py        # LLM integration (172 lines)
│   │   └── personality_service.py # BERT personality detection (215 lines)
│   │
│   ├── database/                 # Database Layer
│   │   ├── __init__.py
│   │   ├── supabase_client.py    # Supabase REST client (202 lines)
│   │   └── user_service.py       # User/conversation management (329 lines)
│   │
│   └── rag_layer/                # RAG Services
│       ├── __init__.py
│       ├── rag_service.py        # RAG retrieval service (126 lines)
│       └── pinecone_engine.py    # Pinecone inference search (82 lines)
│
├── tests/                        # Test Suite
│   └── test_full_system.py       # Comprehensive integration tests (648 lines)
│
├── frontend/                     # React + TypeScript Frontend
│   ├── package.json              # Node.js dependencies
│   ├── tsconfig.json             # TypeScript configuration
│   ├── tailwind.config.ts        # Tailwind CSS configuration
│   ├── components.json           # Radix UI/shadcn config
│   │
│   └── client/
│       ├── index.html
│       └── src/
│           ├── main.tsx          # React entry point
│           ├── App.tsx           # Main app with routing
│           ├── pages/            # Page components
│           │   ├── Landing.tsx   # Marketing landing page
│           │   ├── Auth.tsx      # Login/Register
│           │   ├── Dashboard.tsx # User dashboard
│           │   ├── Therapist.tsx # Main chat interface (802 lines)
│           │   ├── History.tsx   # Conversation history
│           │   ├── Profile.tsx   # User profile
│           │   ├── About.tsx     # About page
│           │   ├── LearnMore.tsx # Learn more page
│           │   ├── OAuthSuccess.tsx # OAuth callback
│           │   └── NotFound.tsx  # 404 page
│           ├── components/
│           │   ├── Navigation.tsx
│           │   ├── ThemeProvider.tsx
│           │   ├── AuthWrapper.tsx
│           │   ├── VoiceCall.tsx  # LiveKit voice component
│           │   ├── auth/          # Auth-related components
│           │   └── ui/            # Radix UI primitives (40+ components)
│           ├── context/
│           │   └── AuthContext.tsx # Authentication context
│           ├── hooks/             # Custom React hooks
│           │   ├── useAuth.ts
│           │   ├── useConversations.ts
│           │   ├── useMoodEntries.ts
│           │   ├── useProfile.ts
│           │   ├── useSessionTracker.ts
│           │   ├── useUserStats.ts
│           │   ├── useVoiceCall.ts
│           │   └── use-toast.ts
│           ├── lib/
│           │   ├── supabaseBrowser.ts
│           │   └── utils.ts
│           └── types/
│               └── auth.ts
│
├── livekit-server/               # LiveKit server binaries
│   └── livekit-server.exe        # Windows LiveKit server
│
└── .venv/                        # Python virtual environment
```

---

## Key Components Deep Dive

### 1. Backend API (api.py)

**Port**: 5050

**Authentication**:
- Cookie-based sessions using `itsdangerous.TimestampSigner` with 7-day expiry
- Supabase Auth for user management (email/password + OAuth)
- OAuth flow: `/api/auth/oauth/{provider}/start` → Supabase → `/api/oauth/session`

**Key Endpoints**:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Service health check |
| `/api/register` | POST | User registration |
| `/api/login` | POST | User login |
| `/api/logout` | POST | Clear session cookie |
| `/api/user` | GET | Get current authenticated user |
| `/api/auth/oauth/{provider}/start` | GET | Start OAuth flow (Google/Facebook) |
| `/api/oauth/session` | POST | Exchange OAuth token for session |
| `/api/chat` | POST | Main AI conversation endpoint |
| `/api/data/{table}` | GET/POST | Generic CRUD operations |
| `/api/data/{table}/{id}` | GET/PATCH/DELETE | Record operations |
| `/api/livekit/token` | POST | Generate LiveKit access token |
| `/api/voice/bootstrap` | POST | Voice agent session initialization |
| `/api/voice/chat` | POST | Voice agent message processing |
| `/api/account/email` | PATCH | Update user email |
| `/api/account/password` | PATCH | Update user password |
| `/api/account` | DELETE | Permanently delete account |

**Important Patterns**:
- **Lazy Initialization**: `ConversationManager` is loaded on first request via `get_manager()` to prevent blocking startup
- **Schema Translation**: Backend schema differs from frontend expectations; helper functions handle translation
- **CORS**: Configured for localhost development (ports 5173, 5050)

---

### 2. ConversationManager (conversation_manager.py)

**Purpose**: Main orchestrator for the entire therapy system.

**Initialization Parameters**:
```python
ConversationManager(
    model_name="psychocounsel",              # LLM model name
    personality_model_path="Models/bert-base-personality",
    personality_update_interval=40,          # Update personality every N turns
    enable_rag=True,                         # Enable RAG retrieval
    enable_personality=True                   # Enable personality detection
)
```

**Message Processing Pipeline** (`process_message` method):

1. **Load Conversation State** - Verify conversation exists and is active
2. **Load User Profile** - Fetch personality scores and history
3. **Handle Questionnaire** - Process initial personality assessment (if new user)
4. **Save User Message** - Persist to database with turn tracking
5. **Update Personality** - If interval reached (every 40 turns by default)
6. **Retrieve RAG Techniques** - Based on inferred issue tags
7. **Build Context Updates** - Combine personality + RAG + onboarding instructions
8. **Generate LLM Response** - Call LLM with full context
9. **Save and Return** - Persist assistant response, update turn count

**Issue Tag Inference** (for RAG filtering):
```python
keywords_map = {
    "anxiety": ["anxious", "worried", "nervous", "panic", "fear"],
    "depression": ["sad", "depressed", "hopeless", "empty", "down"],
    "stress": ["stress", "overwhelmed", "pressure", "burden"],
    "anger": ["angry", "frustrated", "mad", "irritated"],
    "relationships": ["relationship", "partner", "friend", "family"],
    "self-esteem": ["worthless", "inadequate", "failure", "not good enough"],
    "trauma": ["trauma", "ptsd", "flashback", "triggered"]
}
```

---

### 3. AI Layer

#### LLMService (llm_service.py)

**Purpose**: Manages communication with the therapy LLM via OpenAI-compatible API.

**Configuration**:
- Endpoint: `COLAB_API_URL` environment variable
- Model: `psychocounsel`
- Temperature: 0.7
- Response format: JSON object

**Prompt Architecture** (Layered System):

1. **Base Persona** (immutable):
```python
SYSTEM_PERSONA = "Act as a professional therapist for eliciting automatic thoughts..."
```

2. **Core Concepts** (CBT methodology):
```python
SYSTEM_CONCEPTS = """
Automatic Thoughts (ATs): Spontaneous, often negative thoughts...
Five good strategies for downward arrow technique...
Good questions for downward arrow technique...
"""
```

3. **Context Updates** (dynamic, appended per-request):
   - Personality adaptation instructions
   - RAG-retrieved therapeutic techniques
   - Onboarding/new user handling

**Output Format**:
```json
{"Response": "therapist's response text"}
```

#### PersonalityService (personality_service.py)

**Purpose**: Detect Big Five personality traits from text using fine-tuned BERT model.

**Model**: `BertForSequenceClassification` with 5 outputs (sigmoid activation)

**Big Five Traits**:
- Extroversion (index 0)
- Neuroticism (index 1)
- Agreeableness (index 2)
- Conscientiousness (index 3)
- Openness (index 4)

**Therapeutic Adaptation Logic** (PsyCOTInference class):

| Score Condition | Adaptation |
|-----------------|------------|
| Neuroticism > 0.6 | Gentle, reassuring tone; slower pacing |
| Neuroticism < 0.4 | Direct, matter-of-fact tone |
| Conscientiousness > 0.6 | Structured guidance; systematic approach |
| Conscientiousness < 0.4 | Flexible, exploratory guidance |
| Openness > 0.6 | Encourage new perspectives |
| Openness < 0.4 | Build on familiar concepts |
| Extroversion > 0.6 | Interactive, conversational pacing |
| Extroversion < 0.4 | Allow silence and reflection |

---

### 4. RAG Layer (rag_layer/)

**Purpose**: Retrieve relevant therapeutic techniques from Pinecone vector database.

**Configuration**:
- Index: `3am-talks-rag`
- Namespace: `default`
- Embedding: Pinecone inference API (`llama-text-embed-v2`)
- Default top_k: 3

**Technique Metadata Structure**:
```python
{
    "id": "technique_id",
    "score": 0.85,
    "text": "Full technique description...",
    "metadata": {
        "technique_name": "Cognitive Restructuring",
        "modality": "CBT",
        "difficulty": "intermediate",
        "culture_notes": "..."
    }
}
```

**Data Source**: `techniques.json` (525KB) - Contains therapeutic techniques for indexing

---

### 5. Database Layer (database/)

#### SupabaseClient (supabase_client.py)

**Purpose**: Low-level REST API client for Supabase.

**Key Methods**:
| Method | Purpose |
|--------|---------|
| `select(table, columns, filters)` | Query records |
| `insert(table, data)` | Create record |
| `update(table, data, filters)` | Update records |
| `delete(table, filters)` | Delete records |
| `rpc(function_name, params)` | Call stored procedure |
| `sign_up(email, password)` | Register user |
| `sign_in(email, password)` | Authenticate user |
| `admin_update_user(user_id, attrs)` | Admin update |
| `admin_delete_user(user_id)` | Admin delete |

#### UserService (user_service.py)

**Purpose**: High-level service for user, conversation, and message management.

**Profile Management**:
- `create_user_profile(user_id)` - Create with default personality scores (0.5)
- `get_user_profile(user_id)` - Fetch profile
- `update_personality_scores(user_id, scores, text_length)` - Update Big Five
- `update_risk_flags(user_id, flags)` - Store risk indicators
- `update_preferences(user_id, prefs)` - User preferences

**Conversation Management**:
- `create_conversation(user_id)` - Start new conversation
- `get_conversation(conversation_id)` - Fetch conversation
- `get_active_conversation(user_id)` - Get user's active session
- `end_conversation(conversation_id)` - Mark as ended
- `update_conversation_turns(...)` - Track progress

**Message Management**:
- `add_message(...)` - Save message with optional personality_scores and rag_techniques
- `get_conversation_history(conversation_id, limit)` - Get messages sorted by turn
- `get_user_conversation_text(user_id, conversation_id, last_n_turns)` - Extract user text

---

### 6. Voice Agent (voice_agent.py)

**Purpose**: LiveKit voice agent bridging audio conversations to backend.

**Pipeline Architecture**:
```
User Audio → Silero VAD → ElevenLabs STT → Backend API → ElevenLabs TTS → User Audio
```

**Configuration** (`build_session()`):
```python
AgentSession(
    vad=silero.VAD.load(),                    # Voice Activity Detection
    stt=elevenlabs.STT("scribe_v2_realtime"), # Speech-to-Text
    llm=openai.LLM(model="psychocounsel"),   # Placeholder (overridden)
    tts=elevenlabs.TTS("eleven_multilingual_v2"),  # Text-to-Speech
    allow_interruptions=True,
    min_interruption_duration=0.5
)
```

**Bootstrap Flow**:
1. Connect to LiveKit room
2. Wait for user to join (extract user_id from identity)
3. Call `/api/voice/bootstrap` to get/resume conversation
4. Start session with Ella agent

**Critical Design**: All "thinking" (persona, history, RAG, personality) happens in backend ConversationManager, ensuring consistency between text and voice interfaces.

---

### 7. Questionnaire System (questionnaire.py)

**Purpose**: Structured personality assessment for new users.

**Questions**: 8 open-ended questions targeting Big Five traits:

| ID | Question | Category |
|----|----------|----------|
| 1 | Tell me about yourself... | openness |
| 2 | How do you handle social situations? | extroversion |
| 3 | How do you respond to challenges? | neuroticism |
| 4 | How do you approach goals? | conscientiousness |
| 5 | How do you interact in relationships? | agreeableness |
| 6 | What brings you joy? | general |
| 7 | How do you deal with stress? | neuroticism |
| 8 | What's something new you've tried? | openness |

**Flow**:
1. New user starts session → questionnaire initiated
2. Each response collected and stored
3. After completion, all responses analyzed by BERT personality model
4. Initial personality scores stored in user profile

---

### 8. Frontend Architecture

**Technology Stack**:
- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS + Radix UI
- TanStack Query (React Query)
- React Router DOM
- Framer Motion (animations)
- LiveKit React Components

**Path Alias**: `@/` maps to `client/src/`

**Routing** (App.tsx):
```tsx
<Routes>
  <Route path="/" element={<Landing />} />
  <Route path="/auth" element={<Auth />} />
  <Route path="/dashboard" element={<Dashboard />} />
  <Route path="/therapist" element={<Therapist />} />
  <Route path="/history" element={<History />} />
  <Route path="/profile" element={<Profile />} />
  <Route path="/about" element={<About />} />
  <Route path="/learn-more" element={<LearnMore />} />
  <Route path="/auth/oauth-success" element={<OAuthSuccess />} />
</Routes>
```

**State Management**:
- **AuthContext**: Global authentication state (user, loading, isAuthenticated, signOut)
- **TanStack Query**: Server state (conversations, messages, profile, stats)
- **Local State**: Component-level state for UI interactions

**Key Components**:
- **Therapist.tsx** (802 lines): Main chat interface with conversation sidebar, message display, voice call integration
- **VoiceCall.tsx**: LiveKit room integration with audio visualizer
- **AuthContext.tsx**: Authentication provider wrapping entire app

---

## Database Schema

### Supabase Tables

#### `user_profiles`
| Column | Type | Purpose |
|--------|------|---------|
| user_id | UUID | Primary key (references auth.users) |
| extroversion | float | Big Five trait score (0.0-1.0) |
| neuroticism | float | Big Five trait score (0.0-1.0) |
| agreeableness | float | Big Five trait score (0.0-1.0) |
| conscientiousness | float | Big Five trait score (0.0-1.0) |
| openness | float | Big Five trait score (0.0-1.0) |
| total_text_analyzed | int | Character count for personality analysis |
| personality_updated_at | timestamp | Last personality update |
| profile_version | int | Version for optimistic locking |
| risk_flags | jsonb | Risk indicators |
| preferences | jsonb | User preferences |

#### `conversations`
| Column | Type | Purpose |
|--------|------|---------|
| conversation_id | UUID | Primary key |
| user_id | UUID | Foreign key to user_profiles |
| is_active | boolean | Whether conversation is ongoing |
| total_turns | int | Number of message exchanges |
| last_personality_update_turn | int | Turn count at last personality update |
| title | text | Auto-generated title |
| summary | text | Auto-generated summary |
| tags | text[] | Issue tags |
| mood | text | Detected mood |
| duration_minutes | int | Session duration |
| ended_at | timestamp | When conversation ended |

#### `messages`
| Column | Type | Purpose |
|--------|------|---------|
| message_id | UUID | Primary key |
| conversation_id | UUID | Foreign key to conversations |
| user_id | UUID | Foreign key to user_profiles |
| role | text | "user" or "assistant" |
| content | text | Message text |
| turn_index | int | Position in conversation |
| personality_scores_at_turn | jsonb | Personality scores when message was sent |
| rag_techniques_used | jsonb | RAG techniques used for response |

---

## Development Commands

### Backend Setup
```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run backend API server (port 5050)
python src/api.py

# Or use uvicorn directly
python -m uvicorn src.api:app --host 0.0.0.0 --port 5050 --reload

# Run voice agent separately
python src/voice_agent.py dev
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev      # Development server (port 5173)
npm run build    # Production build
npm run check    # TypeScript type checking
```

### Start All Services
```bash
# Windows
start.bat

# Linux/Mac
./start.sh
```

This starts:
1. Backend API on port 5050
2. Frontend dev server on port 5173
3. Voice agent process

### Testing
```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_full_system.py

# Run with verbose output
pytest tests/ -v
```

---

## Environment Variables

Required in `.env`:

```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key

# Pinecone (RAG)
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX_NAME=3am-talks-rag

# Session Management
SESSION_SECRET=your-random-secret-string

# LiveKit (Voice)
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

# ElevenLabs (STT/TTS)
ELEVEN_API_KEY=your_elevenlabs_api_key

# Voice Agent Auth
VOICE_AGENT_SECRET=your-voice-agent-secret

# Public URLs (OAuth redirects)
FRONTEND_URL=http://localhost:5173
BACKEND_PUBLIC_URL=http://localhost:5050

# External LLM (Optional)
COLAB_API_URL=https://your-colab-endpoint
COLAB_API_KEY=your-api-key
```

---

## Prerequisites

1. **Python 3.10+** with pip
2. **Node.js 18+** with npm
3. **Supabase Project** - Create at supabase.com
4. **Pinecone Index** - Create at pinecone.io with name `3am-talks-rag`
5. **LiveKit Server**:
   - Windows: Use `livekit-server/livekit-server.exe --dev`
   - Or use LiveKit Cloud
6. **ElevenLabs Account** - For STT/TTS API keys

---

## Code Conventions

### Backend (Python)

- **Imports**: Standard library → Third-party → Local (alphabetical within groups)
- **Logging**: Use standard `logging` module with `logger = logging.getLogger(__name__)`
- **Type Hints**: Use for function signatures
- **Docstrings**: Google-style for public methods
- **Error Handling**: Catch specific exceptions, log with context, re-raise or return safe defaults
- **Configuration**: Environment variables via `python-dotenv`
- **Database**: Use `UserService` methods, not raw `SupabaseClient` in business logic

### Frontend (TypeScript/React)

- **Path Alias**: Use `@/` for imports from `client/src/`
- **Components**: Functional components with hooks
- **Styling**: Tailwind CSS classes, Radix UI for complex components
- **State**: React Query for server state, Context for global client state
- **Types**: Define interfaces in `types/` or co-locate with components
- **Naming**: PascalCase for components, camelCase for utilities

---

## Common Tasks

### Adding a New API Endpoint

1. Add route in `src/api.py`
2. Create Pydantic models for request/response
3. Implement logic using `ConversationManager` or `UserService`
4. Add error handling and logging
5. Update frontend hooks if needed

### Adding a New Frontend Page

1. Create component in `frontend/client/src/pages/`
2. Add route in `App.tsx`
3. Add navigation link in `Navigation.tsx`
4. Update any necessary hooks or context

### Modifying Personality Detection

1. Update `PersonalityService` in `ai_layer/personality_service.py`
2. Modify `PsyCOTInference` for therapeutic adaptations
3. Adjust `personality_update_interval` in `ConversationManager`

### Adding RAG Techniques

1. Add techniques to `techniques.json`
2. Re-index in Pinecone (not automatic)
3. Verify retrieval with `RAGService`

---

## Architecture Decisions

### Why Cookie-Based Sessions Instead of JWT?

- Simpler for server-side rendering compatibility
- Automatic expiration handling
- No need for refresh token logic in frontend
- Supabase handles the underlying auth

### Why Lazy Initialization for ConversationManager?

- Model loading (BERT) can take 5-10 seconds
- Prevents blocking server startup
- Allows graceful degradation if models fail to load

### Why Separate Voice Agent Process?

- Voice processing requires dedicated resources
- Can be deployed independently for scaling
- Isolates real-time audio processing from HTTP API

### Why Pinecone Inference Instead of Local Embeddings?

- No need to manage embedding model
- Consistent embeddings across environments
- Lower latency for small-medium datasets

---

## Troubleshooting

### Backend Won't Start
- Check `.env` file has all required variables
- Verify virtual environment is activated
- Check if port 5050 is already in use

### Frontend Build Errors
- Run `npm run check` to see TypeScript errors
- Delete `node_modules` and reinstall if dependencies are stale

### Voice Agent Not Connecting
- Ensure LiveKit server is running
- Check `LIVEKIT_URL` matches server address
- Verify `ELEVEN_API_KEY` is valid

### Personality Detection Returns Defaults
- Check if BERT model exists in `Models/bert-base-personality/`
- Verify `transformers` and `torch` are installed
- Check logs for model loading errors

### RAG Not Returning Results
- Verify Pinecone index exists and is populated
- Check `PINECONE_API_KEY` is valid
- Ensure namespace matches (default: "default")

---

## Research References

This project is based on research in LLM-assisted therapy:

- **LLM4CBT**: Framework for using LLMs in Cognitive Behavioral Therapy
- **PsyCoT**: PsychoCounsel model fine-tuned for therapeutic conversations
- **Big Five Personality Model**: OCEAN model for personality assessment

See `Docs/` folder for detailed research papers.