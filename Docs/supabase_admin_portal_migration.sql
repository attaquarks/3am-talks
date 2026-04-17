-- Admin portal schema migration for Ella Speaks Calmly
-- Run this in Supabase SQL Editor or via supabase db push.

begin;

-- 1) Extend user_profiles for role-based access and moderation state
alter table public.user_profiles
  add column if not exists role text,
  add column if not exists account_status text,
  add column if not exists suspended_until timestamptz,
  add column if not exists status_reason text,
  add column if not exists moderated_by uuid,
  add column if not exists moderated_at timestamptz,
  add column if not exists email text;

update public.user_profiles
set
  role = coalesce(role, 'patient'),
  account_status = coalesce(account_status, 'active');

alter table public.user_profiles
  alter column role set default 'patient',
  alter column role set not null,
  alter column account_status set default 'active',
  alter column account_status set not null;

alter table public.user_profiles
  drop constraint if exists user_profiles_role_check;

alter table public.user_profiles
  add constraint user_profiles_role_check
  check (role in ('patient', 'therapist', 'admin'));

alter table public.user_profiles
  drop constraint if exists user_profiles_account_status_check;

alter table public.user_profiles
  add constraint user_profiles_account_status_check
  check (account_status in ('active', 'suspended', 'banned'));

create index if not exists idx_user_profiles_role on public.user_profiles(role);
create index if not exists idx_user_profiles_status on public.user_profiles(account_status);
create index if not exists idx_user_profiles_email on public.user_profiles(email);

-- 2) Moderation reports queue for admin operations
create table if not exists public.moderation_reports (
  report_id uuid primary key default gen_random_uuid(),
  reporter_user_id uuid not null,
  reported_user_id uuid,
  category text not null,
  description text not null,
  priority text not null default 'medium',
  status text not null default 'open',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resolved_at timestamptz,
  resolved_by uuid,
  constraint moderation_reports_priority_check check (priority in ('low', 'medium', 'high', 'urgent')),
  constraint moderation_reports_status_check check (status in ('open', 'in_review', 'resolved', 'dismissed'))
);

create index if not exists idx_moderation_reports_status on public.moderation_reports(status);
create index if not exists idx_moderation_reports_priority on public.moderation_reports(priority);
create index if not exists idx_moderation_reports_created_at on public.moderation_reports(created_at desc);

-- 3) Product feedback inbox for admin review
create table if not exists public.platform_feedback (
  feedback_id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  rating int,
  comment text not null,
  status text not null default 'open',
  created_at timestamptz not null default now(),
  reviewed_at timestamptz,
  reviewed_by uuid,
  constraint platform_feedback_status_check check (status in ('open', 'reviewed', 'dismissed')),
  constraint platform_feedback_rating_check check (rating is null or (rating >= 1 and rating <= 5))
);

create index if not exists idx_platform_feedback_status on public.platform_feedback(status);
create index if not exists idx_platform_feedback_created_at on public.platform_feedback(created_at desc);

commit;

-- Optional: promote a known account to admin after migration.
-- update public.user_profiles set role = 'admin' where email = 'your-admin-email@example.com';
