-- Foreign key constraints with cascade behavior to prevent orphaned data.
-- Identified during codebase audit (DATA-001).
--
-- Uses IF NOT EXISTS pattern via DO blocks to be idempotent.

-- therapist_notes -> patient_therapist_links (therapist+patient pair)
-- If link is revoked, notes are preserved (SET NULL on therapist_id) for audit trail.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'fk_therapist_notes_therapist'
    AND table_name = 'therapist_notes'
  ) THEN
    ALTER TABLE public.therapist_notes
      ADD CONSTRAINT fk_therapist_notes_therapist
      FOREIGN KEY (therapist_id) REFERENCES auth.users(id) ON DELETE SET NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'fk_therapist_notes_patient'
    AND table_name = 'therapist_notes'
  ) THEN
    ALTER TABLE public.therapist_notes
      ADD CONSTRAINT fk_therapist_notes_patient
      FOREIGN KEY (patient_id) REFERENCES auth.users(id) ON DELETE CASCADE;
  END IF;
END $$;

-- therapist_messages -> patient_therapist_links
-- If link is revoked, messages are cleaned up.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'fk_therapist_messages_link'
    AND table_name = 'therapist_messages'
  ) THEN
    ALTER TABLE public.therapist_messages
      ADD CONSTRAINT fk_therapist_messages_link
      FOREIGN KEY (link_id) REFERENCES public.patient_therapist_links(link_id) ON DELETE CASCADE;
  END IF;
END $$;

-- patient_homework -> treatment_plans (optional parent)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'fk_homework_plan'
    AND table_name = 'patient_homework'
  ) THEN
    ALTER TABLE public.patient_homework
      ADD CONSTRAINT fk_homework_plan
      FOREIGN KEY (plan_id) REFERENCES public.treatment_plans(plan_id) ON DELETE SET NULL;
  END IF;
END $$;

-- patient_homework -> therapist (if therapist deleted, keep homework but null out therapist)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'fk_homework_therapist'
    AND table_name = 'patient_homework'
  ) THEN
    ALTER TABLE public.patient_homework
      ADD CONSTRAINT fk_homework_therapist
      FOREIGN KEY (therapist_id) REFERENCES auth.users(id) ON DELETE SET NULL;
  END IF;
END $$;

-- patient_homework -> patient (if patient deleted, cascade delete homework)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'fk_homework_patient'
    AND table_name = 'patient_homework'
  ) THEN
    ALTER TABLE public.patient_homework
      ADD CONSTRAINT fk_homework_patient
      FOREIGN KEY (patient_id) REFERENCES auth.users(id) ON DELETE CASCADE;
  END IF;
END $$;

-- treatment_plans -> patient (cascade on patient deletion)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'fk_treatment_plans_patient'
    AND table_name = 'treatment_plans'
  ) THEN
    ALTER TABLE public.treatment_plans
      ADD CONSTRAINT fk_treatment_plans_patient
      FOREIGN KEY (patient_id) REFERENCES auth.users(id) ON DELETE CASCADE;
  END IF;
END $$;

-- treatment_plans -> therapist (set null on therapist deletion)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'fk_treatment_plans_therapist'
    AND table_name = 'treatment_plans'
  ) THEN
    ALTER TABLE public.treatment_plans
      ADD CONSTRAINT fk_treatment_plans_therapist
      FOREIGN KEY (therapist_id) REFERENCES auth.users(id) ON DELETE SET NULL;
  END IF;
END $$;
