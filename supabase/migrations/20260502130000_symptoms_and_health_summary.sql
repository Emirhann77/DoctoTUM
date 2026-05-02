-- Per-user symptoms + read-only health summary (name, DOB, age)
-- Run after 20260502120000_initial_schema.sql

-- ---------------------------------------------------------------------------
-- Symptom catalog (chips / picker) + user-reported symptoms
-- ---------------------------------------------------------------------------
CREATE TABLE public.symptom_definitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  slug text NOT NULL UNIQUE,
  label text NOT NULL
);

CREATE TABLE public.user_symptoms (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  symptom_id uuid REFERENCES public.symptom_definitions (id) ON DELETE SET NULL,
  custom_label text,
  notes text,
  severity smallint,
  started_at timestamptz,
  ended_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT user_symptoms_severity_range CHECK (
    severity IS NULL
    OR (
      severity >= 1
      AND severity <= 10
    )
  ),
  CONSTRAINT user_symptoms_label CHECK (
    symptom_id IS NOT NULL
    OR (
      custom_label IS NOT NULL
      AND length(trim(custom_label)) > 0
    )
  )
);

CREATE INDEX user_symptoms_user_id_idx ON public.user_symptoms (user_id);

ALTER TABLE public.symptom_definitions ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.user_symptoms ENABLE ROW LEVEL SECURITY;

CREATE POLICY "symptom_definitions_read" ON public.symptom_definitions FOR SELECT TO authenticated USING (true);

CREATE POLICY "user_symptoms_rw_own" ON public.user_symptoms FOR ALL TO authenticated USING (user_id = auth.uid ())
WITH CHECK (user_id = auth.uid ());

INSERT INTO
  public.symptom_definitions (slug, label)
VALUES
  ('fever', 'Fever'),
  ('cough', 'Cough'),
  ('headache', 'Headache'),
  ('nausea', 'Nausea'),
  ('fatigue', 'Fatigue'),
  ('shortness_of_breath', 'Shortness of breath'),
  ('chest_pain', 'Chest pain')
ON CONFLICT (slug) DO NOTHING;

-- ---------------------------------------------------------------------------
-- One-row summary per user: legal name, DOB, age (years), blood type
-- security_invoker: RLS on medical_profiles applies when the user selects.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.user_health_summary
WITH
  (security_invoker = true) AS
SELECT
  mp.user_id,
  mp.legal_full_name,
  mp.date_of_birth,
  CASE
    WHEN mp.date_of_birth IS NOT NULL THEN (date_part('year', age (mp.date_of_birth)))::integer
    ELSE NULL
  END AS age_years,
  mp.blood_type
FROM
  public.medical_profiles mp;

COMMENT ON VIEW public.user_health_summary IS 'Convenience view: name, DOB, computed age, blood type. RLS follows medical_profiles.';
