from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


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

