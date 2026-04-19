# Ella Speaks Calmly (3AM Talks)

**Ella Speaks Calmly** (formerly *3AM Talks*) is an AI-powered therapy and
counseling platform. It delivers personalized mental-health support through
a personality-aware LLM, retrieval-augmented generation (RAG) over therapeutic
techniques, real-time voice conversations, multi-stage crisis detection, and
a clinical portal for linked therapists.

This is my Final Year Project. It combines a Python/FastAPI backend, a React
(Vite + TypeScript) frontend, and a separate LiveKit voice-agent process.

---

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Directory Layout](#directory-layout)
5. [Prerequisites](#prerequisites)
6. [Environment Variables](#environment-variables)
7. [Quickstart](#quickstart)
8. [Development](#development)
9. [Running Tests](#running-tests)
10. [Crisis Detection Pipeline](#crisis-detection-pipeline)
11. [User Roles](#user-roles)
12. [Security Notes](#security-notes)
13. [License](#license)

---

## Features

### Patient experience
- **Personality-aware conversations** — a BERT-based classifier scores
  Big-Five traits from the user's own messages; responses are adapted to
  the resulting personality profile.
- **Evidence-based techniques** — CBT / DBT / ACT snippets are retrieved
  from a Pinecone vector index and grounded into the LLM prompt per turn.
- **Session memory** — conversations, messages, and summaries are persisted
  to Supabase so context survives across sessions.
- **Real-time voice** — a LiveKit voice agent (Silero VAD → ElevenLabs STT
  → backend LLM → ElevenLabs / Edge TTS) lets users talk to Ella in the
  browser. The voice worker is a **transport worker only**: all therapy
  logic runs on the backend so voice and text share the exact same
  ConversationManager, RAG, and personality adaptation.
- **Multi-stage crisis detection** — every user message is scored for
  self-harm / suicide risk. HIGH fires a safety modal with local helplines;
  CRITICAL optionally kicks off a consent-gated countdown that dispatches
  WhatsApp / SMS alerts to emergency contacts via Twilio.

### Therapist portal
- Verified therapist profiles (admin-approved).
- Patient list with consent-scoped access: SOAP notes, treatment plans,
  homework, secure messaging, and crisis-event history.
- Patient-therapist links with explicit consent scopes (`read_notes`,
  `write_notes`, `view_sessions`, etc.). Scope checks **fail closed** — if
  `consent_scope` is malformed or missing, the portal denies access.
- Clinical access log: every read of patient data is recorded and visible
  to the patient.

### Admin dashboard
- User management (status, role, delete).
- Therapist verification queue.
- Reports, feedback, announcements, and full audit logs.
- Overview + analytics cards (active users, session volume, crisis events).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)                     │
│                  localhost:5173                                  │
│   Roles: Patient, Therapist, Admin                              │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / WebSocket / LiveKit WS
┌────────────────────────────▼────────────────────────────────────┐
│                   Backend (FastAPI, port 5050)                   │
│                                                                  │
│  routes/chat.py  ─────►  process_message_with_crisis            │
│                            │                                     │
│                            ├── ConversationManager (LLM + RAG)  │
│                            └── crisis.integration               │
│                                  ├── keyword_scan               │
│                                  ├── roberta_client             │
│                                  └── llm_arbitrate              │
│                                                                  │
│  routes/voice.py ─────►  HMAC-verified voice bridge             │
│  routes/therapist.py ──► link-scoped portal + shared patient    │
│  routes/crisis.py ────►  settings, contacts, events, alerts     │
│  routes/admin.py ─────►  dashboard, users, reports, audit       │
└──────────┬─────────────────┬─────────────────┬──────────────────┘
           │                 │                 │
           ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐
    │   Supabase   │  │   Pinecone   │  │  Colab OpenAI-compatible LLM │
    │ (DB + auth)  │  │    (RAG)     │  │   (psychocounsel endpoint)   │
    └──────────────┘  └──────────────┘  └──────────────────────────────┘
                                                     ▲
                                                     │
┌─────────────────────────────────────────────────────────────────┐
│              Voice Agent (separate process)                      │
│   src/voice/agent.py — LiveKit worker (Ella)                    │
│   Pipeline: Silero VAD → ElevenLabs STT → backend → TTS         │
│   Crisis events from the backend are republished to the room    │
│   via a LiveKit data channel so the browser modal opens live.   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

**Backend**
- Python 3.11+ / FastAPI
- Supabase (PostgREST-style client in `src/database/supabase_client.py`)
- Pinecone (RAG index `3am-talks-rag` by default)
- HuggingFace Transformers (RoBERTa suicide-prediction head, BERT personality)
- Twilio (WhatsApp + SMS for crisis alerts)
- slowapi (per-route rate limiting)
- itsdangerous (signed session cookies)
- httpx (pooled clients for Colab LLM + RoBERTa remote mode)

**Frontend**
- React 18 + TypeScript + Vite
- React Router
- TanStack Query
- Radix UI + Tailwind CSS
- `@/` path alias for `client/src/`

**Voice**
- LiveKit Agents SDK
- ElevenLabs STT / TTS (with Edge TTS fallback)
- Silero VAD

---

## Directory Layout

```
src/
├── main.py                     # FastAPI entrypoint (port 5050)
├── config.py                   # Centralized runtime config
├── core/
│   ├── sessions.py             # Signed cookie session store
│   ├── helpers.py              # Auth guards, DB helpers, _parse_pagination
│   └── rate_limit.py           # slowapi Limiter singleton
├── routes/
│   ├── auth.py                 # Register / login / OAuth (rate-limited, CSRF)
│   ├── chat.py                 # /api/chat — therapy + crisis in parallel
│   ├── voice.py                # /api/voice/* — HMAC-verified bridge
│   ├── therapist.py            # Portal (router) + patient-side (shared_router)
│   ├── crisis.py               # /api/v1/crisis/*
│   ├── admin.py                # /api/admin/*
│   ├── user.py                 # Current-user profile + account
│   └── data.py                 # Generic /api/data/{table} CRUD
├── conversation/
│   ├── manager.py              # Main orchestrator
│   ├── summary.py              # Pooled httpx summarization client
│   └── questionnaire.py        # Personality questionnaire
├── crisis/
│   ├── service.py              # 3-stage detector + fusion rules
│   ├── integration.py          # Shared pipeline for chat + voice
│   ├── roberta_client.py       # Local or remote RoBERTa scorer
│   ├── alert.py                # Twilio notifiers, countdown runner
│   └── data/helplines.json
├── voice/
│   ├── agent.py                # LiveKit Ella worker (transport only)
│   └── tts_plugin.py           # Edge TTS fallback
├── ai_layer/                   # LLM + personality services
├── rag_layer/                  # Pinecone engine + service
└── database/                   # Supabase client + user service

frontend/client/src/
├── pages/                      # Landing, Auth, Dashboard, ...
│   ├── PatientMessages.tsx     # Secure chat with linked therapists
│   ├── PatientAccessLog.tsx    # Audit trail visible to patient
│   ├── MyTherapists.tsx
│   ├── TherapistDashboard.tsx
│   ├── PatientView.tsx
│   └── AdminDashboard.tsx
├── components/                 # Navigation, VoiceCall, CrisisCountdownModal…
└── context/AuthContext.tsx

tests/
├── conftest.py                 # Loads .env, adds src/ to sys.path
├── test_crisis_detector.py     # Stage-1/2/3 + fusion unit tests
├── test_therapist_auth.py      # SEC-003 scope fail-closed + link checks
└── test_full_system.py         # End-to-end smoke test

supabase/migrations/            # Schema + performance indexes
Docs/                           # Crisis roadmap, setup guides, research papers
Models/                         # Local BERT / RoBERTa checkpoints (gitignored)
```

---

## Prerequisites

1. **Python 3.11 or 3.12** (Transformers wheels and torch builds target these).
2. **Node.js 18+** for the frontend.
3. **LiveKit server** — either self-host (`livekit-server/livekit-server.exe` on
   Windows) or use LiveKit Cloud.
4. **Supabase project** with the migrations under `supabase/migrations/` applied.
5. **Pinecone index** (name configurable via `PINECONE_INDEX_NAME`).
6. **Colab OpenAI-compatible LLM endpoint** — used both for the therapy
   response and for the crisis LLM arbiter.
7. Optional: local RoBERTa checkpoint at
   `Models/roberta-base-suicide-prediction-phr/` *or* a `ROBERTA_REMOTE_URL`
   pointing at a `/classify` endpoint.

---

## Environment Variables

Required (`.env` in project root):

| Variable | Purpose |
| -------- | ------- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase anon key |
| `SESSION_SECRET` | Secret for signed session cookies (fail-fast on boot) |
| `PINECONE_API_KEY` | Pinecone auth |
| `PINECONE_ENVIRONMENT` | e.g. `us-east-1` |
| `PINECONE_INDEX_NAME` | Default `3am-talks-rag` |
| `COLAB_API_URL` | OpenAI-compatible LLM endpoint (also used by crisis arbiter) |
| `LIVEKIT_URL` | LiveKit WS URL (e.g. `ws://localhost:7880`) |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | LiveKit credentials |
| `ELEVEN_API_KEY` | ElevenLabs STT + TTS |
| `VOICE_AGENT_SECRET` | HMAC shared secret for `/api/voice/*` |

Optional:

| Variable | Purpose |
| -------- | ------- |
| `COLAB_API_KEY` | Auth header for Colab endpoint (defaults to `EMPTY`) |
| `CRISIS_ARBITER_MODEL` | Override model name (default `psychocounsel`) |
| `ROBERTA_REMOTE_URL` | If set, hit `{URL}/classify` instead of loading locally |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | Crisis WhatsApp + SMS |
| `TWILIO_WHATSAPP_FROM` | Twilio WhatsApp sender number |

---

## Quickstart

```bash
# 1. Clone and enter the repo
git clone https://github.com/<you>/<repo>.git
cd <repo>

# 2. Python backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS
pip install -r requirements.txt

# 3. Frontend
cd frontend
npm install
cd ..

# 4. Populate .env (see table above)

# 5. Run everything
start.bat                       # Windows
# ./start.sh                    # Linux / macOS
```

`start.bat` / `start.sh` launches the backend API (port 5050), the voice
agent (`src/voice/agent.py dev`), and the Vite dev server (port 5173).

---

## Development

### Backend only
```bash
python src/main.py              # FastAPI on :5050, auto-reload via uvicorn
```

### Voice agent only
```bash
python src/voice/agent.py dev
```

### Frontend only
```bash
cd frontend
npm run dev                     # :5173
npm run build                   # production bundle
npm run check                   # TypeScript type-check
```

### LiveKit server (Windows, self-hosted)
```bash
livekit-server\livekit-server.exe --dev
```

---

## Running Tests

Tests use `pytest` and share a `conftest.py` that loads `.env` and adds
`src/` to `sys.path` — this is required because several `src/` modules
read env vars (e.g. `SESSION_SECRET`) at import time.

```bash
pytest tests/                           # full suite
pytest tests/test_crisis_detector.py    # crisis pipeline unit tests
pytest tests/test_therapist_auth.py     # portal authorization unit tests
pytest tests/test_full_system.py        # end-to-end smoke
```

---

## Crisis Detection Pipeline

Every user message to `/api/chat` and `/api/voice/chat` passes through a
three-stage detector that runs *in parallel* with the therapy LLM so users
never wait longer because of safety checks.

1. **Stage 1 — keyword/regex tiers** (`crisis.service.keyword_scan`).
   Bands: `critical`, `high`, `medium`, `none`. Contextual modifiers
   (`tonight`, `pills`, `bridge`, `plan`, etc.) bump tier by one.
   Target: &lt;10 ms.
2. **Stage 1.5 — RoBERTa suicide probability**
   (`crisis.roberta_client.score`). Loaded locally on first call, or hit
   over HTTP if `ROBERTA_REMOTE_URL` is set. Gates: `0.35` / `0.60` / `0.85`.
3. **Stage 2 — LLM arbiter** (`crisis.service.llm_arbitrate`). Calls the
   Colab endpoint with a strict JSON schema to judge *intent vs. hyperbole*,
   *third-party framing*, *imminence*, and — when conversation history is
   passed — *escalation patterns*. Called only when stage 1 or 1.5 tripped,
   or when the session has already fired a HIGH/CRITICAL event.

Fusion is a deterministic rule table in `_fuse()`:
- Keyword CRITICAL → CRITICAL unless the LLM confirms hyperbole / third-party.
- Keyword HIGH + imminent intent → CRITICAL.
- Keyword NONE + prior-risk-in-session + escalating → HIGH / CRITICAL
  (closes the calm-resignation false-negative class from real data).
- LLM unreachable + stage-1 CRITICAL → fail to CRITICAL (over-alert is safer).

CRITICAL + explicit user consent starts a countdown
(`crisis.alert.run_countdown_and_fire`) — when the countdown elapses without
user cancellation, WhatsApp / SMS is dispatched to the user's emergency
contacts. Consent is **re-checked immediately before dispatch**, not only at
countdown start.

---

## User Roles

| Role | Home | Notable routes |
| ---- | ---- | -------------- |
| **Patient** | `/dashboard` | `/chat`, `/history`, `/safety`, `/profile`, `/my-therapists`, `/my-therapists/messages`, `/my-therapists/access-log` |
| **Therapist** | `/therapist-portal` | `/therapist-portal`, `/therapist-profile`, `/therapist-messages`, `/therapist-portal/patients/:id`, `/therapist-pending` |
| **Admin** | `/admin` | `/admin`, `/admin-profile` |

`AuthWrapper` enforces role-based redirects — patient-only URLs redirect
admins to `/admin` and therapists to `/therapist-portal` (including nested
paths like `/my-therapists/messages`).

---

## Security Notes

- `SESSION_SECRET` absence fails the backend at startup (no silent fallback).
- All mutating therapist-portal endpoints go through `_require_link` +
  `_has_scope` which **fail closed** on malformed `consent_scope` (covered
  by `tests/test_therapist_auth.py`).
- Auth, chat, and crisis endpoints are rate-limited via the shared
  `slowapi` Limiter.
- OAuth nonces are set with `SameSite=Lax` because they are read after a
  cross-site redirect back to the backend.
- Twilio dispatch re-checks consent at the moment of sending, not only
  when the countdown starts.
- The voice agent authenticates every backend call with an HMAC using
  `VOICE_AGENT_SECRET` — browser clients cannot hit `/api/voice/chat`.
- `clinical_access_logs` records every therapist read of patient data and
  is surfaced to the patient at `/my-therapists/access-log`.

---

## License

See the repository for license and contribution details.
