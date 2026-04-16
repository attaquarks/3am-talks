-- Add user_phone to crisis_safety_settings so the safety alert can include
-- the user's own number for emergency contacts to call back.
-- Stored on safety settings (not user_profiles) because it's strictly
-- emergency-channel data and may differ from any signup phone.

begin;

alter table public.crisis_safety_settings
  add column if not exists user_phone text;

-- Soft constraint via application layer; we still validate E.164 there.
-- (No CHECK constraint here so future formats don't block migration.)

commit;
