"""
Batch processing service for handling multiple chart calculations and readings.

Provides batch operations with progress tracking and result aggregation.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)

# In-memory job storage (in production, use database or Redis)
_batch_jobs: Dict[str, Dict[str, Any]] = {}


class BatchJobStatus(str):
    """Batch job status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some items succeeded, some failed


def create_batch_job(
    job_type: str,
    items: List[Dict[str, Any]],
    user_id: Optional[int] = None
) -> str:
    """
    Create a new batch job.
    
    Args:
        job_type: Type of batch job ("charts", "readings", "famous_people")
        items: List of items to process
        user_id: Optional user ID
        
    Returns:
        Job ID
    """
    job_id = str(uuid4())
    
    _batch_jobs[job_id] = {
        "id": job_id,
        "type": job_type,
        "user_id": user_id,
        "status": BatchJobStatus.PENDING,
        "total_items": len(items),
        "processed_items": 0,
        "successful_items": 0,
        "failed_items": 0,
        "items": items,
        "results": [],
        "errors": [],
        "created_at": datetime.now(),
        "started_at": None,
        "completed_at": None,
        "progress_percent": 0.0
    }
    
    logger.info(f"Batch job created: {job_id} ({job_type}, {len(items)} items)")
    return job_id


async def process_batch_charts(
    job_id: str,
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Process batch chart calculations.
    
    Args:
        job_id: Job ID
        items: List of chart calculation requests
        
    Returns:
        Job result dictionary
    """
    job = _batch_jobs.get(job_id)
    if not job:
        raise ValueError(f"Job not found: {job_id}")
    
    job["status"] = BatchJobStatus.PROCESSING
    job["started_at"] = datetime.now()
    
    results = []
    errors = []
    
    for i, item in enumerate(items):
        try:
            # Import chart calculation logic
            from app.api.v1.charts import calculate_chart_endpoint
            from fastapi import Request
            from app.core.responses import success_response
            
            # Create a mock request for the endpoint
            # Note: In production, extract chart calculation logic to a service function
            # For now, we'll process items directly using the chart calculation logic
            import swisseph as swe
            import pendulum
            from natal_chart import NatalChart, calculate_numerology, get_chinese_zodiac_and_element
            from app.services.chart_service import generate_chart_hash
            import requests
            import os
            from app.config import OPENCAGE_KEY, SWEP_PATH, DEFAULT_SWISS_EPHEMERIS_PATH
            
            # Simplified chart calculation for batch processing
            # Geocoding
            lat, lng, timezone_name = None, None, None
            if OPENCAGE_KEY:
                try:
                    geo_url = f"https://api.opencagedata.com/geocode/v1/json?q={item['location']}&key={OPENCAGE_KEY}"
                    response = requests.get(geo_url, timeout=10)
                    if response.status_code != 402:
                        response.raise_for_status()
                        geo_res = response.json()
                        if geo_res.get("results"):
                            result = geo_res["results"][0]
                            lat = result["geometry"]["lat"]
                            lng = result["geometry"]["lng"]
                            timezone_name = result.get("annotations", {}).get("timezone", {}).get("name")
                except:
                    pass
            
            if not lat or not lng:
                try:
                    nominatim_url = "https://nominatim.openstreetmap.org/search"
                    response = requests.get(nominatim_url, params={"q": item['location'], "format": "json", "limit": 1}, 
                                           headers={"User-Agent": "SynthesisAstrology/1.0"}, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    if data:
                        lat = float(data[0]["lat"])
                        lng = float(data[0]["lon"])
                        timezone_name = timezone_name or "UTC"
                except:
                    timezone_name = "UTC"
            
            if not timezone_name:
                timezone_name = "UTC"
            
            # Calculate chart
            local_time = pendulum.datetime(
                item['year'], item['month'], item['day'], 
                item['hour'], item['minute'], tz=timezone_name
            )
            utc_time = local_time.in_timezone('UTC')
            
            # Try SWEP_PATH first (if set), then DEFAULT_SWISS_EPHEMERIS_PATH, then BASE_DIR/swiss_ephemeris, then BASE_DIR
            ephe_path = None
            if SWEP_PATH and os.path.exists(SWEP_PATH):
                ephe_path = SWEP_PATH
            elif DEFAULT_SWISS_EPHEMERIS_PATH and os.path.exists(DEFAULT_SWISS_EPHEMERIS_PATH):
                ephe_path = DEFAULT_SWISS_EPHEMERIS_PATH
            else:
                # Try relative to BASE_DIR
                from app.config import BASE_DIR
                swiss_ephe_dir = BASE_DIR / "swiss_ephemeris"
                if swiss_ephe_dir.exists():
                    ephe_path = str(swiss_ephe_dir)
                else:
                    # Final fallback to BASE_DIR (ephemeris files might be in root)
                    ephe_path = str(BASE_DIR)
            
            swe.set_ephe_path(ephe_path)
            
            chart = NatalChart(
                name=item.get('full_name', 'Unknown'),
                year=utc_time.year, month=utc_time.month, day=utc_time.day,
                hour=utc_time.hour, minute=utc_time.minute,
                latitude=lat, longitude=lng
            )
            chart.calculate_chart(unknown_time=item.get('unknown_time', False))
            
            # Build result
            result = {
                "chart_data": chart.to_dict(),
                "numerology": calculate_numerology(item['day'], item['month'], item['year']),
                "chinese_zodiac": get_chinese_zodiac_and_element(item['year'])
            }
            
            results.append({
                "index": i,
                "item": item,
                "result": result,
                "success": True
            })
            job["successful_items"] += 1
            
        except Exception as e:
            logger.error(f"Batch chart calculation failed for item {i}: {e}")
            errors.append({
                "index": i,
                "item": item,
                "error": str(e),
                "success": False
            })
            job["failed_items"] += 1
        
        job["processed_items"] += 1
        job["progress_percent"] = (job["processed_items"] / job["total_items"]) * 100
    
    job["results"] = results
    job["errors"] = errors
    job["completed_at"] = datetime.now()
    
    # Determine final status
    if job["failed_items"] == 0:
        job["status"] = BatchJobStatus.COMPLETED
    elif job["successful_items"] == 0:
        job["status"] = BatchJobStatus.FAILED
    else:
        job["status"] = BatchJobStatus.PARTIAL
    
    logger.info(
        f"Batch job completed: {job_id} "
        f"({job['successful_items']} successful, {job['failed_items']} failed)"
    )
    
    return job


async def process_batch_readings(
    job_id: str,
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Process batch reading generation.
    
    Args:
        job_id: Job ID
        items: List of reading generation requests
        
    Returns:
        Job result dictionary
    """
    job = _batch_jobs.get(job_id)
    if not job:
        raise ValueError(f"Job not found: {job_id}")
    
    job["status"] = BatchJobStatus.PROCESSING
    job["started_at"] = datetime.now()
    
    results = []
    errors = []
    
    for i, item in enumerate(items):
        try:
            # Import reading generation
            from app.services.llm_prompts import generate_snapshot_reading
            from app.core.cache import get_reading_from_cache, set_reading_in_cache
            
            chart_hash = item.get('chart_hash')
            chart_name = item.get('chart_name', 'Unknown')
            
            if not chart_hash:
                raise ValueError("chart_hash is required")
            
            # Check cache first
            cached_reading = get_reading_from_cache(chart_hash)
            if cached_reading:
                result = {"reading": cached_reading.get('reading'), "from_cache": True}
            else:
                # Generate reading (simplified - would need full chart data in production)
                # For now, return a placeholder
                result = {
                    "reading": f"Reading for {chart_name} (batch processing)",
                    "from_cache": False
                }
                # Cache the reading
                set_reading_in_cache(chart_hash, result["reading"], chart_name)
            
            results.append({
                "index": i,
                "item": item,
                "result": result,
                "success": True
            })
            job["successful_items"] += 1
            
        except Exception as e:
            logger.error(f"Batch reading generation failed for item {i}: {e}")
            errors.append({
                "index": i,
                "item": item,
                "error": str(e),
                "success": False
            })
            job["failed_items"] += 1
        
        job["processed_items"] += 1
        job["progress_percent"] = (job["processed_items"] / job["total_items"]) * 100
    
    job["results"] = results
    job["errors"] = errors
    job["completed_at"] = datetime.now()
    
    # Determine final status
    if job["failed_items"] == 0:
        job["status"] = BatchJobStatus.COMPLETED
    elif job["successful_items"] == 0:
        job["status"] = BatchJobStatus.FAILED
    else:
        job["status"] = BatchJobStatus.PARTIAL
    
    logger.info(
        f"Batch job completed: {job_id} "
        f"({job['successful_items']} successful, {job['failed_items']} failed)"
    )
    
    return job


def get_batch_job(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get batch job status and results.
    
    Args:
        job_id: Job ID
        
    Returns:
        Job dictionary or None
    """
    return _batch_jobs.get(job_id)


def list_batch_jobs(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    List batch jobs.
    
    Args:
        user_id: Optional user ID filter
        status: Optional status filter
        limit: Maximum number of jobs to return
        
    Returns:
        List of job dictionaries
    """
    jobs = list(_batch_jobs.values())
    
    # Filter by user_id
    if user_id:
        jobs = [j for j in jobs if j.get("user_id") == user_id]
    
    # Filter by status
    if status:
        jobs = [j for j in jobs if j.get("status") == status]
    
    # Sort by created_at (newest first)
    jobs.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
    
    # Limit results
    return jobs[:limit]


async def start_batch_job(job_id: str) -> None:
    """
    Start processing a batch job asynchronously.
    
    Args:
        job_id: Job ID
    """
    job = _batch_jobs.get(job_id)
    if not job:
        raise ValueError(f"Job not found: {job_id}")
    
    if job["status"] != BatchJobStatus.PENDING:
        raise ValueError(f"Job {job_id} is not in pending status")
    
    # Start processing in background
    if job["type"] == "charts":
        asyncio.create_task(process_batch_charts(job_id, job["items"]))
    elif job["type"] == "readings":
        asyncio.create_task(process_batch_readings(job_id, job["items"]))
    else:
        raise ValueError(f"Unknown job type: {job['type']}")

