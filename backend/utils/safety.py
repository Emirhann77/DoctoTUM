from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class SafetyResult:
    is_emergency: bool
    matched: tuple[str, ...] = ()


_EMERGENCY_PHRASES: tuple[str, ...] = (
    "chest pain",
    "pressure in my chest",
    "difficulty breathing",
    "can't breathe",
    "cant breathe",
    "shortness of breath",
    "loss of consciousness",
    "passed out",
    "fainted",
    "stroke",
    "face drooping",
    "arm weakness",
    "slurred speech",
    "severe bleeding",
    "bleeding heavily",
    "suicidal",
    "suicidal thoughts",
    "kill myself",
    "self harm",
    "severe allergic reaction",
    "anaphylaxis",
    "swelling of the tongue",
    "swelling of the throat",
)


def check_emergency_symptoms(text: Optional[str]) -> SafetyResult:
    if not text:
        return SafetyResult(is_emergency=False, matched=())
    haystack = text.lower()
    matched = tuple(p for p in _EMERGENCY_PHRASES if p in haystack)
    return SafetyResult(is_emergency=bool(matched), matched=matched)


def safety_disclaimer() -> str:
    return (
        "I can share general health information, but I can’t diagnose conditions. "
        "If symptoms feel severe or rapidly worsening, seek urgent medical care."
    )


def emergency_message() -> dict:
    return {
        "risk_level": "high",
        "message": (
            "Your symptoms may require urgent medical attention. Please contact emergency services "
            "immediately or go to the nearest emergency department."
        ),
        "recommendation": "emergency",
    }


def normalize_conditions(conditions: Iterable[str]) -> list[str]:
    return [c.strip() for c in conditions if c and c.strip()]

