from datetime import datetime
from typing import Dict, List

# Harf → sayı tablosu (Pythagorean'a yakın basit sistem)
LETTER_VALUES = {c: i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", start=1)}


def _reduce_to_digit(n: int) -> int:
    """Çok haneli sayıyı 1–9 aralığına indirger."""
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n


def date_to_digit(dt: datetime) -> int:
    """Tarihi (YYYYMMDD) formatında numeroloji sayısına çevirir."""
    s = int(dt.strftime("%Y%m%d"))
    return _reduce_to_digit(s)


def name_value(name: str) -> int:
    """İsim içindeki harflerden numeroloji değeri üretir."""
    total = 0
    for ch in name.upper():
        if ch in LETTER_VALUES:
            total += LETTER_VALUES[ch]
    if total == 0:
        return 1
    return _reduce_to_digit(total)


def core_numbers(first_name: str, last_name: str, birth_date: datetime) -> Dict[str, int]:
    """
    Çekirdek numeroloji değerleri:
    - destiny: isim + soyisim
    - soul: sesli harfler
    - personality: sessiz harfler
    - life_path: doğum tarihi
    """
    full_name = first_name + last_name
    destiny = name_value(full_name)

    vowels = "".join(ch for ch in first_name if ch.lower() in "aeiou")
    consonants = "".join(ch for ch in first_name if ch.lower() not in "aeiou")

    soul = name_value(vowels) if vowels else 1
    personality = name_value(consonants) if consonants else 1
    life_path = _reduce_to_digit(int(birth_date.strftime("%Y%m%d")))

    return {
        "destiny": destiny,
        "soul": soul,
        "personality": personality,
        "life_path": life_path,
    }


def daily_energy_word(current_date: datetime, numerology_lookup: Dict[str, List[str]]) -> str:
    """
    Günlük numeroloji enerjisi:
    - current_date → tek haneli sayı (1–9)
    - numerology_keywords.json içinden ilgili liste
    - deterministik seçim (tarih ordinalsine göre)
    """
    d = date_to_digit(current_date)
    lst = numerology_lookup.get(str(d), [])
    if not lst:
        return "Akış"
    return lst[current_date.toordinal() % len(lst)]

