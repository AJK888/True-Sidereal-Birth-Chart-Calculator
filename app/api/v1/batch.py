"""
Batch processing API endpoints.

Allows users to process multiple chart calculations or readings in batch.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from database import get_db, User
from auth import get_current_user
from app.services.batch_service import (
    create_batch_job, get_batch_job, list_batch_jobs,
    start_batch_job, BatchJobStatus
)

logger = setup_logger(__name__)

router = APIRouter(prefix="/batch", tags=["batch"])


# Pydantic Models
class BatchChartRequest(BaseModel):
    """Schema for batch chart calculation request."""
    items: List[Dict[str, Any]] = Field(..., description="List of chart calculation requests", min_items=1, max_items=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "full_name": "John Doe",
                        "year": 1990,
                        "month": 6,
                        "day": 15,
                        "hour": 14,
                        "minute": 30,
                        "location": "New York, NY, USA"
                    },
                    {
                        "full_name": "Jane Smith",
                        "year": 1985,
                        "month": 3,
                        "day": 20,
                        "hour": 10,
                        "minute": 0,
                        "location": "Los Angeles, CA, USA"
                    }
                ]
            }
        }


class BatchReadingRequest(BaseModel):
    """Schema for batch reading generation request."""
    items: List[Dict[str, Any]] = Field(..., description="List of reading generation requests", min_items=1, max_items=50)
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "chart_hash": "abc123",
                        "chart_name": "John Doe"
                    },
                    {
                        "chart_hash": "def456",
                        "chart_name": "Jane Smith"
                    }
                ]
            }
        }


class BatchJobResponse(BaseModel):
    """Schema for batch job response."""
    id: str
    type: str
    status: str
    total_items: int
    processed_items: int
    successful_items: int
    failed_items: int
    progress_percent: float
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


class BatchJobDetailResponse(BatchJobResponse):
    """Schema for detailed batch job response with results."""
    results: Optional[List[Dict[str, Any]]] = None
    errors: Optional[List[Dict[str, Any]]] = None


@router.post("/charts", response_model=BatchJobResponse)
async def create_batch_charts(
    data: BatchChartRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a batch job for chart calculations.
    
    Processes up to 100 chart calculations in batch. Returns immediately with job ID.
    Use GET /batch/{job_id} to check status and retrieve results.
    """
    if len(data.items) > 100:
        raise HTTPException(
            status_code=400,
            detail="Maximum 100 items allowed per batch"
        )
    
    # Create batch job
    job_id = create_batch_job("charts", data.items, current_user.id)
    
    # Start processing in background
    background_tasks.add_task(start_batch_job, job_id)
    
    job = get_batch_job(job_id)
    
    return BatchJobResponse(
        id=job["id"],
        type=job["type"],
        status=job["status"],
        total_items=job["total_items"],
        processed_items=job["processed_items"],
        successful_items=job["successful_items"],
        failed_items=job["failed_items"],
        progress_percent=job["progress_percent"],
        created_at=job["created_at"].isoformat(),
        started_at=job["started_at"].isoformat() if job["started_at"] else None,
        completed_at=job["completed_at"].isoformat() if job["completed_at"] else None
    )


@router.post("/readings", response_model=BatchJobResponse)
async def create_batch_readings(
    data: BatchReadingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a batch job for reading generation.
    
    Processes up to 50 reading generations in batch. Returns immediately with job ID.
    Use GET /batch/{job_id} to check status and retrieve results.
    """
    if len(data.items) > 50:
        raise HTTPException(
            status_code=400,
            detail="Maximum 50 items allowed per batch"
        )
    
    # Create batch job
    job_id = create_batch_job("readings", data.items, current_user.id)
    
    # Start processing in background
    background_tasks.add_task(start_batch_job, job_id)
    
    job = get_batch_job(job_id)
    
    return BatchJobResponse(
        id=job["id"],
        type=job["type"],
        status=job["status"],
        total_items=job["total_items"],
        processed_items=job["processed_items"],
        successful_items=job["successful_items"],
        failed_items=job["failed_items"],
        progress_percent=job["progress_percent"],
        created_at=job["created_at"].isoformat(),
        started_at=job["started_at"].isoformat() if job["started_at"] else None,
        completed_at=job["completed_at"].isoformat() if job["completed_at"] else None
    )


@router.get("/{job_id}", response_model=BatchJobDetailResponse)
async def get_batch_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get batch job status and results."""
    job = get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    
    # Check authorization
    if job.get("user_id") and job["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return BatchJobDetailResponse(
        id=job["id"],
        type=job["type"],
        status=job["status"],
        total_items=job["total_items"],
        processed_items=job["processed_items"],
        successful_items=job["successful_items"],
        failed_items=job["failed_items"],
        progress_percent=job["progress_percent"],
        created_at=job["created_at"].isoformat(),
        started_at=job["started_at"].isoformat() if job["started_at"] else None,
        completed_at=job["completed_at"].isoformat() if job["completed_at"] else None,
        results=job.get("results") if job["status"] in [BatchJobStatus.COMPLETED, BatchJobStatus.PARTIAL] else None,
        errors=job.get("errors") if job["status"] in [BatchJobStatus.FAILED, BatchJobStatus.PARTIAL] else None
    )


@router.get("", response_model=List[BatchJobResponse])
async def list_user_batch_jobs(
    status: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List batch jobs for the authenticated user."""
    jobs = list_batch_jobs(user_id=current_user.id, status=status, limit=limit)
    
    return [
        BatchJobResponse(
            id=job["id"],
            type=job["type"],
            status=job["status"],
            total_items=job["total_items"],
            processed_items=job["processed_items"],
            successful_items=job["successful_items"],
            failed_items=job["failed_items"],
            progress_percent=job["progress_percent"],
            created_at=job["created_at"].isoformat(),
            started_at=job["started_at"].isoformat() if job["started_at"] else None,
            completed_at=job["completed_at"].isoformat() if job["completed_at"] else None
        )
        for job in jobs
    ]

