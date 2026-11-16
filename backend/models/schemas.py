from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints, model_validator
from typing_extensions import Annotated

MedicationName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]

# ---------------------------------------------------------------------------
# Doctors
# ---------------------------------------------------------------------------


class Specialist(BaseModel):
    id: str
    name: str
    specialty: str
    location: str = ""
    country: Optional[str] = None
    languages: List[str] = Field(default_factory=list)
    is_available: bool = True
    years_experience: Optional[int] = None
    image_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------


class AppointmentCreateRequest(BaseModel):
    specialist_id: str = Field(..., min_length=1, max_length=64)
    start_time: datetime
    reason: Optional[str] = Field(default=None, max_length=500)


class Appointment(BaseModel):
    id: str
    specialist_id: Optional[str] = None
    specialist_name: Optional[str] = None
    specialty: Optional[str] = None
    start_time: datetime
    status: str = "booked"
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Prescriptions and pharmacy
# ---------------------------------------------------------------------------


class Prescription(BaseModel):
    id: str
    medication: str
    dosage: Optional[str] = None
    instructions: Optional[str] = None
    prescribed_by: Optional[str] = None
    status: str = "issued"
    created_at: datetime


class PharmacyOrderItem(BaseModel):
    medication_name: MedicationName
    prescription_id: Optional[str] = Field(default=None, max_length=64)
    quantity: int = Field(default=1, ge=1, le=10)
    notes: Optional[str] = Field(default=None, max_length=300)


class PharmacyOrderCreateRequest(BaseModel):
    items: List[PharmacyOrderItem] = Field(..., min_length=1, max_length=10)


class PharmacyOrder(BaseModel):
    id: str
    medication_name: str
    quantity: int = 1
    status: str = "requested"
    prescription_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Emergency
# ---------------------------------------------------------------------------


class CareLocation(BaseModel):
    country: Optional[str] = Field(default=None, max_length=80)
    city: Optional[str] = Field(default=None, max_length=80)
    postalCode: Optional[str] = Field(default=None, max_length=20)


class EmergencyStartRequest(BaseModel):
    symptoms: Optional[str] = Field(default=None, max_length=1000)
    preferred_language: Optional[str] = Field(default=None, max_length=8)
    location: Optional[CareLocation] = None


class EmergencyAlert(BaseModel):
    alert_id: str
    status: str = Field(..., description="active | cancelled | resolved")
    created_at: datetime
    # This service records the alert. It does not contact emergency services.
    dispatched: bool = False
    emergency_number: str = "112"


class EmergencyEndRequest(BaseModel):
    alert_id: str = Field(..., min_length=1, max_length=64)


# ---------------------------------------------------------------------------
# AI assistant
# ---------------------------------------------------------------------------


class AIChatRequest(BaseModel):
    user_message: str = Field(..., min_length=1, max_length=2000)
    # Sent by public/js/api.js from CarePrefs; the reply is written in this language.
    language: Optional[str] = Field(default=None, max_length=8)


class AIChatResponse(BaseModel):
    risk_level: str = Field(..., description="low | medium | high")
    message: str
    recommendation: str = Field(..., description="book_appointment | emergency | self_monitor")


class TriageRequest(BaseModel):
    symptoms: str = Field(..., min_length=1, max_length=2000)
    age: int = Field(..., ge=0, le=130)
    known_conditions: List[str] = Field(default_factory=list, max_length=20)
    duration: str = Field(..., min_length=1, max_length=40)


class TriageResponse(BaseModel):
    risk_level: str = Field(..., description="low | medium | high")
    summary: str
    recommendation: str = Field(..., description="book_appointment | emergency | self_monitor")
    suggested_specialist: str


# ---------------------------------------------------------------------------
# Care Navigator
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class Me(BaseModel):
    id: str
    email: Optional[str] = None
    display_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Plans (simulated billing)
# ---------------------------------------------------------------------------


class Plan(BaseModel):
    slug: str
    name: str
    price_cents_monthly: int
    features: List[str] = Field(default_factory=list)


class PlanChooseRequest(BaseModel):
    slug: str = Field(..., pattern=r"^[a-z0-9_-]{1,40}$")


class PlanChoice(BaseModel):
    plan: Plan
    charged: bool = False
