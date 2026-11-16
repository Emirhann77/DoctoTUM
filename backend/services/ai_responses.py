"""
AI assistant: uses OpenAI when OPENAI_API_KEY is set; otherwise deterministic mock triage/chat.
"""

from __future__ import annotations

import os
import random
import re
from typing import Optional

import httpx

from backend.models.schemas import AIChatResponse, TriageResponse
from backend.utils import safety


_REPLY_LANGUAGES = {"en": "English", "de": "German", "tr": "Turkish", "es": "Spanish", "fr": "French"}


def _openai_chat_completion(user_message: str, language: Optional[str] = None) -> Optional[str]:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    try:
        with httpx.Client(timeout=45.0) as client:
            r = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a cautious medical triage assistant for a telehealth app. "
                                "Do not diagnose. Give short, clear guidance. "
                                "If symptoms sound severe or emergency-like, tell the user to seek urgent care."
                                + (
                                    f" Reply in {_REPLY_LANGUAGES[language]}."
                                    if language in _REPLY_LANGUAGES
                                    else ""
                                )
                            ),
                        },
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": 350,
                    "temperature": 0.3,
                },
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _mock_chat_reply(user_message: str) -> AIChatResponse:
    er = safety.check_emergency_symptoms(user_message)
    if er.is_emergency:
        em = safety.emergency_message()
        return AIChatResponse(
            risk_level=em["risk_level"],
            message=em["message"],
            recommendation=em["recommendation"],
        )

    lower = user_message.lower()
    disclaimer = safety.safety_disclaimer()

    if any(k in lower for k in ("cough", "fever", "cold", "flu")):
        return AIChatResponse(
            risk_level="medium",
            message=(
                f"{disclaimer} Respiratory symptoms can have many causes. Rest, fluids, and monitoring "
                "temperature can help. If breathing becomes difficult or fever is very high or prolonged, "
                "contact a clinician or urgent care."
            ),
            recommendation="book_appointment",
        )
    if any(k in lower for k in ("headache", "migraine", "dizzy")):
        return AIChatResponse(
            risk_level="low",
            message=(
                f"{disclaimer} For mild headaches, hydration, rest, and a dark quiet room often help. "
                "Seek care if the headache is sudden and severe or comes with neurological symptoms."
            ),
            recommendation="self_monitor",
        )
    if any(k in lower for k in ("rash", "skin", "itch")):
        return AIChatResponse(
            risk_level="low",
            message=(
                f"{disclaimer} Skin changes are easier to assess with a photo in a consult. "
                "Avoid scratching; note if it spreads quickly or you have fever."
            ),
            recommendation="book_appointment",
        )

    fallbacks = [
        f"{disclaimer} Thanks for sharing. Could you add when this started and how severe it is (0–10)?",
        f"{disclaimer} I noted your message. Any fever, shortness of breath, or chest pain?",
        f"{disclaimer} If symptoms are stable, scheduling a virtual visit can help narrow next steps.",
    ]
    return AIChatResponse(
        risk_level="low",
        message=random.choice(fallbacks),
        recommendation="book_appointment",
    )


def chat(user_message: str, user_id: Optional[int], language: Optional[str] = None) -> AIChatResponse:
    er = safety.check_emergency_symptoms(user_message)
    if er.is_emergency:
        em = safety.emergency_message()
        return AIChatResponse(
            risk_level=em["risk_level"],
            message=em["message"],
            recommendation=em["recommendation"],
        )

    live = _openai_chat_completion(user_message, language)
    if live:
        lower = user_message.lower()
        if any(w in lower for w in ("chest", "breath", "severe", "fever", "bleed", "suicid")):
            risk = "medium"
            rec = "book_appointment"
        else:
            risk = "low"
            rec = "self_monitor"
        return AIChatResponse(risk_level=risk, message=live, recommendation=rec)
    return _mock_chat_reply(user_message)


def triage(
    symptoms: str,
    age: int,
    known_conditions: list[str],
    duration: str,
) -> TriageResponse:
    text = f"{symptoms} age {age} conditions {known_conditions} duration {duration}"
    er = safety.check_emergency_symptoms(text)
    if er.is_emergency:
        return TriageResponse(
            risk_level="high",
            summary="Possible emergency pattern detected from symptoms.",
            recommendation="emergency",
            suggested_specialist="Emergency Medicine",
        )

    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if key:
        prompt = (
            f"Patient age {age}. Symptoms: {symptoms}. Known conditions: {known_conditions}. "
            f"Duration: {duration}. Respond in 3 short lines: summary, risk (low/medium/high), "
            f"recommended specialty (one phrase)."
        )
        live = _openai_chat_completion(prompt)
        if live:
            risk = "medium"
            if re.search(r"\bhigh\b", live, re.I):
                risk = "high"
            elif re.search(r"\blow\b", live, re.I):
                risk = "low"
            spec = "General Practitioner"
            for line in live.splitlines():
                if "specialist" in line.lower() or "specialty" in line.lower():
                    spec = line.split(":")[-1].strip() or spec
            return TriageResponse(
                risk_level=risk if risk in ("low", "medium", "high") else "medium",
                summary=live[:500],
                recommendation="book_appointment" if risk != "high" else "emergency",
                suggested_specialist=spec[:80],
            )

    # Mock triage
    risk = "low"
    if age > 65 or any(c for c in known_conditions if c):
        risk = "medium"
    if len(symptoms) > 120 or "severe" in symptoms.lower():
        risk = "medium"

    return TriageResponse(
        risk_level=risk,
        summary=(
            f"Reported symptoms over ~{duration}. "
            f"{'Known conditions noted; ' if known_conditions else ''}"
            "This is a mock triage without a live model—book a clinician for a real assessment."
        ),
        recommendation="book_appointment" if risk == "low" else "book_appointment",
        suggested_specialist="General Practitioner",
    )
