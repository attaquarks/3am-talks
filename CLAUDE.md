# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Ella Speaks Calmly** (formerly 3AM Talks) is an AI-powered therapy and counseling system. It provides personalized mental health support through:
- Personality-aware responses (BERT-based personality assessment)
- Retrieval-augmented generation (RAG) using Pinecone for therapeutic technique retrieval
- Evidence-based therapy techniques (CBT, DBT, ACT)
- Real-time voice conversations via LiveKit

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)                     │
│                  localhost:5173                                  │
│   Pages: Landing, Auth, Dashboard, Therapist, History, Profile │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│                   Backend (FastAPI)                              │
│                  localhost:5050                                  │
│   src/api.py - REST endpoints under /api/*                       │
│   src/conversation_manager.py - Core orchestration               │
└──────────┬─────────────────┬─────────────────┬──────────────────┘
           │                 │                 │
           ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐
    │   Supabase   │  │   Pinecone   │  │  Colab OpenAI-compatible LLM │
    │   Database   │  │   (RAG)      │  │  (psychocounsel endpoint)    │
    └──────────────┘  └──────────────┘  └──────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              Voice Agent (separate process)                      │
│   src/voice_agent.py - LiveKit + ElevenLabs STT/TTS              │
│   Pipeline: Silero VAD → ElevenLabs STT → LLM → ElevenLabs TTS   │
└─────────────────────────────────────────────────────────────────┘
```

## Key Directories

- `src/` - Python backend
  - `api.py` - FastAPI server entry point (port 5050)
  - `conversation_manager.py` - Main orchestrator for therapy sessions
  - `voice_agent.py` - LiveKit voice agent for real-time audio
  - `ai_layer/` - LLM service and personality detection (BERT-based)
  - `rag_layer/` - Pinecone RAG service for technique retrieval
  - `database/` - Supabase client and user service
  - `questionnaire.py` - Personality questionnaire system
- `frontend/` - React + TypeScript frontend (Vite)
  - `client/src/pages/` - Main app pages
  - `client/src/components/` - Reusable UI components
  - `client/src/context/` - React context providers (AuthContext)
- `Models/` - ML model files (BERT personality model)
- `tests/` - Test suite

## Development Commands

### Backend
```bash
# Activate virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Run backend API server (port 5050)
python src/api.py

# Run voice agent separately
python src/voice_agent.py dev
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

# Run a specific test file
pytest tests/test_full_system.py
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

## Prerequisites

1. **LiveKit server** for voice agent:
   - Windows: Run `livekit-server.exe` from `livekit-server/` directory
   - Or use LiveKit Cloud

## API Endpoints

Backend API runs on `localhost:5050` with `/api/*` prefix:
- `/api/health` - Health check
- `/api/register`, `/api/login` - Authentication
- `/api/chat` - Main conversation endpoint
- `/api/profile` - User profile management
- `/api/conversations` - Conversation history

## Code Conventions

### Backend (Python)
- Uses `python-dotenv` for environment loading
- Pydantic models for request/response validation
- Lazy initialization pattern for ConversationManager (see `get_manager()` in api.py)
- Logging with standard `logging` module

### Frontend (TypeScript/React)
- Uses `@/` path alias for `client/src/`
- Radix UI components with Tailwind CSS
- React Router for routing
- TanStack Query for server state
- AuthContext wraps the entire app

## Database Schema

Supabase stores:
- User profiles (personality traits, preferences)
- Conversations (session history)
- Messages (individual chat messages)