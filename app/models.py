from datetime import datetime, date, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
    email: Optional[str] = Field(default=None, index=True, sa_column_kwargs={"unique": True})
    password_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: Optional[datetime] = None


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


class PhysicalSkull(SQLModel, table=True):
    """
    Fiziksel SkullMod objesi.
    NFC tag kullanıcıya değil bu objeye aittir; sahiplik claim sonrası oluşur.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_code: str = Field(index=True, sa_column_kwargs={"unique": True})
    public_token: str = Field(index=True, sa_column_kwargs={"unique": True})
    claim_token: str = Field(index=True, sa_column_kwargs={"unique": True})
    claim_status: str = Field(default="unclaimed", index=True)
    owner_user_id: Optional[str] = Field(
        default=None,
        foreign_key="user.user_id",
        index=True,
    )
    created_at: datetime = Field(default_factory=utc_now)
    claimed_at: Optional[datetime] = None
    last_scanned_at: Optional[datetime] = None
    scan_count: int = 0
    notes: Optional[str] = None
    production_batch: Optional[str] = Field(default=None, index=True)
    artifact_type: Optional[str] = None
    artifact_series: Optional[str] = None
    edition_number: Optional[str] = None
    first_words: Optional[str] = None
    certificate_code: Optional[str] = Field(default=None, index=True)
    production_notes: Optional[str] = None
    material_type: Optional[str] = None
    visual_theme: Optional[str] = None
    is_limited_edition: bool = False
    premium_content_unlocked: bool = False
    is_active: bool = True


class NFCScanLog(SQLModel, table=True):
    """
    NFC tarama ve claim olayları.
    İlk sürümde lokasyon tutmuyoruz; IP/user-agent ileride anomali tespiti için yeterli temel sağlar.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_id: Optional[int] = Field(
        default=None,
        foreign_key="physicalskull.id",
        index=True,
    )
    user_id: Optional[str] = Field(default=None, foreign_key="user.user_id", index=True)
    scanned_at: datetime = Field(default_factory=utc_now, index=True)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    event_type: str = Field(index=True)
    notes: Optional[str] = None
