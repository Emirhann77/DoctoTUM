-- Symptom catalog for the symptom check (check.html). Slugs must match the keys of
-- "symptoms" in public/data/care_rules.json. Run after 20260502130000_symptoms_and_health_summary.sql
INSERT INTO
  public.symptom_definitions (slug, label)
VALUES
  ('sore_throat', 'Sore throat'),
  ('stomach_pain', 'Stomach pain'),
  ('back_pain', 'Back pain'),
  ('joint_pain', 'Joint pain'),
  ('dizziness', 'Dizziness'),
  ('ear_pain', 'Ear pain'),
  ('rash', 'Rash'),
  ('itching', 'Itching'),
  ('palpitations', 'Racing heart'),
  ('anxiety', 'Anxiety'),
  ('low_mood', 'Low mood'),
  ('insomnia', 'Trouble sleeping')
ON CONFLICT (slug) DO NOTHING;
