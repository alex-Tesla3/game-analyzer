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
    from google_play_scraper import Sort as GPlaySort
    from google_play_scraper import app as gplay_app
    from google_play_scraper import reviews as gplay_reviews
    from google_play_scraper import search as gplay_search

    _GPLAY_AVAILABLE = True
except ImportError:
    GPlaySort = None  # type: ignore
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


class GooglePlayPublicCrawler:
    """Live Google Play scrape via google-play-scraper (public store pages)."""

    def __init__(self, *, market_country: str = "us"):
        from src.services.market_locale import get_market_profile

        self.market = get_market_profile("google_play", market_country)

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

        lang, country = self.market.google_play_lang, self.market.google_play_country
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
        max_reviews_per_app: int | None = None,
        product_name_overrides: Optional[Dict[str, str]] = None,
        review_days: int | None = None,
        use_review_days: bool = True,
        use_max_reviews: bool = False,
        market_country: str | None = None,
    ) -> Dict[str, Any]:
        from src.services.market_locale import get_market_profile

        if market_country:
            self.market = get_market_profile("google_play", market_country)
        from src.services.crawl_runner import throttle_between_products
        from src.services.review_window import normalize_max_reviews, normalize_review_days

        if not use_review_days and not use_max_reviews:
            raise ValueError("至少启用「时间范围」或「评价数量」之一")
        window_days = normalize_review_days(review_days) if use_review_days else None
        review_cap = normalize_max_reviews(max_reviews_per_app) if use_max_reviews else None
        ids = [
            str(pkg).strip().replace("google_play_", "", 1)
            for pkg in (package_ids or app_ids or [])
            if str(pkg).strip()
        ]

        comments: List[Dict[str, Any]] = []
        metrics: List[Dict[str, Any]] = []
        games: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        used_demo = False

        # Google Play throttles parallel review pagination — crawl products sequentially.
        for index, pkg in enumerate(ids):
            if index > 0:
                throttle_between_products()
            try:
                game, reviews, demo = self._fetch_package(
                    pkg,
                    review_days=window_days,
                    max_reviews=review_cap,
                )
                used_demo = used_demo or demo
                games.append(game)
                comments.extend(self._normalize_reviews(pkg, game["name"], reviews))
                metrics.extend(self._build_metrics(pkg, game["name"], reviews))
            except Exception as exc:
                errors.append({"package_id": pkg, "error": str(exc)})

        if not comments and not metrics:
            raise GooglePlayCrawlerError(f"No usable Google Play data. Errors: {errors}")

        review_counts = {
            pkg: sum(1 for comment in comments if str(comment.get("product")) == pkg) for pkg in ids
        }
        payload = {
            "source": "google_play_public",
            "data_mode": "demo_fallback" if used_demo else "live",
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "use_review_days": use_review_days,
            "review_days": window_days,
            "use_max_reviews": use_max_reviews,
            "max_reviews_per_app": review_cap,
            "market_country": self.market.country,
            "market_label": self.market.label,
            "review_locale": [self.market.google_play_lang, self.market.google_play_country],
            "review_counts": review_counts,
            "platform": "Google Play",
            "games": games,
            "comments": comments,
            "metrics": metrics,
            "errors": errors,
        }
        return apply_product_display_names(payload, product_name_overrides)

    def _fetch_reviews_in_window(
        self,
        package_id: str,
        *,
        lang: str,
        country: str,
        window_days: int,
        max_reviews: int | None = None,
    ) -> List[Dict[str, Any]]:
        from src.services.crawl_runner import throttle_page_fetch
        from src.services.review_window import (
            collect_reviews_from_batches,
            gplay_review_datetime,
            normalize_max_reviews,
            normalize_review_days,
        )

        continuation_token = None
        page_size = 200

        def _iter_batches():
            nonlocal continuation_token
            while True:
                throttle_page_fetch()
                kwargs: Dict[str, Any] = {
                    "lang": lang,
                    "country": country,
                    "count": page_size,
                    "sort": GPlaySort.NEWEST,
                }
                if continuation_token is not None:
                    kwargs["continuation_token"] = continuation_token
                rows, next_token = gplay_reviews(package_id, **kwargs)
                continuation_token = next_token
                parsed = [
                    {
                        "score": row.get("score"),
                        "text": row.get("content") or "",
                        "thumbsUp": (row.get("score") or 0) >= 4,
                        "at": row.get("at"),
                        "reviewId": row.get("reviewId"),
                    }
                    for row in (rows or [])
                    if row.get("content")
                ]
                yield parsed
                if continuation_token is None or continuation_token.token is None:
                    break
                if not rows:
                    break

        days = normalize_review_days(window_days) if window_days is not None else None
        cap = normalize_max_reviews(max_reviews)
        return collect_reviews_from_batches(
            _iter_batches(),
            days=days,
            max_count=cap,
            date_fn=gplay_review_datetime,
        )

    def _fetch_package(
        self,
        package_id: str,
        *,
        review_days: int | None = None,
        max_reviews: int | None = None,
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
        from src.services.review_window import normalize_max_reviews, normalize_review_days

        if _GPLAY_AVAILABLE:
            lang, country = self.market.google_play_lang, self.market.google_play_country
            try:
                info = gplay_app(package_id, lang=lang, country=country)
                name = info.get("title") or _merged_gplay_demo().get(package_id) or package_id.split(".")[-1]
                window_days = normalize_review_days(review_days) if review_days is not None else None
                cap = normalize_max_reviews(max_reviews)

                parsed = self._fetch_reviews_in_window(
                    package_id,
                    lang=lang,
                    country=country,
                    window_days=window_days,
                    max_reviews=cap,
                )
                if not parsed:
                    if window_days is not None and cap is not None:
                        detail = f"在近 {window_days} 天内未凑满 {cap} 条评论"
                    elif window_days is not None:
                        detail = f"在近 {window_days} 天内没有可用评论，请扩大时间范围"
                    elif cap is not None:
                        detail = f"未能拉到评论（目标 {cap} 条）"
                    else:
                        detail = "没有可用评论"
                    raise GooglePlayCrawlerError(f"Google Play {package_id} {detail}。")
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
            reviews = self._demo_reviews(package_id, name)
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
        from src.services.review_window import gplay_review_datetime, iso_date_from_datetime

        out: List[Dict[str, Any]] = []
        for review in reviews:
            text = review.get("text") or review.get("content") or ""
            score = int(review.get("score") or review.get("rating") or 0)
            positive = bool(review.get("thumbsUp")) if "thumbsUp" in review else score >= 4
            review_date = iso_date_from_datetime(gplay_review_datetime(review))
            if not review_date:
                review_date = datetime.now(timezone.utc).date().isoformat()
            out.append(
                {
                    "product": package_id,
                    "product_name": game_name,
                    "platform": "Google Play",
                    "channel": "Google Play",
                    "日期": review_date,
                    "date": review_date,
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


def search_google_play_games(
    term: str,
    *,
    limit: int = 8,
    market_country: str = "us",
) -> List[Dict[str, Any]]:
    return GooglePlayPublicCrawler(market_country=market_country).search(term, limit=limit)


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
    from src.services.mvp_dataset_merge import merge_platform_dataset

    return merge_platform_dataset(
        gplay_dataset,
        platform="Google Play",
        output_dir=output_dir,
        platform_artifact_name="google_play_dataset.json",
        extra_platforms=["Steam", "TapTap"],
    )


def run_google_play_pipeline(
    app_ids: Sequence[str],
    max_reviews_per_app: int | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    crawler: Optional[GooglePlayPublicCrawler] = None,
    *,
    product_name_overrides: Optional[Dict[str, str]] = None,
    review_days: int | None = None,
    use_review_days: bool = True,
    use_max_reviews: bool = False,
    market_country: str = "us",
) -> Dict[str, Any]:
    crawler = crawler or GooglePlayPublicCrawler(market_country=market_country)
    dataset = crawler.crawl(
        app_ids=app_ids,
        max_reviews_per_app=max_reviews_per_app,
        product_name_overrides=product_name_overrides,
        review_days=review_days,
        use_review_days=use_review_days,
        use_max_reviews=use_max_reviews,
        market_country=market_country,
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
