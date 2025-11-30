from datetime import datetime, date
from typing import Optional, Dict, Any
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    birth_date: datetime
    birth_place: str


class RegisterResponse(BaseModel):
    success: bool
    token: str
    user_id: str


class DailyWordsResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

