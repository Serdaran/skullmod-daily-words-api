import swisseph as swe
from datetime import datetime
from typing import Dict, List, Tuple
from .geo import resolve_place


# Swiss Ephemeris veri dosyalarının yolu:
# Eğer ephemeris dosyaları yoksa yine çalışır (fallback),
# ama doğruluk artması için app/data/swisseph klasörüne .se1 dosyaları koyulabilir.
swe.set_ephe_path("app/data/swisseph")


# Basit astro keyword eşleşmesi (Güneş burcu için)
SUN_KEYWORDS = {
    "Koç": ["Cesaret", "Eylem", "Atılım"],
    "Boğa": ["Sabitlik", "Güven", "Dayanıklılık"],
    "İkizler": ["İletişim", "Merak", "Zihin"],
    "Yengeç": ["Şefkat", "Duygu", "Koruma"],
    "Aslan": ["Özgüven", "Yaratıcılık", "Liderlik"],
    "Başak": ["Analiz", "Düzen", "Hizmet"],
    "Terazi": ["Denge", "İlişki", "Zerafet"],
    "Akrep": ["Dönüşüm", "Güç", "Sezgi"],
    "Yay": ["Macera", "Keşif", "Özgürlük"],
    "Oğlak": ["Disiplin", "Sorumluluk", "Hırs"],
    "Kova": ["Özgünlük", "Vizyon", "Bağımsızlık"],
    "Balık": ["Hayal", "Şefkat", "Akış"],
}


# Zodyak işareti bulma
def zodiac_sign(lon: float) -> str:
    signs = [
        "Koç", "Boğa", "İkizler", "Yengeç",
        "Aslan", "Başak", "Terazi", "Akrep",
        "Yay", "Oğlak", "Kova", "Balık",
    ]
    return signs[int(lon // 30)]


# Kullanıcının doğum haritası: Güneş, Ay, ASC
def compute_natal(first_name: str, last_name: str, birth_date: datetime, birth_place: str):
    lat, lon, tz = resolve_place(birth_place)
    jd_ut = swe.julday(
        birth_date.year,
        birth_date.month,
        birth_date.day,
        birth_date.hour + birth_date.minute / 60.0 - 3.0  # TR için UTC offset
    )

    # Sun
    sun = swe.calc_ut(jd_ut, swe.SUN)[0]
    sun_lon = sun[0]

    # Moon
    moon = swe.calc_ut(jd_ut, swe.MOON)[0]
    moon_lon = moon[0]

    # Ascendant (swe.houses)
    houses = swe.houses(jd_ut, lat, lon)
    asc = houses[0][0]

    return {
        "sun_lon": sun_lon,
        "moon_lon": moon_lon,
        "asc": asc,
        "sun_sign": zodiac_sign(sun_lon),
    }


# Günlük transit hesapları
def compute_transits(current_date: datetime) -> Dict[str, float]:
    jd_ut = swe.julday(
        current_date.year,
        current_date.month,
        current_date.day,
        current_date.hour + current_date.minute / 60.0
    )
    return {
        "sun": swe.calc_ut(jd_ut, swe.SUN)[0][0],
        "moon": swe.calc_ut(jd_ut, swe.MOON)[0][0],
        "mars": swe.calc_ut(jd_ut, swe.MARS)[0][0],
    }


# Gezegen açıları (orb toleranslı)
def angle_relation(lon1: float, lon2: float) -> str:
    diff = abs(lon1 - lon2)
    diff = diff % 360

    for angle, name in [
        (0, "Kavuşum"),
        (60, "Altılık"),
        (90, "Kare"),
        (120, "Üçgen"),
        (180, "Karşıt"),
    ]:
        if abs(diff - angle) <= 6:
            return name
    return "Nötr"


# Transit → enerji kelimesi
ASPECT_TO_WORD = {
    "Kavuşum": ["Yoğunluk", "Netlik", "Odak"],
    "Altılık": ["Akış", "Uyum", "Destek"],
    "Kare": ["Mücadele", "İnisiyatif", "Cesaret"],
    "Üçgen": ["Akış", "Yaratıcılık", "Kolaylık"],
    "Karşıt": ["Farkındalık", "Gerilim", "Dönüşüm"],
    "Nötr": ["Denge", "Sükunet", "Toplanma"],
}


def daily_astro_word(natal: Dict[str, float], transits: Dict[str, float], current_date: datetime) -> str:
    natal_sun = natal["sun_lon"]
    transit_mars = transits["mars"]

    aspect = angle_relation(natal_sun, transit_mars)
    lst = ASPECT_TO_WORD.get(aspect, ["Denge"])

    return lst[current_date.toordinal() % len(lst)]

