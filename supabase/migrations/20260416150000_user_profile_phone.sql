-- Add phone (E.164) to user_profiles so the user's own callback number lives
-- on the profile and auto-populates the crisis safety settings form.

begin;

alter table public.user_profiles
  add column if not exists phone text;

commit;
