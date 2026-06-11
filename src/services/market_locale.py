"""Per-channel market / country profiles for localized public crawls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

_MARKET_ROWS: Sequence[Dict[str, Any]] = (
    {"id": "cn", "label": "中国大陆", "gp_lang": "zh", "gp_country": "cn", "steam_lang": "schinese", "taptap_host": "cn", "taptap_lang": "zh_CN", "taptap_loc": "CN"},
    {"id": "us", "label": "美国", "gp_lang": "en", "gp_country": "us", "steam_lang": "english", "taptap_host": "io", "taptap_lang": "en_US", "taptap_loc": "US"},
    {"id": "jp", "label": "日本", "gp_lang": "ja", "gp_country": "jp", "steam_lang": "japanese", "taptap_host": "io", "taptap_lang": "ja_JP", "taptap_loc": "JP"},
    {"id": "kr", "label": "韩国", "gp_lang": "ko", "gp_country": "kr", "steam_lang": "koreana", "taptap_host": "io", "taptap_lang": "ko_KR", "taptap_loc": "KR"},
    {"id": "tw", "label": "台湾", "gp_lang": "zh", "gp_country": "tw", "steam_lang": "tchinese", "taptap_host": "io", "taptap_lang": "zh_TW", "taptap_loc": "TW"},
    {"id": "hk", "label": "香港", "gp_lang": "zh", "gp_country": "hk", "steam_lang": "tchinese", "taptap_host": "io", "taptap_lang": "zh_TW", "taptap_loc": "HK"},
    {"id": "gb", "label": "英国", "gp_lang": "en", "gp_country": "gb", "steam_lang": "english", "taptap_host": "io", "taptap_lang": "en_GB", "taptap_loc": "GB"},
    {"id": "de", "label": "德国", "gp_lang": "de", "gp_country": "de", "steam_lang": "german", "taptap_host": "io", "taptap_lang": "de_DE", "taptap_loc": "DE"},
    {"id": "fr", "label": "法国", "gp_lang": "fr", "gp_country": "fr", "steam_lang": "french", "taptap_host": "io", "taptap_lang": "fr_FR", "taptap_loc": "FR"},
    {"id": "br", "label": "巴西", "gp_lang": "pt", "gp_country": "br", "steam_lang": "brazilian", "taptap_host": "io", "taptap_lang": "pt_BR", "taptap_loc": "BR"},
    {"id": "in", "label": "印度", "gp_lang": "en", "gp_country": "in", "steam_lang": "english", "taptap_host": "io", "taptap_lang": "en_IN", "taptap_loc": "IN"},
    {"id": "sg", "label": "新加坡", "gp_lang": "en", "gp_country": "sg", "steam_lang": "english", "taptap_host": "io", "taptap_lang": "en_SG", "taptap_loc": "SG"},
    {"id": "th", "label": "泰国", "gp_lang": "th", "gp_country": "th", "steam_lang": "english", "taptap_host": "io", "taptap_lang": "th_TH", "taptap_loc": "TH"},
    {"id": "vn", "label": "越南", "gp_lang": "vi", "gp_country": "vn", "steam_lang": "english", "taptap_host": "io", "taptap_lang": "vi_VN", "taptap_loc": "VN"},
    {"id": "id", "label": "印尼", "gp_lang": "id", "gp_country": "id", "steam_lang": "english", "taptap_host": "io", "taptap_lang": "id_ID", "taptap_loc": "ID"},
    {"id": "ph", "label": "菲律宾", "gp_lang": "en", "gp_country": "ph", "steam_lang": "english", "taptap_host": "io", "taptap_lang": "en_PH", "taptap_loc": "PH"},
    {"id": "my", "label": "马来西亚", "gp_lang": "en", "gp_country": "my", "steam_lang": "english", "taptap_host": "io", "taptap_lang": "en_MY", "taptap_loc": "MY"},
    {"id": "au", "label": "澳大利亚", "gp_lang": "en", "gp_country": "au", "steam_lang": "english", "taptap_host": "io", "taptap_lang": "en_AU", "taptap_loc": "AU"},
    {"id": "ca", "label": "加拿大", "gp_lang": "en", "gp_country": "ca", "steam_lang": "english", "taptap_host": "io", "taptap_lang": "en_CA", "taptap_loc": "CA"},
    {"id": "mx", "label": "墨西哥", "gp_lang": "es", "gp_country": "mx", "steam_lang": "spanish", "taptap_host": "io", "taptap_lang": "es_MX", "taptap_loc": "MX"},
    {"id": "ru", "label": "俄罗斯", "gp_lang": "ru", "gp_country": "ru", "steam_lang": "russian", "taptap_host": "io", "taptap_lang": "ru_RU", "taptap_loc": "RU"},
    {"id": "sa", "label": "沙特阿拉伯", "gp_lang": "ar", "gp_country": "sa", "steam_lang": "english", "taptap_host": "io", "taptap_lang": "ar_SA", "taptap_loc": "SA"},
    {"id": "ae", "label": "阿联酋", "gp_lang": "ar", "gp_country": "ae", "steam_lang": "english", "taptap_host": "io", "taptap_lang": "ar_AE", "taptap_loc": "AE"},
)

_MARKET_BY_ID = {row["id"]: row for row in _MARKET_ROWS}
_CHANNEL_DEFAULTS = {
    "google_play": "us",
    "google play": "us",
    "steam": "us",
    "taptap": "cn",
    "app_store": "us",
}


@dataclass(frozen=True)
class MarketProfile:
    country: str
    label: str
    google_play_lang: str
    google_play_country: str
    steam_review_language: str
    taptap_api_base: str
    taptap_xua_lang: str
    taptap_xua_loc: str
    taptap_accept_language: str
    taptap_referer: str


def _taptap_api_base(host: str) -> str:
    token = (host or "cn").strip().lower()
    if token == "cn":
        return "https://www.taptap.cn/webapiv2"
    return "https://www.taptap.io/webapiv2"


def normalize_market_country(channel: str, value: Any) -> str:
    channel_key = (channel or "").strip().lower().replace(" ", "_")
    default = _CHANNEL_DEFAULTS.get(channel_key, "us")
    token = str(value or "").strip().lower()
    if not token:
        return default
    if token in _MARKET_BY_ID:
        return token
    aliases = {
        "china": "cn",
        "chn": "cn",
        "usa": "us",
        "uk": "gb",
        "gbr": "gb",
        "uae": "ae",
        "korea": "kr",
        "japan": "jp",
        "taiwan": "tw",
        "hongkong": "hk",
        "hong_kong": "hk",
        "intl": "us",
        "global": "us",
        "international": "us",
    }
    return aliases.get(token, default)


def get_market_profile(channel: str, country: Any) -> MarketProfile:
    normalized = normalize_market_country(channel, country)
    row = _MARKET_BY_ID[normalized]
    host = row["taptap_host"]
    api_base = _taptap_api_base(host)
    referer = "https://www.taptap.cn/" if host == "cn" else "https://www.taptap.io/"
    accept_language = row["taptap_lang"].replace("_", "-")
    return MarketProfile(
        country=normalized,
        label=row["label"],
        google_play_lang=row["gp_lang"],
        google_play_country=row["gp_country"],
        steam_review_language=row["steam_lang"],
        taptap_api_base=api_base,
        taptap_xua_lang=row["taptap_lang"],
        taptap_xua_loc=row["taptap_loc"],
        taptap_accept_language=accept_language,
        taptap_referer=referer,
    )


def list_markets_for_channel(channel: str) -> List[Dict[str, str]]:
    channel_key = (channel or "").strip().lower().replace(" ", "_")
    default = _CHANNEL_DEFAULTS.get(channel_key, "us")
    markets = [{"id": row["id"], "label": row["label"]} for row in _MARKET_ROWS]
    for item in markets:
        if item["id"] == default:
            item["default"] = True
    return markets


def default_market_for_channel(channel: str) -> str:
    return normalize_market_country(channel, "")


def market_label(country: str) -> str:
    row = _MARKET_BY_ID.get(normalize_market_country("steam", country))
    return row["label"] if row else country
