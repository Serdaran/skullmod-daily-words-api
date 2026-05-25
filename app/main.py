from datetime import date, datetime, timezone
from contextlib import asynccontextmanager
import json
import uuid
import random
from typing import Optional

from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update
from sqlmodel import Session, select

from .config import settings
from .db import init_db
from .models import User, PhysicalSkull, NFCScanLog
from .schemas import (
    AuthResponse,
    BasicResponse,
    DailyWordsResponse,
    LoginRequest,
    NFCClaimResponse,
    NFCStatusResponse,
    PhysicalSkullSummary,
    ProfilePasswordResetRequest,
    RegisterRequest,
    RegisterResponse,
)
from .auth import (
    create_token,
    get_current_user_id,
    hash_password,
    parse_token,
    verify_password,
)
from .deps import get_db
from .services.localization import (
    build_localized_motto,
    localize_word,
    normalize_language,
)
from .services.words_engine import build_cornerstone_pool, get_or_create_daily_words


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama ayağa kalkarken DB tablolarını oluştur."""
    init_db()
    yield


app = FastAPI(
    title="SkullMod Daily Words API",
    version="1.0.0",
    description="SkullMod – Günlük 2 Kelime üretim servisi",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "app": "SkullMod Daily Words API"}


def get_optional_user_id(
    authorization: Optional[str] = Header(default=None),
) -> Optional[str]:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    try:
        return parse_token(token)
    except HTTPException:
        return None


def get_client_ip(request: Request) -> Optional[str]:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def log_nfc_scan(
    db: Session,
    artifact: Optional[PhysicalSkull],
    user_id: Optional[str],
    request: Request,
    event_type: str,
    notes: Optional[str] = None,
) -> None:
    db.add(
        NFCScanLog(
            artifact_id=artifact.id if artifact else None,
            user_id=user_id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            event_type=event_type,
            notes=notes,
        )
    )


def normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    return email.strip().lower()


def validate_password(password: Optional[str]) -> None:
    if password is None:
        return
    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Şifre en az 8 karakter olmalıdır.",
        )


def normalize_profile_text(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


# ----------------------------------------------------
# ASTRO TABANLI KİŞİSEL "GÜNLÜK ENERJİ" ALGORİTMASI
# ----------------------------------------------------

ENERGY_WORDS_BY_ELEMENT = {
    "fire": [
        "Atılım", "Cesaret", "Tutku", "Kıvılcım", "Aksiyon",
        "Yeniden Doğuş", "Gözükaralık", "Motivasyon", "Parlama", "İrade",
        "Başlatma", "Sıçrama", "Canlılık", "Risk", "Öncülük",
        "Ateşli Odak", "Kalkış", "Hamle", "Yükseliş", "Diriliş",
        "Karar", "Kazanma", "Kendini Yakma", "Sahne", "Kalp Gücü",
        "Hız", "Meydan Okuma", "Kıvranış", "Alev", "Özgüven",
        "Dürüst Çıkış", "İç Motor", "Tutarlı Hamle", "Kırılma Anı",
        "Cesur İfade", "Enerji Patlaması", "İlk Adım", "Kader Hamlesi",
        "Uyanış", "Ateş Çemberi",
    ],
    "earth": [
        "Toplanma", "Köklenme", "Sabır", "İstikrar", "Dayanıklılık",
        "Planlama", "Somutlaşma", "Denge", "Emek", "Temel",
        "Güven", "Rutin", "Beden", "Bereket", "Sınır",
        "İnşa", "Yavaş Güç", "Olgunlaşma", "Taşıma", "Zemin",
        "Pratiklik", "Sadelik", "Değer", "Düzen", "Kalıcılık",
        "Topraklanma", "Dayanak", "Hedef", "Sessiz Sabır", "Ölçü",
        "Kök Hafızası", "İç Disiplin", "Somut Adım", "Ritim",
        "Yapı Kurma", "Güvenli Alan", "Sabitleme", "Derlenme",
        "Konsantrasyon", "Taş Gibi Netlik",
    ],
    "air": [
        "İlham", "Merak", "Fikir", "İletişim", "Bağlantı",
        "Öğrenme", "Bakış Açısı", "Netlik", "Soru", "Nefes",
        "Anlatı", "Kıvraklık", "Zihinsel Açılım", "Gözlem", "Esneklik",
        "Diyalog", "Kavrayış", "Hafifleme", "Yön Değişimi", "İşaret",
        "Söz", "Dinleme", "Uzak Görüş", "Harita", "Seçenek",
        "Zihinsel Temizlik", "Açık Pencere", "Haber", "Farkındalık",
        "Köprü", "Açıklık", "Düşünce", "Perspektif", "İnce Ayar",
        "Dikkat", "Çağrı", "Yeniden Çerçeve", "Zihin Işığı",
        "Rüzgar", "Sessiz Bilgi",
    ],
    "water": [
        "Şifa", "Akış", "Duyarlılık", "Arınma", "Empati",
        "Kabulleniş", "Derinleşme", "Sakinleşme", "Sezgi", "Rüya",
        "Merhamet", "İç Ses", "Teslimiyet", "Hafıza", "Yumuşama",
        "Duygu", "Bağışlama", "Dalga", "İç Temizlik", "Saklı Bilgi",
        "Yakınlık", "Ruhsal Dinlenme", "Gölgeyle Barış", "İç Deniz", "Akışa Güven",
        "Kırılganlık", "Besleme", "Sessiz Şifa", "Derin Görüş", "Gizem",
        "Kalp Suyu", "İçsel Uyum", "Sızıntı", "Duygusal Netlik",
        "Arka Plan", "İnce Sezgi", "Kabul", "Ruh Hafızası",
        "Suların Yolu", "Yavaş Çözülme",
    ],
}

def get_zodiac_element_from_birth(birth_dt) -> str:
    """
    Kullanıcının doğum tarihinden zodyak elementini çıkarır.
    Element: fire / earth / air / water
    """
    if birth_dt is None:
        return "earth"  # nötr

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

    ÖNEMLİ: Seed artık user_id'ye değil, KİŞİSEL BİLGİLERE bağlı:
    - first_name, last_name
    - birth_date
    - birth_place
    - gün
    Böylece aynı verilerle tekrar kayıt olunsa bile, aynı gün aynı kelime gelir.
    """
    birth_dt = getattr(user, "birth_date", None)
    element = get_zodiac_element_from_birth(birth_dt)
    words = ENERGY_WORDS_BY_ELEMENT.get(element, ENERGY_WORDS_BY_ELEMENT["earth"])

    # Kişisel verileri toplayalım
    first = (getattr(user, "first_name", "") or "").strip().upper()
    last = (getattr(user, "last_name", "") or "").strip().upper()
    birth_place = (getattr(user, "birth_place", "") or "").strip().upper()

    if hasattr(birth_dt, "date"):
        birth_str = birth_dt.date().isoformat()
    elif birth_dt:
        birth_str = birth_dt.isoformat()
    else:
        birth_str = "NO_BIRTH"

    # Deterministik seed: Kişisel veriler + gün + element
    seed_str = f"{first}-{last}-{birth_str}-{birth_place}-{today.isoformat()}-{element}"

    rnd = random.Random(seed_str)
    index = rnd.randint(0, len(words) - 1)

    return words[index], element


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
    email = normalize_email(payload.email)
    validate_password(payload.password)

    if email:
        existing_user = db.exec(select(User).where(User.email == email)).first()
        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="Bu e-posta adresiyle kayıtlı bir SkullMod hesabı var.",
            )

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
        email=email,
        password_hash=hash_password(payload.password) if payload.password else None,
    )
    db.add(user)
    db.commit()

    token = create_token(user_id)

    return RegisterResponse(
        success=True,
        token=token,
        user_id=user_id,
    )


@app.post("/api/v1/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    email = normalize_email(payload.email)
    user = db.exec(select(User).where(User.email == email)).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="E-posta veya şifre hatalı.",
        )

    return AuthResponse(
        success=True,
        token=create_token(user.user_id),
        user_id=user.user_id,
    )


@app.post("/api/v1/password-reset/profile", response_model=BasicResponse)
def reset_password_with_profile(
    payload: ProfilePasswordResetRequest,
    db: Session = Depends(get_db),
):
    validate_password(payload.new_password)

    email = normalize_email(payload.email)
    user = db.exec(select(User).where(User.email == email)).first()

    profile_matches = False
    if user:
        profile_matches = (
            user.birth_date.date() == payload.birth_date.date()
            and normalize_profile_text(user.birth_place) == normalize_profile_text(payload.birth_place)
        )

    if not user or not profile_matches:
        raise HTTPException(
            status_code=400,
            detail="Hesap bilgileri doğrulanamadı.",
        )

    user.password_hash = hash_password(payload.new_password)
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()

    return BasicResponse(
        success=True,
        message="Şifre güncellendi.",
    )


# ----------------------------------------------------
# GÜNLÜK KELİMELER ENDPOINT
# ----------------------------------------------------


@app.get("/api/v1/daily-words", response_model=DailyWordsResponse)
def daily_words(
    lang: str = "tr",
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Günlük 2 kelime + motto:
    - Köşe taşı kelimesi (kişisel cornerstone_pool'dan)
    - Günlük enerji kelimesi (kişisel + astro element'e göre)
    - Aynı gün + aynı kişisel veriler için deterministik
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
    cornerstone_word, _, _ = get_or_create_daily_words(db, user, today)

    language = normalize_language(lang)

    # KİŞİYE ÖZEL GÜNLÜK ENERJİ + MOTTOSU
    energy_word, element_key = pick_personal_daily_energy_word(user, today)
    localized_cornerstone = localize_word(cornerstone_word, language)
    localized_energy = localize_word(energy_word, language)
    motto = build_localized_motto(
        localized_cornerstone,
        localized_energy,
        element_key,
        language,
    )

    return DailyWordsResponse(
        success=True,
        data={
            "word1": localized_cornerstone,
            "word2": localized_energy,
            "motto": motto,
            "date": today.isoformat(),
            "language": language,
        }
    )


# ----------------------------------------------------
# FİZİKSEL SKULLMOD / NFC CLAIM ENDPOINT'LERİ
# ----------------------------------------------------


@app.get("/api/v1/nfc/{public_token}", response_model=NFCStatusResponse)
def get_nfc_status(
    public_token: str,
    request: Request,
    current_user_id: Optional[str] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    artifact = db.exec(
        select(PhysicalSkull).where(PhysicalSkull.public_token == public_token)
    ).first()

    if not artifact:
        log_nfc_scan(
            db,
            artifact=None,
            user_id=current_user_id,
            request=request,
            event_type="invalid_token",
        )
        db.commit()
        return NFCStatusResponse(
            valid=False,
            message="Bu SkullMod bağlantısı geçersiz veya devre dışı bırakılmış olabilir.",
        )

    if not artifact.is_active or artifact.claim_status in {"disabled", "locked"}:
        artifact.last_scanned_at = datetime.now(timezone.utc)
        artifact.scan_count += 1
        log_nfc_scan(
            db,
            artifact=artifact,
            user_id=current_user_id,
            request=request,
            event_type="disabled_artifact",
        )
        db.add(artifact)
        db.commit()
        return NFCStatusResponse(
            valid=False,
            artifact_code=artifact.artifact_code,
            claim_status=artifact.claim_status,
            is_active=artifact.is_active,
            message="Bu SkullMod bağlantısı geçersiz veya devre dışı bırakılmış olabilir.",
        )

    event_type = "anonymous_scan"
    if artifact.scan_count == 0:
        event_type = "first_scan"
    elif current_user_id:
        event_type = "authenticated_scan"

    artifact.last_scanned_at = datetime.now(timezone.utc)
    artifact.scan_count += 1
    log_nfc_scan(
        db,
        artifact=artifact,
        user_id=current_user_id,
        request=request,
        event_type=event_type,
    )
    db.add(artifact)
    db.commit()

    owner_match = None
    if current_user_id and artifact.owner_user_id:
        owner_match = artifact.owner_user_id == current_user_id

    return NFCStatusResponse(
        valid=True,
        artifact_code=artifact.artifact_code,
        claim_status=artifact.claim_status,
        requires_auth=current_user_id is None,
        owner_match=owner_match,
        is_active=artifact.is_active,
    )


@app.post("/api/v1/nfc/{public_token}/claim", response_model=NFCClaimResponse)
def claim_nfc_artifact(
    public_token: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    artifact = db.exec(
        select(PhysicalSkull).where(PhysicalSkull.public_token == public_token)
    ).first()

    if not artifact or not artifact.is_active:
        log_nfc_scan(
            db,
            artifact=artifact,
            user_id=current_user_id,
            request=request,
            event_type="invalid_token" if not artifact else "disabled_artifact",
        )
        db.commit()
        raise HTTPException(
            status_code=404,
            detail="Bu SkullMod bağlantısı geçersiz veya devre dışı bırakılmış olabilir.",
        )

    if artifact.claim_status != "unclaimed":
        if artifact.owner_user_id == current_user_id and artifact.claim_status == "claimed":
            log_nfc_scan(
                db,
                artifact=artifact,
                user_id=current_user_id,
                request=request,
                event_type="authenticated_scan",
                notes="Artifact already claimed by current user.",
            )
            db.commit()
            return NFCClaimResponse(
                success=True,
                artifact_code=artifact.artifact_code,
                claim_status=artifact.claim_status,
                message="SkullMod hesabınıza bağlandı. Cogitas, Ergo Es.",
            )

        log_nfc_scan(
            db,
            artifact=artifact,
            user_id=current_user_id,
            request=request,
            event_type="authenticated_scan",
            notes="Claim rejected: artifact belongs to another account or is locked.",
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Bu SkullMod başka bir hesaba bağlı görünüyor.",
        )

    claimed_at = datetime.now(timezone.utc)
    claim_result = db.exec(
        update(PhysicalSkull)
        .where(PhysicalSkull.id == artifact.id)
        .where(PhysicalSkull.claim_status == "unclaimed")
        .where(PhysicalSkull.is_active == True)  # noqa: E712
        .values(
            owner_user_id=current_user_id,
            claim_status="claimed",
            claimed_at=claimed_at,
            last_scanned_at=claimed_at,
            scan_count=PhysicalSkull.scan_count + 1,
        )
    )

    if claim_result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Bu SkullMod başka bir hesaba bağlı görünüyor.",
        )

    artifact = db.exec(
        select(PhysicalSkull).where(PhysicalSkull.public_token == public_token)
    ).first()

    log_nfc_scan(
        db,
        artifact=artifact,
        user_id=current_user_id,
        request=request,
        event_type="claimed",
    )
    db.add(artifact)
    db.commit()

    return NFCClaimResponse(
        success=True,
        artifact_code=artifact.artifact_code,
        claim_status=artifact.claim_status,
        message="SkullMod hesabınıza bağlandı. Cogitas, Ergo Es.",
    )


@app.get("/api/v1/me/artifacts", response_model=list[PhysicalSkullSummary])
def list_my_artifacts(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    artifacts = db.exec(
        select(PhysicalSkull)
        .where(PhysicalSkull.owner_user_id == current_user_id)
        .order_by(PhysicalSkull.claimed_at.desc())
    ).all()

    return [
        PhysicalSkullSummary(
            artifact_code=artifact.artifact_code,
            claim_status=artifact.claim_status,
            claimed_at=artifact.claimed_at,
            production_batch=artifact.production_batch,
            artifact_type=artifact.artifact_type,
            artifact_series=artifact.artifact_series,
            edition_number=artifact.edition_number,
            certificate_code=artifact.certificate_code,
            material_type=artifact.material_type,
            visual_theme=artifact.visual_theme,
            is_limited_edition=artifact.is_limited_edition,
            premium_content_unlocked=artifact.premium_content_unlocked,
        )
        for artifact in artifacts
    ]
