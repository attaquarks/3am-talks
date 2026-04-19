-- Performance indexes for commonly-filtered query paths.
-- Identified during codebase audit (PERF-003).

-- Patient-therapist links: therapist dashboard filters by therapist + status
create index if not exists idx_ptl_therapist_status
  on patient_therapist_links(therapist_id, status);

-- Patient-therapist links: partial index for active/pending statuses
create index if not exists idx_ptl_active_pending
  on patient_therapist_links(status)
  where status in ('pending_therapist', 'pending_patient', 'active');

-- Crisis events: patient lookup ordered by time
create index if not exists idx_crisis_events_patient_date
  on crisis_events(patient_id, created_at desc);

-- Session summaries: patient lookup ordered by generation time
create index if not exists idx_session_summaries_patient
  on session_summaries(patient_id, generated_at desc);

-- Mood entries: user lookup ordered by time (dashboard charts)
create index if not exists idx_mood_entries_user_date
  on mood_entries(user_id, created_at desc);

-- Conversations: user lookup ordered by time
create index if not exists idx_conversations_user_date
  on conversations(user_id, started_at desc);

-- Messages: conversation lookup ordered by time
create index if not exists idx_messages_conversation_date
  on messages(conversation_id, created_at asc);

-- Therapist messages: unread messages per recipient
create index if not exists idx_therapist_messages_unread
  on therapist_messages(recipient_id)
  where read_at is null;

-- Clinical access logs: patient audit trail
create index if not exists idx_access_logs_patient
  on clinical_access_logs(patient_id, created_at desc);

-- Emergency contacts: active contacts per user (alert dispatch)
create index if not exists idx_emergency_contacts_active
  on emergency_contacts(user_id)
  where is_active = true;

-- Crisis countdowns: active (unfired, uncancelled) per user
create index if not exists idx_crisis_countdowns_active
  on crisis_countdowns(user_id)
  where cancelled_at is null and fired_at is null;
