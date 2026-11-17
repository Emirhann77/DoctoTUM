from __future__ import annotations

import re
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
    "unconscious",
    "not breathing",
    "stopped breathing",
    "seizure",
    "overdose",
    "want to die",
    # --- Multilingual (the UI ships en/de/tr/es/fr; people describe emergencies
    # in their own language). All lowercase. Mirrored in public/js/api.js.
    "suicid",  # suicide / Suizid / suicidio / suicidaire
    # German
    "brustschmerz",
    "druck auf der brust",
    "atemnot",
    "keine luft",
    "bewusstlos",
    "ohnmächtig",
    "schlaganfall",
    "starke blutung",
    "selbstmord",
    "mich umbringen",
    "anaphylaxie",
    "überdosis",
    "krampfanfall",
    # Turkish
    "göğüs ağrısı",
    "göğsümde ağrı",
    "nefes alamıyorum",
    "nefes darlığı",
    "bayıldım",
    "bilinç kaybı",
    "felç",
    "şiddetli kanama",
    "intihar",
    "kendimi öldür",
    "anafilaksi",
    "aşırı doz",
    # Spanish
    "dolor en el pecho",
    "dolor de pecho",
    "no puedo respirar",
    "dificultad para respirar",
    "falta de aire",
    "me desmayé",
    "pérdida de conciencia",
    "derrame cerebral",
    "sangrado abundante",
    "hemorragia grave",
    "anafilaxia",
    "sobredosis",
    "convulsiones",
    # French
    "douleur thoracique",
    "douleur à la poitrine",
    "douleur dans la poitrine",
    "du mal à respirer",
    "pas à respirer",
    "difficulté à respirer",
    "perte de connaissance",
    "évanoui",
    "saignement abondant",
    "hémorragie",
    "choc anaphylactique",
    "surdose",
    "convulsions",
)


def emergency_phrases() -> tuple[str, ...]:
    return _EMERGENCY_PHRASES


_APOSTROPHES = re.compile("[\u2018\u2019\u02bc\u0060\u00b4]")


def fold(text: str) -> str:
    """Case-fold for matching. Turkish I/ı/İ do not round-trip through lower(), so
    "GÖĞÜS AĞRISI" would otherwise miss "göğüs ağrısı". Mirrored in public/js/api.js."""
    folded = text.lower().replace("i\u0307", "i").replace("\u0131", "i")
    # Phone keyboards type a curly apostrophe; it must still match the plain one.
    return _APOSTROPHES.sub("'", folded)


def check_emergency_symptoms(text: Optional[str]) -> SafetyResult:
    if not text:
        return SafetyResult(is_emergency=False, matched=())
    haystack = fold(text)
    matched = tuple(p for p in _EMERGENCY_PHRASES if fold(p) in haystack)
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

