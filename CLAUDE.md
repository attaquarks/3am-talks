# Project Guide

This file is the orientation doc for engineers and coding agents working in
this repository. Keep it up-to-date whenever the architecture, routing surface,
or cross-module contracts change — it is the first thing new contributors
(human or automated) read.

---

## Project Overview

**Ella Speaks Calmly** (formerly *3AM Talks*) is an AI-powered therapy and
counseling system. It provides personalized mental-health support through:

- Personality-aware responses (BERT-based personality assessment).
- Retrieval-augmented generation (RAG) using Pinecone for therapeutic
  technique retrieval.
- Evidence-based therapy techniques (CBT, DBT, ACT).
- Real-time voice conversations via LiveKit.
- **Three-stage** crisis detection (keyword → RoBERTa → LLM arbiter) shared
  between text and voice, with WhatsApp / SMS emergency alerts via Twilio.
- Therapist portal with patient management, notes, treatment plans, homework,
  secure messaging, and a patient-visible access log.
- Admin dashboard with user management, analytics, reports, announcements,
  and audit logs.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)                     │
│                  localhost:5173                                  │
│   Roles: Patient, Therapist, Admin                              │
│   Pages: Landing, Auth, Dashboard, Chat, History, Profile,      │
│          Safety, MyTherapists, PatientMessages, PatientAccess-  │
│          Log, AdminDashboard, TherapistDashboard, PatientView,  │
│          TherapistMessages, TherapistPending, InviteAccept, ... │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / WebSocket / LiveKit WS
┌────────────────────────────▼────────────────────────────────────┐
│                   Backend (FastAPI, port 5050)                   │
│                                                                  │
│   src/main.py                 - App entry, middleware, routers   │
│   src/config.py               - Centralized configuration        │
│   src/core/                   - Sessions, auth guards, rate lim. │
│   src/routes/auth.py          - Register / login / OAuth         │
│   src/routes/chat.py          - /api/chat (therapy + crisis)     │
│   src/routes/voice.py         - /api/voice/* (HMAC-verified)     │
│   src/routes/admin.py         - Admin dashboard routes           │
│   src/routes/crisis.py        - Crisis settings / events / test  │
│   src/routes/therapist.py     - Portal + shared patient router   │
│   src/routes/data.py          - Generic /api/data/{table}        │
│   src/routes/user.py          - Current-user profile + account   │
│   src/conversation/manager.py - Session orchestration            │
│   src/conversation/summary.py - Conversation summarization       │
│   src/crisis/service.py       - Keyword + RoBERTa + LLM fusion   │
│   src/crisis/integration.py   - Shared pipeline for chat+voice   │
│   src/crisis/roberta_client.py- Local/remote suicide-prob model  │
│   src/crisis/alert.py         - Twilio notifiers + countdown     │
└──────────┬─────────────────┬─────────────────┬──────────────────┘
           │                 │                 │
           ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐
    │   Supabase   │  │   Pinecone   │  │  Colab OpenAI-compatible LLM │
    │   Database   │  │    (RAG)     │  │   (psychocounsel endpoint)   │
    └──────────────┘  └──────────────┘  └──────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              Voice Agent (separate process)                      │
│   src/voice/agent.py — LiveKit worker (Ella)                    │
│   Pipeline: Silero VAD → ElevenLabs STT → backend                │
│             → ElevenLabs TTS (primary) with Edge TTS fallback    │
│   Crisis events from /api/voice/chat are re-published to the    │
│   LiveKit data channel so the frontend CrisisCountdownModal     │
│   opens alongside the TTS reply.                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Directories

- `src/` — Python backend (modularized)
  - `main.py` — FastAPI entry point (port 5050); lifespan, middleware,
    router registration. **Both** `therapist_router` and
    `therapist_shared_router` are registered here — the second one owns the
    patient-facing endpoints that live in `routes/therapist.py`.
  - `config.py` — Centralized runtime configuration.
  - `core/` — Shared infrastructure.
    - `sessions.py` — Cookie signing, session store, `SESSION_SECRET`
      fail-fast on boot.
    - `helpers.py` — Auth guards (`require_user`, `require_admin`,
      `require_voice_agent`), DB helpers, and `_parse_pagination()` (used
      by chat, admin, and any paginated list route — clamps `limit` and
      `offset` with safe defaults).
    - `rate_limit.py` — Shared slowapi `Limiter` singleton.
  - `routes/` — HTTP route modules.
    - `auth.py` — Register / login / OAuth (rate-limited, CSRF-nonce
      protected; OAuth nonce cookie is deliberately `SameSite=Lax` because
      it is read after a cross-site redirect).
    - `chat.py` — `/api/chat` runs `process_message_with_crisis`
      (therapy LLM + crisis detector in parallel). `/api/conversations`
      and `/api/conversations/{id}/messages` are paginated via
      `_parse_pagination`.
    - `voice.py` — `/api/voice/bootstrap` and `/api/voice/chat`.
      HMAC-verified (`VOICE_AGENT_SECRET`). `/api/voice/chat` also runs
      `process_message_with_crisis`; when a crisis is detected the payload
      is forwarded to the voice agent which republishes it on the LiveKit
      data channel.
    - `admin.py` — Admin dashboard endpoints; `/api/admin/users` is
      paginated (`default_limit=50`, `max_limit=500`).
    - `crisis.py` — `/api/v1/crisis/*` (settings, contacts, events,
      location, cancel-alert, test-alert). Rate-limited.
    - `therapist.py` — Two routers:
      - `router` (prefix `/api/therapist`) — therapist-only endpoints
        (notes, treatment plans, homework, messaging, patient list).
      - `shared_router` (no prefix) — endpoints that both patients and
        therapists hit: `/api/patient/homework`, `/api/invite-therapist`,
        `/api/links/*`, `/api/invite/info`, `/api/invite/accept`.
      Separating them keeps the `/api/therapist` prefix scope-gated
      without breaking the patient-facing URLs.
    - `data.py` — Generic `/api/data/{table}` CRUD.
    - `user.py` — Current-user profile + account management.
  - `conversation/`
    - `manager.py` — Main orchestrator for therapy sessions.
    - `summary.py` — Conversation summarization (pooled httpx client).
    - `questionnaire.py` — Personality questionnaire system.
  - `crisis/`
    - `service.py` — Three-stage engine (see
      [Crisis Pipeline](#crisis-detection-pipeline) below). Also still
      exports the legacy `scan_messages(...)` used by therapist SOAP
      summaries — do not modify its signature.
    - `integration.py` — `process_message_with_crisis()` runs the therapy
      response and `detect_and_maybe_alert()` concurrently with
      `asyncio.gather(..., return_exceptions=True)`. This is the **only**
      integration seam both `/api/chat` and `/api/voice/chat` call.
    - `roberta_client.py` — Suicide-prediction head. Local mode loads
      `Models/roberta-base-suicide-prediction-phr/` (falls back to the HF
      id on miss). Remote mode is enabled by setting `ROBERTA_REMOTE_URL`.
      Never raises — failures return `0.0` so the rest of the pipeline
      still runs.
    - `alert.py` — Twilio WhatsApp/SMS notifiers (thread-safe lazy
      singletons), `start_countdown` / `cancel_active_countdown` /
      `run_countdown_and_fire`. **Consent is re-checked immediately
      before dispatch**, not only at countdown start.
    - `data/helplines.json` — Static helpline directory used by locale
      lookup.
  - `voice/`
    - `agent.py` — LiveKit voice agent worker (transport layer only).
      Accepts a `room` handle so it can `publish_data` crisis events to
      the browser. When launched as `python src/voice/agent.py dev`,
      Python puts `src/voice/` on `sys.path`; `agent.py` prepends `src/`
      so imports like `from voice.tts_plugin import TTS` resolve.
    - `tts_plugin.py` — Edge TTS plugin (used as fallback).
  - `ai_layer/` — LLM service (`llm_service.py`) and personality
    detection (`personality_service.py`).
  - `rag_layer/` — Pinecone RAG engine and service.
  - `database/` — Supabase client and user service.

- `frontend/` — React + TypeScript frontend (Vite).
  - `client/src/pages/`
    - Patient: `Landing`, `Auth`, `Dashboard`, `Chat` (in `Therapist.tsx`
      for legacy naming), `History`, `Profile`, `Safety`, `MyTherapists`,
      `PatientMessages`, `PatientAccessLog`.
    - Therapist: `TherapistDashboard`, `TherapistProfile`,
      `TherapistMessages`, `TherapistPending`, `PatientView`.
    - Admin: `AdminDashboard`, `AdminProfile`.
    - Shared: `About`, `LearnMore`, `InviteAccept`.
  - `client/src/components/` — Reusable UI (`Navigation`, `VoiceCall`,
    `CrisisCountdownModal`, `AuthWrapper`, `ThemeProvider`, plus subdirs
    `admin/`, `auth/`, `patient/`, `shared/`).
  - `client/src/context/` — React context providers (`AuthContext`).

- `Models/` — ML checkpoints (BERT personality head; RoBERTa suicide head).
  Gitignored.
- `Docs/` — Crisis roadmap, setup guides, research papers, SQL migrations.
- `supabase/` — Supabase config and migrations.
- `tests/`
  - `conftest.py` — Loads `.env` and prepends `src/` to `sys.path` so
    modules that read env vars at import time don't crash.
  - `test_full_system.py` — End-to-end smoke.
  - `test_crisis_detector.py` — Stage-1/2/3 + fusion unit tests.
  - `test_therapist_auth.py` — Portal authorization primitives: SEC-003
    scope-fails-closed, AUTH-002 link-required enforcement, AUTH-003
    homework-update link check.

---

## Development Commands

### Backend
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS
pip install -r requirements.txt

python src/main.py            # API on :5050
python src/voice/agent.py dev # voice worker (separate process)
```

### Frontend
```bash
cd frontend
npm install
npm run dev                   # :5173
npm run build
npm run check                 # TypeScript
```

### Start All Services
```bash
start.bat                     # Windows — local dev (frontend vite on :5173)
vercel.bat                    # Windows — Vercel-deployed frontend; starts ngrok
# ./start.sh                  # Linux / macOS
```

`start.bat` launches backend + local Vite dev server + voice agent. Use it
for pure local development.

`vercel.bat` launches backend + `ngrok` tunnel (pinned to the reserved
static domain) + voice agent. Use it when iterating against the live
frontend on Vercel — the deployed site proxies `/api/*` through the
tunnel to your laptop's backend. See [Deployment](#deployment) below.

### Testing
```bash
pytest tests/
pytest tests/test_crisis_detector.py
pytest tests/test_therapist_auth.py
pytest tests/test_full_system.py
```

---

## Environment Setup

Required environment variables (`.env` in project root):

- `SUPABASE_URL`, `SUPABASE_KEY`
- `SESSION_SECRET` *(fail-fast on missing)*
- `PINECONE_API_KEY`, `PINECONE_ENVIRONMENT`, `PINECONE_INDEX_NAME`
  *(default `3am-talks-rag`)*
- **LLM endpoints** — OpenAI-compatible `/v1/chat/completions` shape.
  Resolved by `src/ai_layer/llm_client.py` in priority order:
  - `LLM_PRIMARY_URL` / `LLM_PRIMARY_API_KEY` — primary (e.g. Ollama on
    a LAN peer or Tailscale). Key defaults to `ollama` when unset.
  - `LLM_FALLBACK_URL` / `LLM_FALLBACK_API_KEY` — used when primary is
    unreachable. Falls back further to `COLAB_API_URL` / `COLAB_API_KEY`
    if these are absent, so existing deployments keep working.
  - At least one of `LLM_PRIMARY_URL` or `COLAB_API_URL` must be set.
  Failover triggers on connection errors and 5xx only — read timeouts
  are not retried, so caller time budgets (e.g. the 8 s crisis arbiter)
  are respected.
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `ELEVEN_API_KEY` — powers ElevenLabs STT and primary TTS. If unset, the
  voice agent skips ElevenLabs entirely and uses Edge TTS alone. If set,
  ElevenLabs TTS is wrapped in `livekit.agents.tts.FallbackAdapter` with
  Edge TTS as the fallback, so exhausted credits / auth errors / 5xx
  transparently fail over mid-session.
- `VOICE_AGENT_SECRET` — HMAC shared secret between backend and voice agent

Optional:

- `CRISIS_ARBITER_MODEL` — model name for the arbiter (default `psychocounsel`)
- `ROBERTA_REMOTE_URL` — if set, RoBERTa is scored over HTTP instead of
  loaded locally
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` —
  crisis alert dispatch
- `FRONTEND_URL` — absolute URL of the deployed frontend (default
  `http://localhost:5173`). Used for the OAuth success redirect in
  `src/routes/auth.py`. Set to the Vercel URL in production so Google /
  Facebook sign-in doesn't bounce users back to localhost.
- `ELEVEN_VOICE_ID` — override the ElevenLabs TTS voice (default Rachel,
  `l7kNoIfnJKPg7779LI2t`).
- `EDGE_TTS_VOICE` — override the Edge TTS fallback voice (default
  `en-US-JennyNeural`).

---

## Prerequisites

1. **LiveKit server** for voice agent:
   - Windows: run `livekit-server.exe` from `livekit-server/`.
   - Or use LiveKit Cloud.
2. **Local RoBERTa checkpoint** at
   `Models/roberta-base-suicide-prediction-phr/` *or* `ROBERTA_REMOTE_URL`
   pointing at a `/classify` endpoint. Without either, the RoBERTa stage
   returns `0.0` and the pipeline falls back to keyword + LLM arbiter only.

---

## Deployment

The frontend is deployed on **Vercel** (Hobby plan, free). The backend
runs on a developer's laptop and is exposed through an **ngrok** tunnel;
Vercel rewrites `/api/*` to the tunnel host. There is no paid hosting
in the loop.

- Vercel project: `abdullahfarid1s-projects/frontend`, root directory
  `frontend/`, framework auto-detected as Vite.
- Stable production URL: `https://frontend-ten-rho-38.vercel.app`.
- ngrok reserved domain: `earache-procurer-console.ngrok-free.dev`
  (pinned via `ngrok http --domain=... 5050` so `vercel.json`'s rewrite
  doesn't change across restarts).
- `frontend/vercel.json` owns two rewrites:
  1. `/api/:path*` → `https://<ngrok-domain>/api/:path*` (backend proxy).
  2. `/((?!api/).*)` → `/index.html` (SPA fallback).

### Deploy a new frontend build
```bash
cd frontend
vercel deploy --prod --yes     # uploads local files; requires `vercel login` once
```

### Run the backend for the deployed frontend
```bash
vercel.bat                     # backend + ngrok (static domain) + voice agent
```

### Notes for future edits
- Because the browser only sees the Vercel origin (the ngrok host is
  hidden behind the rewrite), `CORSMiddleware` in `src/main.py` does
  **not** need the Vercel origin added, and session cookies stay
  `SameSite=Lax` / non-secure. Preserve that invariant — if you ever
  replace the rewrite with direct cross-origin calls, you must also
  allowlist the Vercel origin *and* flip cookies to `SameSite=None;
  Secure`.
- Vercel Hobby-plan rewrites impose a ~30 s response timeout. Keep
  `/api/chat` end-to-end under that when the LLM is slow or the browser
  sees a 504 despite the backend still working.
- Add `FRONTEND_URL=https://frontend-ten-rho-38.vercel.app` and the same
  URL plus `/auth/oauth-success` to Supabase → Authentication → Redirect
  URLs, otherwise OAuth success will bounce to localhost.

---

## API Endpoints

Backend API runs on `localhost:5050`.

### Core
- `/api/health` — Health check.
- `/api/register`, `/api/login`, `/api/logout` — Authentication.
- `/api/auth/social`, `/api/auth/oauth/{provider}/start`,
  `/api/auth/oauth/session` — OAuth flows.
- `/api/user` — Get current user.
- `/api/account/email`, `/api/account/password`, `DELETE /api/account`.
- `/api/chat` — Main conversation endpoint. Runs the therapy LLM and
  crisis detector in parallel. On HIGH/CRITICAL the response contains a
  `crisis` field with `risk_level`, `event_id`, and (CRITICAL + consent)
  a `countdown` object.
- `/api/conversations`, `/api/conversations/active`,
  `/api/conversations/{id}/messages` — Paginated via `_parse_pagination`.
- `/api/data/{table}` — Generic CRUD for Supabase tables.
- `/api/livekit/token` — LiveKit room token generation.
- `/api/voice/bootstrap`, `/api/voice/chat` — Voice session endpoints.
  HMAC-verified with `VOICE_AGENT_SECRET`. `/api/voice/chat` also emits
  the `crisis` field; the voice agent forwards it over the LiveKit data
  channel as `{"type": "crisis.countdown.start", ...}`.

### Admin (`src/routes/admin.py`)
- `/api/admin/overview`, `/api/admin/analytics` — Dashboard stats.
- `/api/admin/users` — Paginated user list (up to 500 per page).
- `/api/admin/reports`, `/api/admin/feedback` — Content moderation.
- `/api/admin/therapists/queue` — Therapist verification queue.
- `/api/admin/announcements` — System announcements.
- `/api/admin/logs` — Audit logs.

### Therapist Portal (`src/routes/therapist.py` — `router`)
- `/api/therapist/register`, `/api/therapist/me` — Therapist profile.
- `/api/therapist/patients` — Patient list and details.
- `/api/therapist/notes`, `/api/therapist/treatment-plans`,
  `/api/therapist/homework` — Clinical tools.
- `/api/therapist/messages` — Therapist ↔ patient messaging.
- `/api/therapist/crisis` — Crisis event management.
- `/api/reports`, `/api/feedback` — Reports and feedback.

### Patient / Shared (`src/routes/therapist.py` — `shared_router`)
- `/api/patient/homework` — Patient-visible homework list.
- `/api/invite-therapist` — Patient invites a therapist.
- `/api/therapist/invite-patient` — Therapist invites a patient.
- `/api/links`, `/api/links/pending` — Link listing.
- `/api/links/{id}/accept|decline|confirm-consent|revoke`.
- `/api/invite/info`, `/api/invite/accept` — Invitation token handling.

### Crisis System (`src/routes/crisis.py`)
- `/api/v1/crisis/settings` — User crisis preferences.
- `/api/v1/crisis/contacts` — Emergency contact CRUD.
- `/api/v1/crisis/location` — Location for nearest-helpline lookup.
- `/api/v1/crisis/events` — Crisis event history.
- `/api/v1/crisis/cancel-alert`, `/api/v1/crisis/test-alert`.

---

## Crisis Detection Pipeline

The entry point for both `/api/chat` and `/api/voice/chat` is
`process_message_with_crisis()` in `src/crisis/integration.py`. It runs two
coroutines concurrently:

1. `mgr.process_message(...)` — the normal therapy reply (LLM + RAG).
2. `detect_and_maybe_alert(...)` — the safety pipeline.

### Detector stages (`crisis.service.detect_crisis`)

1. **Stage 1 — `keyword_scan`** (&lt;10 ms).
   - Tiered regex dictionaries: `CRITICAL_PHRASES`, `HIGH_PHRASES`,
     `MEDIUM_PHRASES`.
   - Contextual modifiers (`tonight`, `pills`, `bridge`, `plan`, etc.)
     bump tier by one.
2. **Stage 1.5 — RoBERTa suicide probability** (`roberta_client.score`).
   - Gates: `_ROBERTA_GATE=0.35`, `_ROBERTA_MID=0.60`, `_ROBERTA_HIGH=0.85`.
   - Skipped entirely when the caller passes `use_llm=False` and no
     `roberta_score` (keyword-only mode — e.g. unit tests) to avoid
     flagging benign phrases like "goodbye ella".
3. **Stage 2 — LLM arbiter** (`llm_arbitrate`).
   - Called only when tier ≠ `none`, RoBERTa ≥ gate, or the session has
     a prior HIGH/CRITICAL event.
   - Two prompt templates: `_LLM_ARBITER_USER_TEMPLATE` (no history) and
     `_LLM_ARBITER_CONTEXT_TEMPLATE` (with up to the last 10 turns). The
     context template adds explicit escalation rules so calm-resignation
     after prior ideation is treated as a severity signal, not
     reassurance.
   - If the LLM is unreachable → `available=False`; the fuser falls back
     conservatively.

### Fusion (`_fuse`)
- Keyword CRITICAL → CRITICAL (unless LLM clearly says hyperbole or
  third-party and no intent, in which case → HIGH).
- Keyword HIGH + LLM `intent` + imminence ≥ medium → CRITICAL.
- Keyword NONE + `session_has_prior_risk` + LLM `intent`/`escalating` →
  HIGH or CRITICAL. This "sticky session" rule closes the dominant
  false-negative class (calm resignation after prior ideation), measured
  on 132 labeled real messages.
- LLM unreachable + keyword CRITICAL → still CRITICAL (over-alert safer).

### After detection
`detect_and_maybe_alert` only returns a payload when the risk is
HIGH or CRITICAL. For CRITICAL + consent, it:

1. Cancels any lingering countdown.
2. Logs a `crisis_events` row (severity, score, reasoning, trigger text).
3. Starts a new countdown (10–120 s, configurable per user).
4. Schedules `run_countdown_and_fire` as a background task.

The frontend receives the `crisis` field on the chat response and opens
`CrisisCountdownModal`. For voice, `src/voice/agent.py` republishes the
same payload on the LiveKit data channel so the browser modal opens
alongside the spoken response.

---

## Code Conventions

### Backend (Python)
- `python-dotenv` for environment loading; `conftest.py` ensures tests
  see the same `.env`.
- Pydantic models for request / response validation.
- Lazy initialization pattern for `ConversationManager`
  (`get_manager()` in `src/core/helpers.py`).
- Route modules expose an `APIRouter` named `router`; where patient and
  therapist share endpoints, a second `shared_router` lives in the same
  module (see `src/routes/therapist.py`) and is registered separately in
  `src/main.py`.
- `_parse_pagination(request, default_limit, max_limit)` is the canonical
  way to read `?limit=`/`?offset=` from any list endpoint.
- Thread-safe lazy singletons use double-checked locking with a module
  `threading.Lock` (see `src/crisis/alert.py`).
- Logging with the standard `logging` module; each subsystem uses a
  named logger (`3am-chat`, `3am-voice`, `ella-voice`, etc.).

### Frontend (TypeScript / React)
- Uses `@/` path alias for `client/src/`.
- Radix UI components with Tailwind CSS.
- React Router for routing.
- TanStack Query for server state.
- `AuthContext` wraps the entire app; `AuthWrapper` handles
  role-based redirects and supports nested patient paths (e.g.
  `/my-therapists/messages`) via prefix matching.
- Role-based pages:
  - Patient: `Dashboard`, `History`, `Profile`, `Safety`, `MyTherapists`,
    `PatientMessages`, `PatientAccessLog`.
  - Therapist: `TherapistDashboard`, `PatientView`, `TherapistMessages`,
    `TherapistPending`, `TherapistProfile`.
  - Admin: `AdminDashboard`, `AdminProfile`.
- `therapistFetchJson` is used for every portal endpoint so error shapes
  and auth headers stay consistent.

---

## Database Schema

Supabase stores:

- `user_profiles` (personality traits, preferences, roles).
- `conversations` (session history).
- `messages` (individual chat messages).
- `therapist_profiles` and verification records.
- `patient_therapist_links` (status + `consent_scope` JSON).
- `clinical_notes`, `treatment_plans`, `patient_homework`.
- `secure_messages` (therapist ↔ patient threads).
- `crisis_events`, `crisis_countdowns`, `crisis_safety_settings`,
  `emergency_contacts`.
- `clinical_access_logs` — every therapist read of patient data; surfaced
  to the patient at `/my-therapists/access-log`.
- `reports`, `feedback`, `announcements`, `audit_logs`.

Performance indexes live in
`supabase/migrations/20260417050000_performance_indexes.sql`. When adding
indexes here, double-check the column names exist on the target tables
(`conversations.started_at`, `clinical_access_logs.created_at`, etc.).
