"""Google Play public review MVP — package resolve, offline demo crawl, merge into MVP."""

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

_PACKAGE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$")

_ALIASES: Dict[str, str] = {
    "原神": "com.miHoYo.GenshinImpact",
    "genshin": "com.miHoYo.GenshinImpact",
    "genshin impact": "com.miHoYo.GenshinImpact",
    "王者荣耀": "com.tencent.tmgp.sgame",
    "honor of kings": "com.tencent.tmgp.sgame",
    "和平精英": "com.tencent.tmgp.pubgmhd",
    "pubg mobile": "com.tencent.ig",
}

_DEMO_GAMES: Dict[str, str] = {
    "com.miHoYo.GenshinImpact": "原神",
    "com.tencent.tmgp.sgame": "王者荣耀",
    "com.tencent.tmgp.pubgmhd": "和平精英",
}


class GooglePlayCrawlerError(RuntimeError):
    pass


class GooglePlayPublicCrawler:
    """Offline-first demo crawler for known package names (no API key required)."""

    def search(self, term: str, *, limit: int = 8) -> List[Dict[str, Any]]:
        query = (term or "").strip()
        if len(query) < 2:
            return []
        alias = _ALIASES.get(query.lower())
        if alias:
            return [{"package_id": alias, "app_id": alias, "name": _DEMO_GAMES.get(alias, query), "type": "app"}]
        hits: List[Dict[str, Any]] = []
        lower = query.lower()
        for pkg, name in _DEMO_GAMES.items():
            if lower in name.lower() or lower in pkg.lower():
                hits.append({"package_id": pkg, "app_id": pkg, "name": name, "type": "app"})
        if hits:
            return hits[:limit]
        if _PACKAGE_RE.match(query):
            return [{"package_id": query, "app_id": query, "name": query.split(".")[-1], "type": "app"}]
        return []

    def crawl(
        self,
        package_ids: Sequence[str] | None = None,
        *,
        app_ids: Sequence[str] | None = None,
        max_reviews_per_app: int = 30,
    ) -> Dict[str, Any]:
        ids = list(package_ids or app_ids or [])
        comments: List[Dict[str, Any]] = []
        metrics: List[Dict[str, Any]] = []
        games: List[Dict[str, Any]] = []
        for pkg in ids:
            pkg = str(pkg).strip()
            if not pkg:
                continue
            name = _DEMO_GAMES.get(pkg, pkg.split(".")[-1])
            reviews = self._demo_reviews(pkg, name)[: max(3, min(max_reviews_per_app, 50))]
            games.append({"package_id": pkg, "name": name, "platform": "Google Play"})
            comments.extend(self._normalize_reviews(pkg, name, reviews))
            metrics.extend(self._build_metrics(pkg, name, reviews))
        return {
            "source": "google_play_public",
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "platform": "Google Play",
            "games": games,
            "comments": comments,
            "metrics": metrics,
        }

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
        bare = token.replace("google_play_", "", 1)
        if _PACKAGE_RE.match(bare):
            if bare not in app_ids:
                app_ids.append(bare)
                resolved.append(
                    {
                        "input": token,
                        "app_id": bare,
                        "name": _DEMO_GAMES.get(bare),
                        "via": "package_id",
                    }
                )
            continue
        alias = _ALIASES.get(token.strip().lower())
        if alias and alias not in app_ids:
            app_ids.append(alias)
            resolved.append(
                {
                    "input": token,
                    "app_id": alias,
                    "name": _DEMO_GAMES.get(alias),
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
) -> Dict[str, Any]:
    crawler = crawler or GooglePlayPublicCrawler()
    dataset = crawler.crawl(app_ids=app_ids, max_reviews_per_app=max_reviews_per_app)
    merge_result = merge_into_mvp_dataset(dataset, output_dir)
    return {
        "success": merge_result.get("success"),
        "platform": "google_play",
        "dataset": dataset,
        "artifacts": merge_result.get("artifacts"),
        "validation": merge_result.get("validation"),
    }
