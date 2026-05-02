-- DoctoTUM / CareConnect-style schema for Supabase (Postgres)
-- Apply in Dashboard → SQL Editor, or: supabase db push (CLI)

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'app_role') THEN
    CREATE TYPE public.app_role AS ENUM ('patient', 'provider', 'admin');
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscription_status') THEN
    CREATE TYPE public.subscription_status AS ENUM ('active', 'past_due', 'cancelled', 'trialing');
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'consultation_status') THEN
    CREATE TYPE public.consultation_status AS ENUM (
      'queued',
      'active',
      'completed',
      'cancelled'
    );
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'prescription_status') THEN
    CREATE TYPE public.prescription_status AS ENUM ('pending', 'issued', 'filled', 'cancelled');
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pharmacy_order_status') THEN
    CREATE TYPE public.pharmacy_order_status AS ENUM (
      'requested',
      'processing',
      'shipped',
      'cancelled'
    );
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Profiles (1:1 with auth.users)
-- ---------------------------------------------------------------------------
CREATE TABLE public.profiles (
  id uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  display_name text,
  avatar_url text,
  role public.app_role NOT NULL DEFAULT 'patient',
  -- Marketing / UX labels from UI (Indigo tier, Pro member, etc.)
  tier_label text,
  is_pro_member boolean NOT NULL DEFAULT false,
  direct_specialist_access boolean NOT NULL DEFAULT false,
  onboarding_step smallint NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX profiles_role_idx ON public.profiles (role);

-- ---------------------------------------------------------------------------
-- Medical onboarding (Health profile / Medical history screen)
-- ---------------------------------------------------------------------------
CREATE TABLE public.medical_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  user_id uuid NOT NULL UNIQUE REFERENCES auth.users (id) ON DELETE CASCADE,
  legal_full_name text,
  date_of_birth date,
  blood_type text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX medical_profiles_user_id_idx ON public.medical_profiles (user_id);

CREATE TABLE public.condition_definitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  slug text NOT NULL UNIQUE,
  label text NOT NULL
);

CREATE TABLE public.profile_conditions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  condition_id uuid REFERENCES public.condition_definitions (id) ON DELETE SET NULL,
  custom_label text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT profile_conditions_custom_or_catalog CHECK (
    condition_id IS NOT NULL
    OR (custom_label IS NOT NULL AND length(trim(custom_label)) > 0)
  )
);

CREATE INDEX profile_conditions_user_id_idx ON public.profile_conditions (user_id);

-- Insurance card upload + OCR output (store file in Supabase Storage; keep path here)
CREATE TABLE public.insurance_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  card_front_path text,
  card_back_path text,
  ocr_raw jsonb,
  ocr_provider text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX insurance_documents_user_id_idx ON public.insurance_documents (user_id);

-- ---------------------------------------------------------------------------
-- Plans & subscriptions (Choose your care plan)
-- ---------------------------------------------------------------------------
CREATE TABLE public.plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  slug text NOT NULL UNIQUE,
  name text NOT NULL,
  price_cents_monthly integer NOT NULL,
  max_family_members integer,
  features jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.subscriptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  plan_id uuid NOT NULL REFERENCES public.plans (id) ON DELETE RESTRICT,
  status public.subscription_status NOT NULL DEFAULT 'active',
  current_period_end timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX subscriptions_user_id_idx ON public.subscriptions (user_id);

CREATE TABLE public.family_groups (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  primary_user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  max_members integer NOT NULL DEFAULT 6,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX family_groups_primary_user_id_idx ON public.family_groups (primary_user_id);

CREATE TABLE public.family_group_members (
  group_id uuid NOT NULL REFERENCES public.family_groups (id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  is_primary boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (group_id, user_id)
);

-- ---------------------------------------------------------------------------
-- Providers / specialists (directory + video call header)
-- ---------------------------------------------------------------------------
CREATE TABLE public.providers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  user_id uuid UNIQUE REFERENCES auth.users (id) ON DELETE SET NULL,
  display_name text NOT NULL,
  specialty text,
  title text,
  organization text,
  image_url text,
  years_experience integer,
  is_board_certified boolean NOT NULL DEFAULT false,
  pro_active boolean NOT NULL DEFAULT false,
  is_available boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX providers_available_idx ON public.providers (is_available);

-- ---------------------------------------------------------------------------
-- Consultations / video sessions
-- ---------------------------------------------------------------------------
CREATE TABLE public.consultations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  patient_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  provider_id uuid REFERENCES public.providers (id) ON DELETE SET NULL,
  status public.consultation_status NOT NULL DEFAULT 'queued',
  requested_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  ended_at timestamptz,
  avg_wait_seconds integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX consultations_patient_id_idx ON public.consultations (patient_id);
CREATE INDEX consultations_provider_id_idx ON public.consultations (provider_id);
CREATE INDEX consultations_status_idx ON public.consultations (status);

CREATE TABLE public.consultation_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  consultation_id uuid NOT NULL REFERENCES public.consultations (id) ON DELETE CASCADE,
  sender_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  body text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX consultation_messages_consultation_id_idx ON public.consultation_messages (
  consultation_id
);

CREATE TABLE public.prescriptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  consultation_id uuid REFERENCES public.consultations (id) ON DELETE SET NULL,
  patient_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  prescriber_provider_id uuid NOT NULL REFERENCES public.providers (id) ON DELETE RESTRICT,
  medication_name text NOT NULL,
  dosage text,
  status public.prescription_status NOT NULL DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX prescriptions_patient_id_idx ON public.prescriptions (patient_id);
CREATE INDEX prescriptions_consultation_id_idx ON public.prescriptions (consultation_id);

-- ---------------------------------------------------------------------------
-- Pharmacy refills (home “Pharmacy / Order refills”)
-- ---------------------------------------------------------------------------
CREATE TABLE public.pharmacy_orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  medication_name text NOT NULL,
  status public.pharmacy_order_status NOT NULL DEFAULT 'requested',
  notes text,
  request_date date NOT NULL DEFAULT (CURRENT_DATE),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX pharmacy_orders_user_id_idx ON public.pharmacy_orders (user_id);

-- ---------------------------------------------------------------------------
-- Activity / “My walks” history
-- ---------------------------------------------------------------------------
CREATE TABLE public.user_activities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  activity_type text NOT NULL,
  summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at timestamptz,
  ended_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX user_activities_user_id_idx ON public.user_activities (user_id);

-- ---------------------------------------------------------------------------
-- Daily health tips
-- ---------------------------------------------------------------------------
CREATE TABLE public.health_tips (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  title text NOT NULL,
  body text NOT NULL,
  show_on date NOT NULL DEFAULT CURRENT_DATE,
  sort_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX health_tips_show_on_idx ON public.health_tips (show_on);

-- ---------------------------------------------------------------------------
-- SOS / emergency (optional log — wire to app logic later)
-- ---------------------------------------------------------------------------
CREATE TABLE public.emergency_alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  latitude double precision,
  longitude double precision,
  note text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX emergency_alerts_user_id_idx ON public.emergency_alerts (user_id);

-- ---------------------------------------------------------------------------
-- Auto-create profile on signup
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_new_user ()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, display_name)
  VALUES (
    new.id,
    COALESCE(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name', split_part(new.email, '@', 1))
  );
  RETURN new;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE TRIGGER on_auth_user_created
AFTER INSERT ON auth.users FOR EACH ROW
EXECUTE PROCEDURE public.handle_new_user ();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medical_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.condition_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profile_conditions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.insurance_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.family_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.family_group_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consultations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consultation_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prescriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pharmacy_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.health_tips ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.emergency_alerts ENABLE ROW LEVEL SECURITY;

-- Profiles: users manage own row
CREATE POLICY "profiles_select_own" ON public.profiles FOR SELECT TO authenticated USING (id = auth.uid ());

CREATE POLICY "profiles_update_own" ON public.profiles
FOR UPDATE TO authenticated USING (id = auth.uid ())
WITH CHECK (id = auth.uid ());

-- Medical data: owner only
CREATE POLICY "medical_profiles_rw_own" ON public.medical_profiles FOR ALL TO authenticated USING (user_id = auth.uid ())
WITH CHECK (user_id = auth.uid ());

CREATE POLICY "profile_conditions_rw_own" ON public.profile_conditions FOR ALL TO authenticated USING (user_id = auth.uid ())
WITH CHECK (user_id = auth.uid ());

CREATE POLICY "insurance_documents_rw_own" ON public.insurance_documents FOR ALL TO authenticated USING (user_id = auth.uid ())
WITH CHECK (user_id = auth.uid ());

-- Lookup: all signed-in users can read condition chips & plans
CREATE POLICY "condition_definitions_read" ON public.condition_definitions FOR SELECT TO authenticated USING (true);

CREATE POLICY "plans_read" ON public.plans FOR SELECT TO authenticated USING (true);

-- Subscriptions: own rows
CREATE POLICY "subscriptions_rw_own" ON public.subscriptions FOR ALL TO authenticated USING (user_id = auth.uid ())
WITH CHECK (user_id = auth.uid ());

-- Family: primary or member can see group; only primary mutates group (simplified)
CREATE POLICY "family_groups_select_member" ON public.family_groups FOR SELECT TO authenticated USING (
  primary_user_id = auth.uid ()
  OR EXISTS (
    SELECT 1
    FROM public.family_group_members m
    WHERE m.group_id = family_groups.id
      AND m.user_id = auth.uid ()
  )
);

CREATE POLICY "family_groups_insert_primary" ON public.family_groups FOR INSERT TO authenticated WITH CHECK (primary_user_id = auth.uid ());

CREATE POLICY "family_groups_update_primary" ON public.family_groups FOR UPDATE TO authenticated USING (primary_user_id = auth.uid ())
WITH CHECK (primary_user_id = auth.uid ());

CREATE POLICY "family_members_rw_if_primary" ON public.family_group_members FOR ALL TO authenticated USING (
  EXISTS (
    SELECT 1
    FROM public.family_groups g
    WHERE g.id = family_group_members.group_id
      AND g.primary_user_id = auth.uid ()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1
    FROM public.family_groups g
    WHERE g.id = family_group_members.group_id
      AND g.primary_user_id = auth.uid ()
  )
);

CREATE POLICY "family_members_select_self" ON public.family_group_members FOR SELECT TO authenticated USING (user_id = auth.uid ());

-- Providers: readable directory; providers may update their own row if linked to auth user
CREATE POLICY "providers_select_authenticated" ON public.providers FOR SELECT TO authenticated USING (true);

CREATE POLICY "providers_update_own" ON public.providers FOR UPDATE TO authenticated USING (user_id = auth.uid ())
WITH CHECK (user_id = auth.uid ());

-- Consultations: patient or assigned provider (via providers.user_id)
CREATE POLICY "consultations_select_participant" ON public.consultations FOR SELECT TO authenticated USING (
  patient_id = auth.uid ()
  OR EXISTS (
    SELECT 1
    FROM public.providers p
    WHERE p.id = consultations.provider_id
      AND p.user_id = auth.uid ()
  )
);

CREATE POLICY "consultations_insert_patient" ON public.consultations FOR INSERT TO authenticated WITH CHECK (patient_id = auth.uid ());

CREATE POLICY "consultations_update_participant" ON public.consultations
FOR UPDATE TO authenticated USING (
  patient_id = auth.uid ()
  OR EXISTS (
    SELECT 1
    FROM public.providers p
    WHERE p.id = consultations.provider_id
      AND p.user_id = auth.uid ()
  )
)
WITH CHECK (
  patient_id = auth.uid ()
  OR EXISTS (
    SELECT 1
    FROM public.providers p
    WHERE p.id = consultations.provider_id
      AND p.user_id = auth.uid ()
  )
);

-- Messages: only if participant in parent consultation
CREATE POLICY "consultation_messages_rw_participant" ON public.consultation_messages FOR ALL TO authenticated USING (
  EXISTS (
    SELECT 1
    FROM public.consultations c
    WHERE c.id = consultation_messages.consultation_id
      AND (
        c.patient_id = auth.uid ()
        OR EXISTS (
          SELECT 1
          FROM public.providers p
          WHERE p.id = c.provider_id
            AND p.user_id = auth.uid ()
        )
      )
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1
    FROM public.consultations c
    WHERE c.id = consultation_messages.consultation_id
      AND (
        c.patient_id = auth.uid ()
        OR EXISTS (
          SELECT 1
          FROM public.providers p
          WHERE p.id = c.provider_id
            AND p.user_id = auth.uid ()
        )
      )
  )
  AND sender_id = auth.uid ()
);

-- Prescriptions: patient sees own; prescribing provider sees theirs
CREATE POLICY "prescriptions_select_patient_or_prescriber" ON public.prescriptions FOR SELECT TO authenticated USING (
  patient_id = auth.uid ()
  OR EXISTS (
    SELECT 1
    FROM public.providers p
    WHERE p.id = prescriptions.prescriber_provider_id
      AND p.user_id = auth.uid ()
  )
);

CREATE POLICY "prescriptions_insert_provider" ON public.prescriptions FOR INSERT TO authenticated WITH CHECK (
  EXISTS (
    SELECT 1
    FROM public.providers p
    WHERE p.id = prescriber_provider_id
      AND p.user_id = auth.uid ()
  )
  AND patient_id IS NOT NULL
);

CREATE POLICY "prescriptions_update_provider" ON public.prescriptions
FOR UPDATE TO authenticated USING (
  EXISTS (
    SELECT 1
    FROM public.providers p
    WHERE p.id = prescriptions.prescriber_provider_id
      AND p.user_id = auth.uid ()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1
    FROM public.providers p
    WHERE p.id = prescriptions.prescriber_provider_id
      AND p.user_id = auth.uid ()
  )
);

-- Pharmacy & activities: owner
CREATE POLICY "pharmacy_orders_rw_own" ON public.pharmacy_orders FOR ALL TO authenticated USING (user_id = auth.uid ())
WITH CHECK (user_id = auth.uid ());

CREATE POLICY "user_activities_rw_own" ON public.user_activities FOR ALL TO authenticated USING (user_id = auth.uid ())
WITH CHECK (user_id = auth.uid ());

-- Health tips: read-only for users (admin backfill via service role / dashboard)
CREATE POLICY "health_tips_read" ON public.health_tips FOR SELECT TO authenticated USING (true);

-- Emergency alerts: insert/select own
CREATE POLICY "emergency_alerts_rw_own" ON public.emergency_alerts FOR ALL TO authenticated USING (user_id = auth.uid ())
WITH CHECK (user_id = auth.uid ());

-- ---------------------------------------------------------------------------
-- Seed: plans, common conditions, sample tips & demo providers (idempotent)
-- ---------------------------------------------------------------------------
INSERT INTO
  public.plans (slug, name, price_cents_monthly, max_family_members, features)
VALUES
  (
    'basic',
    'Basic',
    2900,
    NULL,
    '["Virtual visits","Medical records"]'::jsonb
  ),
  (
    'pro',
    'Pro',
    5900,
    NULL,
    '["Virtual visits","E-prescriptions","Specialist chat","Health coach"]'::jsonb
  ),
  (
    'family',
    'Family',
    9900,
    6,
    '["Everything in Pro","Up to 6 family members","Home lab collections"]'::jsonb
  )
ON CONFLICT (slug) DO NOTHING;

INSERT INTO
  public.condition_definitions (slug, label)
VALUES
  ('diabetes', 'Diabetes'),
  ('hypertension', 'Hypertension'),
  ('asthma', 'Asthma'),
  ('thyroid', 'Thyroid'),
  ('heart_disease', 'Heart Disease')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO public.health_tips (title, body, show_on, sort_order)
SELECT 'Stay Hydrated during Summer',
  'Drink water regularly and limit peak-sun outdoor activity when it is hot.',
  CURRENT_DATE,
  0
WHERE
  NOT EXISTS (
    SELECT 1
    FROM public.health_tips
    WHERE
      title = 'Stay Hydrated during Summer'
  );

-- Demo specialists (no auth user — for UI listing; link user_id when doctor accounts exist)
INSERT INTO public.providers (
  display_name,
  specialty,
  title,
  organization,
  image_url,
  years_experience,
  is_board_certified,
  pro_active,
  is_available
)
SELECT
  display_name,
  specialty,
  title,
  organization,
  image_url,
  years_experience,
  is_board_certified,
  pro_active,
  is_available
FROM
  (
    VALUES
      (
        'Dr. Sarah Chen',
        'Cardiology',
        'Cardiologist',
        'Pro Care',
        NULL::text,
        12,
        true,
        true,
        true
      ),
      (
        'Dr. James Wilson',
        'Dermatology',
        'Dermatologist',
        'Pro Care',
        NULL::text,
        10,
        true,
        false,
        true
      ),
      (
        'Dr. Sarah Mitchell',
        'Pediatrics',
        'Senior Pediatrician',
        'Pro Care',
        NULL::text,
        15,
        true,
        true,
        true
      )
  ) AS v (
    display_name,
    specialty,
    title,
    organization,
    image_url,
    years_experience,
    is_board_certified,
    pro_active,
    is_available
  )
WHERE
  NOT EXISTS (SELECT 1 FROM public.providers);
