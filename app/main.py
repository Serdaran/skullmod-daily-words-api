from datetime import date
import json
import uuid

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from .config import settings
from .db import init_db
from .models import User
from .schemas import RegisterRequest, RegisterResponse, DailyWordsResponse
from .auth import create_token, get_current_user_id
from .deps import get_db
from .services.words_engine import build_cornerstone_pool, get_or_create_daily_words


app = FastAPI(
    title="SkullMod Daily Words API",
    version="1.0.0",
    description="SkullMod – Günlük 2 Kelime üretim servisi"
)

# CORS (ileride mobil / web istemciler için rahatlık)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Uygulama ayağa kalkarken DB tablolarını oluştur."""
    init_db()


@app.get("/")
def root():
    return {"status": "ok", "app": "SkullMod Daily Words API"}


@app.post("/api/v1/register", response_model=RegisterResponse)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Kullanıcı kaydı:
    - Kişisel cornerstone_pool oluşturulur
    - DB'ye kaydedilir
    - JWT token döner
    """
    user_id = str(uuid.uuid4())

    pool = build_cornerstone_pool(
        payload.first_name,
        payload.last_name,
        payload.birth_date,
        payload.birth_place,
    )
    pool_json = json.dumps(pool, ensure_ascii=False)

    user = User(
        user_id=user_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        birth_date=payload.birth_date,
        birth_place=payload.birth_place,
        cornerstone_pool=pool_json,
    )
    db.add(user)
    db.commit()

    token = create_token(user_id)

    return RegisterResponse(
        success=True,
        token=token,
        user_id=user_id,
    )


@app.get("/api/v1/daily-words", response_model=DailyWordsResponse)
def daily_words(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Günlük 2 kelime + motto:
    - Aynı gün + aynı kullanıcı için cache (DailyWord tablosu)
    """
    user = db.exec(select(User).where(User.user_id == current_user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.cornerstone_pool:
        return DailyWordsResponse(
            success=False,
            error="Kullanıcının köşe taşı havuzu bulunamadı. Lütfen profilinizi kontrol edin."
        )

    today = date.today()
    word1, word2, motto = get_or_create_daily_words(db, user, today)

    return DailyWordsResponse(
        success=True,
        data={
            "word1": word1,
            "word2": word2,
            "motto": motto,
            "date": today.isoformat()
        }
    )

