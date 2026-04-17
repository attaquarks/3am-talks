-- Therapist portal schema migration for Ella Speaks Calmly
-- Introduces therapist profiles, patient-therapist linking with consent,
-- invitations, clinical notes, AI SOAP summaries, treatment plans, homework,
-- async secure messaging, and crisis events — with row-level security.
-- Run in Supabase SQL Editor AFTER the admin portal migrations.

begin;

-- ---------------------------------------------------------------------------
-- 0) Extend user_profiles to support pending_verification status for therapists
-- ---------------------------------------------------------------------------
alter table public.user_profiles
  drop constraint if exists user_profiles_account_status_check;

alter table public.user_profiles
  add constraint user_profiles_account_status_check
  check (account_status in ('active', 'suspended', 'banned', 'pending_verification'));

-- ---------------------------------------------------------------------------
-- 1) Therapist profiles (extended clinical profile)
-- ---------------------------------------------------------------------------
create table if not exists public.therapist_profiles (
  therapist_user_id uuid primary key,
  display_name text,
  title text,
  license_number text,
  license_jurisdiction text,
  license_verified_at timestamptz,
  specializations text[] default '{}',
  modalities text[] default '{}',
  languages text[] default '{}',
  years_experience int,
  bio text,
  pronouns text,
  photo_url text,
  accepting_patients boolean not null default true,
  max_caseload int default 25,
  timezone text,
  availability jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_therapist_profiles_accepting on public.therapist_profiles(accepting_patients);
create index if not exists idx_therapist_profiles_specializations on public.therapist_profiles using gin(specializations);

-- ---------------------------------------------------------------------------
-- 2) Patient <-> Therapist links with consent
-- ---------------------------------------------------------------------------
create table if not exists public.patient_therapist_links (
  link_id uuid primary key default gen_random_uuid(),
  patient_id uuid not null,
  therapist_id uuid not null,
  status text not null default 'pending_therapist',
  initiated_by uuid not null,
  patient_consented_at timestamptz,
  therapist_consented_at timestamptz,
  consent_scope jsonb not null default '{"conversations":true,"journals":true,"mood":true,"reports":true,"personality":true}'::jsonb,
  revoked_at timestamptz,
  revoked_by uuid,
  revoke_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint patient_therapist_links_status_check check (
    status in ('pending_therapist', 'pending_patient', 'active', 'declined', 'revoked', 'expired')
  )
);

create unique index if not exists idx_ptl_active_unique
  on public.patient_therapist_links(patient_id, therapist_id)
  where status in ('pending_therapist', 'pending_patient', 'active');

create index if not exists idx_ptl_patient on public.patient_therapist_links(patient_id, status);
create index if not exists idx_ptl_therapist on public.patient_therapist_links(therapist_id, status);

-- ---------------------------------------------------------------------------
-- 3) Therapist invites (email invites for non-users)
-- ---------------------------------------------------------------------------
create table if not exists public.therapist_invites (
  invite_id uuid primary key default gen_random_uuid(),
  token text unique not null,
  inviter_user_id uuid not null,
  invitee_email text not null,
  invite_type text not null,
  status text not null default 'pending',
  expires_at timestamptz not null default (now() + interval '14 days'),
  accepted_user_id uuid,
  accepted_at timestamptz,
  created_at timestamptz not null default now(),
  constraint therapist_invites_type_check check (invite_type in ('patient_invites_therapist', 'therapist_invites_patient')),
  constraint therapist_invites_status_check check (status in ('pending', 'accepted', 'expired', 'revoked'))
);

create index if not exists idx_therapist_invites_email on public.therapist_invites(invitee_email, status);
create index if not exists idx_therapist_invites_inviter on public.therapist_invites(inviter_user_id);

-- ---------------------------------------------------------------------------
-- 4) Therapist private clinical notes
-- ---------------------------------------------------------------------------
create table if not exists public.therapist_notes (
  note_id uuid primary key default gen_random_uuid(),
  therapist_id uuid not null,
  patient_id uuid not null,
  conversation_id uuid,
  body text not null,
  tags text[] default '{}',
  follow_up_at timestamptz,
  is_private boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_therapist_notes_therapist_patient on public.therapist_notes(therapist_id, patient_id);
create index if not exists idx_therapist_notes_follow_up on public.therapist_notes(follow_up_at) where follow_up_at is not null;

-- ---------------------------------------------------------------------------
-- 5) AI-generated SOAP session summaries
-- ---------------------------------------------------------------------------
create table if not exists public.session_summaries (
  summary_id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null unique,
  patient_id uuid not null,
  subjective text,
  objective text,
  assessment text,
  plan text,
  risk_flags jsonb default '{}'::jsonb,
  action_items text[] default '{}',
  themes text[] default '{}',
  mood_trajectory text,
  generated_by text,
  generated_at timestamptz not null default now(),
  therapist_reviewed boolean not null default false,
  reviewed_by uuid,
  reviewed_at timestamptz
);

create index if not exists idx_session_summaries_patient on public.session_summaries(patient_id, generated_at desc);

-- ---------------------------------------------------------------------------
-- 6) Treatment plans
-- ---------------------------------------------------------------------------
create table if not exists public.treatment_plans (
  plan_id uuid primary key default gen_random_uuid(),
  therapist_id uuid not null,
  patient_id uuid not null,
  title text not null,
  primary_concern text,
  goals jsonb default '[]'::jsonb,
  interventions text[] default '{}',
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint treatment_plans_status_check check (status in ('active', 'paused', 'completed', 'archived'))
);

create index if not exists idx_treatment_plans_therapist on public.treatment_plans(therapist_id);
create index if not exists idx_treatment_plans_patient on public.treatment_plans(patient_id, status);

-- ---------------------------------------------------------------------------
-- 7) Homework / between-session tasks
-- ---------------------------------------------------------------------------
create table if not exists public.patient_homework (
  homework_id uuid primary key default gen_random_uuid(),
  plan_id uuid,
  therapist_id uuid not null,
  patient_id uuid not null,
  title text not null,
  description text,
  due_at timestamptz,
  status text not null default 'assigned',
  patient_reflection text,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint patient_homework_status_check check (status in ('assigned', 'in_progress', 'completed', 'skipped'))
);

create index if not exists idx_patient_homework_patient on public.patient_homework(patient_id, status);
create index if not exists idx_patient_homework_therapist on public.patient_homework(therapist_id, status);

-- ---------------------------------------------------------------------------
-- 8) Secure async messaging between therapist and patient
-- ---------------------------------------------------------------------------
create table if not exists public.therapist_messages (
  message_id uuid primary key default gen_random_uuid(),
  thread_id uuid not null,
  link_id uuid not null,
  sender_id uuid not null,
  recipient_id uuid not null,
  body text not null,
  urgency text not null default 'normal',
  is_system boolean not null default false,
  read_at timestamptz,
  created_at timestamptz not null default now(),
  constraint therapist_messages_urgency_check check (urgency in ('normal', 'priority', 'urgent'))
);

create index if not exists idx_therapist_messages_thread on public.therapist_messages(thread_id, created_at);
create index if not exists idx_therapist_messages_recipient_unread on public.therapist_messages(recipient_id) where read_at is null;

-- ---------------------------------------------------------------------------
-- 9) Crisis events
-- ---------------------------------------------------------------------------
create table if not exists public.crisis_events (
  event_id uuid primary key default gen_random_uuid(),
  patient_id uuid not null,
  therapist_id uuid,
  triggered_by text not null,
  severity text not null default 'medium',
  context jsonb default '{}'::jsonb,
  escalated_at timestamptz,
  resolved_at timestamptz,
  resolution_notes text,
  created_at timestamptz not null default now(),
  constraint crisis_events_severity_check check (severity in ('low', 'medium', 'high', 'critical'))
);

create index if not exists idx_crisis_events_patient on public.crisis_events(patient_id, created_at desc);
create index if not exists idx_crisis_events_unresolved on public.crisis_events(therapist_id) where resolved_at is null;

-- ---------------------------------------------------------------------------
-- 10) Extend platform_feedback to target a specific therapist
-- ---------------------------------------------------------------------------
alter table public.platform_feedback
  add column if not exists target_therapist_id uuid,
  add column if not exists feedback_type text default 'product';

create index if not exists idx_platform_feedback_target_therapist on public.platform_feedback(target_therapist_id);

-- ---------------------------------------------------------------------------
-- 11) Clinical data access audit log (transparency for patients)
-- ---------------------------------------------------------------------------
create table if not exists public.clinical_access_logs (
  log_id uuid primary key default gen_random_uuid(),
  therapist_id uuid not null,
  patient_id uuid not null,
  resource text not null,
  resource_id text,
  action text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_clinical_access_logs_patient on public.clinical_access_logs(patient_id, created_at desc);
create index if not exists idx_clinical_access_logs_therapist on public.clinical_access_logs(therapist_id, created_at desc);

commit;

-- ---------------------------------------------------------------------------
-- NOTE on Row-Level Security
-- ---------------------------------------------------------------------------
-- This project currently performs authorization in the FastAPI layer (see
-- require_therapist, require_link helpers in src/api.py), using the Supabase
-- service key. RLS is intentionally NOT enabled here because the application
-- enforces access rules before hitting the database. If you later switch to
-- per-user JWT access to Postgres, enable RLS with policies like:
--
-- alter table public.messages enable row level security;
-- create policy therapist_read_linked_patient_messages on public.messages
--   for select using (
--     user_id = auth.uid()
--     or user_id in (
--       select patient_id from public.patient_therapist_links
--        where therapist_id = auth.uid()
--          and status = 'active'
--          and (consent_scope->>'conversations')::bool = true
--     )
--   );
--
-- Repeat analogous policies for conversations, mood_entries, session_summaries,
-- therapist_notes (therapist-only), treatment_plans, patient_homework,
-- therapist_messages, crisis_events.
