from datetime import datetime

ZODIAC = [
    "Sıçan", "Öküz", "Kaplan", "Tavşan",
    "Ejderha", "Yılan", "At", "Keçi",
    "Maymun", "Horoz", "Köpek", "Domuz",
]

ELEMENTS = ["Ağaç", "Ateş", "Toprak", "Metal", "Su"]


def zodiac_for_year(year: int) -> str:
    """Yıla göre Çin zodyak hayvanı."""
    return ZODIAC[year % 12]


def element_for_year(year: int) -> str:
    """
    Basit element döngüsü (2 yıllık periyotlarla):
    - Bu demo için yeterli; istenirse ayrıntılı Wu Xing döngüsü eklenebilir.
    """
    return ELEMENTS[(year // 2) % 5]

