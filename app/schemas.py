from datetime import datetime, date
from typing import Optional, Dict, Any
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    birth_date: datetime
    birth_place: str
    email: Optional[str] = None
    password: Optional[str] = None


class RegisterResponse(BaseModel):
    success: bool
    token: str
    user_id: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfilePasswordResetRequest(BaseModel):
    email: str
    birth_date: datetime
    birth_place: str
    new_password: str


class AuthResponse(BaseModel):
    success: bool
    token: str
    user_id: str


class BasicResponse(BaseModel):
    success: bool
    message: Optional[str] = None


class DailyWordsResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class NFCStatusResponse(BaseModel):
    valid: bool
    artifact_code: Optional[str] = None
    claim_status: Optional[str] = None
    requires_auth: bool = True
    owner_match: Optional[bool] = None
    is_active: Optional[bool] = None
    message: Optional[str] = None


class NFCClaimResponse(BaseModel):
    success: bool
    artifact_code: Optional[str] = None
    claim_status: Optional[str] = None
    message: Optional[str] = None


class PhysicalSkullSummary(BaseModel):
    artifact_code: str
    claim_status: str
    claimed_at: Optional[datetime] = None
    production_batch: Optional[str] = None
    artifact_type: Optional[str] = None
    artifact_series: Optional[str] = None
    edition_number: Optional[str] = None
    certificate_code: Optional[str] = None
    material_type: Optional[str] = None
    visual_theme: Optional[str] = None
    is_limited_edition: bool = False
    premium_content_unlocked: bool = False
