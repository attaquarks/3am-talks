# Crisis Detection & Emergency Alert System — Roadmap

Living document. Update at end of each session. Source of truth for what's
done and what's next.

## Architecture decisions (locked)

- **Detection:** two-stage — keyword regex (fast gate, high recall) → existing
  Colab LLM arbiter (kills false positives like "exam is killing me"). No
  `facebook/bart-large-mnli`, no torch/transformers dependency.
- **Alerts:** Twilio WhatsApp sandbox as primary channel (PK delivery is
  reliable, free for opted-in numbers). SMS as fallback when/if a production
  sender ID is approved.
- **Consent:** off by default. Two independent checkboxes (alerts + location).
  Exact consent string stored in `crisis_safety_settings.consent_text_shown`.
- **Safety ladder:**
  - `HIGH` / `CRITICAL` → always show pre-scripted crisis response + helplines
    (never LLM-generated). Bypasses RAG.
  - `CRITICAL` only → 30s cancellable countdown → notify contacts.
  - Keyword CRITICAL + LLM unreachable → **fail to CRITICAL** (safe default).
  - LLM says "hyperbole" on a keyword hit → log silently, no user disruption.
- **Auth:** FastAPI-enforced with Supabase service key (no RLS — matches
  therapist_portal convention).
- **Storage:** extend existing `public.crisis_events` (therapist_portal
  migration) rather than creating a parallel table. Add `emergency_contacts`,
  `crisis_safety_settings`, `crisis_countdowns`.

## Progress

### ✅ Session 1 (2026-04-16) — Step 1 complete

- **Migration:** `supabase/migrations/20260416130000_crisis_alert_system.sql`
  - New: `emergency_contacts` (E.164 phone check, whatsapp/sms/both channel)
  - New: `crisis_safety_settings` (consent + countdown config + country)
  - New: `crisis_countdowns` (active-countdown tracker, cancellable)
  - Extended `crisis_events` with: `session_id`, `severity_score`,
    `trigger_text`, `keyword_matches`, `ml_scores`, `emergency_alerts_sent`,
    `contacts_notified`, `user_location`, `intervention_type`,
    `trigger_text_purge_at`
- Roadmap doc created.

### ✅ Session 2 (2026-04-16) — Detection core + routes + integration

- Extended `src/crisis_service.py`:
  - `RiskLevel` enum (LOW/MEDIUM/HIGH/CRITICAL)
  - `CrisisResult` dataclass with `to_dict()`, `requires_intervention`,
    `requires_emergency_alert`
  - Tiered keyword dicts (CRITICAL / HIGH / MEDIUM / CONTEXTUAL_MODIFIERS)
    compiled to regex — p95 scan <10ms verified by tests
  - `detect_crisis(text, use_llm=True)` — full two-stage pipeline
  - `llm_arbitrate()` — Colab LLM classifier; fails-safe to keyword tier
    (CRITICAL keyword + LLM unreachable → stays CRITICAL)
  - `crisis_response(country_code, alerts_being_sent)` — pre-scripted PK text
  - Existing `scan_messages()` kept untouched (SOAP summary callers work)
- Created `src/emergency_alert.py`:
  - `Notifier` protocol + `TwilioWhatsAppNotifier` + `TwilioSMSNotifier`
    (both graceful no-op when env unset)
  - `compose_alert_body(...)` — WhatsApp-formatted safety alert (PK copy
    with optional location link)
  - `start_countdown`, `cancel_active_countdown`, `run_countdown_and_fire`,
    `fire_alerts`, `log_crisis_event`
- Created `src/crisis_routes.py` + `register_crisis_routes(app)`:
  - `GET/POST /api/v1/crisis/settings`
  - `GET/POST/PUT/DELETE /api/v1/crisis/contacts[/{id}]`
  - `POST /api/v1/crisis/cancel-alert`
  - `GET /api/v1/crisis/events`
  - `POST /api/v1/crisis/test-alert`
  - `POST /api/v1/crisis/location` (bonus — only stores if consented)
- Mounted router in `src/api.py` under the therapist routes block.
- Hooked detection into `/api/chat`: HIGH/CRITICAL bypasses RAG with
  pre-scripted response; CRITICAL + consent launches countdown as
  background task; MEDIUM appends helpline tail to the normal reply.
- Created `src/data/helplines.json` (PK/US/GB).
- `tests/test_crisis_detector.py` — 28 tests, all passing.
- `Docs/CRISIS_SETUP.md` — Twilio sandbox walkthrough + full curl test plan.
- `requirements.txt` — added `twilio>=9.0.0`.

**Tests:** 28/28 pass. Keyword layer p95 <10ms. No LLM calls in tests.

### ✅ Session 3 (2026-04-16) — End-to-end live test PASSED

Twilio WhatsApp sandbox + Colab LLM both live. Test contact "Mr. Chu Teeya"
(`+923344117908`, whatsapp channel) opted into sandbox. All four success
criteria met:

1. **Test alert path** — `POST /api/v1/crisis/test-alert` →
   `intervention_type=alerts_sent`, `emergency_alerts_sent=true`,
   `contacts_notified=["S***(whatsapp)"]`. WhatsApp delivery confirmed by
   user.
2. **Real CRITICAL chat path** — explicit suicidal-intent message →
   detection HIGH/CRITICAL → countdown started → 30s elapsed → alert
   dispatched (`event cba673a6...`, `emergency_alerts_sent=true`).
3. **Cancel mid-countdown** — CRITICAL message then
   `POST /api/v1/crisis/cancel-alert` within 30s → event recorded as
   `intervention_type=user_cancelled`, `emergency_alerts_sent=false`,
   `contacts_notified=[]` (event `16e95e25...`). No WhatsApp sent.
4. **Hyperbole suppression** — `"ugh i want to die these exams are killing
   me lol"` → keyword tier CRITICAL but **LLM arbiter downgraded to HIGH**
   → `countdown=null`, `alerts_being_sent=false`. Pre-scripted response +
   helplines still shown (safe), but no contact notification (no false
   positive).

Module-duplication issue resolved by switching `register_crisis_routes` to
explicit dependency injection: caller passes `require_user_fn=require_user`
so the router shares the exact same `sessions` dict as `src/api.py`.

### ⏳ Remaining

**Session 2 — Detection core + routes** ← DONE
**Session 3 — End-to-end live test** ← DONE
1. Extend `src/crisis_service.py`:
   - Add `RiskLevel` enum (LOW / MEDIUM / HIGH / CRITICAL)
   - Add `CrisisResult` dataclass (risk_level, severity_score,
     keyword_matches, ml_scores, requires_intervention,
     requires_emergency_alert, timestamp)
   - Add tiered keyword dicts (critical / high / medium / contextual
     modifiers) per the original plan's phrase lists
   - Add `detect_crisis(text: str) -> CrisisResult` — runs keyword layer
     then calls LLM arbiter via existing Colab client
   - Keep the existing `scan_messages()` function for therapist SOAP
     summaries (don't break that)
2. `src/services/emergency_alert.py`:
   - `Notifier` interface with `TwilioWhatsAppNotifier` impl (graceful
     no-op if `TWILIO_*` envs missing — logs a warning)
   - `run_countdown(user_id, event_id, seconds)` — records countdown row,
     sleeps, re-checks cancellation flag, fires if still active
   - `send_alerts(user_id, event_id)` — fetches contacts + location + sends
     WhatsApp messages, updates event row
3. `src/routes/crisis.py` with 9 endpoints from original plan:
   - `POST   /api/v1/crisis/settings`       (consent)
   - `GET    /api/v1/crisis/settings`
   - `POST   /api/v1/crisis/contacts`
   - `GET    /api/v1/crisis/contacts`
   - `PUT    /api/v1/crisis/contacts/{id}`
   - `DELETE /api/v1/crisis/contacts/{id}`
   - `POST   /api/v1/crisis/cancel-alert`
   - `GET    /api/v1/crisis/events`
   - `POST   /api/v1/crisis/test-alert`
4. Mount router in `src/api.py`; add env vars to `.env.example` and
   `requirements.txt` (add `twilio>=9.0.0`).
5. Hook detection into `/api/chat` in `src/api.py` — HIGH/CRITICAL bypasses
   RAG with the pre-scripted response + helplines; CRITICAL kicks off
   countdown as background asyncio task.
6. `src/data/helplines.json` (PK / US / GB).
7. `tests/test_crisis_detector.py` — critical/high/safe message sets from
   original plan, with keyword-only timing assertion.
8. `Docs/CRISIS_SETUP.md` — Twilio sandbox walkthrough +
   curl examples to exercise endpoints end-to-end.

**Session 3 — End-to-end test with Twilio + Colab live**
- User sets up Twilio sandbox, sends `join <code>` from test phone
- User brings Colab LLM online
- Run the test-alert endpoint, confirm WhatsApp delivery
- Run the crisis detection against a real chat message end-to-end
- Fix anything that breaks

**Session 4 — Frontend**
- Settings page: consent toggles + countdown slider + country selector
- Emergency contacts CRUD page
- Test-alert button (with confirmation modal)
- Crisis response rendering in chat (special bubble with helpline cards)
- Countdown modal with big "I'm safe, cancel" button
- Past events viewer

**Session 5 — Voice agent integration**
- Hook crisis detection into `src/voice_agent.py` STT output
- Pre-scripted response via ElevenLabs TTS
- WebSocket events via LiveKit data channel for frontend

## Open decisions

- Production WhatsApp template (needs approval before non-sandbox launch)
- How to detect user country for helplines — profile field, IP geolocation,
  or explicit setting? Currently planning explicit `country_code` field on
  `crisis_safety_settings` (default `PK`).
- Trigger text retention: stored for 30 days for review then purged (via
  `trigger_text_purge_at` + a scheduled job). Job not written yet.

## Env vars needed (add when Twilio set up)

```
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886   # sandbox number
TWILIO_SMS_FROM=+1...                         # optional fallback
CRISIS_COUNTDOWN_SECONDS=30
CRISIS_LLM_ENABLED=true
```
