from __future__ import annotations
from typing import Tuple
from pathlib import Path
import json

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Yerleşik minimal şehir listesi – JSON yoksa bunu kullanır.
_DEF = {
    "Niğde, Türkiye": {"lat": 37.9667, "lon": 34.6833, "tz": "Europe/Istanbul"},
}


def resolve_place(place: str) -> Tuple[float, float, str]:
    """
    Girilen yer ismini (örn. 'Niğde, Türkiye') enlem, boylam ve timezone string'e çevirir.
    - Önce app/data/cities_min.json varsa onu okur.
    - Yoksa _DEF içindeki taban değerleri kullanır.
    - Yine bulunamazsa (0.0, 0.0, 'UTC') döner.
    """
    path = DATA_DIR / "cities_min.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = _DEF
    else:
        data = _DEF

    rec = data.get(place) or next(
        (v for k, v in data.items() if k.lower() == place.lower()),
        None,
    )
    if not rec:
        return 0.0, 0.0, "UTC"

    return float(rec.get("lat", 0.0)), float(rec.get("lon", 0.0)), rec.get("tz", "UTC")

