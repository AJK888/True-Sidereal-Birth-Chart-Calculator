"""
Background Job Queue Service

Simple in-memory job queue for background task processing.
For production, consider using Celery, RQ, or similar.
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Job data structure."""
    id: str
    job_type: str
    payload: Dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: float = 0.0


class JobQueue:
    """Simple in-memory job queue."""
    
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._handlers: Dict[str, Callable] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
    
    def register_handler(self, job_type: str, handler: Callable):
        """Register a handler for a job type."""
        self._handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")
    
    def create_job(
        self,
        job_type: str,
        payload: Dict[str, Any]
    ) -> Job:
        """Create a new job."""
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            job_type=job_type,
            payload=payload
        )
        self._jobs[job_id] = job
        
        # Start processing if handler exists
        if job_type in self._handlers:
            self._start_job(job)
        
        logger.info(f"Created job {job_id} of type {job_type}")
        return job
    
    def _start_job(self, job: Job):
        """Start processing a job."""
        if job.status != JobStatus.PENDING:
            return
        
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        
        handler = self._handlers.get(job.job_type)
        if not handler:
            job.status = JobStatus.FAILED
            job.error = f"No handler registered for job type: {job.job_type}"
            return
        
        # Create async task
        task = asyncio.create_task(self._process_job(job, handler))
        self._running_tasks[job.id] = task
    
    async def _process_job(self, job: Job, handler: Callable):
        """Process a job with the given handler."""
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(job.payload)
            else:
                result = handler(job.payload)
            
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result = result
            job.progress = 100.0
            
            logger.info(f"Job {job.id} completed successfully")
        except Exception as e:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error = str(e)
            logger.error(f"Job {job.id} failed: {str(e)}")
        finally:
            if job.id in self._running_tasks:
                del self._running_tasks[job.id]
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self._jobs.get(job_id)
    
    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        job_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Job]:
        """List jobs with optional filtering."""
        jobs = list(self._jobs.values())
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        if job_type:
            jobs = [j for j in jobs if j.job_type == job_type]
        
        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        return jobs[:limit]
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return False
        
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        
        # Cancel running task
        if job_id in self._running_tasks:
            task = self._running_tasks[job_id]
            task.cancel()
            del self._running_tasks[job_id]
        
        logger.info(f"Job {job_id} cancelled")
        return True
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        jobs = list(self._jobs.values())
        
        return {
            "total_jobs": len(jobs),
            "pending": len([j for j in jobs if j.status == JobStatus.PENDING]),
            "running": len([j for j in jobs if j.status == JobStatus.RUNNING]),
            "completed": len([j for j in jobs if j.status == JobStatus.COMPLETED]),
            "failed": len([j for j in jobs if j.status == JobStatus.FAILED]),
            "cancelled": len([j for j in jobs if j.status == JobStatus.CANCELLED]),
            "registered_handlers": list(self._handlers.keys())
        }


# Global job queue instance
job_queue = JobQueue()

