from datetime import date
import json
import uuid
import random  # 🔥 astro tabanlı günlük enerji için

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


# ----------------------------------------------------
# ASTRO TABANLI KİŞİSEL "GÜNLÜK ENERJİ" ALGORİTMASI
# ----------------------------------------------------

ENERGY_WORDS_BY_ELEMENT = {
    "fire": [
        "Atılım",
        "Cesaret",
        "Tutku",
        "Kıvılcım",
        "Aksiyon",
        "Yeniden Doğuş",
        "Gözükaralık",
        "Motivasyon",
    ],
    "earth": [
        "Toplanma",
        "Köklenme",
        "Sabır",
        "İstikrar",
        "Dayanıklılık",
        "Planlama",
        "Somutlaşma",
        "Denge",
    ],
    "air": [
        "İlham",
        "Merak",
        "Fikir",
        "İletişim",
        "Bağlantı",
        "Öğrenme",
        "Bakış Açısı",
        "Netlik",
    ],
    "water": [
        "Şifa",
        "Akış",
        "Duyarlılık",
        "Arınma",
        "Empati",
        "Kabulleniş",
        "Derinleşme",
        "Sakinleşme",
    ],
}

ELEMENT_LABEL_TR = {
    "fire": "ateş",
    "earth": "toprak",
    "air": "hava",
    "water": "su",
}


def get_zodiac_element_from_birth(birth_dt) -> str:
    """
    Kullanıcının doğum tarihinden (datetime veya date) zodyak elementini çıkarır.
    Element: fire / earth / air / water
    """
    if birth_dt is None:
        return "earth"  # default, nötr

    # datetime ise .date() ile sadeleştir
    if hasattr(birth_dt, "date"):
        birth_dt = birth_dt.date()

    m = birth_dt.month
    d = birth_dt.day

    # Koç: 21 Mart – 19 Nisan (ateş)
    if (m == 3 and d >= 21) or (m == 4 and d <= 19):
        return "fire"
    # Boğa: 20 Nisan – 20 Mayıs (toprak)
    if (m == 4 and d >= 20) or (m == 5 and d <= 20):
        return "earth"
    # İkizler: 21 Mayıs – 20 Haziran (hava)
    if (m == 5 and d >= 21) or (m == 6 and d <= 20):
        return "air"
    # Yengeç: 21 Haziran – 22 Temmuz (su)
    if (m == 6 and d >= 21) or (m == 7 and d <= 22):
        return "water"
    # Aslan: 23 Temmuz – 22 Ağustos (ateş)
    if (m == 7 and d >= 23) or (m == 8 and d <= 22):
        return "fire"
    # Başak: 23 Ağustos – 22 Eylül (toprak)
    if (m == 8 and d >= 23) or (m == 9 and d <= 22):
        return "earth"
    # Terazi: 23 Eylül – 22 Ekim (hava)
    if (m == 9 and d >= 23) or (m == 10 and d <= 22):
        return "air"
    # Akrep: 23 Ekim – 21 Kasım (su)
    if (m == 10 and d >= 23) or (m == 11 and d <= 21):
        return "water"
    # Yay: 22 Kasım – 21 Aralık (ateş)
    if (m == 11 and d >= 22) or (m == 12 and d <= 21):
        return "fire"
    # Oğlak: 22 Aralık – 19 Ocak (toprak)
    if (m == 12 and d >= 22) or (m == 1 and d <= 19):
        return "earth"
    # Kova: 20 Ocak – 18 Şubat (hava)
    if (m == 1 and d >= 20) or (m == 2 and d <= 18):
        return "air"
    # Balık: 19 Şubat – 20 Mart (su)
    if (m == 2 and d >= 19) or (m == 3 and d <= 20):
        return "water"

    return "earth"


def pick_personal_daily_energy_word(user: User, today: date) -> tuple[str, str]:
    """
    Kullanıcı + tarih + astro element'e göre deterministik bir günlük enerji kelimesi seçer.
    DÖNÜŞ: (energy_word, element_key)
    """
    birth_dt = getattr(user, "birth_date", None)
    element = get_zodiac_element_from_birth(birth_dt)

    words = ENERGY_WORDS_BY_ELEMENT.get(element, ENERGY_WORDS_BY_ELEMENT["earth"])

    # user_id + doğum tarihi + gün bilgisi ile seed oluştur
    user_id_str = getattr(user, "user_id", None) or str(getattr(user, "id", "unknown"))
    birth_str = birth_dt.date().isoformat() if hasattr(birth_dt, "date") else (
        birth_dt.isoformat() if birth_dt else "no-birth"
    )
    seed_str = f"{user_id_str}-{birth_str}-{today.isoformat()}-{element}"

    rnd = random.Random(seed_str)
    index = rnd.randint(0, len(words) - 1)

    return words[index], element


def build_motto(word1: str, energy_word: str, element_key: str) -> str:
    """
    Köşe taşı + günlük enerji + element bilgisine göre motto üretir.
    """
    element_label = ELEMENT_LABEL_TR.get(element_key, "toprak")

    # Birkaç basit şablondan deterministik seçim
    templates = [
        "Bugün {energy} senin {element} enerjini uyandırırken, {corner} pusulan olmaya devam ediyor.",
        "{energy} enerjisi bugün alanında; {corner} ise attığın her adımın merkezinde.",
        "Gökyüzü bugün {element} tınısında: {energy} seni çağırıyor, {corner} rotanı sabitliyor.",
        "Bugünün akışı {energy}; sen {corner} ile kendi hikâyeni yeniden yazıyorsun.",
    ]

    # Kelime kombinasyonuna göre aynı şablonu seçmek için seed
    seed_str = f"{word1}-{energy_word}-{element_key}"
    rnd = random.Random(seed_str)
    idx = rnd.randint(0, len(templates) - 1)

    template = templates[idx]
    return template.format(
        energy=energy_word,
        corner=word1,
        element=element_label,
    )


# ----------------------------------------------------
# KAYIT / REGISTER ENDPOINT
# ----------------------------------------------------


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


# ----------------------------------------------------
# GÜNLÜK KELİMELER ENDPOINT
# ----------------------------------------------------


@app.get("/api/v1/daily-words", response_model=DailyWordsResponse)
def daily_words(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Günlük 2 kelime + motto:
    - Köşe taşı kelimesi (kişisel cornerstone_pool'dan)
    - Günlük enerji kelimesi (kişisel + astro element'e göre)
    - Aynı gün + aynı kullanıcı için sonuç deterministik
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

    # words_engine içindeki mantığı kişisel köşe taşı için kullanmaya devam ediyoruz
    # (word2 ve eski mottoyu artık kullanmıyoruz)
    cornerstone_word, _, _ = get_or_create_daily_words(db, user, today)

    # KİŞİYE ÖZEL GÜNLÜK ENERJİ + MOTTOSU
    energy_word, element_key = pick_personal_daily_energy_word(user, today)
    motto = build_motto(cornerstone_word, energy_word, element_key)

    return DailyWordsResponse(
        success=True,
        data={
            "word1": cornerstone_word,
            "word2": energy_word,
            "motto": motto,
            "date": today.isoformat()
        }
    )
