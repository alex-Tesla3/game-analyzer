"""数据 Agent API: 状态 / 处理管道 / 语义检索。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.services import supabase_store
from src.web_common import get_current_user

router = APIRouter(tags=["agent"])

_ALLOWED_STEPS = ("clean", "label", "embed", "store", "aggregate")


@router.get("/api/agent/status")
async def agent_status(token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)

    from src.services.llm_client import LLM_CONFIG, default_embedding_model, embedding_dim

    payload = {
        "success": True,
        "supabase_enabled": supabase_store.enabled(),
        "supabase_url": supabase_store._url_host() if supabase_store.enabled() else None,
        "embedding_dim": embedding_dim(),
        "embedding_model": __import__("os").getenv("EMBEDDING_MODEL", "") or default_embedding_model(),
        "llm_provider": LLM_CONFIG.get("provider", "openai"),
        "steps": list(_ALLOWED_STEPS),
    }
    if supabase_store.enabled():
        try:
            payload["supabase_dim"] = supabase_store.schema_dim()
            payload["noise_summary"] = supabase_store.noise_summary()
        except Exception as exc:
            payload["supabase_error"] = str(exc)
    return payload


@router.post("/api/agent/process")
async def agent_process(request: Request, token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    current_user = await get_current_user(token)

    body = await request.json()
    steps_raw = body.get("steps")
    steps = None
    if steps_raw:
        steps = [s for s in steps_raw if s in _ALLOWED_STEPS] or None
    use_llm = bool(body.get("use_llm", True))
    dataset_path = str(body.get("dataset_path") or "").strip()

    from src.services.data_agent import run_data_agent

    report = await run_data_agent(
        current_user.username,
        dataset_path=dataset_path,
        steps=steps,
        use_llm=use_llm,
    )
    return report


@router.post("/api/agent/semantic-search")
async def semantic_search(request: Request, token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)

    body = await request.json()
    query = str(body.get("query") or "").strip()
    if not query:
        return {"success": False, "message": "query 不能为空"}
    if not supabase_store.enabled():
        return {"success": False, "message": "Supabase 未配置,无法语义检索"}

    from src.services.llm_client import embed_text

    try:
        vector = await embed_text(query)
    except Exception as exc:
        return {"success": False, "message": f"生成查询向量失败: {exc}"}

    try:
        results = supabase_store.semantic_search(
            vector,
            game_id=body.get("game_id") or None,
            platform=body.get("platform") or None,
            exclude_noise=bool(body.get("exclude_noise", True)),
            limit=int(body.get("limit", 10)),
        )
    except Exception as exc:
        return {"success": False, "message": f"语义检索失败: {exc}"}

    return {"success": True, "query": query, "results": results}
