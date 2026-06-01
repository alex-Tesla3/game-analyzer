"""CSV/XLS import validation and parsing."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List

import pandas as pd
from fastapi import HTTPException, UploadFile

IMPORT_REQUIRED_FIELDS = {
    "metrics": [
        ("product",),
        ("metric",),
        ("值", "value"),
    ],
    "comments": [
        ("product",),
        ("内容", "content"),
    ],
}

IMPORT_TEMPLATES = {
    "metrics": [
        {
            "product": "game_a",
            "channel": "Steam",
            "cycle": "week_22",
            "metric": "用户总下载量",
            "值": 65000,
            "环比变化": "+8%",
        }
    ],
    "comments": [
        {
            "product": "game_a",
            "platform": "Steam",
            "日期": "2026-05-17",
            "用户角色": "核心用户",
            "情绪": "positive",
            "内容": "战斗系统反馈很爽，但新手引导还可以更清晰。",
        }
    ],
}


def dataframe_to_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    df = df.where(pd.notnull(df), "")
    return df.to_dict(orient="records")


def validate_import_records(dataset_type: str, records: List[Dict[str, Any]]) -> None:
    required_groups = IMPORT_REQUIRED_FIELDS[dataset_type]
    columns = set()
    for record in records:
        columns.update(record.keys())

    missing_columns = [
        " 或 ".join(group)
        for group in required_groups
        if not any(field in columns for field in group)
    ]
    row_errors = []

    for index, record in enumerate(records, start=1):
        for group in required_groups:
            if not any(str(record.get(field, "")).strip() for field in group):
                row_errors.append(
                    {"row": index, "field": " 或 ".join(group), "message": "必填字段为空"}
                )

    if missing_columns or row_errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "导入数据校验失败",
                "dataset_type": dataset_type,
                "missing_columns": missing_columns,
                "row_errors": row_errors[:50],
            },
        )


async def parse_import_file(file: UploadFile) -> List[Dict[str, Any]]:
    filename = (file.filename or "").lower()
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(BytesIO(content))
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(BytesIO(content))
        else:
            raise HTTPException(status_code=400, detail="仅支持 CSV、XLS、XLSX 文件")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {exc}")

    if df.empty:
        raise HTTPException(status_code=400, detail="上传文件没有可导入的数据行")
    return dataframe_to_records(df)
