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
- Real-time voice conversations via LiveKit (Ella voice agent).
- **Three-stage** crisis detection (keyword → RoBERTa → LLM arbiter) shared
  between text and voice, with WhatsApp / SMS emergency alerts via Twilio.
- Therapist portal with patient management, clinical notes, treatment plans,
  homework, secure messaging, and a patient-visible access log.
- Admin dashboard with user management, analytics, reports, announcements,
  and audit logs.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│            Frontend (React 18 + Vite, TypeScript)                │
│                     localhost:5173                               │
│   Roles: Patient, Therapist, Admin                              │
│   Root: frontend/client/src/ (Vite root = frontend/client)      │
│   @/ alias → frontend/client/src/                               │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / WebSocket / LiveKit WS
                             │ (Vite dev proxy /api → 127.0.0.1:5050)
┌────────────────────────────▼────────────────────────────────────┐
│                  Backend (FastAPI, port 5050)                    │
│                                                                  │
│   src/main.py                 - App entry, middleware, routers   │
│   src/config.py               - Config class (fail-fast)         │
│   src/core/                   - Sessions, auth guards, rate lim. │
│   src/routes/*.py             - HTTP route modules               │
│   src/conversation/manager.py - Session orchestration            │
│   src/conversation/summary.py - Conversation summarization       │
│   src/conversation/questionnaire.py - Personality quiz           │
│   src/crisis/service.py       - Keyword + RoBERTa + LLM fusion   │
│   src/crisis/integration.py   - Shared pipeline for chat+voice   │
│   src/crisis/roberta_client.py- Local/remote suicide-prob model  │
│   src/crisis/alert.py         - Twilio notifiers + countdown     │
│   src/crisis/data/helplines.json - Locale helpline directory     │
│   src/ai_layer/llm_service.py - Colab OpenAI-compatible client   │
│   src/ai_layer/personality_service.py - BERT personality head    │
│   src/rag_layer/rag_service.py - Pinecone retrieval              │
│   src/rag_layer/pinecone_engine.py - Pinecone inference search   │
│   src/database/supabase_client.py - Supabase REST wrapper        │
│   src/database/user_service.py - Profile/stats/mood CRUD         │
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
│   Pipeline: Silero VAD → ElevenLabs STT → backend → TTS         │
│   src/voice/tts_plugin.py — Edge TTS fallback plugin            │
│   Crisis events from /api/voice/chat are re-published to the    │
│   LiveKit data channel so the frontend CrisisCountdownModal     │
│   opens alongside the TTS reply.                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Repository Layout (Top-Level)

```
ella-speaks-calmly/
├── CLAUDE.md               # This file.
├── README.md
├── requirements.txt        # Python deps
├── techniques.json         # Seed data for RAG (therapeutic techniques)
├── start.bat / start.sh    # Dev launchers (Windows / POSIX)
├── src/                    # FastAPI backend (see below)
├── frontend/               # React + Vite frontend
│   ├── client/src/         # Actual app source; Vite `root` is frontend/client
│   ├── package.json, vite.config.ts, tailwind.config.ts,
│   │   tsconfig.json, postcss.config.js, components.json
│   └── vercel.json         # Vercel deploy config (SPA rewrite)
├── Models/                 # ML checkpoints (gitignored payloads)
│   ├── bert-base-personality/  # Personality head
│   └── psychocounsel/          # Local Llama-3-8B GGUF + Ollama Modelfile
├── Docs/                   # SDP, SRS, research papers (LLM4CBT, PsyCoT)
└── livekit-server/         # Bundled LiveKit server binary (Windows .exe)
```

> There is **no** `tests/` directory and **no** `supabase/` migrations
> directory in this repo at the moment. If you add tests, create `tests/`
> at the project root and include a `conftest.py` that prepends `src/` to
> `sys.path` (modules read env vars at import time).

---

## Backend Layout (`src/`)

### Entry point — `src/main.py`
- FastAPI app on **port 5050** (`uvicorn.run` in `__main__`).
- Lifespan eagerly preloads `ConversationManager` so missing BERT / Colab /
  Pinecone / Supabase credentials fail fast on boot.
- CORS middleware allows `localhost:5173`, `127.0.0.1:5173`, and the
  backend's own origins; `allow_credentials=True`.
- `slowapi` rate-limit exception handler wired.
- Custom middleware `agent_log_unmatched_api` logs unmatched `/api*` 404s
  to `debug-a2dded.log`.
- Registers routers: `auth_router`, `chat_router`, `user_router`,
  `admin_router`, `crisis_router`, `therapist_router`,
  `therapist_shared_router`, `therapist_public_router`, `voice_router`,
  `data_router`.

### `src/config.py` — centralized runtime config
Reads env vars and exposes a `Config` class. Notable fields:
- `SUPABASE_URL`, `SUPABASE_KEY`
- `SESSION_SECRET` — **raises `RuntimeError` on boot if missing**
- `PINECONE_API_KEY`, `PINECONE_ENVIRONMENT`, `PINECONE_INDEX_NAME`
  (default `3am-talks-rag`)
- `COLAB_API_URL`, `COLAB_API_KEY`
- `ENVIRONMENT` — `development` / `production`
- `CONVERSATION_PERSISTENCE_MODE` — `immediate` (sync write) or
  `buffered` (async batching, default)
- `CONVERSATION_FLUSH_INTERVAL_SECONDS` (default 20)
- `CONVERSATION_FLUSH_TURN_THRESHOLD` (default 2)

### `src/core/` — shared infrastructure
- **`sessions.py`** — Cookie signing (`TimestampSigner`), in-memory
  `sessions` and `temp_oauth_sessions` dicts, `SESSION_COOKIE`,
  `SESSION_MAX_AGE` (7d), `VOICE_AGENT_SECRET`; functions
  `create_session`, `get_current_user`, `clear_user_sessions`,
  `update_user_sessions`.
- **`helpers.py`** — Auth guards (`require_user`, `require_admin`,
  `require_voice_agent`), DB helpers, `_parse_pagination(request,
  default_limit, max_limit)` (canonical pagination), schema translators
  (`_backend_conversation_to_frontend`, `_backend_message_to_frontend`),
  `_resume_or_start_conversation`, admin-action logging helpers.
- **`rate_limit.py`** — `slowapi` `Limiter` singleton
  (`key_func=get_remote_address`).
- `__init__.py` re-exports the public surface.

### `src/routes/` — HTTP route modules

All paths below are **full paths** (prefix + sub-path).

#### `auth.py`
- `POST /api/register` — rate-limited `10/minute`.
- `POST /api/login` — rate-limited `10/minute`.
- `POST /api/auth/social`, `GET /api/auth/oauth/{provider}/start`,
  `POST /api/auth/oauth/session`, `POST /api/oauth/session`.
- `GET /api/user`, `POST /api/logout`.
- `PATCH /api/account/email`, `PATCH /api/account/password`,
  `DELETE /api/account`.
- The OAuth nonce cookie is deliberately `SameSite=Lax` because it is
  read after a cross-site redirect.

#### `chat.py`
- `POST /api/chat` — rate-limited `30/minute`; runs
  `process_message_with_crisis` (therapy LLM + crisis detector in
  parallel via `asyncio.gather(..., return_exceptions=True)`).
- `GET/POST/PUT/DELETE /api/conversations`,
  `GET /api/conversations/active`,
  `GET /api/conversations/{id}/messages` — paginated via
  `_parse_pagination`.
- `POST /api/end-session`, `POST /api/session/start`,
  `POST /api/session/flush`.
- `GET/POST /api/mood`.
- `POST /api/questionnaire/submit`.

#### `crisis.py` (prefix `/api/crisis`)
- `GET/POST /settings` — user crisis preferences.
- `GET/POST/PUT/DELETE /contacts[/{id}]` — emergency contacts
  (E.164 validation on write).
- `POST /location` — for nearest-helpline lookup.
- `GET /events` — paginated crisis event history.
- `POST /cancel-alert`, `POST /test-alert`.

> The previous revision of this doc called the prefix `/api/v1/crisis`;
> the actual router is mounted under `/api/crisis`.

#### `voice.py` — all endpoints gated by `require_voice_agent` (HMAC via `VOICE_AGENT_SECRET`)
- `POST /api/livekit/token`.
- `POST /api/voice/bootstrap`.
- `POST /api/voice/chat` — emits a `crisis` field; the voice agent
  forwards it over the LiveKit data channel as
  `{"type": "crisis.countdown.start", ...}`.
- `POST /api/voice/end`.

#### `admin.py` (prefix `/api/admin`) — all endpoints `require_admin`
- `GET /overview`, `GET /analytics`, `GET /me`.
- `GET /users` — paginated (default 50, max 500),
  `PATCH /users/{id}/status`, `PATCH /users/{id}/role`,
  `DELETE /users/{id}`.
- `GET/PATCH /reports[/{id}]`, `GET/PATCH /feedback[/{id}]`.
- `GET /therapists/queue`, `PATCH /therapists/{verification_id}`.
- `GET/POST/DELETE /announcements[/{id}]`.
- `GET /logs`.

#### `therapist.py` — **three routers exported**, all registered in `main.py`
- `router` (prefix `/api/therapist`, guard `_require_therapist` + per-patient `_require_link` scope check):
  - `POST /register`, `GET/PATCH /me`, `POST /me/verification`.
  - `GET /patients`, `GET /patients/{id}`,
    `GET /patients/{id}/conversations`,
    `GET /patients/{id}/conversations/{conv_id}`,
    `GET /patients/{id}/mood`, `GET /patients/{id}/journals`,
    `GET /patients/{id}/prep-brief`.
  - `GET/POST/PATCH/DELETE /notes[/{id}]`.
  - `GET/POST/PATCH /treatment-plans[/{id}]`.
  - `GET/POST/PATCH /homework[/{id}]`.
  - `POST /invite-patient`.
- `shared_router` (patient + therapist, guard `require_user` + link scoping):
  - `GET/PATCH /api/patient/homework[/{id}]`,
    `POST /api/invite-therapist`,
    link management endpoints under `/api/links/*`,
    `/api/invite/info`, `/api/invite/accept`.
- `public_router` (no session — password-protected invite tokens):
  - Unauthenticated homework view/patch and invite submission for
    recipients who haven't registered yet.

Splitting by scope keeps the `/api/therapist` prefix strictly
scope-gated without breaking the patient-facing URLs.

#### `data.py`
- Generic CRUD `/api/data/{table}` (GET list, `GET/PATCH/DELETE /{id}`,
  `POST` create) — `require_user`, used by the SPA for conversations,
  messages, profiles, `user_stats`, `mood_entries`.

#### `user.py`
- `GET/PUT /api/profile`, `GET /api/stats`.

### `src/conversation/`
- **`manager.py`** — Main `ConversationManager` orchestrator (lazy
  singleton via `get_manager()` in `core/helpers.py`). Wires
  `LLMService`, `PersonalityService`, `RAGService`, `UserService`.
  Handles the immediate vs buffered persistence modes with a background
  flush worker.
- **`summary.py`** — Conversation summarization with a pooled `httpx`
  client.
- **`questionnaire.py`** — `PersonalityQuestionnaire` system.

### `src/crisis/` — see [Crisis Pipeline](#crisis-detection-pipeline)
- **`service.py`** — Three-stage engine. Also exports the legacy
  `scan_messages(...)` used by therapist SOAP summaries — do not modify
  its signature. Classes: `CrisisResult`, `RiskLevel` enum.
- **`integration.py`** — `process_message_with_crisis()` is the **only**
  integration seam both `/api/chat` and `/api/voice/chat` call.
- **`roberta_client.py`** — Local mode loads
  `Models/roberta-base-suicide-prediction-phr/` (fallback to HF id on
  miss). Remote mode enabled by `ROBERTA_REMOTE_URL`. Never raises —
  failures return `0.0`.
- **`alert.py`** — Twilio WhatsApp/SMS notifiers (thread-safe lazy
  singletons), `start_countdown` / `cancel_active_countdown` /
  `run_countdown_and_fire`. **Consent is re-checked immediately before
  dispatch**, not only at countdown start.
- **`data/helplines.json`** — Static helpline directory used by locale
  lookup.

### `src/ai_layer/`
- **`llm_service.py`** — `LLMService`; model `psychocounsel` against
  `COLAB_API_URL`. Holds the Ella system persona and
  `_construct_prompt(patient_utterance, context_updates)` which merges
  RAG + personality context.
- **`personality_service.py`** — BERT-based personality detection
  (loads `Models/bert-base-personality/`).

### `src/rag_layer/`
- **`rag_service.py`** — `RAGService`; Pinecone index
  `3am-talks-rag`, namespace `default`, `top_k=3`. Key methods
  `retrieve_relevant_techniques(query, issue_tags, difficulty)` and
  `format_techniques_for_prompt(techniques)`.
- **`pinecone_engine.py`** — Pinecone inference-based search.

### `src/database/`
- **`supabase_client.py`** — `SupabaseClient` REST wrapper over `httpx`
  (timeout 60s, 3 retries). Methods `select`, `insert`, `update`,
  `delete`; helper `normalize_postgrest_value` strips `eq.` prefixes.
- **`user_service.py`** — `UserService` wraps the client for profile,
  stats, mood entries, conversation history.

### `src/voice/`
- **`agent.py`** — `Ella` class extending the LiveKit `Agent`. The
  `llm_node()` method routes to the backend (via HMAC'd
  `/api/voice/chat`) instead of a local LLM, so persona / RAG / history
  stay canonical in the backend. Launches via
  `python src/voice/agent.py dev`; `agent.py` prepends `src/` to
  `sys.path` so imports like `from voice.tts_plugin import TTS` resolve.
- **`tts_plugin.py`** — Edge TTS plugin (fallback to ElevenLabs).

---

## Frontend Layout (`frontend/`)

Vite `root` is `frontend/client`, alias `@/` → `frontend/client/src/`,
`envDir` is `frontend/..` so `.env` at the project root is shared with
the backend. Dev server on **5173** proxies `/api` → `127.0.0.1:5050`.

### `frontend/client/src/`
- **`App.tsx`** — Route table; `AuthWrapper` wraps all routes and
  enforces role-based redirects.
- **`main.tsx`** — React root.
- **`context/AuthContext.tsx`** — Current-user + role state for the SPA.
- **`hooks/`** — `useAuth`, `useConversations`, `useMoodEntries`,
  `useProfile`, `useSessionTracker` (invoked once in `App.tsx`),
  `useUserStats`, `useVoiceCall`, plus `use-mobile` and `use-toast`.
- **`lib/`** — `therapistFetch.ts` (canonical `therapistFetchJson` used
  by every portal endpoint so error shapes and auth headers stay
  consistent), `crisisApi.ts`, `supabaseBrowser.ts`, `utils.ts`.
- **`pages/`** — Landing, Auth, OAuthSuccess, Questionnaire,
  NotFound, About, LearnMore, InviteAccept.
  - Patient: `Dashboard`, `Therapist` (the chat page — file name is
    `Therapist.tsx` for legacy reasons; mounted at `/chat` **and**
    `/therapist`), `History`, `Profile`, `Safety`, `MyTherapists`,
    `PatientMessages`, `PatientAccessLog`.
  - Therapist portal: `TherapistDashboard`, `TherapistProfile`,
    `TherapistMessages`, `TherapistPending`, `PatientView`.
  - Admin: `AdminDashboard`, `AdminProfile`.
- **`components/`** — Top-level: `Navigation`, `VoiceCall`,
  `CrisisCountdownModal`, `AuthWrapper`, `ThemeProvider`,
  `PersonalityTraits`. Subdirs:
  - `admin/` — `ConfirmActionDialog`.
  - `auth/` — `BackgroundDecor`, `LoginCard`, `QuickSupport`.
  - `patient/` — `HomeworkCard`.
  - `shared/` — `ConsentPrimer`.
  - `ui/` — shadcn/Radix UI primitives.

### Routing (`App.tsx`)
```
/                         → Landing
/auth, /auth/therapist    → Auth
/auth/oauth-success       → OAuthSuccess
/questionnaire            → Questionnaire
/dashboard                → Dashboard             (patient)
/chat, /therapist         → Therapist (chat page) (patient)
/history                  → History               (patient)
/profile                  → Profile               (patient)
/my-therapists            → MyTherapists
/my-therapists/messages   → PatientMessages
/my-therapists/access-log → PatientAccessLog
/safety                   → Safety
/admin                    → AdminDashboard
/admin/profile            → AdminProfile
/therapist-portal(/clients|/pending|/profile|/messages|/patients/:id)
                          → therapist portal pages
/about, /learn-more       → About, LearnMore
/invite/accept            → InviteAccept
*                         → NotFound
```

### Build & deploy
- `npm run dev` / `npm run build` / `npm run check` (TypeScript).
- Stack: React 18, React Router 7, TanStack Query 5, Radix UI,
  Tailwind CSS, framer-motion, `@livekit/components-react`,
  `livekit-client`, `@supabase/supabase-js`, Zod, react-hook-form,
  recharts.
- **`frontend/vercel.json`** — `framework: "vite"`,
  `outputDirectory: "dist"`, SPA rewrite
  `"/((?!api/).*)" → "/index.html"`.

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
start.bat     # Windows — opens backend, frontend, voice agent in 3 windows
./start.sh    # POSIX — backend + frontend, traps SIGINT to clean up
```

### Testing
No test suite is currently committed. When adding tests, create
`tests/conftest.py` that loads `.env` and prepends `src/` to
`sys.path` (import-time env reads will fail otherwise).

---

## Environment Setup

Required environment variables (`.env` in project root — the frontend's
Vite config uses `envDir: ..` so the same file is shared):

- `SUPABASE_URL`, `SUPABASE_KEY`
- `SESSION_SECRET` *(fail-fast on missing)*
- `PINECONE_API_KEY`, `PINECONE_ENVIRONMENT`, `PINECONE_INDEX_NAME`
  *(default `3am-talks-rag`)*
- `COLAB_API_URL` — OpenAI-compatible LLM endpoint (also used by the
  crisis arbiter)
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `ELEVEN_API_KEY`
- `VOICE_AGENT_SECRET` — HMAC shared secret between backend and voice agent

Optional:

- `COLAB_API_KEY` — auth header for Colab (defaults to `EMPTY`)
- `CRISIS_ARBITER_MODEL` — model name for the arbiter (default
  `psychocounsel`)
- `ROBERTA_REMOTE_URL` — if set, RoBERTa is scored over HTTP instead of
  loaded locally
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` —
  crisis alert dispatch
- `CONVERSATION_PERSISTENCE_MODE`,
  `CONVERSATION_FLUSH_INTERVAL_SECONDS`,
  `CONVERSATION_FLUSH_TURN_THRESHOLD`

---

## Prerequisites

1. **LiveKit server** for the voice agent:
   - Windows: run `livekit-server.exe` from `livekit-server/`.
   - Or use LiveKit Cloud.
2. **Local personality checkpoint** at `Models/bert-base-personality/`.
   The `Models/psychocounsel/` folder holds the Llama-3-8B GGUF used
   by the local Ollama variant of the arbiter (optional — Colab works
   without it).
3. **RoBERTa suicide head** at
   `Models/roberta-base-suicide-prediction-phr/` *or* `ROBERTA_REMOTE_URL`
   pointing at a `/classify` endpoint. Without either, the RoBERTa
   stage returns `0.0` and the pipeline falls back to keyword + LLM
   arbiter only.

---

## Crisis Detection Pipeline

The entry point for both `/api/chat` and `/api/voice/chat` is
`process_message_with_crisis()` in `src/crisis/integration.py`. It runs
two coroutines concurrently:

1. `mgr.process_message(...)` — the normal therapy reply (LLM + RAG).
2. `detect_and_maybe_alert(...)` — the safety pipeline.

### Detector stages (`crisis.service.detect_crisis`)

1. **Stage 1 — `keyword_scan`** (<10 ms).
   - Tiered regex dictionaries: `CRITICAL_PHRASES`, `HIGH_PHRASES`,
     `MEDIUM_PHRASES`.
   - Contextual modifiers (`tonight`, `pills`, `bridge`, `plan`, etc.)
     bump tier by one.
2. **Stage 1.5 — RoBERTa suicide probability** (`roberta_client.score`).
   - Gates: `_ROBERTA_GATE=0.35`, `_ROBERTA_MID=0.60`,
     `_ROBERTA_HIGH=0.85`.
   - Skipped entirely when the caller passes `use_llm=False` and no
     `roberta_score` (keyword-only mode — e.g. unit tests) to avoid
     flagging benign phrases like "goodbye ella".
3. **Stage 2 — LLM arbiter** (`llm_arbitrate`).
   - Called only when tier ≠ `none`, RoBERTa ≥ gate, or the session has
     a prior HIGH/CRITICAL event.
   - Two prompt templates: `_LLM_ARBITER_USER_TEMPLATE` (no history) and
     `_LLM_ARBITER_CONTEXT_TEMPLATE` (with up to the last 10 turns).
     The context template adds explicit escalation rules so
     calm-resignation after prior ideation is treated as a severity
     signal, not reassurance.
   - If the LLM is unreachable → `available=False`; the fuser falls
     back conservatively.

### Fusion (`_fuse`)
- Keyword CRITICAL → CRITICAL (unless LLM clearly says hyperbole or
  third-party and no intent, in which case → HIGH).
- Keyword HIGH + LLM `intent` + imminence ≥ medium → CRITICAL.
- Keyword NONE + `session_has_prior_risk` + LLM `intent`/`escalating` →
  HIGH or CRITICAL. This "sticky session" rule closes the dominant
  false-negative class (calm resignation after prior ideation).
- LLM unreachable + keyword CRITICAL → still CRITICAL (over-alert
  safer).

### After detection
`detect_and_maybe_alert` only returns a payload when risk is HIGH or
CRITICAL. For CRITICAL + consent, it:

1. Cancels any lingering countdown.
2. Logs a `crisis_events` row (severity, score, reasoning, trigger
   text).
3. Starts a new countdown (10–120 s, configurable per user).
4. Schedules `run_countdown_and_fire` as a background task.

The frontend receives the `crisis` field on the chat response and opens
`CrisisCountdownModal`. For voice, `src/voice/agent.py` republishes the
same payload on the LiveKit data channel so the browser modal opens
alongside the spoken response.

---

## Code Conventions

### Backend (Python)
- `python-dotenv` for environment loading.
- Pydantic models for request / response validation.
- Lazy initialization pattern for `ConversationManager`
  (`get_manager()` in `src/core/helpers.py`).
- Route modules expose an `APIRouter` named `router`; where patient and
  therapist share endpoints, additional routers (`shared_router`,
  `public_router`) live in the same module (see `src/routes/therapist.py`)
  and are registered separately in `src/main.py`.
- `_parse_pagination(request, default_limit, max_limit)` is the
  canonical way to read `?limit=`/`?offset=` from any list endpoint.
- Thread-safe lazy singletons use double-checked locking with a module
  `threading.Lock` (see `src/crisis/alert.py`).
- Logging with the standard `logging` module; each subsystem uses a
  named logger (`3am-chat`, `3am-voice`, `ella-voice`, etc.).

### Frontend (TypeScript / React)
- `@/` path alias for `frontend/client/src/`.
- Radix UI primitives (shadcn style) + Tailwind CSS.
- React Router 7 for routing, TanStack Query 5 for server state.
- `AuthContext` wraps the entire app; `AuthWrapper` enforces
  role-based redirects and supports nested patient paths (e.g.
  `/my-therapists/messages`) via prefix matching.
- `therapistFetchJson` (in `lib/therapistFetch.ts`) is used for every
  portal endpoint so error shapes and auth headers stay consistent.
- `useSessionTracker` is invoked once at `App` level to keep the
  session alive / log presence.

---

## Database Schema (Supabase — no local migrations folder)

Tables the backend expects to exist:

- `user_profiles` (personality traits, preferences, roles).
- `conversations`, `messages`.
- `therapist_profiles` and verification records.
- `patient_therapist_links` (status + `consent_scope` JSON).
- `clinical_notes`, `treatment_plans`, `patient_homework`.
- `secure_messages` (therapist ↔ patient threads).
- `crisis_events`, `crisis_countdowns`, `crisis_safety_settings`,
  `emergency_contacts`.
- `clinical_access_logs` — every therapist read of patient data;
  surfaced to the patient at `/my-therapists/access-log`.
- `reports`, `feedback`, `announcements`, `audit_logs`.
- `mood_entries`, `user_stats`.

Schema changes are managed directly in the hosted Supabase project —
there is no `supabase/` folder committed here. If migrations are added
in the future, put them under `supabase/migrations/` and reference them
in this file.
