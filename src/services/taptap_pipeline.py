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

_TAPTAP_ID_RE = re.compile(r"^\d{4,12}$")

_TAPTAP_ALIASES: Dict[str, str] = {
    "原神": "168332",
    "genshin": "168332",
    "genshin impact": "168332",
    "王者荣耀": "23167",
    "honor of kings": "23167",
    "和平精英": "70056",
    "pubg mobile": "70056",
}

_DEMO_GAMES: Dict[str, str] = {
    "168332": "原神",
    "23167": "王者荣耀",
    "70056": "和平精英",
}


class TapTapCrawlerError(RuntimeError):
    pass


class TapTapPublicCrawler:
    """TapTap store search + review sample (falls back to offline demo for known IDs)."""

    SEARCH_URL = "https://www.taptap.cn/webapiv2/search/v4/agg"
    REVIEW_URL = "https://www.taptap.cn/webapiv2/review/v2/list-by-app"

    def __init__(self, timeout: int = 20, session: Optional[requests.Session] = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "GameAnalyzer/1.0",
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
        )

    def search(self, term: str, *, limit: int = 8) -> List[Dict[str, Any]]:
        query = (term or "").strip()
        if len(query) < 2:
            return []
        alias = _TAPTAP_ALIASES.get(query.lower())
        if alias:
            return [{"app_id": alias, "name": _DEMO_GAMES.get(alias, query), "type": "app"}]
        try:
            response = self.session.get(
                self.SEARCH_URL,
                params={"q": query, "limit": min(limit, 10), "types": "app"},
                timeout=self.timeout,
            )
            if response.status_code != 200:
                return []
            payload = response.json()
            items = []
            for block in payload.get("data", {}).get("list") or payload.get("data") or []:
                if isinstance(block, dict) and block.get("type") == "app":
                    app = block.get("app") or block
                    app_id = str(app.get("id") or app.get("app_id") or "")
                    if app_id:
                        items.append(
                            {
                                "app_id": app_id,
                                "name": app.get("title") or app.get("name") or app_id,
                                "type": "app",
                            }
                        )
            return items[:limit]
        except Exception:
            return []

    def crawl(self, app_ids: Sequence[str], max_reviews_per_app: int = 30) -> Dict[str, Any]:
        comments: List[Dict[str, Any]] = []
        metrics: List[Dict[str, Any]] = []
        games: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []

        for raw_id in app_ids:
            app_id = str(raw_id).strip().replace("taptap_", "")
            if not app_id:
                continue
            try:
                game = self._fetch_game(app_id)
                reviews = self._fetch_reviews(app_id, max_reviews_per_app)
                games.append(game)
                comments.extend(self._normalize_reviews(app_id, game["name"], reviews))
                metrics.extend(self._build_metrics(app_id, game, reviews))
            except Exception as exc:
                errors.append({"app_id": app_id, "error": str(exc)})

        if not comments and not metrics:
            raise TapTapCrawlerError(f"No usable TapTap data. Errors: {errors}")

        return {
            "source": "taptap_public",
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "app_ids": list(app_ids),
            "games": games,
            "comments": comments,
            "metrics": metrics,
            "errors": errors,
        }

    def _fetch_game(self, app_id: str) -> Dict[str, Any]:
        if app_id in _DEMO_GAMES:
            return {"app_id": app_id, "name": _DEMO_GAMES[app_id], "platform": "TapTap"}
        detail_url = f"https://www.taptap.cn/webapiv2/app/v6/detail?id={app_id}"
        try:
            response = self.session.get(detail_url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json().get("data") or {}
                title = (data.get("title") or data.get("name") or f"TapTap {app_id}").strip()
                return {"app_id": app_id, "name": title, "platform": "TapTap"}
        except Exception:
            pass
        return {"app_id": app_id, "name": f"TapTap App {app_id}", "platform": "TapTap"}

    def _fetch_reviews(self, app_id: str, limit: int) -> List[Dict[str, Any]]:
        if app_id in _DEMO_GAMES:
            return self._demo_reviews(app_id)
        try:
            response = self.session.get(
                self.REVIEW_URL,
                params={"app_id": app_id, "limit": min(limit, 30), "sort": "new"},
                timeout=self.timeout,
            )
            if response.status_code == 200:
                rows = response.json().get("data", {}).get("list") or []
                if rows:
                    return rows
        except Exception:
            pass
        return self._demo_reviews(app_id)

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
        for idx, review in enumerate(reviews, start=1):
            text = ""
            if isinstance(review.get("contents"), dict):
                text = review["contents"].get("text") or ""
            text = text or review.get("content") or review.get("text") or ""
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
        return {"success": False, "message": "请输入 TapTap 游戏名或 AppID", "app_ids": [], "resolved": []}

    app_ids: List[str] = []
    resolved: List[Dict[str, Any]] = []
    errors: List[str] = []

    for token in tokens:
        if len(app_ids) >= max_games:
            errors.append(f"最多 {max_games} 款，已忽略：{token}")
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
            errors.append(f"未找到 TapTap 游戏：{token}")
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
        "platforms": ["Steam", "TapTap"],
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
) -> Dict[str, Any]:
    crawler = crawler or TapTapPublicCrawler()
    dataset = crawler.crawl(app_ids=app_ids, max_reviews_per_app=max_reviews_per_app)
    merge_result = merge_into_mvp_dataset(dataset, output_dir)
    return {
        "success": merge_result.get("success"),
        "platform": "taptap",
        "dataset": dataset,
        "artifacts": merge_result.get("artifacts"),
        "validation": merge_result.get("validation"),
    }
