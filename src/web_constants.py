"""Shared paths and catalog constants for the web application."""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "mock_data")
HTML_FILE = os.path.join(BASE_DIR, "templates", "index.html")
LOGIN_FILE = os.path.join(BASE_DIR, "templates", "login.html")
ADMIN_FILE = os.path.join(BASE_DIR, "templates", "admin.html")

AVAILABLE_PRODUCTS: list = []

AVAILABLE_TIME_PERIODS = [
    {"id": "week_22", "name": "第22周"},
    {"id": "week_21", "name": "第21周"},
    {"id": "week_20", "name": "第20周"},
    {"id": "month_5", "name": "5月份"},
    {"id": "month_4", "name": "4月份"},
    {"id": "quarter_2", "name": "Q2季度"},
]

AVAILABLE_DATA_SOURCES = [
    {"id": "all", "name": "全部来源"},
    {"id": "steam", "name": "Steam"},
    {"id": "taptap", "name": "TapTap"},
    {"id": "google_play", "name": "Google Play"},
    {"id": "app_store", "name": "App Store"},
]

SENSITIVE_CONFIG_FIELDS = {"api_key", "credentials", "private_key"}
