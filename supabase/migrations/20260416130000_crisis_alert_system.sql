-- Crisis detection & emergency alert system for Ella Speaks Calmly
-- Adds: emergency_contacts, crisis_safety_settings, and extends the existing
-- crisis_events table (from therapist_portal migration) with alert-pipeline
-- columns so we don't fragment crisis data across two tables.
--
-- RLS is intentionally NOT enabled — authorization is enforced in the FastAPI
-- layer using the Supabase service key (same pattern as therapist_portal).
--
-- Run in Supabase SQL Editor AFTER 20260416120000_therapist_portal.sql.

begin;

-- ---------------------------------------------------------------------------
-- 1) Emergency contacts — people notified during a CRITICAL crisis
-- ---------------------------------------------------------------------------
create table if not exists public.emergency_contacts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  contact_name text not null,
  contact_phone text not null,
  relationship text,
  is_active boolean not null default true,
  notification_channel text not null default 'whatsapp',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint emergency_contacts_phone_e164
    check (contact_phone ~ '^\+[1-9][0-9]{6,14}$'),
  constraint emergency_contacts_channel_check
    check (notification_channel in ('whatsapp', 'sms', 'both'))
);

create index if not exists idx_emergency_contacts_user
  on public.emergency_contacts(user_id)
  where is_active = true;

-- ---------------------------------------------------------------------------
-- 2) Crisis safety settings — per-user consent + configuration
-- ---------------------------------------------------------------------------
create table if not exists public.crisis_safety_settings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique,
  emergency_alerts_enabled boolean not null default false,
  location_sharing_consent boolean not null default false,
  consent_given_at timestamptz,
  consent_text_shown text,
  countdown_seconds integer not null default 30,
  country_code text default 'PK',
  last_known_location jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint crisis_safety_countdown_range
    check (countdown_seconds between 10 and 120)
);

-- ---------------------------------------------------------------------------
-- 3) Extend existing crisis_events with alert-pipeline fields
--    (existing columns: event_id, patient_id, therapist_id, triggered_by,
--     severity, context, escalated_at, resolved_at, resolution_notes, created_at)
-- ---------------------------------------------------------------------------
alter table public.crisis_events
  add column if not exists session_id uuid,
  add column if not exists severity_score double precision,
  add column if not exists trigger_text text,
  add column if not exists keyword_matches text[] default '{}',
  add column if not exists ml_scores jsonb,
  add column if not exists emergency_alerts_sent boolean not null default false,
  add column if not exists contacts_notified text[] default '{}',
  add column if not exists user_location jsonb,
  add column if not exists intervention_type text,
  add column if not exists trigger_text_purge_at timestamptz;

-- intervention_type expected values: modal_shown, alerts_sent, user_cancelled,
-- response_only, failed_no_contacts, failed_not_consented
create index if not exists idx_crisis_events_severity_recent
  on public.crisis_events(severity, created_at desc);

create index if not exists idx_crisis_events_purge
  on public.crisis_events(trigger_text_purge_at)
  where trigger_text is not null;

-- ---------------------------------------------------------------------------
-- 4) Countdown tracker — lets cancel-alert endpoint race the background task
-- ---------------------------------------------------------------------------
create table if not exists public.crisis_countdowns (
  countdown_id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  event_id uuid references public.crisis_events(event_id) on delete cascade,
  started_at timestamptz not null default now(),
  fires_at timestamptz not null,
  cancelled_at timestamptz,
  fired_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_crisis_countdowns_active
  on public.crisis_countdowns(user_id)
  where cancelled_at is null and fired_at is null;

commit;
