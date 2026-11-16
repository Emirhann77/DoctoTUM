"""Run from the repo root: python -m pytest backend/tests"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.database import db
from backend.main import app
from backend.services import care_navigator
from backend.utils import safety

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "tests" / "care_rules.cases.json").read_text(encoding="utf-8"))

client = TestClient(app)


@pytest.fixture(autouse=True)
def _mock_mode(monkeypatch):
    for var in ("OPENAI_API_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(var, raising=False)


# --- shared cases: the same file is run against public/js/navigator.js -------------


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_shared_case(case):
    out = care_navigator.evaluate(**case["input"])
    assert out["urgency"] == case["urgency"]
    assert out["specialty_slug"] == case["specialty"]


# --- safety: a missed emergency is the failure that matters ------------------


@pytest.mark.parametrize("phrase", safety.emergency_phrases())
def test_every_emergency_phrase_escalates(phrase):
    text = f"Since this morning: {phrase.upper()} and it is getting worse"
    out = care_navigator.evaluate(["cough"], severity=1, duration="today", age=30, description=text)
    assert out["urgency"] == "emergency"
    assert out["risk_level"] == "high"


def test_frontend_emergency_phrases_match_backend():
    js = (ROOT / "public" / "js" / "api.js").read_text(encoding="utf-8")
    block = re.search(r"const EMERGENCY_PHRASES = \[(.*?)\];", js, re.S).group(1)
    assert tuple(json.loads(f"[{block.rstrip().rstrip(',')}]")) == safety.emergency_phrases()


def test_every_red_flag_symptom_is_an_emergency_at_any_severity():
    rules = care_navigator.load_rules()
    red = [slug for slug, spec in rules["symptoms"].items() if spec.get("red_flag")]
    assert red
    for slug in red:
        for severity in (1, 10):
            assert care_navigator.evaluate([slug], severity, "today", 30)["urgency"] == "emergency"


def test_self_care_only_from_explicitly_safe_symptoms():
    rules = care_navigator.load_rules()
    for slug, spec in rules["symptoms"].items():
        out = care_navigator.evaluate([slug], severity=1, duration="today", age=30)
        assert (out["urgency"] == "self_care") == bool(spec.get("self_care_ok"))


def test_emergency_gives_no_self_care_tips():
    out = care_navigator.evaluate(["fever", "chest_pain"], 2, "today", 30)
    assert out["self_care"] == []


# --- matching ---------------------------------------------------------------


def test_language_match_outranks_availability_alone():
    ranked = care_navigator.rank_specialists(db.list_specialists(), "general", language="tr", city="Garching")
    assert ranked[0]["specialist"].name == "Dr. Ayşe Yılmaz"
    assert "language" in ranked[0]["reasons"]


def test_emergency_doctors_are_never_offered_for_booking():
    for slug in ("general", "cardiology", "mental_health"):
        ranked = care_navigator.rank_specialists(db.list_specialists(), slug, language="tr", limit=10)
        assert all(m["specialist"].specialty != "Emergency Medicine" for m in ranked)


def test_gp_stands_in_but_ranks_below_the_specialist():
    ranked = care_navigator.rank_specialists(db.list_specialists(), "dermatology", language="en", limit=10)
    assert ranked[0]["specialist"].specialty == "Dermatology"
    assert {m["specialist"].specialty for m in ranked} == {"Dermatology", "General Practitioner"}


# --- HTTP -------------------------------------------------------------------


def _body(**over):
    base = {"symptoms": ["low_mood"], "severity": 4, "duration": "over_week", "age": 23}
    return {**base, **over}


def test_navigate_matches_on_preferred_consult_language():
    r = client.post("/api/care/navigate", json=_body(language="en", preferred_consult_language="es"))
    assert r.status_code == 200
    data = r.json()
    assert data["urgency"] == "routine"
    assert data["specialty_slug"] == "mental_health"
    assert data["match_language"] == "es"
    assert data["matches"][0]["specialist"]["name"] == "Dr. Lucía Fernández"
    assert {"specialty", "language"} <= set(data["matches"][0]["reasons"])


def test_navigate_emergency_returns_no_bookable_matches():
    r = client.post("/api/care/navigate", json=_body(symptoms=[], description="Ich habe Atemnot"))
    assert r.json()["urgency"] == "emergency"
    assert r.json()["matches"] == []


@pytest.mark.parametrize(
    "over",
    [
        {"symptoms": [], "description": "  "},
        {"severity": 0},
        {"severity": 11},
        {"duration": "forever"},
        {"age": -1},
    ],
)
def test_navigate_rejects_invalid_input(over):
    assert client.post("/api/care/navigate", json=_body(**over)).status_code == 422


def test_can_book_the_matched_specialist():
    match = client.post("/api/care/navigate", json=_body()).json()["matches"][0]
    r = client.post(
        "/api/appointments",
        json={
            "user_id": 1,
            "specialist_id": match["specialist"]["id"],
            "start_time": "2026-12-01T09:00:00Z",
            "reason": "Symptom check: low mood",
        },
    )
    assert r.status_code == 200
    assert r.json()["reason"] == "Symptom check: low mood"


def test_rules_endpoint_serves_the_shared_file():
    assert client.get("/api/care/rules").json() == care_navigator.load_rules()
