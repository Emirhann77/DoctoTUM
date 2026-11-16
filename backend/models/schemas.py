from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class Specialist(BaseModel):
    id: int
    name: str
    specialty: str
    location: str
    languages: List[str] = Field(default_factory=list)
    is_available: bool = True


class AppointmentCreateRequest(BaseModel):
    user_id: int
    specialist_id: int
    start_time: datetime
    reason: Optional[str] = None


class Appointment(BaseModel):
    id: str
    user_id: int
    specialist_id: int
    start_time: datetime
    status: str = "booked"
    reason: Optional[str] = None


class EmergencyStartRequest(BaseModel):
    user_id: int
    symptoms: Optional[str] = None


class EmergencySession(BaseModel):
    session_id: str
    doctor_id: int
    status: str = "waiting"
    estimated_wait_minutes: int = 2
    video_url: str


class EmergencyEndRequest(BaseModel):
    session_id: str


class AIChatRequest(BaseModel):
    user_message: str = Field(..., min_length=1)
    user_id: Optional[int] = None
    # Sent by public/js/api.js from CarePrefs; the reply is written in this language.
    language: Optional[str] = Field(default=None, max_length=8)


class AIChatResponse(BaseModel):
    risk_level: str = Field(..., description="low | medium | high")
    message: str
    recommendation: str = Field(..., description="book_appointment | emergency | self_monitor")


class TriageRequest(BaseModel):
    symptoms: str = Field(..., min_length=1)
    age: int = Field(..., ge=0, le=130)
    known_conditions: List[str] = Field(default_factory=list)
    duration: str = Field(..., min_length=1)


class TriageResponse(BaseModel):
    risk_level: str = Field(..., description="low | medium | high")
    summary: str
    recommendation: str = Field(..., description="book_appointment | emergency | self_monitor")
    suggested_specialist: str


class SummarizeSymptomsRequest(BaseModel):
    symptoms: str = Field(..., min_length=1)
    user_id: Optional[int] = None


class SummarizeSymptomsResponse(BaseModel):
    summary: str
    risk_level: str = Field(..., description="low | medium | high")
    recommendation: str = Field(..., description="book_appointment | emergency | self_monitor")


class Prescription(BaseModel):
    id: str
    user_id: int
    medication: str
    dosage: str
    instructions: str
    prescribed_by: str
    created_at: datetime


class PrescriptionCreateRequest(BaseModel):
    user_id: int
    medication: str = Field(..., min_length=1)
    dosage: str = Field(..., min_length=1)
    instructions: str = Field(..., min_length=1)
    prescribed_by: str = Field(..., min_length=1)



class CareLocation(BaseModel):
    country: Optional[str] = None
    city: Optional[str] = None
    postalCode: Optional[str] = None


class CareNavigateRequest(BaseModel):
    symptoms: List[str] = Field(default_factory=list, max_length=20)
    description: str = Field(default="", max_length=2000)
    severity: int = Field(..., ge=1, le=10)
    duration: Literal["today", "days_1_3", "days_4_7", "over_week"]
    age: int = Field(..., ge=0, le=130)
    known_conditions: List[str] = Field(default_factory=list, max_length=20)
    language: Optional[str] = Field(default=None, max_length=8)
    preferred_consult_language: Optional[str] = Field(default=None, max_length=8)
    location: Optional[CareLocation] = None

    @model_validator(mode="after")
    def _needs_something_to_assess(self) -> "CareNavigateRequest":
        if not any(s.strip() for s in self.symptoms) and not self.description.strip():
            raise ValueError("Provide at least one symptom or a description")
        return self


class SpecialistMatch(BaseModel):
    specialist: Specialist
    score: int
    reasons: List[str] = Field(
        default_factory=list, description="specialty | language | available | nearby"
    )


class CareNavigateResponse(BaseModel):
    urgency: str = Field(..., description="emergency | urgent | routine | self_care")
    risk_level: str = Field(..., description="low | medium | high")
    specialty_slug: str
    recommended_specialty: str
    reasons: List[str] = Field(default_factory=list, description="Rule codes; localized by the client")
    red_flags: List[str] = Field(default_factory=list)
    self_care: List[str] = Field(default_factory=list, description="Tip codes; localized by the client")
    match_language: Optional[str] = None
    matches: List[SpecialistMatch] = Field(default_factory=list)
