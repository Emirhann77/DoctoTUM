-- End-to-end wiring: columns and tables the app pages need, plus a usable doctor directory.
-- Run after 20261117120000_symptom_check_catalog.sql. Safe to run more than once.

-- ---------------------------------------------------------------------------
-- Doctors: what the matching needs (spoken languages, where they practise)
-- ---------------------------------------------------------------------------
ALTER TABLE public.providers
  ADD COLUMN IF NOT EXISTS languages text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS city text,
  ADD COLUMN IF NOT EXISTS country text;

CREATE UNIQUE INDEX IF NOT EXISTS providers_display_name_key ON public.providers (display_name);

-- ---------------------------------------------------------------------------
-- Appointments are consultations with a time and a reason
-- ---------------------------------------------------------------------------
ALTER TABLE public.consultations
  ADD COLUMN IF NOT EXISTS scheduled_at timestamptz,
  ADD COLUMN IF NOT EXISTS reason text;

ALTER TABLE public.consultations DROP CONSTRAINT IF EXISTS consultations_reason_length;
ALTER TABLE public.consultations ADD CONSTRAINT consultations_reason_length CHECK (
  reason IS NULL OR length(reason) <= 500
);

-- One person cannot hold two live bookings for the same moment.
CREATE UNIQUE INDEX IF NOT EXISTS consultations_patient_slot_key ON public.consultations (patient_id, scheduled_at)
WHERE
  status <> 'cancelled' AND scheduled_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS consultations_patient_scheduled_idx ON public.consultations (patient_id, scheduled_at);

-- ---------------------------------------------------------------------------
-- Prescriptions and pharmacy orders
-- ---------------------------------------------------------------------------
ALTER TABLE public.prescriptions
  ADD COLUMN IF NOT EXISTS instructions text;

ALTER TABLE public.pharmacy_orders
  ADD COLUMN IF NOT EXISTS prescription_id uuid REFERENCES public.prescriptions (id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS quantity integer NOT NULL DEFAULT 1;

ALTER TABLE public.pharmacy_orders DROP CONSTRAINT IF EXISTS pharmacy_orders_quantity_range;
ALTER TABLE public.pharmacy_orders ADD CONSTRAINT pharmacy_orders_quantity_range CHECK (quantity BETWEEN 1 AND 10);

CREATE INDEX IF NOT EXISTS pharmacy_orders_prescription_id_idx ON public.pharmacy_orders (prescription_id);

-- ---------------------------------------------------------------------------
-- SOS log
-- ---------------------------------------------------------------------------
ALTER TABLE public.emergency_alerts
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active',
  ADD COLUMN IF NOT EXISTS ended_at timestamptz,
  ADD COLUMN IF NOT EXISTS symptoms text,
  ADD COLUMN IF NOT EXISTS language text,
  ADD COLUMN IF NOT EXISTS location jsonb;

ALTER TABLE public.emergency_alerts DROP CONSTRAINT IF EXISTS emergency_alerts_status_check;
ALTER TABLE public.emergency_alerts ADD CONSTRAINT emergency_alerts_status_check CHECK (
  status IN ('active', 'cancelled', 'resolved')
);

-- ---------------------------------------------------------------------------
-- Profile details shown on the profile page and the Medical ID
-- ---------------------------------------------------------------------------
ALTER TABLE public.medical_profiles
  ADD COLUMN IF NOT EXISTS phone text,
  ADD COLUMN IF NOT EXISTS height_cm numeric(5, 1),
  ADD COLUMN IF NOT EXISTS weight_kg numeric(5, 1);

ALTER TABLE public.medical_profiles DROP CONSTRAINT IF EXISTS medical_profiles_body_ranges;
ALTER TABLE public.medical_profiles ADD CONSTRAINT medical_profiles_body_ranges CHECK (
  (height_cm IS NULL OR height_cm BETWEEN 30 AND 260)
  AND (weight_kg IS NULL OR weight_kg BETWEEN 1 AND 500)
);

CREATE TABLE IF NOT EXISTS public.profile_allergies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  label text NOT NULL CHECK (length(trim(label)) BETWEEN 1 AND 80),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS profile_allergies_user_id_idx ON public.profile_allergies (user_id);

CREATE TABLE IF NOT EXISTS public.emergency_contacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  name text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 80),
  phone text NOT NULL CHECK (phone ~ '^[0-9+() ./-]{3,30}$'),
  relationship text CHECK (relationship IS NULL OR length(relationship) <= 40),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS emergency_contacts_user_id_idx ON public.emergency_contacts (user_id);

ALTER TABLE public.profile_allergies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.emergency_contacts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "profile_allergies_rw_own" ON public.profile_allergies;
CREATE POLICY "profile_allergies_rw_own" ON public.profile_allergies FOR ALL TO authenticated USING (user_id = (SELECT auth.uid ()))
WITH CHECK (user_id = (SELECT auth.uid ()));

DROP POLICY IF EXISTS "emergency_contacts_rw_own" ON public.emergency_contacts;
CREATE POLICY "emergency_contacts_rw_own" ON public.emergency_contacts FOR ALL TO authenticated USING (user_id = (SELECT auth.uid ()))
WITH CHECK (user_id = (SELECT auth.uid ()));

-- Accounts created before the signup trigger existed still need a profile row.
DROP POLICY IF EXISTS "profiles_insert_own" ON public.profiles;
CREATE POLICY "profiles_insert_own" ON public.profiles FOR INSERT TO authenticated WITH CHECK (id = (SELECT auth.uid ()));

-- A patient may not rewrite who a consultation is with or whose it is; they may cancel.
-- (The original update policy allowed any column change by either participant.)
CREATE OR REPLACE FUNCTION public.guard_consultation_update ()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  IF new.patient_id IS DISTINCT FROM old.patient_id THEN
    RAISE EXCEPTION 'patient_id cannot be changed' USING ERRCODE = '42501';
  END IF;
  RETURN new;
END;
$$;

DROP TRIGGER IF EXISTS consultations_guard_update ON public.consultations;
CREATE TRIGGER consultations_guard_update
BEFORE UPDATE ON public.consultations FOR EACH ROW
EXECUTE PROCEDURE public.guard_consultation_update ();

-- ---------------------------------------------------------------------------
-- updated_at maintenance
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.touch_updated_at ()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  new.updated_at = now();
  RETURN new;
END;
$$;

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['profiles', 'medical_profiles', 'providers', 'consultations', 'prescriptions', 'pharmacy_orders', 'subscriptions', 'insurance_documents']
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.%I', t || '_touch_updated_at', t);
    EXECUTE format(
      'CREATE TRIGGER %I BEFORE UPDATE ON public.%I FOR EACH ROW EXECUTE PROCEDURE public.touch_updated_at ()',
      t || '_touch_updated_at',
      t
    );
  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- Doctor directory (demo doctors, not linked to auth users)
-- Every specialty the symptom check can recommend has someone available, and
-- each interface language (en/de/tr/es/fr) has at least one speaker.
-- ---------------------------------------------------------------------------
INSERT INTO public.providers (display_name, specialty, title, organization, years_experience, is_board_certified, is_available, languages, city, country)
VALUES
  ('Dr. Ayşe Yılmaz', 'General Practitioner', 'General Practitioner', 'CareConnect Munich', 11, true, true, '{Turkish,German,English}', 'Munich', 'Germany'),
  ('Dr. Jonas Weber', 'General Practitioner', 'General Practitioner', 'CareConnect Garching', 9, true, true, '{German,English}', 'Garching', 'Germany'),
  ('Dr. Elena Gómez', 'General Practitioner', 'General Practitioner', 'CareConnect Munich', 11, true, true, '{Spanish,English,German}', 'Munich', 'Germany'),
  ('Dr. Sarah Chen', 'Cardiology', 'Cardiologist', 'CareConnect Munich', 12, true, true, '{English,German}', 'Munich', 'Germany'),
  ('Dr. Max Müller', 'Cardiology', 'Cardiologist', 'CareConnect Munich', 18, true, false, '{German,English}', 'Munich', 'Germany'),
  ('Dr. Sofia Rossi', 'Dermatology', 'Dermatologist', 'CareConnect Garching', 8, true, true, '{English,German}', 'Garching', 'Germany'),
  ('Dr. James Wilson', 'Dermatology', 'Dermatologist', 'CareConnect Munich', 10, true, true, '{English,French}', 'Munich', 'Germany'),
  ('Dr. Camille Laurent', 'Pediatrics', 'Pediatrician', 'CareConnect Garching', 10, true, true, '{French,English,German}', 'Garching', 'Germany'),
  ('Dr. Sarah Mitchell', 'Pediatrics', 'Senior Pediatrician', 'CareConnect Munich', 15, true, true, '{English,German}', 'Munich', 'Germany'),
  ('Dr. Lucía Fernández', 'Psychiatry', 'Psychiatrist', 'CareConnect Munich', 14, true, true, '{Spanish,English,German}', 'Munich', 'Germany'),
  ('Dr. Deniz Arslan', 'Psychiatry', 'Psychiatrist', 'CareConnect Munich', 7, true, true, '{Turkish,German,English}', 'Munich', 'Germany'),
  ('Dr. Elif Kaya', 'Emergency Medicine', 'Emergency Physician', 'CareConnect Munich', 13, true, true, '{Turkish,German,English}', 'Munich', 'Germany')
ON CONFLICT (display_name) DO UPDATE
SET
  specialty = excluded.specialty,
  title = excluded.title,
  organization = excluded.organization,
  years_experience = excluded.years_experience,
  is_board_certified = excluded.is_board_certified,
  is_available = excluded.is_available,
  languages = excluded.languages,
  city = excluded.city,
  country = excluded.country;
