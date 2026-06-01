"""AI analysis, simulated advanced analytics, and realtime WebSocket."""

from __future__ import annotations

import asyncio
import json
import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from advanced_analytics import get_advanced_analytics
from auth import LLM_CONFIG, LLM_PROVIDERS
from src.api_meta import with_simulated
from src.data_resolution import get_metrics_data, get_user_metrics_data, resolve_user_data_source
from src.mvp_data import get_mvp_analysis, mvp_validation_passed, product_matches
from src.services.legacy_ai_report import (
    MOCK_PRODUCT_NAMES,
    generate_action_plan,
    generate_issues_diagnosis,
    generate_new_product_trends,
    generate_optimization_suggestions,
    generate_product_trends,
)
from src.services.llm_client import llm_is_configured, parse_json_from_llm, complete_prompt
from src.services.llm_mvp_summary import summarize_mvp_with_llm
from src.web_common import get_current_user

router = APIRouter(tags=["analytics"])

analytics = get_advanced_analytics()
active_connections: list = []


def _parse_product_ids(product_ids: Optional[str]) -> List[str]:
    if not product_ids or not str(product_ids).strip():
        return ["all"]
    parts = [p.strip() for p in str(product_ids).split(",") if p.strip()]
    return parts or ["all"]


def _filter_metrics_by_products(metrics_data: list, products: List[str]) -> list:
    if not products or products == ["all"]:
        return metrics_data
    return [
        row
        for row in metrics_data
        if any(product_matches(row, product) for product in products)
    ]


def _advanced_data_basis(username: str) -> str:
    source = resolve_user_data_source(username) or "mock"
    if source == "mvp_steam":
        return "mvp_steam"
    if source == "imported":
        return "imported"
    return "mock_data"


async def generate_ai_report_with_llm(products: List[str], product_names: dict, time_label: str):
    selected = [product_names[p] for p in products if p in product_names]
    product_label = ", ".join(selected) if selected else "全部产品"
    prompt = f"""你是一位专业的游戏数据分析顾问。请基于以下信息生成一份游戏数据分析报告：

产品：{product_label}
时间周期：{time_label}

请生成以下内容的JSON格式报告（只需要JSON，不要其他内容）：
{{
    "summary": "总体分析摘要，100字左右",
    "product_trends": [
        {{"product": "产品名", "rating": "良好/中等/较差", "trend": "趋势描述", "change": "+5%"}}
    ],
    "action_plan": {{
        "short_term": ["行动项1", "行动项2", "行动项3"],
        "medium_term": ["行动项1", "行动项2", "行动项3"],
        "long_term": ["行动项1", "行动项2", "行动项3"]
    }}
}}"""
    try:
        response_text = await complete_prompt(prompt)
        report_data = parse_json_from_llm(response_text)
        if not report_data:
            return None
        provider = LLM_CONFIG["provider"]
        report_data["using_llm"] = True
        report_data["llm_provider"] = LLM_PROVIDERS.get(provider, {}).get("name", provider)
        report_data["llm_model"] = LLM_CONFIG.get("model")
        report_data["llm_configured"] = True
        return report_data
    except Exception as exc:
        print(f"LLM调用失败: {exc}")
        return None


@router.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None, product_ids: Optional[str] = None):
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    try:
        current_user = await get_current_user(token)
    except Exception:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        from src.data_resolution import get_user_metrics_data
        from src.api_meta import with_simulated

        products = _parse_product_ids(product_ids)
        metrics_data = get_user_metrics_data(current_user.username)
        
        if products != ['all']:
            filtered_metrics = [m for m in metrics_data if m.get('product') in products]
        else:
            filtered_metrics = metrics_data
        
        initial_data = with_simulated(
            analytics['realtime'].calculate_real_time_metrics(filtered_metrics),
            basis="user_data",
        )
        await websocket.send_json(initial_data)
        
        while True:
            await asyncio.sleep(5)
            new_data = with_simulated(
                analytics['realtime'].calculate_real_time_metrics(filtered_metrics),
                basis="user_data",
            )
            await websocket.send_json(new_data)
    
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        if websocket in active_connections:
            active_connections.remove(websocket)


# --- AI analysis ---

@router.get("/api/ai_analysis")
async def get_ai_analysis(
    token: Optional[str] = Query(None),
    product_ids: Optional[str] = Query(None), 
    time_period: Optional[str] = Query(None), 
    data_source: Optional[str] = Query(None)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    current_user = await get_current_user(token)
    source = resolve_user_data_source(current_user.username)

    if source == "mvp_steam" and mvp_validation_passed():
        analysis = get_mvp_analysis() or {}
        strategy = analysis.get("ai_strategy") or {}
        rule_summary = strategy.get("opportunity_summary") or analysis.get("summary") or ""
        data = {
            "format": "mvp_steam",
            "summary": rule_summary,
            "rule_based_summary": rule_summary,
            "product_reports": analysis.get("product_reports", []),
            "ai_strategy": strategy,
            "peer_comparison": strategy.get("peer_comparison", []),
            "user_needs": strategy.get("user_needs", []),
            "prioritized_actions": strategy.get("prioritized_actions", []),
            "using_llm": False,
            "llm_configured": llm_is_configured(),
        }
        llm_layer = await summarize_mvp_with_llm(analysis)
        analysis_mode = "mvp_steam_verified"
        llm_error = None
        if llm_layer:
            data["summary"] = llm_layer["executive_summary"]
            data["using_llm"] = True
            data["llm_provider"] = llm_layer.get("llm_provider")
            data["llm_model"] = llm_layer.get("llm_model")
            data["grounded_in"] = llm_layer.get("grounded_in")
            analysis_mode = "mvp_steam_verified_llm_summary"
        elif llm_is_configured():
            llm_error = (
                "已配置本地/云端 LLM，但生成摘要失败。请确认 Ollama 已启动、模型名称与设置一致，"
                "且 endpoint 为 http://localhost:11434（不要填 /api/generate 路径）。"
            )
        return {
            "success": True,
            "source": source,
            "analysis_mode": analysis_mode,
            "validation_passed": True,
            "llm_error": llm_error,
            "data": data,
        }

    products = _parse_product_ids(product_ids)
    
    product_names = MOCK_PRODUCT_NAMES
    
    time_label = {
        'week_20': '第20周',
        'week_21': '第21周', 
        'week_22': '第22周',
        'quarter_2': 'Q2季度'
    }.get(time_period, time_period or '全时段')
    
    selected_product_names = [product_names[p] for p in products if p in product_names]
    product_label = ', '.join(selected_product_names) if selected_product_names else '全部产品'
    
    if LLM_CONFIG.get("api_key") or LLM_CONFIG.get("provider") == "ollama":
        llm_report = await generate_ai_report_with_llm(products, product_names, time_label)
        if llm_report:
            return {
                "success": True,
                "source": source,
                "analysis_mode": "llm",
                "data": llm_report,
            }
    
    ai_report = {
        "summary": f"⚠️ 【默认报告】本次分析覆盖 {product_label}，时间周期为 {time_label}。核心结论：用户对产品核心玩法认可度较高，但付费设计和新手引导需要优化。建议关注付费转化率和用户留存问题，适时推出限时活动提升活跃度。\n\n💡 提示：如需获得AI深度分析，请在配置面板中设置LLM提供商（如OpenAI、Claude、Gemini或Ollama本地模型），或运行 Steam MVP 抓取真实评论。",
        "product_trends": generate_product_trends(products, product_names),
        "new_product_analysis": generate_new_product_trends(),
        "issues_diagnosis": generate_issues_diagnosis(products, product_names),
        "optimization_suggestions": generate_optimization_suggestions(products, product_names),
        "action_plan": generate_action_plan(),
        "using_llm": False,
        "llm_provider": None,
        "llm_model": None,
        "llm_configured": False
    }
    
    return {
        "success": True,
        "source": source,
        "analysis_mode": "legacy_template",
        "simulated": source == "mock",
        "data": ai_report,
    }

@router.get("/api/advanced/journey")
async def get_user_journey(
    token: Optional[str] = Query(None),
    time_range: str = Query("all"),
    product_ids: Optional[str] = Query(None),
    compare_mode: bool = Query(False)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    
    products = _parse_product_ids(product_ids)
    
    if compare_mode and products != ['all']:
        # 对比模式：按产品分别获取数据
        journey_by_product = {}
        path_dist_by_product = {}
        
        for product in products:
            journey_by_product[product] = analytics['journey'].analyze_user_journey(time_range, [product])
            path_dist_data = analytics['journey'].get_path_distribution([product])
            path_dist_by_product[product] = path_dist_data.get(product, [])
        
        return with_simulated({
            "success": True,
            "selected_products": products,
            "compare_mode": True,
            "journey_by_product": journey_by_product,
            "path_dist_by_product": path_dist_by_product
        })
    else:
        journey_data = analytics['journey'].analyze_user_journey(time_range, products)
        path_distribution_data = analytics['journey'].get_path_distribution(products)
        
        first_product = products[0] if products else 'all'
        path_distribution = path_distribution_data.get(first_product, path_distribution_data.get('all', [])) if isinstance(path_distribution_data, dict) else path_distribution_data
        
        return with_simulated({
            "success": True,
            "selected_products": products,
            "compare_mode": False,
            "journey": journey_data,
            "path_distribution": path_distribution
        })

@router.get("/api/advanced/funnel")
async def get_funnel_analysis(
    token: Optional[str] = Query(None),
    time_range: str = Query("all"),
    product_ids: Optional[str] = Query(None),
    compare_mode: bool = Query(False)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    
    products = _parse_product_ids(product_ids)
    
    if compare_mode and products != ['all']:
        funnel_by_product = {}
        for product in products:
            funnel_by_product[product] = analytics['funnel'].create_funnel(time_range=time_range, products=[product])
        
        return with_simulated({
            "success": True,
            "selected_products": products,
            "compare_mode": True,
            "funnel_by_product": funnel_by_product
        })
    else:
        funnel_data = analytics['funnel'].create_funnel(time_range=time_range, products=products)
        
        return with_simulated({
            "success": True,
            "selected_products": products,
            "compare_mode": False,
            "funnel": funnel_data
        })

@router.get("/api/advanced/funnel/compare")
async def compare_funnels(
    token: Optional[str] = Query(None),
    time_range_a: str = Query(""),
    time_range_b: str = Query("")
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    
    comparison_data = analytics['funnel'].compare_funnels(time_range_a, time_range_b)
    
    return with_simulated({
        "success": True,
        "comparison": comparison_data
    })

@router.get("/api/advanced/cohort")
async def get_cohort_analysis(
    token: Optional[str] = Query(None),
    cohort_type: str = Query("weekly"),
    date_range: str = Query(None),
    product_ids: Optional[str] = Query(None),
    compare_mode: bool = Query(False)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    
    products = _parse_product_ids(product_ids)
    
    if compare_mode and products != ['all']:
        cohort_by_product = {}
        for product in products:
            cohort_by_product[product] = analytics['cohort'].create_cohort(cohort_type, date_range, [product])
        
        return with_simulated({
            "success": True,
            "selected_products": products,
            "compare_mode": True,
            "cohort_by_product": cohort_by_product
        })
    else:
        cohort_data = analytics['cohort'].create_cohort(cohort_type, date_range, products)
        
        return with_simulated({
            "success": True,
            "selected_products": products,
            "compare_mode": False,
            "cohort": cohort_data
        })

@router.get("/api/advanced/cohort/{cohort_id}")
async def get_cohort_detail(
    cohort_id: str,
    token: Optional[str] = Query(None)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    
    detail_data = analytics['cohort'].analyze_retention_by_cohort(cohort_id)
    
    return with_simulated({
        "success": True,
        "detail": detail_data
    })

@router.get("/api/advanced/anomaly")
async def get_anomaly_detection(
    token: Optional[str] = Query(None),
    metric_name: str = Query(None),
    current_value: float = Query(None),
    product_ids: Optional[str] = Query(None),
    compare_mode: bool = Query(False)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    
    products = _parse_product_ids(product_ids)
    
    if compare_mode and products != ['all']:
        alerts_by_product = {}
        for product in products:
            alerts_by_product[product] = analytics['anomaly'].get_active_alerts([product])
        
        result = {
            "success": True,
            "selected_products": products,
            "compare_mode": True,
            "alerts_by_product": alerts_by_product
        }
        
        if metric_name and current_value is not None:
            anomaly_result = analytics['anomaly'].detect_anomaly(metric_name, current_value)
            result["anomaly_result"] = anomaly_result
        
        return result
    else:
        active_alerts = analytics['anomaly'].get_active_alerts(products)
        
        if metric_name and current_value is not None:
            anomaly_result = analytics['anomaly'].detect_anomaly(metric_name, current_value)
            return with_simulated({
                "success": True,
                "selected_products": products,
                "compare_mode": False,
                "anomaly_result": anomaly_result,
                "active_alerts": active_alerts
            })
        
        return with_simulated({
            "success": True,
            "selected_products": products,
            "compare_mode": False,
            "active_alerts": active_alerts
        })

@router.post("/api/advanced/anomaly/test")
async def test_anomaly_detection(
    request: Request,
    token: Optional[str] = Query(None)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    
    body = await request.json()
    metric_name = body.get('metric_name', 'revenue')
    current_value = body.get('current_value', 1000)
    
    # 初始化基线（如果还没有）
    analytics['anomaly'].initialize_baseline(metric_name)
    
    anomaly_result = analytics['anomaly'].detect_anomaly(metric_name, current_value)
    notification = analytics['anomaly'].generate_alert_notification(anomaly_result)
    
    return with_simulated({
        "success": True,
        "anomaly_result": anomaly_result,
        "notification": notification
    })

@router.get("/api/advanced/dashboard")
async def get_advanced_dashboard(
    token: Optional[str] = Query(None),
    product_ids: Optional[str] = Query(None),
    compare_mode: bool = Query(False)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    current_user = await get_current_user(token)
    
    products = _parse_product_ids(product_ids)
    basis = _advanced_data_basis(current_user.username)
    
    # 优先使用缓存数据，然后使用用户导入的数据，最后使用mock数据
    metrics_data = get_user_metrics_data(current_user.username)
    
    if compare_mode and products != ['all']:
        realtime_by_product = {}
        for product in products:
            product_metrics = _filter_metrics_by_products(metrics_data, [product])
            realtime_by_product[product] = analytics['realtime'].calculate_real_time_metrics(product_metrics)
        
        return with_simulated({
            "success": True,
            "compare_mode": True,
            "realtime_by_product": realtime_by_product,
            "selected_products": products
        }, basis=basis)
    else:
        filtered_metrics = _filter_metrics_by_products(metrics_data, products)
        
        journey = analytics['journey'].analyze_user_journey(products=products)
        funnel = analytics['funnel'].create_funnel(products=products)
        cohort = analytics['cohort'].create_cohort(products=products)
        alerts = analytics['anomaly'].get_active_alerts(products)
        realtime = analytics['realtime'].calculate_real_time_metrics(filtered_metrics)
        
        return with_simulated({
            "success": True,
            "compare_mode": False,
            "realtime": realtime,
            "journey": journey,
            "funnel": funnel,
            "cohort": cohort,
            "alerts": alerts,
            "selected_products": products
        }, basis=basis)

# =========================================
# Phase 2: 预测分析 API
# =========================================

@router.get("/api/predictive/ltv")
async def predict_ltv(
    token: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    prediction_days: int = Query(30)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    
    ltv_prediction = analytics['predictive'].predict_ltv(user_id, prediction_days)
    
    return with_simulated({
        "success": True,
        "ltv_prediction": ltv_prediction
    })

@router.get("/api/predictive/churn")
async def predict_churn(
    token: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    
    churn_prediction = analytics['predictive'].predict_churn_probability(user_id)
    
    return with_simulated({
        "success": True,
        "churn_prediction": churn_prediction
    })

@router.get("/api/predictive/high-value-users")
async def get_high_value_users(
    token: Optional[str] = Query(None),
    time_range: str = Query("30d"),
    top_percent: int = Query(10)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    
    high_value_users = analytics['predictive'].identify_high_value_users(time_range, top_percent)
    
    return with_simulated({
        "success": True,
        "high_value_users": high_value_users
    })

@router.get("/api/predictive/revenue-forecast")
async def get_revenue_forecast(
    token: Optional[str] = Query(None),
    days: int = Query(30)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    
    revenue_forecast = analytics['predictive'].predict_revenue_forecast(days)
    
    return with_simulated({
        "success": True,
        "revenue_forecast": revenue_forecast
    })

@router.get("/api/predictive/dashboard")
async def get_predictive_dashboard(
    token: Optional[str] = Query(None),
    product_ids: Optional[str] = Query(None),
    compare_mode: bool = Query(False)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    
    products = _parse_product_ids(product_ids)
    
    if compare_mode and products != ['all']:
        predictions_by_product = {}
        for product in products:
            predictions_by_product[product] = {
                "ltv": analytics['predictive'].predict_ltv(),
                "churn": analytics['predictive'].predict_churn_probability(),
                "high_value_users": analytics['predictive'].identify_high_value_users(),
                "revenue_forecast": analytics['predictive'].predict_revenue_forecast(30)
            }
        
        return with_simulated({
            "success": True,
            "selected_products": products,
            "compare_mode": True,
            "predictions_by_product": predictions_by_product
        })
    else:
        # 获取所有预测数据
        ltv = analytics['predictive'].predict_ltv()
        churn = analytics['predictive'].predict_churn_probability()
        high_value = analytics['predictive'].identify_high_value_users()
        forecast = analytics['predictive'].predict_revenue_forecast(30)
        
        return with_simulated({
            "success": True,
            "selected_products": products,
            "compare_mode": False,
            "ltv": ltv,
            "churn": churn,
            "high_value_users": high_value,
            "revenue_forecast": forecast
        })

