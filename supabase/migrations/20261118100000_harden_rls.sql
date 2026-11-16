-- Tighten what a signed-in person can change by talking to the database API directly.
-- The original policies checked row ownership only, so an owner could rewrite any column.
-- Run after 20261118090000_end_to_end.sql. Safe to run more than once.

-- True when the statement is not made on behalf of an app user (migrations, the
-- service role, the dashboard). auth.uid() is null in all of those.
CREATE OR REPLACE FUNCTION public.is_backend ()
RETURNS boolean
LANGUAGE sql
STABLE
SET search_path = public
AS $$
  SELECT (SELECT auth.uid ()) IS NULL;
$$;

-- ---------------------------------------------------------------------------
-- profiles: the owner may change how they are shown, never their role or tier
-- ---------------------------------------------------------------------------
DROP POLICY IF EXISTS "profiles_insert_own" ON public.profiles; -- rows come from the signup trigger

REVOKE INSERT, UPDATE, DELETE ON public.profiles FROM authenticated, anon;
GRANT UPDATE (display_name, avatar_url, onboarding_step) ON public.profiles TO authenticated;

-- ---------------------------------------------------------------------------
-- subscriptions: readable by the owner, written only by the backend
-- ---------------------------------------------------------------------------
DROP POLICY IF EXISTS "subscriptions_rw_own" ON public.subscriptions;
DROP POLICY IF EXISTS "subscriptions_select_own" ON public.subscriptions;
CREATE POLICY "subscriptions_select_own" ON public.subscriptions FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid ()));

REVOKE INSERT, UPDATE, DELETE ON public.subscriptions FROM authenticated, anon;

-- ---------------------------------------------------------------------------
-- consultations: a patient books (queued) and cancels; nothing else
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.guard_consultation_write ()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  acting_as_provider boolean;
BEGIN
  IF public.is_backend () THEN
    RETURN new;
  END IF;

  IF tg_op = 'INSERT' THEN
    new.status := 'queued';
    new.started_at := NULL;
    new.ended_at := NULL;
    new.avg_wait_seconds := NULL;
    RETURN new;
  END IF;

  IF new.patient_id IS DISTINCT FROM old.patient_id THEN
    RAISE EXCEPTION 'patient_id cannot be changed' USING ERRCODE = '42501';
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM public.providers p WHERE p.id = old.provider_id AND p.user_id = (SELECT auth.uid ())
  ) INTO acting_as_provider;
  IF acting_as_provider THEN
    RETURN new;
  END IF;

  -- The patient: the only permitted change is queued -> cancelled.
  IF (to_jsonb(new) - 'status' - 'updated_at') IS DISTINCT FROM (to_jsonb(old) - 'status' - 'updated_at')
    OR NOT (new.status = old.status OR (old.status = 'queued' AND new.status = 'cancelled')) THEN
    RAISE EXCEPTION 'patients can only cancel a booking' USING ERRCODE = '42501';
  END IF;
  RETURN new;
END;
$$;

DROP TRIGGER IF EXISTS consultations_guard_update ON public.consultations;
DROP TRIGGER IF EXISTS consultations_guard_write ON public.consultations;
CREATE TRIGGER consultations_guard_write
BEFORE INSERT OR UPDATE ON public.consultations FOR EACH ROW
EXECUTE PROCEDURE public.guard_consultation_write ();

DROP FUNCTION IF EXISTS public.guard_consultation_update ();

REVOKE DELETE ON public.consultations FROM authenticated, anon;

-- ---------------------------------------------------------------------------
-- prescriptions: a doctor prescribes only for a patient they have a consultation with
-- ---------------------------------------------------------------------------
DROP POLICY IF EXISTS "prescriptions_insert_provider" ON public.prescriptions;
CREATE POLICY "prescriptions_insert_provider" ON public.prescriptions FOR INSERT TO authenticated WITH CHECK (
  EXISTS (
    SELECT 1
    FROM public.providers p
    JOIN public.consultations c ON c.provider_id = p.id
    WHERE p.id = prescriber_provider_id
      AND p.user_id = (SELECT auth.uid ())
      AND c.patient_id = prescriptions.patient_id
      AND c.status <> 'cancelled'
  )
);

CREATE OR REPLACE FUNCTION public.guard_prescription_update ()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  IF NOT public.is_backend ()
    AND (new.patient_id IS DISTINCT FROM old.patient_id
      OR new.prescriber_provider_id IS DISTINCT FROM old.prescriber_provider_id) THEN
    RAISE EXCEPTION 'a prescription cannot be moved to another patient or prescriber' USING ERRCODE = '42501';
  END IF;
  RETURN new;
END;
$$;

DROP TRIGGER IF EXISTS prescriptions_guard_update ON public.prescriptions;
CREATE TRIGGER prescriptions_guard_update
BEFORE UPDATE ON public.prescriptions FOR EACH ROW
EXECUTE PROCEDURE public.guard_prescription_update ();

REVOKE DELETE ON public.prescriptions FROM authenticated, anon;

-- ---------------------------------------------------------------------------
-- pharmacy orders: request against your own prescription; afterwards only cancel
-- ---------------------------------------------------------------------------
DROP POLICY IF EXISTS "pharmacy_orders_rw_own" ON public.pharmacy_orders;
DROP POLICY IF EXISTS "pharmacy_orders_select_own" ON public.pharmacy_orders;
DROP POLICY IF EXISTS "pharmacy_orders_insert_own" ON public.pharmacy_orders;
DROP POLICY IF EXISTS "pharmacy_orders_update_own" ON public.pharmacy_orders;

CREATE POLICY "pharmacy_orders_select_own" ON public.pharmacy_orders FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid ()));

CREATE POLICY "pharmacy_orders_insert_own" ON public.pharmacy_orders FOR INSERT TO authenticated WITH CHECK (
  user_id = (SELECT auth.uid ())
  AND status = 'requested'
  AND (
    prescription_id IS NULL
    OR EXISTS (
      SELECT 1 FROM public.prescriptions rx
      WHERE rx.id = pharmacy_orders.prescription_id AND rx.patient_id = (SELECT auth.uid ())
    )
  )
);

CREATE POLICY "pharmacy_orders_update_own" ON public.pharmacy_orders FOR UPDATE TO authenticated USING (user_id = (SELECT auth.uid ()))
WITH CHECK (user_id = (SELECT auth.uid ()));

CREATE OR REPLACE FUNCTION public.guard_pharmacy_order_update ()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  IF public.is_backend () THEN
    RETURN new;
  END IF;
  IF (to_jsonb(new) - 'status' - 'updated_at') IS DISTINCT FROM (to_jsonb(old) - 'status' - 'updated_at')
    OR NOT (new.status = old.status OR (old.status = 'requested' AND new.status = 'cancelled')) THEN
    RAISE EXCEPTION 'an order can only be cancelled while it is requested' USING ERRCODE = '42501';
  END IF;
  RETURN new;
END;
$$;

DROP TRIGGER IF EXISTS pharmacy_orders_guard_update ON public.pharmacy_orders;
CREATE TRIGGER pharmacy_orders_guard_update
BEFORE UPDATE ON public.pharmacy_orders FOR EACH ROW
EXECUTE PROCEDURE public.guard_pharmacy_order_update ();

REVOKE DELETE ON public.pharmacy_orders FROM authenticated, anon;

-- ---------------------------------------------------------------------------
-- SOS log: the owner may add and close an alert, not erase or rewrite it
-- ---------------------------------------------------------------------------
DROP POLICY IF EXISTS "emergency_alerts_rw_own" ON public.emergency_alerts;
DROP POLICY IF EXISTS "emergency_alerts_select_own" ON public.emergency_alerts;
DROP POLICY IF EXISTS "emergency_alerts_insert_own" ON public.emergency_alerts;
DROP POLICY IF EXISTS "emergency_alerts_update_own" ON public.emergency_alerts;

CREATE POLICY "emergency_alerts_select_own" ON public.emergency_alerts FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid ()));
CREATE POLICY "emergency_alerts_insert_own" ON public.emergency_alerts FOR INSERT TO authenticated WITH CHECK (
  user_id = (SELECT auth.uid ()) AND status = 'active'
);
CREATE POLICY "emergency_alerts_update_own" ON public.emergency_alerts FOR UPDATE TO authenticated USING (user_id = (SELECT auth.uid ()))
WITH CHECK (user_id = (SELECT auth.uid ()));

REVOKE DELETE ON public.emergency_alerts FROM authenticated, anon;
REVOKE UPDATE ON public.emergency_alerts FROM authenticated, anon;
GRANT UPDATE (status, ended_at) ON public.emergency_alerts TO authenticated;

-- ---------------------------------------------------------------------------
-- Nothing in this app is for signed-out visitors.
-- ---------------------------------------------------------------------------
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon;
