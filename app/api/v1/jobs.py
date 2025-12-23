"""
Job Management Endpoints

Endpoints for managing background jobs.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.rbac import require_admin
from app.services.job_queue import job_queue, JobStatus
from database import get_db, User

logger = setup_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# Pydantic Models
class JobCreateRequest(BaseModel):
    """Schema for creating a job."""
    job_type: str
    payload: Dict[str, Any]


class JobResponse(BaseModel):
    """Schema for job response."""
    id: str
    job_type: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: float = 0.0
    error: Optional[str] = None


@router.post("", response_model=Dict[str, Any])
async def create_job(
    request: JobCreateRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a new background job.
    
    Requires admin access.
    """
    try:
        job = job_queue.create_job(
            job_type=request.job_type,
            payload=request.payload
        )
        
        return {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "message": "Job created successfully"
        }
    except Exception as e:
        logger.error(f"Error creating job: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create job: {str(e)}"
        )


@router.get("/{job_id}", response_model=Dict[str, Any])
async def get_job(
    job_id: str,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get job status and details.
    
    Requires admin access.
    """
    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status.value,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "progress": job.progress,
        "error": job.error,
        "result": job.result
    }


@router.get("", response_model=Dict[str, Any])
async def list_jobs(
    status: Optional[str] = Query(None, regex="^(pending|running|completed|failed|cancelled)$"),
    job_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List jobs with optional filtering.
    
    Requires admin access.
    """
    try:
        job_status = JobStatus(status) if status else None
        jobs = job_queue.list_jobs(
            status=job_status,
            job_type=job_type,
            limit=limit
        )
        
        jobs_data = [
            {
                "id": job.id,
                "job_type": job.job_type,
                "status": job.status.value,
                "created_at": job.created_at.isoformat(),
                "progress": job.progress
            }
            for job in jobs
        ]
        
        return {
            "jobs": jobs_data,
            "count": len(jobs_data)
        }
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list jobs: {str(e)}"
        )


@router.post("/{job_id}/cancel", response_model=Dict[str, Any])
async def cancel_job(
    job_id: str,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Cancel a job.
    
    Requires admin access.
    """
    success = job_queue.cancel_job(job_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Job cannot be cancelled (not found or already completed/failed)"
        )
    
    return {"message": f"Job {job_id} cancelled successfully"}


@router.get("/stats/queue", response_model=Dict[str, Any])
async def get_queue_stats(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get job queue statistics.
    
    Requires admin access.
    """
    try:
        stats = job_queue.get_queue_stats()
        return {
            "status": "success",
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting queue stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get queue stats: {str(e)}"
        )

