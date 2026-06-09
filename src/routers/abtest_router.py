"""A/B Test router — /api/abtest/* endpoints."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.ab_test_platform import ab_test_platform
from src.web_common import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["abtest"])


@router.get("/api/abtest/experiments")
async def list_ab_experiments(current_user=Depends(get_current_user)):
    experiments = ab_test_platform.list_experiments()
    result = []

    for exp in experiments:
        results = exp.get_results()
        total_users = sum(r["total_users"] for r in results.values())

        result.append({
            "experiment_id": exp.experiment_id,
            "name": exp.name,
            "description": exp.description,
            "status": exp.status,
            "variants": exp.variants,
            "traffic_allocation": exp.traffic_allocation,
            "start_date": exp.start_date,
            "end_date": exp.end_date,
            "total_users": total_users,
            "created_at": exp.created_at,
        })

    return {"success": True, "experiments": result}


@router.get("/api/abtest/experiments/{experiment_id}")
async def get_ab_experiment(experiment_id: str, current_user=Depends(get_current_user)):
    exp = ab_test_platform.get_experiment(experiment_id)
    if not exp:
        return {"success": False, "message": "Experiment not found"}

    results = exp.get_results()
    total_users = sum(r["total_users"] for r in results.values())

    return {
        "success": True,
        "experiment": {
            "experiment_id": exp.experiment_id,
            "name": exp.name,
            "description": exp.description,
            "status": exp.status,
            "variants": exp.variants,
            "traffic_allocation": exp.traffic_allocation,
            "start_date": exp.start_date,
            "end_date": exp.end_date,
            "total_users": total_users,
            "created_at": exp.created_at,
            "results": results,
        },
    }


@router.post("/api/abtest/experiments")
async def create_ab_experiment(
    current_user=Depends(get_current_user),
    name: str = Query(None),
    description: str = Query(""),
    traffic_allocation: float = Query(1.0),
):
    if not name:
        return {"success": False, "message": "Experiment name is required"}

    exp = ab_test_platform.create_experiment(
        name=name,
        description=description,
        traffic_allocation=traffic_allocation,
    )

    return {
        "success": True,
        "experiment_id": exp.experiment_id,
        "message": "Experiment created successfully",
    }


@router.put("/api/abtest/experiments/{experiment_id}")
async def update_ab_experiment(
    experiment_id: str,
    current_user=Depends(get_current_user),
    name: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    traffic_allocation: Optional[float] = Query(None),
    end_date: Optional[str] = Query(None),
):
    try:
        kwargs = {}
        if name:
            kwargs["name"] = name
        if description:
            kwargs["description"] = description
        if traffic_allocation is not None:
            kwargs["traffic_allocation"] = traffic_allocation
        if end_date:
            kwargs["end_date"] = end_date

        exp = ab_test_platform.update_experiment(experiment_id, **kwargs)

        return {
            "success": True,
            "experiment_id": exp.experiment_id,
            "message": "Experiment updated successfully",
        }
    except ValueError as e:
        logger.warning("Update experiment error: %s", e)
        return {"success": False, "message": str(e)}


@router.delete("/api/abtest/experiments/{experiment_id}")
async def delete_ab_experiment(experiment_id: str, current_user=Depends(get_current_user)):
    ab_test_platform.delete_experiment(experiment_id)
    return {"success": True, "message": "Experiment deleted successfully"}


@router.get("/api/abtest/experiments/{experiment_id}/results")
async def get_ab_experiment_results(experiment_id: str, current_user=Depends(get_current_user)):
    results = ab_test_platform.get_experiment_results(experiment_id)

    if "error" in results:
        return {"success": False, "message": results["error"]}

    return {"success": True, "data": results}


@router.post("/api/abtest/track")
async def track_ab_test(
    current_user=Depends(get_current_user),
    experiment_id: str = Query(None),
    user_id: str = Query(None),
):
    if not experiment_id or not user_id:
        return {"success": False, "message": "experiment_id and user_id are required"}

    try:
        variant_id = ab_test_platform.track_user(experiment_id, user_id)
        return {"success": True, "variant_id": variant_id}
    except ValueError as e:
        logger.warning("AB track error: %s", e)
        return {"success": False, "message": str(e)}


@router.post("/api/abtest/convert")
async def track_ab_conversion(
    current_user=Depends(get_current_user),
    experiment_id: str = Query(None),
    user_id: str = Query(None),
    variant_id: str = Query(None),
    conversion_type: str = Query("default"),
):
    if not experiment_id or not user_id or not variant_id:
        return {"success": False, "message": "experiment_id, user_id, and variant_id are required"}

    try:
        ab_test_platform.track_conversion(experiment_id, user_id, variant_id, conversion_type)
        return {"success": True, "message": "Conversion tracked successfully"}
    except ValueError as e:
        logger.warning("AB conversion error: %s", e)
        return {"success": False, "message": str(e)}
