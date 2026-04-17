-- Admin portal extensions: admin_id, audit logs, therapist verification, announcements.
-- Run this in Supabase SQL Editor after the base admin portal migration.

begin;

-- 1) Admin ID on user_profiles (auto-assigned when role becomes admin)
alter table public.user_profiles
  add column if not exists admin_id text;

create unique index if not exists idx_user_profiles_admin_id
  on public.user_profiles(admin_id)
  where admin_id is not null;

-- 2) Immutable audit log of admin actions
create table if not exists public.admin_audit_logs (
  log_id uuid primary key default gen_random_uuid(),
  admin_user_id uuid not null,
  admin_id text,
  action text not null,
  target_user_id uuid,
  target_resource text,
  reason text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_admin_audit_logs_admin on public.admin_audit_logs(admin_user_id);
create index if not exists idx_admin_audit_logs_target on public.admin_audit_logs(target_user_id);
create index if not exists idx_admin_audit_logs_action on public.admin_audit_logs(action);
create index if not exists idx_admin_audit_logs_created on public.admin_audit_logs(created_at desc);

-- 3) Therapist verification queue
create table if not exists public.therapist_verifications (
  verification_id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  license_number text,
  license_url text,
  specializations text[] default '{}',
  years_of_experience int,
  bio text,
  status text not null default 'pending',
  submitted_at timestamptz not null default now(),
  reviewed_by uuid,
  reviewed_at timestamptz,
  review_notes text,
  constraint therapist_verifications_status_check check (status in ('pending', 'approved', 'rejected'))
);

create index if not exists idx_therapist_verifications_status on public.therapist_verifications(status);
create index if not exists idx_therapist_verifications_user on public.therapist_verifications(user_id);

-- 4) Announcements composed by admins
create table if not exists public.announcements (
  announcement_id uuid primary key default gen_random_uuid(),
  admin_user_id uuid not null,
  title text not null,
  body text not null,
  audience text not null default 'all',
  active boolean not null default true,
  created_at timestamptz not null default now(),
  expires_at timestamptz,
  constraint announcements_audience_check check (audience in ('all', 'patients', 'therapists', 'inactive'))
);

create index if not exists idx_announcements_audience on public.announcements(audience);
create index if not exists idx_announcements_active on public.announcements(active);
create index if not exists idx_announcements_created on public.announcements(created_at desc);

commit;
