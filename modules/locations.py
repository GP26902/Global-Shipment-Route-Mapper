"""Country and state/region lists for the entry form dropdowns. No Streamlit dependency.

Source: ISO 3166 data via pycountry. Names are tidied for English readers: accents and
bracketed notes removed, a few well-known exonyms substituted. Only top-level regions are
listed (US: 50 states and DC). City names are typed by the user, not listed here.
"""
import re
import unicodedata
from functools import lru_cache
from typing import Dict, List, Optional

import pycountry

from modules.geocoding import _norm_country

_COUNTRY_RENAMES = {"RU": "Russia", "TR": "Turkey"}   # pycountry has no common_name for these

# English names for regions whose ISO name is local-language or romanised oddly.
_REGION_RENAMES: Dict[str, str] = {
    # Germany (matches the English names used by the example routes)
    "DE-BW": "Baden-Wurttemberg", "DE-BY": "Bavaria", "DE-BE": "Berlin", "DE-BB": "Brandenburg",
    "DE-HB": "Bremen", "DE-HH": "Hamburg", "DE-HE": "Hesse", "DE-MV": "Mecklenburg-Vorpommern",
    "DE-NI": "Lower Saxony", "DE-NW": "North Rhine-Westphalia", "DE-RP": "Rhineland-Palatinate",
    "DE-SL": "Saarland", "DE-SN": "Saxony", "DE-ST": "Saxony-Anhalt", "DE-SH": "Schleswig-Holstein",
    "DE-TH": "Thuringia",
    # China: autonomous regions and special administrative regions
    "CN-NX": "Ningxia", "CN-XJ": "Xinjiang", "CN-GX": "Guangxi", "CN-NM": "Inner Mongolia",
    "CN-XZ": "Tibet", "CN-HK": "Hong Kong", "CN-MO": "Macau",
    # United Arab Emirates
    "AE-AZ": "Abu Dhabi", "AE-DU": "Dubai", "AE-SH": "Sharjah", "AE-AJ": "Ajman",
    "AE-FU": "Fujairah", "AE-RK": "Ras Al Khaimah", "AE-UQ": "Umm Al Quwain",
}
_CN_SUFFIX = re.compile(r"\s+(Sheng|Shi|Zizhiqu|Tebie Xingzhengqu)$")
_LETTERS = str.maketrans({"ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ı": "i",
                          "ß": "ss", "æ": "ae", "Æ": "AE", "ð": "d", "þ": "th", "ə": "e", "Ə": "E", "ŋ": "n", "ʻ": "'", "’": "'", "‘": "'", "ħ": "h", "Ħ": "H", "†": ""})


def _strip_accents(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.translate(_LETTERS))
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def _clean_region(code: str, name: str) -> str:
    if code in _REGION_RENAMES:
        return _REGION_RENAMES[code]
    n = re.sub(r"\s*\[.*?\]", "", name)
    n = _strip_accents(n).strip()
    if code.startswith("CN-"):
        n = _CN_SUFFIX.sub("", n)
    return n


@lru_cache(maxsize=1)
def _countries() -> Dict[str, str]:
    """display name -> alpha-2 code."""
    out = {}
    for c in pycountry.countries:
        name = _COUNTRY_RENAMES.get(c.alpha_2) or getattr(c, "common_name", None) or c.name
        out[_strip_accents(name)] = c.alpha_2
    return out


def country_names() -> List[str]:
    return sorted(_countries())


@lru_cache(maxsize=None)
def state_names(country: Optional[str]) -> List[str]:
    """Top-level regions for a country name from country_names(); [] if none are listed."""
    code = _countries().get(country or "")
    if not code:
        return []
    subs = [s for s in (pycountry.subdivisions.get(country_code=code) or []) if s.parent_code is None]
    if code == "US":
        subs = [s for s in subs if s.type in ("State", "District")]   # 50 states + DC
    names = {_clean_region(s.code, s.name) for s in subs}
    return sorted(n for n in names if n)


@lru_cache(maxsize=1)
def _codes_by_norm() -> Dict[str, str]:
    """Matching name (any common spelling) -> alpha-2 code."""
    out: Dict[str, str] = {}
    for c in pycountry.countries:
        for n in (c.name, getattr(c, "official_name", None), getattr(c, "common_name", None)):
            if n:
                out.setdefault(_norm_country(n), c.alpha_2)
    for display, code in _countries().items():
        out[_norm_country(display)] = code
    return out


def country_code(name: Optional[str]) -> Optional[str]:
    """ISO alpha-2 code for a country name as the app stores it ('United States' -> 'US')."""
    return _codes_by_norm().get(_norm_country(name or ""))
