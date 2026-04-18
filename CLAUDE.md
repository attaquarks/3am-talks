# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Ella Speaks Calmly** (formerly 3AM Talks) is an AI-powered therapy and counseling system. It provides personalized mental health support through:
- Personality-aware responses (BERT-based personality assessment)
- Retrieval-augmented generation (RAG) using Pinecone for therapeutic technique retrieval
- Evidence-based therapy techniques (CBT, DBT, ACT)
- Real-time voice conversations via LiveKit
- Multi-session crisis detection with WhatsApp/SMS emergency alerts (Twilio)
- Therapist portal with patient management, notes, treatment plans, and homework
- Admin dashboard with user management, analytics, reports, and announcements

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)                     │
│                  localhost:5173                                  │
│   Roles: Patient, Therapist, Admin                              │
│   Pages: Landing, Auth, Dashboard, Therapist, History, Profile, │
│          Safety, AdminDashboard, TherapistDashboard, MyTherapists│
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│                   Backend (FastAPI)                              │
│                  localhost:5050                                  │
│   src/main.py                - App entry, middleware, routers    │
│   src/config.py              - Centralized configuration         │
│   src/core/                  - Sessions, auth guards, rate limit │
│   src/routes/auth.py         - Register/login/OAuth              │
│   src/routes/chat.py         - Main conversation endpoint        │
│   src/routes/admin.py        - Admin dashboard routes            │
│   src/routes/crisis.py       - Crisis detection & alert routes   │
│   src/routes/therapist.py    - Therapist portal routes           │
│   src/routes/data.py         - Generic table CRUD                │
│   src/routes/user.py         - Current-user profile routes       │
│   src/routes/voice.py        - Voice-agent bootstrap/chat        │
│   src/conversation/manager.py - Session orchestration            │
│   src/conversation/summary.py - Conversation summarization       │
│   src/crisis/service.py      - Multi-session crisis detection    │
│   src/crisis/alert.py        - Twilio WhatsApp/SMS alerts        │
└──────────┬─────────────────┬─────────────────┬──────────────────┘
           │                 │                 │
           ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐
    │   Supabase   │  │   Pinecone   │  │  Colab OpenAI-compatible LLM │
    │   Database   │  │   (RAG)      │  │  (psychocounsel endpoint)    │
    └──────────────┘  └──────────────┘  └──────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              Voice Agent (separate process)                      │
│   src/voice/agent.py - LiveKit + Edge TTS / ElevenLabs          │
│   Pipeline: Silero VAD → ElevenLabs STT → LLM → TTS            │
└─────────────────────────────────────────────────────────────────┘
```

## Key Directories

- `src/` - Python backend (modularized)
  - `main.py` - FastAPI entry point (port 5050), lifespan, middleware, routers
  - `config.py` - Centralized runtime configuration
  - `core/` - Shared infrastructure
    - `sessions.py` - Cookie signing, session store, SESSION_SECRET fail-fast
    - `helpers.py` - Auth guards (`require_user`, `require_admin`, `require_voice_agent`), DB helpers
    - `rate_limit.py` - Shared slowapi Limiter singleton
  - `routes/` - HTTP route modules
    - `auth.py` - Register/login/OAuth (rate-limited, CSRF-nonce protected)
    - `chat.py` - Main conversation endpoint (rate-limited)
    - `admin.py` - Admin dashboard endpoints
    - `crisis.py` - `/api/v1/crisis/*` — settings, contacts, events, test-alert (rate-limited)
    - `therapist.py` - `/api/therapist/*` — linking, notes, treatment plans, homework, messaging, reports
    - `data.py` - Generic table CRUD
    - `user.py` - Current-user profile
    - `voice.py` - Voice agent bootstrap + chat (HMAC-verified)
  - `conversation/`
    - `manager.py` - Main orchestrator for therapy sessions
    - `summary.py` - Conversation summarization (pooled HTTP client)
    - `questionnaire.py` - Personality questionnaire system
  - `crisis/`
    - `service.py` - Multi-session crisis detection logic
    - `alert.py` - Twilio WhatsApp/SMS alerts (consent re-checked before dispatch)
    - `data/helplines.json` - Static helpline directory
  - `voice/`
    - `agent.py` - LiveKit voice agent for real-time audio
    - `tts_plugin.py` - Edge TTS plugin
  - `ai_layer/` - LLM service (`llm_service.py`) and personality detection (`personality_service.py`)
  - `rag_layer/` - Pinecone RAG engine and service
  - `database/` - Supabase client and user service
- `frontend/` - React + TypeScript frontend (Vite)
  - `client/src/pages/` - Main app pages (Landing, Auth, Dashboard, Therapist, History, Profile, Safety, About, LearnMore, AdminDashboard, AdminProfile, TherapistDashboard, TherapistProfile, TherapistMessages, TherapistPending, MyTherapists, PatientView, InviteAccept)
  - `client/src/components/` - Reusable UI components (Navigation, VoiceCall, CrisisCountdownModal, AuthWrapper, ThemeProvider, plus subdirs: admin/, auth/, patient/, shared/)
  - `client/src/context/` - React context providers (AuthContext)
- `Models/` - ML model files (BERT personality model)
- `Docs/` - Project documentation (crisis roadmap, setup guides, research papers, SQL migrations)
- `supabase/` - Supabase config and migrations
- `tests/` - Test suite (`test_full_system.py`, `test_crisis_detector.py`)

## Development Commands

### Backend
```bash
# Activate virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Run backend API server (port 5050)
python src/main.py

# Run voice agent separately
python src/voice/agent.py dev
```

### Frontend
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

### Testing
```bash
# Run tests with pytest
pytest tests/

# Run specific test files
pytest tests/test_full_system.py
pytest tests/test_crisis_detector.py
```

## Environment Setup

Required environment variables in `.env`:
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_KEY` - Supabase anon key
- `PINECONE_API_KEY` - Pinecone API key
- `PINECONE_ENVIRONMENT` - Pinecone environment (e.g., us-east-1)
- `PINECONE_INDEX_NAME` - Pinecone index name (default: 3am-talks-rag)
- `SESSION_SECRET` - Secret for cookie signing
- `LIVEKIT_URL` - LiveKit server URL
- `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` - LiveKit credentials
- `ELEVEN_API_KEY` - ElevenLabs API key (for STT/TTS)
- `COLAB_API_URL` - Optional: External LLM API URL
- `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` - Twilio credentials (for crisis WhatsApp/SMS alerts)
- `TWILIO_WHATSAPP_FROM` - Twilio WhatsApp sender number

## Prerequisites

1. **LiveKit server** for voice agent:
   - Windows: Run `livekit-server.exe` from `livekit-server/` directory
   - Or use LiveKit Cloud

## API Endpoints

Backend API runs on `localhost:5050`:

### Core (`src/routes/auth.py`, `src/routes/chat.py`, `src/routes/user.py`, `src/routes/data.py`, `src/routes/voice.py`)
- `/api/health` - Health check
- `/api/register`, `/api/login`, `/api/logout` - Authentication
- `/api/auth/social`, `/api/auth/oauth/{provider}/start`, `/api/auth/oauth/session` - OAuth flows
- `/api/user` - Get current user
- `/api/account/email`, `/api/account/password` - Account management
- `/api/account` (DELETE) - Delete account
- `/api/chat` - Main conversation endpoint
- `/api/data/{table}` - Generic CRUD for Supabase tables
- `/api/livekit/token` - LiveKit room token generation
- `/api/voice/bootstrap`, `/api/voice/chat` - Voice session endpoints

### Admin (`src/routes/admin.py`)
- `/api/admin/overview`, `/api/admin/analytics` - Dashboard stats
- `/api/admin/users` - User management (list, status, role, delete)
- `/api/admin/reports`, `/api/admin/feedback` - Content moderation
- `/api/admin/therapists/queue` - Therapist verification queue
- `/api/admin/announcements` - System announcements
- `/api/admin/logs` - Audit logs

### Therapist Portal (`src/routes/therapist.py`)
- `/api/therapist/register`, `/api/therapist/me` - Therapist profile
- `/api/therapist/patients` - Patient list and details
- `/api/therapist/notes`, `/api/therapist/treatment-plans`, `/api/therapist/homework` - Clinical tools
- `/api/therapist/messages` - Therapist-patient messaging
- `/api/therapist/crisis` - Crisis event management
- `/api/invite-therapist`, `/api/therapist/invite-patient` - Linking invitations
- `/api/links/*` - Accept/decline/revoke patient-therapist links
- `/api/reports`, `/api/feedback` - User reports and feedback

### Crisis System (`src/routes/crisis.py`)
- `/api/v1/crisis/settings` - User crisis preferences
- `/api/v1/crisis/contacts` - Emergency contact management
- `/api/v1/crisis/location` - Location for nearest helpline lookup
- `/api/v1/crisis/events` - Crisis event history
- `/api/v1/crisis/cancel-alert`, `/api/v1/crisis/test-alert` - Alert management

## Code Conventions

### Backend (Python)
- Uses `python-dotenv` for environment loading
- Pydantic models for request/response validation
- Lazy initialization pattern for ConversationManager (see `get_manager()` in api.py)
- Route modules register via functions (e.g., `register_crisis_routes(app)`, `register_therapist_routes(app)`)
- Logging with standard `logging` module

### Frontend (TypeScript/React)
- Uses `@/` path alias for `client/src/`
- Radix UI components with Tailwind CSS
- React Router for routing
- TanStack Query for server state
- AuthContext wraps the entire app
- Role-based pages: patient (Dashboard, History, Profile, Safety, MyTherapists), therapist (TherapistDashboard, PatientView, TherapistMessages), admin (AdminDashboard, AdminProfile)

## Database Schema

Supabase stores:
- User profiles (personality traits, preferences, roles)
- Conversations (session history)
- Messages (individual chat messages)
- Therapist profiles and verification records
- Patient-therapist links (with consent tracking)
- Clinical notes, treatment plans, homework assignments
- Crisis events and emergency contacts
- Reports, feedback, announcements, audit logs
