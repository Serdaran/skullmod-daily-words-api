import json
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Tuple

from sqlmodel import Session, select

from ..models import User, DailyWord
from .astrology import compute_natal, compute_transits, daily_astro_word
from .numerology import core_numbers, daily_energy_word as numerology_daily
from .chinese import zodiac_for_year, element_for_year

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_json(name: str) -> dict:
    """app/data içinden JSON dosyası yükler."""
    with open(DATA_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_cornerstone_pool(u: User) -> List[str]:
    """User.cornerstone_pool JSON string'ini Python list'e çevirir."""
    return json.loads(u.cornerstone_pool)


def build_cornerstone_pool(
    first_name: str,
    last_name: str,
    birth_date: datetime,
    birth_place: str,
) -> List[str]:
    """
    Kayıt anında 1 kez çalışan fonksiyon.
    - Batı astrolojisi (Güneş, Ay, ASC) → astro_keywords.json
    - Çin astrolojisi (hayvan + element) → chinese_keywords.json
    - Numeroloji (destiny, soul, personality, life_path) → numerology_keywords.json
    Sonuç: 30–50 kelimelik kişisel havuz (tekrarlar temizlenmiş, max 50).
    """
    astro_kw = load_json("astro_keywords.json")
    num_kw = load_json("numerology_keywords.json")
    chi_kw = load_json("chinese_keywords.json")

    natal = compute_natal(first_name, last_name, birth_date, birth_place)
    nums = core_numbers(first_name, last_name, birth_date)

    pool: List[str] = []

    # Batı astro: Güneş burcu
    sun_sign = natal["sun_sign"]
    pool.extend(astro_kw.get(sun_sign, [])[:5])

    # Çin zodyak: hayvan + element
    zy = zodiac_for_year(birth_date.year)
    el = element_for_year(birth_date.year)
    pool.extend(chi_kw.get(zy, [])[:5])
    pool.extend(chi_kw.get(el, [])[:5])

    # Numeroloji: 4 temel sayı
    for k, v in nums.items():
        pool.extend(num_kw.get(str(v), [])[:5])

    # Tekrarları temizle + maksimum 50 kelime
    dedup: List[str] = []
    seen = set()
    for w in pool:
        if w not in seen:
            seen.add(w)
            dedup.append(w)

    if len(dedup) > 50:
        # Deterministik bir seçim için isim/soyisim tabanlı sıralama
        key = (first_name + last_name + birth_place)
        dedup.sort(key=lambda x: (hash(key + x) % 10_000))
        dedup = dedup[:50]

    return dedup


def pick_word2(current_date: datetime, first_name: str, last_name: str, birth_date: datetime, birth_place: str) -> str:
    """
    Günlük enerji kelimesi (word2):
    - Astro tarafı: natal Güneş + günlük Mars açısı → daily_astro_word
    - Numeroloji tarafı: current_date → numerology_daily
    - Seçim: Tek/çift güne göre deterministik bir tercih
    """
    # Natal ve transitler
    natal = compute_natal(first_name, last_name, birth_date, birth_place)
    transits = compute_transits(current_date)

    astro_word = daily_astro_word(natal, transits, current_date)

    num_kw = load_json("numerology_keywords.json")
    num_word = numerology_daily(current_date, num_kw)

    # Tek/çift gün mekanizması: hem astro hem numeroloji devrede
    return astro_word if (current_date.toordinal() % 2 == 0) else num_word


def pick_word1(word2: str, cornerstone_pool: List[str]) -> str:
    """
    Köşe taşı kelimesi (word1):
    - relationship_map.json içinden word2 → [ilişkili kelimeler] al
    - Kullanıcının cornerstone_pool'unda olan ilk kelimeyi seç
    - Hiçbiri yoksa havuzdan deterministik rastgele bir kelime seç
    """
    rel = load_json("relationship_map.json")
    candidates = rel.get(word2, [])
    for w in candidates:
        if w in cornerstone_pool:
            return w

    if not cornerstone_pool:
        return "Odak"

    idx = (hash(word2) % len(cornerstone_pool))
    return cornerstone_pool[idx]


def build_motto(word1: str, word2: str) -> str:
    """
    Motto üretimi:
    - motto_templates.json içinden şablon seç
    - [word1] ve [word2] yerlerine kelimeleri koy
    """
    templates = load_json("motto_templates.json")
    if not templates:
        return f"Bugün {word1}'ınız, {word2} yolunda size rehberlik edecek."
    idx = (hash(word1 + word2) % len(templates))
    return templates[idx].replace("[word1]", word1).replace("[word2]", word2)


def get_or_create_daily_words(session: Session, user: User, current_day: date) -> Tuple[str, str, str]:
    """
    - Aynı kullanıcı + aynı gün için kayıt varsa **cache** olarak onu döner.
    - Yoksa yeni word1, word2, motto üretir; DB'ye yazar.
    """
    # Cache kontrolü
    q = session.exec(
        select(DailyWord).where(
            DailyWord.user_id == user.user_id,
            DailyWord.date == current_day,
        )
    ).first()
    if q:
        return q.word1, q.word2, q.motto

    # Köşe taşı havuzu
    cs_pool = ensure_cornerstone_pool(user)

    # Günlük enerji kelimesi (word2)
    current_dt = datetime.combine(current_day, datetime.min.time())
    word2 = pick_word2(
        current_dt,
        user.first_name,
        user.last_name,
        user.birth_date,
        user.birth_place,
    )

    # Köşe taşı kelimesi (word1)
    word1 = pick_word1(word2, cs_pool)

    # Motto
    motto = build_motto(word1, word2)

    # DB'ye kaydet
    rec = DailyWord(
        user_id=user.user_id,
        date=current_day,
        word1=word1,
        word2=word2,
        motto=motto,
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)

    return rec.word1, rec.word2, rec.motto

