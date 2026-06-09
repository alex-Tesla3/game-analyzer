"""Thin async clients for configured LLM providers."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

import asyncio

from auth import LLM_CONFIG

_DEFAULT_LLM_TIMEOUT = float(os.getenv("GA_LLM_TIMEOUT_SECONDS", "45"))


def refresh_llm_config_from_db() -> None:
    """Load persisted LLM settings from SQLite into in-memory LLM_CONFIG."""
    try:
        from database import LLMConfigRepository

        row = LLMConfigRepository.get()
        if not row:
            return
        api_key = row.get("api_key") or ""
        if api_key and "..." in api_key and len(api_key) < 24:
            api_key = ""
            try:
                LLMConfigRepository.save({"api_key": ""})
            except Exception:
                pass
        endpoint = row.get("endpoint") or ""
        if (row.get("provider") or "") == "ollama" and not endpoint:
            endpoint = "http://localhost:11434"
        LLM_CONFIG.update(
            {
                "provider": row.get("provider") or LLM_CONFIG.get("provider", "openai"),
                "model": row.get("model") or LLM_CONFIG.get("model", ""),
                "api_key": api_key,
                "endpoint": endpoint,
                "temperature": row.get("temperature", LLM_CONFIG.get("temperature", 0.7)),
                "max_tokens": row.get("max_tokens", LLM_CONFIG.get("max_tokens", 2000)),
            }
        )
    except Exception as exc:
        print(f"Failed to refresh LLM config from DB: {exc}")


def _ollama_base_url(endpoint: str) -> str:
    base = (endpoint or "http://localhost:11434").strip().rstrip("/")
    for suffix in ("/api/generate", "/api/chat", "/v1/chat/completions", "/v1", "/api"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return base.rstrip("/")


def _ollama_error_message(response: Any, model: str, base: str) -> str:
    """Turn Ollama HTTP errors into actionable Chinese messages."""
    err_text = ""
    try:
        body = response.json()
        err_text = str(body.get("error") or body.get("message") or "")
    except Exception:
        err_text = (getattr(response, "text", None) or "")[:200]

    if "not found" in err_text.lower() or getattr(response, "status_code", None) == 404:
        hint = f"模型「{model}」未在本机 Ollama 中安装。"
        if err_text:
            hint += f" ({err_text})"
        hint += " 请运行 `ollama list` 查看已安装模型，或在管理页选择本地模型（如 gemma4:latest）。"
        return hint

    status = getattr(response, "status_code", "?")
    if status == 405:
        return f"Ollama 地址配置有误：{base}。请只填写根地址，例如 http://localhost:11434"
    return f"Ollama 请求失败（HTTP {status}）{(': ' + err_text) if err_text else ''}"


async def call_openai_api(prompt: str, api_key: str, model: str, endpoint: str, *, max_tokens: int = 500) -> str:
    import httpx

    if not api_key:
        raise RuntimeError("请先配置API密钥")

    url = endpoint or "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data, timeout=60.0)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def call_anthropic_api(prompt: str, api_key: str, model: str, *, max_tokens: int = 500) -> str:
    import httpx

    if not api_key:
        raise RuntimeError("请先配置API密钥")

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    data = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data, timeout=60.0)
        response.raise_for_status()
        return response.json()["content"][0]["text"]


async def call_gemini_api(prompt: str, api_key: str, model: str, *, max_tokens: int = 500) -> str:
    import httpx

    if not api_key:
        raise RuntimeError("请先配置API密钥")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers={"Content-Type": "application/json"}, json=data, timeout=60.0)
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]


async def call_ollama_api(prompt: str, model: str, endpoint: str, *, max_tokens: int = 500) -> str:
    import httpx

    base = _ollama_base_url(endpoint)
    chat_url = f"{base}/api/chat"
    generate_url = f"{base}/api/generate"
    timeout = httpx.Timeout(180.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            probe = await client.get(f"{base}/api/tags", timeout=5.0)
            if probe.status_code != 200:
                raise RuntimeError(
                    f"无法连接 Ollama（{base}）。请确认已执行 `ollama serve`，地址为 http://localhost:11434"
                )
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"无法连接 Ollama（{base}）。请确认已启动 Ollama 服务（ollama serve 或打开 Ollama 应用）。"
            ) from exc

        chat_payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        generate_payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }

        last_error: Optional[str] = None
        for url, payload, extract in (
            (chat_url, chat_payload, lambda b: (b.get("message") or {}).get("content")),
            (generate_url, generate_payload, lambda b: b.get("response")),
        ):
            try:
                response = await client.post(url, json=payload)
            except httpx.HTTPError as exc:
                last_error = str(exc)
                continue
            if response.status_code == 200:
                content = extract(response.json())
                if content:
                    return content
            if response.status_code in (404, 400):
                raise RuntimeError(_ollama_error_message(response, model, base))
            last_error = _ollama_error_message(response, model, base)

        raise RuntimeError(last_error or f"Ollama 无有效响应（{base}）")


async def _complete_prompt_inner(prompt: str, *, max_tokens: int = 500) -> str:
    refresh_llm_config_from_db()
    provider = LLM_CONFIG["provider"]
    model = LLM_CONFIG["model"]
    api_key = LLM_CONFIG.get("api_key", "")
    endpoint = LLM_CONFIG.get("endpoint", "")

    if provider == "openai":
        return await call_openai_api(prompt, api_key, model, endpoint, max_tokens=max_tokens)
    if provider == "anthropic":
        return await call_anthropic_api(prompt, api_key, model, max_tokens=max_tokens)
    if provider == "gemini":
        return await call_gemini_api(prompt, api_key, model, max_tokens=max_tokens)
    if provider == "ollama":
        return await call_ollama_api(prompt, model, endpoint, max_tokens=max_tokens)
    raise RuntimeError("不支持的LLM提供商")


async def complete_prompt(prompt: str, *, max_tokens: int = 500, timeout: Optional[float] = None) -> str:
    limit = _DEFAULT_LLM_TIMEOUT if timeout is None else timeout
    try:
        return await asyncio.wait_for(_complete_prompt_inner(prompt, max_tokens=max_tokens), timeout=limit)
    except asyncio.TimeoutError as exc:
        raise RuntimeError(f"LLM 请求超时（{int(limit)} 秒），已回退规则引擎") from exc


async def complete_prompt_with_retry(
    prompt: str,
    *,
    max_tokens: int = 500,
    timeout: Optional[float] = None,
    retries: int = 1,
) -> str:
    """Call LLM with one or more retries on transport/timeout failures."""
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            suffix = ""
            if attempt > 0:
                suffix = (
                    "\n\n重要：仅输出一个合法 JSON 对象，不要用 Markdown 代码块，不要附加说明文字。"
                )
            return await complete_prompt(prompt + suffix, max_tokens=max_tokens, timeout=timeout)
        except RuntimeError as exc:
            last_exc = exc
            if attempt >= retries:
                raise
    if last_exc:
        raise last_exc
    raise RuntimeError("LLM 请求失败")


async def llm_is_reachable() -> bool:
    """Quick probe so wizard/report flows skip hung local LLM backends."""
    if not llm_is_configured():
        return False
    refresh_llm_config_from_db()
    provider = LLM_CONFIG.get("provider")
    if provider != "ollama":
        return True
    try:
        import httpx

        base = _ollama_base_url(LLM_CONFIG.get("endpoint") or "")
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{base}/api/tags")
            return response.status_code == 200
    except Exception:
        return False


def llm_is_configured() -> bool:
    if os.getenv("GA_E2E_DISABLE_LLM", "").strip().lower() in ("1", "true", "yes"):
        return False
    refresh_llm_config_from_db()
    return bool(LLM_CONFIG.get("api_key")) or LLM_CONFIG.get("provider") == "ollama"


async def get_local_ollama_models(endpoint: str = None):
    try:
        import httpx

        refresh_llm_config_from_db()
        base = _ollama_base_url(endpoint or LLM_CONFIG.get("endpoint") or "")
        url = f"{base}/api/tags"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
    except Exception as exc:
        print(f"Failed to get Ollama models: {exc}")
    return None


def parse_json_from_llm(text: str) -> Optional[Dict[str, Any]]:
    """Extract a JSON object from LLM output (markdown fences, prose wrappers, etc.)."""
    if not text or not str(text).strip():
        return None

    seen: set[str] = set()
    for chunk in _json_candidate_chunks(str(text)):
        if chunk in seen:
            continue
        seen.add(chunk)
        obj = _loads_json_dict(chunk)
        if obj is not None:
            return obj
    return None


def _json_candidate_chunks(text: str) -> list[str]:
    raw = text.strip()
    chunks: list[str] = []

    for match in re.finditer(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL | re.IGNORECASE):
        block = match.group(1).strip()
        if block:
            chunks.append(block)

    chunks.append(raw)

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        chunks.append(raw[start : end + 1])

    return chunks


def _loads_json_dict(text: str) -> Optional[Dict[str, Any]]:
    variants = [text, re.sub(r",\s*([}\]])", r"\1", text)]
    collapsed = re.sub(r"\s+", " ", text.replace("\r\n", "\n").replace("\n", " "))
    variants.extend([collapsed, re.sub(r",\s*([}\]])", r"\1", collapsed)])

    for candidate in variants:
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def clean_llm_report_text(text: str) -> str:
    """Strip markdown/JSON wrappers so report fields render as plain prose."""
    t = (text or "").strip()
    if not t:
        return ""

    if t.startswith("```") or (t.startswith("{") and "executive_summary" in t):
        parsed = parse_json_from_llm(t)
        if parsed and parsed.get("executive_summary"):
            t = str(parsed["executive_summary"]).strip()

    t = re.sub(r"^```(?:json)?\s*\n?", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\n?```\s*$", "", t)
    return t.strip()
