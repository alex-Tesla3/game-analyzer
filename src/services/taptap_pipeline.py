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
    **taptap_demo_map(),
}
_TAPTAP_ALIASES.update(taptap_alias_map())


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

        alias = _TAPTAP_ALIASES.get(query.lower())
        if alias:
            return [
                {
                    "app_id": alias,
                    "name": _DEMO_GAMES.get(alias, query),
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
        max_reviews_per_app: int = 30,
        *,
        product_name_overrides: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        comments: List[Dict[str, Any]] = []
        metrics: List[Dict[str, Any]] = []
        games: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        used_demo = False

        for raw_id in app_ids:
            app_id = str(raw_id).strip().replace("taptap_", "")
            if not app_id:
                continue
            try:
                game = self._fetch_game(app_id)
                reviews, demo = self._fetch_reviews(app_id, max_reviews_per_app)
                used_demo = used_demo or demo
                games.append(game)
                comments.extend(self._normalize_reviews(app_id, game["name"], reviews))
                metrics.extend(self._build_metrics(app_id, game, reviews))
            except Exception as exc:
                if app_id in _DEMO_GAMES:
                    demo_name = _DEMO_GAMES[app_id]
                    game = {"app_id": app_id, "name": demo_name, "platform": "TapTap"}
                    reviews = self._demo_reviews(app_id)
                    used_demo = True
                    games.append(game)
                    comments.extend(self._normalize_reviews(app_id, demo_name, reviews))
                    metrics.extend(self._build_metrics(app_id, game, reviews))
                    errors.append({"app_id": app_id, "error": f"live_fetch_failed: {exc}"})
                else:
                    errors.append({"app_id": app_id, "error": str(exc)})

        if not comments and not metrics:
            raise TapTapCrawlerError(f"No usable TapTap data. Errors: {errors}")

        payload = {
            "source": "taptap_public",
            "data_mode": "demo_fallback" if used_demo else "live",
            "crawled_at": datetime.now(timezone.utc).isoformat(),
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

    def _fetch_reviews(self, app_id: str, limit: int) -> tuple[List[Dict[str, Any]], bool]:
        try:
            payload = self._get_json(
                "review/v2/list-by-app",
                {
                    "app_id": app_id,
                    "limit": min(max(limit, 3), 30),
                    "sort": "new",
                },
            )
            rows = (payload.get("data") or {}).get("list") or []
            parsed = [parse_taptap_review_row(row) for row in rows if row]
            parsed = [r for r in parsed if r.get("content")]
            if parsed:
                return parsed, False
        except TapTapCrawlerError:
            if not allow_demo_fallback() and app_id not in _DEMO_GAMES:
                raise

        if allow_demo_fallback() or app_id in _DEMO_GAMES:
            return self._demo_reviews(app_id), True
        raise TapTapCrawlerError(
            f"TapTap 评论抓取失败（app_id={app_id}）。"
            "请确认 AppID 正确，或设置 GA_PLATFORM_DEMO_FALLBACK=true 启用演示回退。"
        )

    def _demo_reviews(self, app_id: str) -> List[Dict[str, Any]]:
        name = _DEMO_GAMES.get(app_id, f"App {app_id}")
        return [
            {"score": 5, "contents": {"text": f"{name} 玩法不错，画面精美，值得推荐。"}, "voted_up": True},
            {"score": 2, "contents": {"text": f"{name} 抽卡概率太低，肝度偏高。"}, "voted_up": False},
            {"score": 3, "contents": {"text": f"{name} 最近版本更新后优化变好了。"}, "voted_up": True},
        ]

    def _normalize_reviews(
        self, app_id: str, game_name: str, reviews: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for review in reviews:
            text = review.get("content") or review.get("text") or ""
            if isinstance(review.get("contents"), dict) and not text:
                text = review["contents"].get("text") or ""
            score = review.get("score") or review.get("rating") or 0
            positive = bool(review.get("voted_up")) if "voted_up" in review else int(score) >= 4
            out.append(
                {
                    "product": app_id,
                    "product_name": game_name,
                    "platform": "TapTap",
                    "channel": "TapTap",
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
        alias = _TAPTAP_ALIASES.get(token.strip().lower())
        if alias and alias not in app_ids:
            app_ids.append(alias)
            resolved.append({"input": token, "app_id": alias, "name": _DEMO_GAMES.get(alias), "via": "alias"})
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
    """Merge TapTap crawl into existing steam_dataset.json and re-validate."""
    out_dir = os.path.abspath(output_dir)
    os.makedirs(out_dir, exist_ok=True)
    steam_path = os.path.join(out_dir, "steam_dataset.json")
    existing: Dict[str, Any] = {"comments": [], "metrics": [], "games": []}
    if os.path.exists(steam_path):
        with open(steam_path, "r", encoding="utf-8") as handle:
            existing = json.load(handle)

    merged = {
        "source": "mvp_multi",
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "games": list(existing.get("games") or []) + list(taptap_dataset.get("games") or []),
        "comments": list(existing.get("comments") or []) + list(taptap_dataset.get("comments") or []),
        "metrics": list(existing.get("metrics") or []) + list(taptap_dataset.get("metrics") or []),
        "platforms": sorted(set((existing.get("platforms") or []) + ["Steam", "TapTap"])),
        "data_mode": taptap_dataset.get("data_mode", "live"),
    }
    analysis = analyze_actual_steam_data(merged["comments"], merged["metrics"])
    validation = validate_analysis(merged["comments"], merged["metrics"], analysis)

    with open(steam_path, "w", encoding="utf-8") as handle:
        json.dump(merged, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "taptap_dataset.json"), "w", encoding="utf-8") as handle:
        json.dump(taptap_dataset, handle, ensure_ascii=False, indent=2)
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


def run_taptap_pipeline(
    app_ids: Sequence[str],
    max_reviews_per_app: int = 30,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    crawler: Optional[TapTapPublicCrawler] = None,
    *,
    product_name_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    crawler = crawler or TapTapPublicCrawler()
    dataset = crawler.crawl(
        app_ids=app_ids,
        max_reviews_per_app=max_reviews_per_app,
        product_name_overrides=product_name_overrides,
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
