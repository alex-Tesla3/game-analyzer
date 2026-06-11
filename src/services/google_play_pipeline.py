"""Google Play public review MVP — package resolve, live scrape, merge into MVP."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from src.mvp_pipeline import (
    DEFAULT_OUTPUT_DIR,
    analyze_actual_steam_data,
    validate_analysis,
)
from src.product_registry import (
    apply_product_display_names,
    google_play_alias_map,
    google_play_demo_map,
)
from src.services.platform_crawl_utils import allow_demo_fallback

try:
    from google_play_scraper import app as gplay_app
    from google_play_scraper import reviews as gplay_reviews
    from google_play_scraper import search as gplay_search

    _GPLAY_AVAILABLE = True
except ImportError:
    gplay_app = None  # type: ignore
    gplay_reviews = None  # type: ignore
    gplay_search = None  # type: ignore
    _GPLAY_AVAILABLE = False

_PACKAGE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$")

_ALIASES: Dict[str, str] = {
    "原神": "com.miHoYo.GenshinImpact",
    "genshin": "com.miHoYo.GenshinImpact",
    "genshin impact": "com.miHoYo.GenshinImpact",
    "王者荣耀": "com.levelinfinite.sgameGlobal",
    "王者荣耀国际服": "com.levelinfinite.sgameGlobal",
    "honor of kings": "com.levelinfinite.sgameGlobal",
    "和平精英": "com.tencent.tmgp.pubgmhd",
    "pubg mobile": "com.tencent.ig",
    "崩坏星穹铁道": "com.HoYoverse.hkrpgoversea",
    "星穹铁道": "com.HoYoverse.hkrpgoversea",
}

_DEMO_GAMES: Dict[str, str] = {
    "com.miHoYo.GenshinImpact": "原神",
    "com.levelinfinite.sgameGlobal": "王者荣耀国际服",
    "com.tencent.tmgp.pubgmhd": "和平精英",
}


def _merged_gplay_aliases() -> Dict[str, str]:
    merged = dict(_ALIASES)
    merged.update(google_play_alias_map())
    return merged


def _merged_gplay_demo() -> Dict[str, str]:
    merged = dict(_DEMO_GAMES)
    merged.update(google_play_demo_map())
    return merged


class GooglePlayCrawlerError(RuntimeError):
    pass


def _gplay_locale() -> tuple[str, str]:
    return (
        os.getenv("GOOGLE_PLAY_LANG", "zh").strip() or "zh",
        os.getenv("GOOGLE_PLAY_COUNTRY", "cn").strip() or "cn",
    )


class GooglePlayPublicCrawler:
    """Live Google Play scrape via google-play-scraper (public store pages)."""

    def search(self, term: str, *, limit: int = 8) -> List[Dict[str, Any]]:
        query = (term or "").strip()
        if len(query) < 2:
            return []

        pkg_from_url = _extract_package_id(query)
        if pkg_from_url:
            return [{"package_id": pkg_from_url, "app_id": pkg_from_url, "name": pkg_from_url, "type": "app"}]

        alias = _merged_gplay_aliases().get(query.lower())
        if alias:
            return [
                {
                    "package_id": alias,
                    "app_id": alias,
                    "name": _merged_gplay_demo().get(alias, query),
                    "type": "app",
                }
            ]

        if _PACKAGE_RE.match(query):
            return [{"package_id": query, "app_id": query, "name": query.split(".")[-1], "type": "app"}]

        if not _GPLAY_AVAILABLE:
            return self._offline_search(query, limit=limit)

        lang, country = _gplay_locale()
        try:
            hits = gplay_search(query, lang=lang, country=country, n_hits=min(limit, 10))
            out: List[Dict[str, Any]] = []
            for row in hits or []:
                pkg = str(row.get("appId") or "")
                if not pkg:
                    continue
                out.append(
                    {
                        "package_id": pkg,
                        "app_id": pkg,
                        "name": row.get("title") or pkg,
                        "type": "app",
                        "score": row.get("score"),
                    }
                )
            return out[:limit]
        except Exception:
            return self._offline_search(query, limit=limit)

    def _offline_search(self, query: str, *, limit: int) -> List[Dict[str, Any]]:
        hits: List[Dict[str, Any]] = []
        lower = query.lower()
        for pkg, name in _merged_gplay_demo().items():
            if lower in name.lower() or lower in pkg.lower():
                hits.append({"package_id": pkg, "app_id": pkg, "name": name, "type": "app"})
        return hits[:limit]

    def crawl(
        self,
        package_ids: Sequence[str] | None = None,
        *,
        app_ids: Sequence[str] | None = None,
        max_reviews_per_app: int = 30,
        product_name_overrides: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        ids = list(package_ids or app_ids or [])
        comments: List[Dict[str, Any]] = []
        metrics: List[Dict[str, Any]] = []
        games: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        used_demo = False

        for pkg in ids:
            pkg = str(pkg).strip().replace("google_play_", "", 1)
            if not pkg:
                continue
            try:
                game, reviews, demo = self._fetch_package(pkg, max_reviews_per_app)
                used_demo = used_demo or demo
                games.append(game)
                comments.extend(self._normalize_reviews(pkg, game["name"], reviews))
                metrics.extend(self._build_metrics(pkg, game["name"], reviews))
            except Exception as exc:
                errors.append({"package_id": pkg, "error": str(exc)})

        if not comments and not metrics:
            raise GooglePlayCrawlerError(f"No usable Google Play data. Errors: {errors}")

        payload = {
            "source": "google_play_public",
            "data_mode": "demo_fallback" if used_demo else "live",
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "platform": "Google Play",
            "games": games,
            "comments": comments,
            "metrics": metrics,
            "errors": errors,
        }
        return apply_product_display_names(payload, product_name_overrides)

    def _fetch_package(
        self, package_id: str, max_reviews: int
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
        if _GPLAY_AVAILABLE:
            lang, country = _gplay_locale()
            try:
                info = gplay_app(package_id, lang=lang, country=country)
                name = info.get("title") or _merged_gplay_demo().get(package_id) or package_id.split(".")[-1]
                count = min(max(max_reviews, 3), 100)
                rows, _ = gplay_reviews(package_id, lang=lang, country=country, count=count)
                parsed = [
                    {
                        "score": row.get("score"),
                        "text": row.get("content") or "",
                        "thumbsUp": (row.get("score") or 0) >= 4,
                    }
                    for row in (rows or [])
                    if row.get("content")
                ]
                if parsed:
                    return (
                        {
                            "package_id": package_id,
                            "name": name,
                            "platform": "Google Play",
                            "score": info.get("score"),
                            "installs": info.get("installs"),
                        },
                        parsed,
                        False,
                    )
            except Exception as exc:
                if not allow_demo_fallback():
                    raise GooglePlayCrawlerError(str(exc)) from exc

        if allow_demo_fallback() or package_id in _merged_gplay_demo():
            name = _merged_gplay_demo().get(package_id, package_id.split(".")[-1])
            reviews = self._demo_reviews(package_id, name)[: max(3, min(max_reviews, 50))]
            return (
                {"package_id": package_id, "name": name, "platform": "Google Play"},
                reviews,
                True,
            )

        raise GooglePlayCrawlerError(
            f"Google Play 抓取失败（{package_id}）。请安装 google-play-scraper 并确认包名正确。"
        )

    def _demo_reviews(self, package_id: str, name: str) -> List[Dict[str, Any]]:
        return [
            {"score": 5, "text": f"{name} 画面优秀，操作流畅，值得推荐。", "thumbsUp": True},
            {"score": 2, "text": f"{name} 内购偏贵，部分机型发热明显。", "thumbsUp": False},
            {"score": 4, "text": f"{name} 最近版本更新后稳定性有改善。", "thumbsUp": True},
        ]

    def _normalize_reviews(
        self, package_id: str, game_name: str, reviews: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for review in reviews:
            text = review.get("text") or review.get("content") or ""
            score = int(review.get("score") or review.get("rating") or 0)
            positive = bool(review.get("thumbsUp")) if "thumbsUp" in review else score >= 4
            out.append(
                {
                    "product": package_id,
                    "product_name": game_name,
                    "platform": "Google Play",
                    "channel": "Google Play",
                    "情绪": "positive" if positive else "negative",
                    "sentiment": "positive" if positive else "negative",
                    "内容": text,
                    "content": text,
                    "rating": score,
                }
            )
        return out

    def _build_metrics(
        self, package_id: str, name: str, reviews: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        total = len(reviews)
        positive = sum(1 for r in reviews if int(r.get("score") or 0) >= 4)
        rate = round(positive / total * 100, 1) if total else 0.0
        return [
            {
                "product": package_id,
                "product_name": name,
                "platform": "Google Play",
                "source": "google_play_public",
                "metric": "抓取评论数",
                "值": total,
            },
            {
                "product": package_id,
                "product_name": name,
                "platform": "Google Play",
                "source": "google_play_public",
                "metric": "样本好评率",
                "值": f"{rate}%",
            },
        ]


def _extract_package_id(token: str) -> Optional[str]:
    raw = (token or "").strip()
    if not raw:
        return None
    if "play.google.com" in raw and "id=" in raw:
        return raw.split("id=", 1)[1].split("&")[0].strip()
    bare = raw.replace("google_play_", "", 1)
    if _PACKAGE_RE.match(bare):
        return bare
    return None


def search_google_play_games(term: str, *, limit: int = 8) -> List[Dict[str, Any]]:
    return GooglePlayPublicCrawler().search(term, limit=limit)


def split_input_tokens(raw: Sequence[str] | str) -> List[str]:
    if isinstance(raw, str):
        parts: List[str] = []
        for segment in re.split(r"[\n,;]+", raw.strip()):
            token = segment.strip()
            if token:
                parts.append(token)
        return parts
    return [str(x).strip() for x in raw if str(x).strip()]


def resolve_google_play_inputs(raw: Sequence[str] | str, *, max_games: int = 5) -> Dict[str, Any]:
    tokens = split_input_tokens(raw)
    if not tokens:
        return {"success": False, "message": "请输入 Google Play 游戏名或包名", "app_ids": [], "resolved": []}

    app_ids: List[str] = []
    resolved: List[Dict[str, Any]] = []
    errors: List[str] = []

    for token in tokens:
        if len(app_ids) >= max_games:
            errors.append(f"最多 {max_games} 款，已忽略：{token}")
            continue
        pkg = _extract_package_id(token)
        if pkg and pkg not in app_ids:
            app_ids.append(pkg)
            resolved.append({"input": token, "app_id": pkg, "via": "url"})
            continue
        bare = token.replace("google_play_", "", 1)
        if _PACKAGE_RE.match(bare):
            if bare not in app_ids:
                app_ids.append(bare)
                resolved.append(
                    {
                        "input": token,
                        "app_id": bare,
                        "name": _merged_gplay_demo().get(bare),
                        "via": "package_id",
                    }
                )
            continue
        alias = _merged_gplay_aliases().get(token.strip().lower())
        if alias and alias not in app_ids:
            app_ids.append(alias)
            resolved.append(
                {
                    "input": token,
                    "app_id": alias,
                    "name": _merged_gplay_demo().get(alias),
                    "via": "alias",
                }
            )
            continue
        hits = search_google_play_games(token, limit=5)
        if not hits:
            errors.append(f"未找到 Google Play 游戏：{token}")
            continue
        pick = hits[0]
        pkg = str(pick.get("package_id") or "")
        if pkg and pkg not in app_ids:
            app_ids.append(pkg)
            resolved.append(
                {
                    "input": token,
                    "app_id": pkg,
                    "name": pick.get("name"),
                    "via": "search",
                }
            )

    if not app_ids:
        return {
            "success": False,
            "message": "；".join(errors) if errors else "未能解析任何有效 Google Play 游戏",
            "app_ids": [],
            "resolved": resolved,
            "errors": errors,
        }
    return {"success": True, "app_ids": app_ids, "resolved": resolved, "errors": errors}


def merge_into_mvp_dataset(gplay_dataset: Dict[str, Any], output_dir: str = DEFAULT_OUTPUT_DIR) -> Dict[str, Any]:
    out_dir = os.path.abspath(output_dir)
    os.makedirs(out_dir, exist_ok=True)
    steam_path = os.path.join(out_dir, "steam_dataset.json")
    existing: Dict[str, Any] = {"comments": [], "metrics": [], "games": []}
    if os.path.exists(steam_path):
        with open(steam_path, "r", encoding="utf-8") as handle:
            existing = json.load(handle)

    platforms = set(existing.get("platforms") or [])
    platforms.update(["Steam", "TapTap", "Google Play"])

    merged = {
        "source": "mvp_multi",
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "games": list(existing.get("games") or []) + list(gplay_dataset.get("games") or []),
        "comments": list(existing.get("comments") or []) + list(gplay_dataset.get("comments") or []),
        "metrics": list(existing.get("metrics") or []) + list(gplay_dataset.get("metrics") or []),
        "platforms": sorted(platforms),
        "data_mode": gplay_dataset.get("data_mode", "live"),
    }
    analysis = analyze_actual_steam_data(merged["comments"], merged["metrics"])
    validation = validate_analysis(merged["comments"], merged["metrics"], analysis)

    with open(steam_path, "w", encoding="utf-8") as handle:
        json.dump(merged, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "google_play_dataset.json"), "w", encoding="utf-8") as handle:
        json.dump(gplay_dataset, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "analysis.json"), "w", encoding="utf-8") as handle:
        json.dump(analysis, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "validation.json"), "w", encoding="utf-8") as handle:
        json.dump(validation, handle, ensure_ascii=False, indent=2)

    return {
        "success": bool(validation.get("passed")),
        "validation": validation,
        "artifacts": {
            "dataset": steam_path,
            "analysis": os.path.join(out_dir, "analysis.json"),
            "validation": os.path.join(out_dir, "validation.json"),
        },
    }


def run_google_play_pipeline(
    app_ids: Sequence[str],
    max_reviews_per_app: int = 30,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    crawler: Optional[GooglePlayPublicCrawler] = None,
    *,
    product_name_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    crawler = crawler or GooglePlayPublicCrawler()
    dataset = crawler.crawl(
        app_ids=app_ids,
        max_reviews_per_app=max_reviews_per_app,
        product_name_overrides=product_name_overrides,
    )
    merge_result = merge_into_mvp_dataset(dataset, output_dir)
    return {
        "success": merge_result.get("success"),
        "platform": "google_play",
        "data_mode": dataset.get("data_mode"),
        "dataset": dataset,
        "artifacts": merge_result.get("artifacts"),
        "validation": merge_result.get("validation"),
    }
