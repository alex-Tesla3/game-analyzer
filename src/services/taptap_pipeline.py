"""TapTap public review MVP — search, crawl, merge into MVP artifacts."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import requests

from src.mvp_pipeline import (
    DEFAULT_OUTPUT_DIR,
    analyze_actual_steam_data,
    validate_analysis,
)
from src.product_registry import apply_product_display_names, taptap_alias_map, taptap_demo_map
from src.services.platform_crawl_utils import (
    allow_demo_fallback,
    extract_taptap_app_id,
    parse_taptap_review_row,
    taptap_params,
)

_TAPTAP_ID_RE = re.compile(r"^\d{4,12}$")
_TAPTAP_BASE = os.getenv("TAPTAP_API_BASE", "https://www.taptap.cn/webapiv2").rstrip("/")

_TAPTAP_ALIASES: Dict[str, str] = {
    "原神": "168332",
    "genshin": "168332",
    "genshin impact": "168332",
    "王者荣耀": "23167",
    "honor of kings": "23167",
    "和平精英": "70056",
    "pubg mobile": "70056",
    "崩坏星穹铁道": "170608",
    "星穹铁道": "170608",
    "honkai star rail": "170608",
    "绝区零": "234280",
    "zenless zone zero": "234280",
    "明日方舟": "70253",
    "arknights": "70253",
    "阴阳师": "124047",
    "英雄联盟手游": "58881",
    "lolm": "58881",
}

_DEMO_GAMES: Dict[str, str] = {
    "168332": "原神",
    "23167": "王者荣耀",
    "70056": "和平精英",
}


def _merged_taptap_aliases() -> Dict[str, str]:
    merged = dict(_TAPTAP_ALIASES)
    merged.update(taptap_alias_map())
    return merged


def _merged_taptap_demo() -> Dict[str, str]:
    merged = dict(_DEMO_GAMES)
    merged.update(taptap_demo_map())
    return merged


class TapTapCrawlerError(RuntimeError):
    pass


class TapTapPublicCrawler:
    """TapTap webapiv2 — live crawl with optional demo fallback."""

    def __init__(self, timeout: int = 20, session: Optional[requests.Session] = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.taptap.cn/",
            }
        )

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{_TAPTAP_BASE}/{path.lstrip('/')}"
        response = self.session.get(
            url,
            params=taptap_params(params),
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise TapTapCrawlerError(f"TapTap HTTP {response.status_code} for {path}")
        payload = response.json()
        if payload.get("success") is False:
            err = (payload.get("data") or {}).get("msg") or payload.get("error") or "unknown"
            raise TapTapCrawlerError(f"TapTap API error: {err}")
        return payload

    def search(self, term: str, *, limit: int = 8) -> List[Dict[str, Any]]:
        query = (term or "").strip()
        if len(query) < 2:
            return []

        app_from_url = extract_taptap_app_id(query)
        if app_from_url:
            detail = self._fetch_game(app_from_url)
            return [
                {
                    "app_id": app_from_url,
                    "name": detail.get("name") or app_from_url,
                    "type": "app",
                }
            ]

        alias = _merged_taptap_aliases().get(query.lower())
        if alias:
            return [
                {
                    "app_id": alias,
                    "name": _merged_taptap_demo().get(alias, query),
                    "type": "app",
                }
            ]

        if _TAPTAP_ID_RE.match(query.replace("taptap_", "", 1)):
            bare = query.replace("taptap_", "", 1)
            detail = self._fetch_game(bare)
            return [{"app_id": bare, "name": detail.get("name") or bare, "type": "app"}]

        return []

    def crawl(
        self,
        app_ids: Sequence[str],
        max_reviews_per_app: int | None = None,
        *,
        product_name_overrides: Optional[Dict[str, str]] = None,
        review_days: int | None = None,
    ) -> Dict[str, Any]:
        from src.services.crawl_runner import crawl_products_parallel
        from src.services.review_window import normalize_review_days

        window_days = normalize_review_days(review_days)
        valid_ids = [str(raw).strip().replace("taptap_", "") for raw in app_ids if str(raw).strip()]

        def _crawl_one(raw_id: str) -> Dict[str, Any]:
            worker = TapTapPublicCrawler(timeout=self.timeout)
            app_id = str(raw_id).strip().replace("taptap_", "")
            try:
                game = worker._fetch_game(app_id)
                reviews, demo = worker._fetch_reviews(
                    app_id,
                    review_days=window_days,
                    max_reviews=max_reviews_per_app,
                )
                return {
                    "app_id": app_id,
                    "ok": True,
                    "demo": demo,
                    "game": game,
                    "reviews": reviews,
                }
            except Exception as exc:
                if app_id in _merged_taptap_demo():
                    demo_name = _merged_taptap_demo()[app_id]
                    game = {"app_id": app_id, "name": demo_name, "platform": "TapTap"}
                    reviews = worker._demo_reviews(app_id)
                    return {
                        "app_id": app_id,
                        "ok": True,
                        "demo": True,
                        "game": game,
                        "reviews": reviews,
                        "error": f"live_fetch_failed: {exc}",
                    }
                return {"app_id": app_id, "ok": False, "error": str(exc)}

        results = crawl_products_parallel(valid_ids, _crawl_one)

        comments: List[Dict[str, Any]] = []
        metrics: List[Dict[str, Any]] = []
        games: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        used_demo = False

        for app_id in valid_ids:
            row = results.get(app_id) or {"ok": False, "error": "missing crawl result"}
            if row.get("ok"):
                used_demo = used_demo or bool(row.get("demo"))
                game = row["game"]
                reviews = row["reviews"]
                games.append(game)
                comments.extend(self._normalize_reviews(app_id, game["name"], reviews))
                metrics.extend(self._build_metrics(app_id, game, reviews))
                if row.get("error"):
                    errors.append({"app_id": app_id, "error": str(row["error"])})
            else:
                errors.append({"app_id": app_id, "error": str(row.get("error") or "unknown error")})

        if not comments and not metrics:
            raise TapTapCrawlerError(f"No usable TapTap data. Errors: {errors}")

        payload = {
            "source": "taptap_public",
            "data_mode": "demo_fallback" if used_demo else "live",
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "review_days": window_days,
            "app_ids": list(app_ids),
            "games": games,
            "comments": comments,
            "metrics": metrics,
            "errors": errors,
        }
        return apply_product_display_names(payload, product_name_overrides)

    def _fetch_game(self, app_id: str) -> Dict[str, Any]:
        payload = self._get_json("app/v6/detail", {"id": app_id})
        app = (payload.get("data") or {}).get("app") or payload.get("data") or {}
        title = (app.get("title") or app.get("name") or f"TapTap {app_id}").strip()
        return {"app_id": app_id, "name": title, "platform": "TapTap"}

    def _fetch_reviews(
        self,
        app_id: str,
        *,
        review_days: int | None = None,
        max_reviews: int | None = None,
    ) -> tuple[List[Dict[str, Any]], bool]:
        from src.services.crawl_runner import throttle_page_fetch
        from src.services.review_window import (
            collect_recent_reviews_within_days,
            normalize_review_days,
            taptap_review_datetime,
        )

        try:
            window_days = normalize_review_days(review_days)
            cap = int(max_reviews) if max_reviews and max_reviews > 0 else None
            offset = 0
            page_size = 30

            def _iter_batches():
                nonlocal offset
                while True:
                    throttle_page_fetch()
                    batch_limit = page_size
                    payload = self._get_json(
                        "review/v2/list-by-app",
                        {
                            "app_id": app_id,
                            "limit": batch_limit,
                            "from": offset,
                            "sort": "new",
                        },
                    )
                    rows = (payload.get("data") or {}).get("list") or []
                    parsed = [parse_taptap_review_row(row) for row in rows if row]
                    parsed = [r for r in parsed if r.get("content")]
                    yield parsed
                    if not parsed or len(parsed) < batch_limit:
                        break
                    offset += len(parsed)

            collected = collect_recent_reviews_within_days(
                _iter_batches(),
                days=window_days,
                max_count=cap,
                date_fn=taptap_review_datetime,
            )

            if collected:
                return collected, False
            raise TapTapCrawlerError(
                f"TapTap app_id={app_id} 在近 {window_days} 天内没有可用评论，请扩大时间范围。"
            )
        except TapTapCrawlerError:
            if not allow_demo_fallback() and app_id not in _merged_taptap_demo():
                raise

        if allow_demo_fallback() or app_id in _merged_taptap_demo():
            return self._demo_reviews(app_id), True
        raise TapTapCrawlerError(
            f"TapTap 评论抓取失败（app_id={app_id}）。"
            "请确认 AppID 正确，或设置 GA_PLATFORM_DEMO_FALLBACK=true 启用演示回退。"
        )

    def _demo_reviews(self, app_id: str) -> List[Dict[str, Any]]:
        name = _merged_taptap_demo().get(app_id, f"App {app_id}")
        created_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        return [
            {
                "score": 5,
                "contents": {"text": f"{name} 玩法不错，画面精美，值得推荐。"},
                "voted_up": True,
                "created_time": created_ms,
            },
            {
                "score": 2,
                "contents": {"text": f"{name} 抽卡概率太低，肝度偏高。"},
                "voted_up": False,
                "created_time": created_ms,
            },
            {
                "score": 3,
                "contents": {"text": f"{name} 最近版本更新后优化变好了。"},
                "voted_up": True,
                "created_time": created_ms,
            },
        ]

    def _normalize_reviews(
        self, app_id: str, game_name: str, reviews: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        from src.services.review_window import iso_date_from_datetime, taptap_review_datetime

        out: List[Dict[str, Any]] = []
        for review in reviews:
            text = review.get("content") or review.get("text") or ""
            if isinstance(review.get("contents"), dict) and not text:
                text = review["contents"].get("text") or ""
            score = review.get("score") or review.get("rating") or 0
            positive = bool(review.get("voted_up")) if "voted_up" in review else int(score) >= 4
            review_date = iso_date_from_datetime(taptap_review_datetime(review))
            out.append(
                {
                    "product": app_id,
                    "product_name": game_name,
                    "platform": "TapTap",
                    "channel": "TapTap",
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
        self, app_id: str, game: Dict[str, Any], reviews: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        name = game.get("name") or app_id
        total = len(reviews)
        positive = sum(
            1
            for r in reviews
            if (r.get("voted_up") if "voted_up" in r else int(r.get("score") or 0) >= 4)
        )
        rate = round(positive / total * 100, 1) if total else 0.0
        return [
            {
                "product": app_id,
                "product_name": name,
                "platform": "TapTap",
                "source": "taptap_public",
                "metric": "抓取评论数",
                "值": total,
            },
            {
                "product": app_id,
                "product_name": name,
                "platform": "TapTap",
                "source": "taptap_public",
                "metric": "样本好评率",
                "值": f"{rate}%",
            },
        ]


def search_taptap_games(term: str, *, limit: int = 8, crawler: Optional[TapTapPublicCrawler] = None) -> List[Dict[str, Any]]:
    return (crawler or TapTapPublicCrawler()).search(term, limit=limit)


def split_input_tokens(raw: Sequence[str] | str) -> List[str]:
    if isinstance(raw, str):
        parts: List[str] = []
        for segment in re.split(r"[\n,;]+", raw.strip()):
            token = segment.strip()
            if token:
                parts.append(token)
        return parts
    return [str(x).strip() for x in raw if str(x).strip()]


def resolve_taptap_inputs(raw: Sequence[str] | str, *, max_games: int = 5) -> Dict[str, Any]:
    tokens = split_input_tokens(raw)
    if not tokens:
        return {"success": False, "message": "请输入 TapTap 游戏名、AppID 或链接", "app_ids": [], "resolved": []}

    app_ids: List[str] = []
    resolved: List[Dict[str, Any]] = []
    errors: List[str] = []

    for token in tokens:
        if len(app_ids) >= max_games:
            errors.append(f"最多 {max_games} 款，已忽略：{token}")
            continue
        url_id = extract_taptap_app_id(token)
        if url_id and url_id not in app_ids:
            app_ids.append(url_id)
            resolved.append({"input": token, "app_id": url_id, "via": "url"})
            continue
        bare = token.replace("taptap_", "", 1)
        if _TAPTAP_ID_RE.match(bare):
            if bare not in app_ids:
                app_ids.append(bare)
                resolved.append({"input": token, "app_id": bare, "via": "app_id"})
            continue
        alias = _merged_taptap_aliases().get(token.strip().lower())
        if alias and alias not in app_ids:
            app_ids.append(alias)
            resolved.append(
                {
                    "input": token,
                    "app_id": alias,
                    "name": _merged_taptap_demo().get(alias),
                    "via": "alias",
                }
            )
            continue
        hits = search_taptap_games(token, limit=5)
        if not hits:
            errors.append(f"未找到 TapTap 游戏：{token}（可粘贴 taptap.cn/app/数字 链接）")
            continue
        pick = hits[0]
        app_id = str(pick.get("app_id") or "")
        if app_id and app_id not in app_ids:
            app_ids.append(app_id)
            resolved.append({"input": token, "app_id": app_id, "name": pick.get("name"), "via": "search"})

    if not app_ids:
        return {
            "success": False,
            "message": "；".join(errors) if errors else "未能解析 TapTap 游戏",
            "app_ids": [],
            "resolved": resolved,
            "errors": errors,
        }
    return {"success": True, "app_ids": app_ids, "resolved": resolved, "errors": errors}


def merge_into_mvp_dataset(taptap_dataset: Dict[str, Any], output_dir: str = DEFAULT_OUTPUT_DIR) -> Dict[str, Any]:
    from src.services.mvp_dataset_merge import merge_platform_dataset

    return merge_platform_dataset(
        taptap_dataset,
        platform="TapTap",
        output_dir=output_dir,
        platform_artifact_name="taptap_dataset.json",
        extra_platforms=["Steam"],
    )


def run_taptap_pipeline(
    app_ids: Sequence[str],
    max_reviews_per_app: int | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    crawler: Optional[TapTapPublicCrawler] = None,
    *,
    product_name_overrides: Optional[Dict[str, str]] = None,
    review_days: int | None = None,
) -> Dict[str, Any]:
    crawler = crawler or TapTapPublicCrawler()
    dataset = crawler.crawl(
        app_ids=app_ids,
        max_reviews_per_app=max_reviews_per_app,
        product_name_overrides=product_name_overrides,
        review_days=review_days,
    )
    merge_result = merge_into_mvp_dataset(dataset, output_dir)
    return {
        "success": merge_result.get("success"),
        "platform": "taptap",
        "data_mode": dataset.get("data_mode"),
        "dataset": dataset,
        "artifacts": merge_result.get("artifacts"),
        "validation": merge_result.get("validation"),
    }
