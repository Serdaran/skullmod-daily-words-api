from datetime import datetime, date
from typing import Optional
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    """
    Kullanıcı profili tablosu:
    - user_id: UUID string (primary key)
    - cornerstone_pool: JSON string olarak saklanan kelime listesi
    """
    user_id: str = Field(default=None, primary_key=True)
    first_name: str
    last_name: str
    birth_date: datetime
    birth_place: str
    cornerstone_pool: str  # JSON string (list[str])


class DailyWord(SQLModel, table=True):
    """
    Günlük üretilen 2 kelime + motto kaydı.
    Aynı user_id + date için tek satır (cache/log işlevi).
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.user_id")
    date: date
    word1: str
    word2: str
    motto: str

