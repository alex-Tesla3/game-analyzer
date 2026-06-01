"""Static pages and platform sync API routes."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from auth import PLANS
from src.data_catalog import derive_data_catalog, enrich_catalog_from_context
from src.data_resolution import get_user_comments_data, get_user_metrics_data, load_data
from src.services.competitor_workbench import data_provenance_payload
from src.web_constants import (
    AVAILABLE_DATA_SOURCES,
    AVAILABLE_PRODUCTS,
    AVAILABLE_TIME_PERIODS,
    BASE_DIR,
    DATA_DIR,
    HTML_FILE,
)
from src.web_common import get_current_user

router = APIRouter(tags=["pages"])

LANDING_FILE = os.path.join(BASE_DIR, "templates", "landing.html")

_HTML_HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Pragma": "no-cache",
}


def _read_html_page(path: str, label: str) -> HTMLResponse:
    if not os.path.isfile(path):
        raise HTTPException(status_code=500, detail=f"{label} template not found")
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    if not content.strip():
        raise HTTPException(status_code=500, detail=f"{label} template is empty")
    return HTMLResponse(content=content, headers=_HTML_HEADERS)


@router.get("/", response_class=HTMLResponse)
async def home():
    """Product home — default landing."""
    return _read_html_page(LANDING_FILE, "landing")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    return _read_html_page(HTML_FILE, "dashboard")


@router.get("/showcase", response_class=HTMLResponse)
async def showcase_page():
    showcase_file = os.path.join(BASE_DIR, "templates", "showcase.html")
    if not os.path.isfile(showcase_file):
        raise HTTPException(status_code=500, detail="showcase template not found")
    with open(showcase_file, "r", encoding="utf-8") as handle:
        content = handle.read()
    demo_base = os.getenv("PUBLIC_DEMO_BASE_URL", "").strip().rstrip("/")
    content = content.replace("{{PUBLIC_DEMO_BASE_URL}}", demo_base)
    content = content.replace(
        "{{HAS_PUBLIC_DEMO}}",
        "true" if demo_base else "false",
    )
    if not content.strip():
        raise HTTPException(status_code=500, detail="showcase template is empty")
    return HTMLResponse(content=content, headers=_HTML_HEADERS)

@router.get("/comments", response_class=HTMLResponse)
async def comments_page():
    comments_file = os.path.join(BASE_DIR, "templates", "comments.html")
    with open(comments_file, 'r', encoding='utf-8') as f:
        return f.read()

@router.get("/metrics", response_class=HTMLResponse)
async def metrics_page():
    metrics_file = os.path.join(BASE_DIR, "templates", "metrics.html")
    with open(metrics_file, 'r', encoding='utf-8') as f:
        return f.read()

@router.get("/api/options")
async def get_options(token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    current_user = await get_current_user(token)
    comments = get_user_comments_data(current_user.username)
    metrics = get_user_metrics_data(current_user.username)
    catalog = derive_data_catalog(comments or [], metrics or [])
    catalog = enrich_catalog_from_context(catalog, username=current_user.username)
    products = catalog["products"] or AVAILABLE_PRODUCTS
    time_periods = catalog["time_periods"] or AVAILABLE_TIME_PERIODS
    genres = catalog.get("genres") or []
    provenance = data_provenance_payload(current_user.username)
    return {
        "success": True,
        "products": products,
        "genres": genres,
        "time_periods": time_periods,
        "data_sources": AVAILABLE_DATA_SOURCES,
        "data_source": provenance.get("source"),
        "data_trust": provenance.get("trust"),
        "user_plan": PLANS[current_user.plan].model_dump()
        if hasattr(PLANS[current_user.plan], "model_dump")
        else PLANS[current_user.plan].dict(),
    }

class PlatformDataFetcher:
    def __init__(self):
        self.steam_api_key = os.getenv('STEAM_API_KEY', '')
        self.google_credentials = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
        self.appstore_key_id = os.getenv('APPSTORE_KEY_ID', '')
        self.appstore_issuer_id = os.getenv('APPSTORE_ISSUER_ID', '')
        self.appstore_private_key = os.getenv('APPSTORE_PRIVATE_KEY', '')
        self.platform_endpoints = {
            'steam': 'https://store.steampowered.com/api',
            'google_play': 'https://play.googleapis.com/api',
            'app_store': 'https://itunes.apple.com/api'
        }
    
    async def fetch_steam_data(self, app_id: str = None):
        try:
            if self.steam_api_key and app_id:
                url = f'https://api.steampowered.com/ISteamNews/GetNewsForApp/v0002/?appid={app_id}&count=1&format=json&key={self.steam_api_key}'
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, lambda: requests.get(url, timeout=10))
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "data": {
                            "platform": "Steam",
                            "metrics": (
                                data.get('appnews', {}).get('news_items', [{}])[0]
                                if data.get('appnews', {}).get('news_items')
                                else {}
                            ),
                            "source": "steam_api"
                        }
                    }
        except Exception as e:
            print(f"Steam API Error: {e}")
        
        await asyncio.sleep(0.3)
        return {
            "success": True,
            "simulated": True,
            "data_basis": "mock",
            "data": {
                "platform": "Steam",
                "metrics": {
                    "downloads": 125000 + int(abs(hash(str(datetime.now()))) % 10000),
                    "revenue": 450000 + int(abs(hash(str(datetime.now()))) % 50000),
                    "active_users": 8500 + int(abs(hash(str(datetime.now()))) % 1000),
                    "reviews": 3200 + int(abs(hash(str(datetime.now()))) % 500),
                    "rating": round(4.2 + (abs(hash(str(datetime.now()))) % 10) / 10, 1)
                },
                "source": "mock"
            }
        }
    
    async def fetch_google_play_data(self, package_name: str = None):
        try:
            if self.google_credentials and package_name:
                url = f'https://play.googleapis.com/api/developerData?packageName={package_name}'
                headers = {'Authorization': f'Bearer {self.google_credentials}'}
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "data": {
                            "platform": "Google Play",
                            "metrics": data,
                            "source": "google_play_api"
                        }
                    }
        except Exception as e:
            print(f"Google Play API Error: {e}")
        
        await asyncio.sleep(0.3)
        return {
            "success": True,
            "simulated": True,
            "data_basis": "mock",
            "data": {
                "platform": "Google Play",
                "metrics": {
                    "downloads": 89000 + int(abs(hash(str(datetime.now()))) % 8000),
                    "revenue": 180000 + int(abs(hash(str(datetime.now()))) % 30000),
                    "active_users": 6200 + int(abs(hash(str(datetime.now()))) % 800),
                    "reviews": 5800 + int(abs(hash(str(datetime.now()))) % 600),
                    "rating": round(4.0 + (abs(hash(str(datetime.now()))) % 10) / 10, 1)
                },
                "source": "mock"
            }
        }
    
    async def fetch_app_store_data(self, app_id: str = None):
        try:
            if self.appstore_key_id and self.appstore_issuer_id and self.appstore_private_key:
                url = f'https://api.appstoreconnect.apple.com/v1/apps/{app_id}/analytics'
                headers = {
                    'Authorization': f'Bearer {self.appstore_key_id}',
                    'X-Apple-Id-Organization-Id': self.appstore_issuer_id
                }
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "data": {
                            "platform": "App Store",
                            "metrics": data,
                            "source": "app_store_api"
                        }
                    }
        except Exception as e:
            print(f"App Store API Error: {e}")
        
        await asyncio.sleep(0.3)
        return {
            "success": True,
            "simulated": True,
            "data_basis": "mock",
            "data": {
                "platform": "App Store",
                "metrics": {
                    "downloads": 67000 + int(abs(hash(str(datetime.now()))) % 6000),
                    "revenue": 220000 + int(abs(hash(str(datetime.now()))) % 35000),
                    "active_users": 4800 + int(abs(hash(str(datetime.now()))) % 600),
                    "reviews": 4100 + int(abs(hash(str(datetime.now()))) % 400),
                    "rating": round(4.1 + (abs(hash(str(datetime.now()))) % 10) / 10, 1)
                },
                "source": "mock"
            }
        }
    
    async def fetch_all_platforms(self):
        tasks = [
            self.fetch_steam_data(),
            self.fetch_google_play_data(),
            self.fetch_app_store_data()
        ]
        results = await asyncio.gather(*tasks)
        return results
    
    async def discover_new_games(self):
        try:
            url = 'https://api.steampowered.com/ISteamApps/GetAppList/v0002/'
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                apps = data.get('applist', {}).get('apps', [])[:10]
                if apps:
                    return [
                        {
                            "id": str(app['appid']),
                            "name": app['name'],
                            "status": "upcoming",
                            "targetDate": "2026-06-30",
                            "progress": 95,
                            "genre": "RPG",
                            "estimated_revenue": "待评估",
                            "market_potential": "high"
                        }
                        for app in apps if app.get('name')
                    ]
        except Exception as e:
            print(f"Discover games API Error: {e}")
        
        await asyncio.sleep(0.5)
        return [
            {
                "id": "np_auto_001",
                "name": "游戏G - 永恒之塔",
                "status": "upcoming",
                "targetDate": "2026-05-30",
                "progress": 92,
                "genre": "RPG",
                "estimated_revenue": "¥500万+",
                "market_potential": "high"
            },
            {
                "id": "np_auto_002",
                "name": "游戏H - 机甲风暴",
                "status": "testing",
                "targetDate": "2026-06-08",
                "progress": 78,
                "genre": "动作",
                "estimated_revenue": "¥300万+",
                "market_potential": "medium"
            },
            {
                "id": "np_auto_003",
                "name": "游戏I - 失落遗迹",
                "status": "developing",
                "targetDate": "2026-07-15",
                "progress": 45,
                "genre": "冒险",
                "estimated_revenue": "¥200万+",
                "market_potential": "medium"
            },
            {
                "id": "np_auto_004",
                "name": "游戏J - 星际前线",
                "status": "upcoming",
                "targetDate": "2026-05-25",
                "progress": 90,
                "genre": "策略",
                "estimated_revenue": "¥400万+",
                "market_potential": "high"
            },
            {
                "id": "np_auto_005",
                "name": "游戏K - 幻想大陆",
                "status": "testing",
                "targetDate": "2026-06-20",
                "progress": 82,
                "genre": "MMORPG",
                "estimated_revenue": "¥600万+",
                "market_potential": "high"
            }
        ]

fetcher = PlatformDataFetcher()

@router.get("/api/discover_new")
async def discover_new_products(token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    try:
        products = await fetcher.discover_new_games()
        return {
            "success": True,
            "message": "成功从平台发现新品",
            "products": products,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "message": f"发现新品失败: {str(e)}"}

@router.get("/api/fetch_platform_data")
async def fetch_platform_data(
    token: Optional[str] = Query(None),
    platform: Optional[str] = Query(None)
):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    try:
        if platform:
            if platform.lower() == 'steam':
                result = await fetcher.fetch_steam_data()
            elif platform.lower() == 'google_play':
                result = await fetcher.fetch_google_play_data()
            elif platform.lower() == 'app_store':
                result = await fetcher.fetch_app_store_data()
            else:
                return {"success": False, "message": "未知平台"}
            
            if result["success"]:
                return {"success": True, "data": result["data"], "timestamp": datetime.now().isoformat()}
            return result
        else:
            results = await fetcher.fetch_all_platforms()
            combined_data = {
                "total_downloads": sum(r["data"]["metrics"]["downloads"] for r in results if r["success"]),
                "total_revenue": sum(r["data"]["metrics"]["revenue"] for r in results if r["success"]),
                "total_users": sum(r["data"]["metrics"]["active_users"] for r in results if r["success"]),
                "platforms": [r["data"] for r in results if r["success"]]
            }
            return {"success": True, "data": combined_data, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"success": False, "message": f"抓取平台数据失败: {str(e)}"}

@router.post("/api/refresh_data")
async def refresh_data(request: Request, token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    try:
        body = await request.json()
        platforms = body.get("platforms", ["steam", "google_play", "app_store"])
        
        results = []
        for platform in platforms:
            if platform.lower() == 'steam':
                result = await fetcher.fetch_steam_data()
            elif platform.lower() == 'google_play':
                result = await fetcher.fetch_google_play_data()
            elif platform.lower() == 'app_store':
                result = await fetcher.fetch_app_store_data()
            else:
                continue
            results.append(result)
        
        metrics_path = os.path.join(DATA_DIR, "metrics.json")
        current_metrics = load_data(metrics_path) or []
        
        for result in results:
            if result["success"]:
                platform_name = result["data"]["platform"]
                new_metrics = result["data"]["metrics"]
                
                for product in AVAILABLE_PRODUCTS:
                    product_id = product["id"]
                    new_entry = {
                        "product": product_id,
                        "channel": platform_name,
                        "cycle": "Week 22",
                        "metric": "用户总下载量",
                        "值": new_metrics["downloads"],
                        "环比变化": "+5%"
                    }
                    current_metrics.append(new_entry)
        
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(current_metrics, f, ensure_ascii=False, indent=2)
        
        return {
            "success": True,
            "message": "数据刷新完成",
            "updated_platforms": platforms,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "message": f"数据刷新失败: {str(e)}"}

@router.get("/api/sync_status")
async def get_sync_status(token: Optional[str] = Query(None)):
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    await get_current_user(token)
    metrics_path = os.path.join(DATA_DIR, "metrics.json")
    comments_path = os.path.join(DATA_DIR, "comments.json")
    
    return {
        "success": True,
        "last_sync": datetime.now().isoformat(),
        "data_status": {
            "metrics": {
                "exists": os.path.exists(metrics_path),
                "size": os.path.getsize(metrics_path) if os.path.exists(metrics_path) else 0
            },
            "comments": {
                "exists": os.path.exists(comments_path),
                "size": os.path.getsize(comments_path) if os.path.exists(comments_path) else 0
            }
        },
        "available_platforms": ["Steam", "Google Play", "App Store"]
    }

