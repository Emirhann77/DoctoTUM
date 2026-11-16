"""
Care Navigator: turns a structured symptom check into a care path
(emergency / urgent / routine / self_care), a specialty, and a ranked list of
specialists who match the patient's language and location.

Deterministic on purpose. No model call can change the urgency: the rules live in
public/data/care_rules.json (also read by public/js/navigator.js, the offline
fallback), and the shared cases in tests/care_rules.cases.json are run against both implementations.

Fail-safe direction: anything the rules do not recognise is routed to a clinician,
never to self-care.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

from backend.models.schemas import Specialist
from backend.utils import safety

RULES_PATH = Path(__file__).resolve().parents[2] / "public" / "data" / "care_rules.json"

URGENCY_RISK = {"emergency": "high", "urgent": "medium", "routine": "low", "self_care": "low"}

SPECIALTY_NAMES = {
    "general": "General Practitioner",
    "cardiology": "Cardiology",
    "dermatology": "Dermatology",
    "pediatrics": "Pediatrics",
    "mental_health": "Mental Health",
    "emergency": "Emergency Medicine",
}

_LANGUAGE_CODES = {
    "english": "en",
    "german": "de",
    "turkish": "tr",
    "spanish": "es",
    "french": "fr",
}


@lru_cache(maxsize=1)
def load_rules() -> dict[str, Any]:
    with RULES_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def evaluate(
    symptoms: Iterable[str],
    severity: int,
    duration: str,
    age: int,
    description: str = "",
    known_conditions: Iterable[str] = (),
) -> dict[str, Any]:
    """Pure function: same inputs, same care path. Mirrors CareNavigator.evaluate in public/js/navigator.js."""
    rules = load_rules()
    catalog: dict[str, dict[str, Any]] = rules["symptoms"]
    th = rules["thresholds"]

    slugs = [s for s in dict.fromkeys(symptoms) if s]
    known = [s for s in slugs if s in catalog]
    has_unknown = len(known) != len(slugs)
    conditions = safety.normalize_conditions(known_conditions)

    red_flags = [s for s in known if catalog[s].get("red_flag")]
    phrase_hits = list(safety.check_emergency_symptoms(description).matched)

    if red_flags or phrase_hits:
        reasons = []
        if red_flags:
            reasons.append("red_flag_symptom")
        if phrase_hits:
            reasons.append("emergency_phrase")
        return _result("emergency", "emergency", reasons, red_flags, [])

    long_lasting = duration in ("days_4_7", "over_week")
    higher_risk_group = age < th["infant_age"] or age >= th["senior_age"] or bool(conditions)

    urgent: list[str] = []
    if severity >= th["urgent_severity"]:
        urgent.append("high_severity")
    if age < th["infant_age"] and "fever" in known:
        urgent.append("infant_fever")
    if "fever" in known and long_lasting:
        urgent.append("prolonged_fever")
    if age >= th["senior_age"] and severity >= th["elevated_risk_severity"]:
        urgent.append("senior_moderate")
    if conditions and severity >= th["elevated_risk_severity"]:
        urgent.append("conditions_moderate")

    routine: list[str] = []
    if severity >= th["moderate_severity"]:
        routine.append("moderate_severity")
    if long_lasting:
        routine.append("persistent")
    if not known or has_unknown or any(not catalog[s].get("self_care_ok") for s in known):
        routine.append("needs_assessment")
    if higher_risk_group:
        routine.append("higher_risk_group")

    if urgent:
        urgency, reasons = "urgent", urgent
    elif routine:
        urgency, reasons = "routine", routine
    else:
        urgency, reasons = "self_care", ["mild_short"]

    tips: list[str] = []
    for s in known:
        for tip in catalog[s].get("tips", []):
            if tip not in tips:
                tips.append(tip)

    return _result(urgency, _pick_specialty(known, catalog, age, th), reasons, [], tips[:4])


def _pick_specialty(known: list[str], catalog: dict[str, Any], age: int, th: dict[str, int]) -> str:
    if age < th["child_age"]:
        return "pediatrics"
    votes: dict[str, int] = {}
    for s in known:
        spec = catalog[s]["specialty"]
        votes[spec] = votes.get(spec, 0) + 1
    if not votes:
        return "general"
    top = max(votes.values())
    winners = [spec for spec, n in votes.items() if n == top]
    return winners[0] if len(winners) == 1 else "general"


def _result(urgency: str, specialty: str, reasons: list[str], red_flags: list[str], tips: list[str]) -> dict[str, Any]:
    return {
        "urgency": urgency,
        "risk_level": URGENCY_RISK[urgency],
        "specialty_slug": specialty,
        "recommended_specialty": SPECIALTY_NAMES[specialty],
        "reasons": reasons,
        "red_flags": red_flags,
        "self_care": tips,
    }


# ---------------------------------------------------------------------------
# Specialist matching
# ---------------------------------------------------------------------------


def specialty_slug(name: Optional[str]) -> str:
    """Mirrors slugFromSpecialtyName in public/js/doctors.js."""
    s = (name or "").lower()
    if "emergency" in s:
        return "emergency"
    if "mental" in s or "psychiat" in s or "psycholog" in s:
        return "mental_health"
    if "cardio" in s:
        return "cardiology"
    if "derma" in s:
        return "dermatology"
    if "pediatr" in s or "paediatr" in s:
        return "pediatrics"
    return "general"


def language_codes(labels: Iterable[str]) -> list[str]:
    out: list[str] = []
    for label in labels:
        low = (label or "").strip().lower()
        code = _LANGUAGE_CODES.get(low) or (low if low in _LANGUAGE_CODES.values() else None)
        if code and code not in out:
            out.append(code)
    return out


def rank_specialists(
    specialists: Iterable[Specialist],
    specialty: str,
    language: str = "",
    city: str = "",
    limit: int = 3,
) -> list[dict[str, Any]]:
    """
    Score = specialty fit (40, or 15 for a GP standing in) + speaks the patient's
    language (30) + available now (20) + same city (10). A specialist with no
    specialty fit is not offered at all.
    """
    lang = (language or "").strip().lower()
    city_l = (city or "").strip().lower()
    ranked: list[dict[str, Any]] = []
    for sp in specialists:
        slug = specialty_slug(sp.specialty)
        if slug == "emergency":
            continue  # emergency doctors are reached through SOS, not booking
        reasons: list[str] = []
        score = 0
        if slug == specialty:
            score += 40
            reasons.append("specialty")
        elif slug == "general":
            score += 15
        else:
            continue
        if lang and lang in language_codes(sp.languages):
            score += 30
            reasons.append("language")
        if sp.is_available:
            score += 20
            reasons.append("available")
        if city_l and city_l == (sp.location or "").strip().lower():
            score += 10
            reasons.append("nearby")
        ranked.append({"specialist": sp, "score": score, "reasons": reasons})
    ranked.sort(key=lambda m: (-m["score"], m["specialist"].name))
    return ranked[:limit]
