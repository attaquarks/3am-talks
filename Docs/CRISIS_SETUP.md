# Crisis Safety — Setup & Testing Guide

Step-by-step for bringing the crisis detection + emergency alert system
online and exercising it end-to-end.

---

## 1. Run the database migration

In Supabase SQL Editor, paste and execute:
`supabase/migrations/20260416130000_crisis_alert_system.sql`.

It's idempotent — safe to re-run.

Verify by querying:
```sql
select table_name from information_schema.tables
 where table_schema='public'
   and table_name in ('emergency_contacts','crisis_safety_settings','crisis_countdowns');
-- expect 3 rows

select column_name from information_schema.columns
 where table_name='crisis_events' and column_name='severity_score';
-- expect 1 row
```

## 2. Install Python deps

```
pip install -r requirements.txt
```
This adds `twilio>=9.0.0`. The existing `torch`/`transformers` entries in
requirements are **not** used by the crisis system (we use the Colab LLM).

## 3. Twilio WhatsApp sandbox setup

Free, unlimited to opted-in numbers. Perfect for FYP testing.

1. Sign up at [twilio.com](https://www.twilio.com/try-twilio). Free trial
   gives ~$15 of credit (not needed for WhatsApp sandbox).
2. In the Twilio console, open **Messaging → Try it out → Send a
   WhatsApp message**. You'll see:
   - A sandbox WhatsApp number like `+1 415 523 8886`
   - A join code like `join silver-tiger`
3. Every phone that will receive alerts (yours + test emergency contacts)
   must send that join code to the sandbox number **once from WhatsApp**.
   Twilio will reply confirming they've joined.
4. Grab your credentials from the Twilio console dashboard (top of page):
   - **Account SID** (starts with `AC...`)
   - **Auth Token** (click to reveal)

Add to `.env`:
```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
# Optional SMS fallback (leave blank for MVP):
TWILIO_SMS_FROM=
```

## 4. Restart the backend

```
python src/api.py
```
Check the log — you should see:
```
Crisis safety routes registered
```
If you see `twilio_not_configured` warnings, the sandbox env vars are
missing and alerts will no-op (everything else still works).

## 5. Run unit tests

```
pytest tests/test_crisis_detector.py -v
```
All 28 tests must pass. These cover keyword detection for CRITICAL/HIGH/safe
messages, performance (<10ms p95), and result shape. LLM-arbitrated tests
are not included here — we exercise the arbiter through the manual end-to-end
below once the Colab endpoint is live.

## 6. End-to-end with `curl`

Replace `$COOKIE` with your session cookie from the browser (hit any
authenticated page, copy the `session=...` cookie). Or adapt with your
preferred auth flow.

### a) Add an emergency contact (yourself, for the first test)
```
curl -X POST http://localhost:5050/api/v1/crisis/contacts \
  -H "Content-Type: application/json" \
  -H "Cookie: session=$COOKIE" \
  -d '{
    "contact_name": "Test Self",
    "contact_phone": "+923001234567",
    "relationship": "Self-test",
    "notification_channel": "whatsapp"
  }'
```

### b) Enable alerts (store consent)
```
curl -X POST http://localhost:5050/api/v1/crisis/settings \
  -H "Content-Type: application/json" \
  -H "Cookie: session=$COOKIE" \
  -d '{
    "emergency_alerts_enabled": true,
    "location_sharing_consent": false,
    "consent_text_shown": "I consent that in a detected crisis, my registered emergency contacts will be notified via WhatsApp with a pre-written safety alert, after a 30-second countdown during which I can cancel.",
    "countdown_seconds": 30,
    "country_code": "PK"
  }'
```

### c) Fire a test alert (no real crisis needed)
```
curl -X POST http://localhost:5050/api/v1/crisis/test-alert \
  -H "Cookie: session=$COOKIE"
```
Expected: WhatsApp arrives at your phone within a few seconds with the
test-alert body. Response JSON shows `contacts_notified: 1`.

### d) Trigger via chat (real crisis path)

```
curl -X POST http://localhost:5050/api/chat \
  -H "Content-Type: application/json" \
  -H "Cookie: session=$COOKIE" \
  -d '{"message": "I want to kill myself tonight"}'
```
Expected response:
```
{
  "response": "I hear you, and I want you to know...",
  "crisis": {
    "detected": true,
    "risk_level": "CRITICAL",
    "event_id": "...",
    "countdown": {"countdown_id": "...", "seconds": 30, "can_cancel": true},
    "show_modal": true,
    "alerts_being_sent": true
  }
}
```
Within 30 seconds (unless cancelled), WhatsApp arrives at your contacts.

### e) Cancel the countdown (before 30s)
```
curl -X POST http://localhost:5050/api/v1/crisis/cancel-alert \
  -H "Cookie: session=$COOKIE"
```
Expected: `{"cancelled": 1}`. No WhatsApp sent.

### f) View past events
```
curl http://localhost:5050/api/v1/crisis/events -H "Cookie: session=$COOKIE"
```

## 7. Verify the LLM arbiter (once Colab is live)

Send a deliberately hyperbolic message that the keyword layer flags:
```
curl -X POST http://localhost:5050/api/chat \
  -H "Content-Type: application/json" \
  -H "Cookie: session=$COOKIE" \
  -d '{"message": "I cant take this anymore haha"}'
```
With LLM up, the arbiter should return `is_hyperbole=true` and downgrade
the risk level — no alerts fire. With LLM down, the system falls back to
the keyword tier (HIGH → intervention response shown, no SMS).

## 8. Common gotchas

- **WhatsApp sandbox "not joined" error** — the recipient phone must send
  `join <code>` to the sandbox number first. Twilio enforces this per phone.
- **Phone validation** — contacts must be E.164 format (`+923001234567`,
  not `03001234567`). The API rejects non-E.164 with a 400.
- **Countdown task dies with server restart** — asyncio tasks are
  in-process only. A server restart during a live countdown will orphan
  the row but won't fire the alert. Acceptable for MVP; add a job runner
  later if we need persistence.
- **Colab down** — the arbiter fails safely: keyword CRITICAL stays
  CRITICAL (fail-closed), keyword HIGH/MEDIUM stays as-is. You'll see
  `"llm_verdict": "unavailable"` in crisis_events.context.

## 9. Environment variables summary

```
# Colab LLM (already set in your .env)
COLAB_API_URL=...
COLAB_API_KEY=...

# Crisis arbiter (optional override)
CRISIS_ARBITER_MODEL=psychocounsel

# Twilio WhatsApp (required for alerts to actually send)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# Twilio SMS fallback (optional, disabled if blank)
TWILIO_SMS_FROM=
```
