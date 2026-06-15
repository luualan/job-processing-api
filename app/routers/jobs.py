from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import db, models, schemas, services
from ..queue import queue as job_queue

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/summary", response_model=schemas.JobSummary)
def get_summary(session: Session = Depends(db.get_db)):
    """Get count of jobs by status."""
    summary_dict = services.get_job_summary(session)
    return schemas.JobSummary(
        pending=summary_dict.get("PENDING", 0),
        running=summary_dict.get("RUNNING", 0),
        completed=summary_dict.get("COMPLETED", 0),
        failed=summary_dict.get("FAILED", 0),
    )


@router.get("/queue", response_model=list[schemas.QueueEntry])
def get_queue(session: Session = Depends(db.get_db)):
    """Return the current entries in the in-memory queue for inspection."""
    return job_queue.peek()


@router.post("/claim", response_model=schemas.JobRead)
def claim_next(session: Session = Depends(db.get_db)):
    """Claim the next pending job according to priority/FIFO ordering."""
    job = job_queue.claim_next_job(session)
    if job is None:
        raise HTTPException(status_code=404, detail="No pending jobs")
    return job


@router.post("", response_model=schemas.JobRead, status_code=status.HTTP_201_CREATED)
def create_job(job_in: schemas.JobCreate, session: Session = Depends(db.get_db)):
    """Create a new job with PENDING status."""
    job = services.create_job(session, job_in)
    return job


@router.get("", response_model=list[schemas.JobRead])
def list_jobs(
    status: Optional[models.JobStatus] = None,
    limit: int = 100,
    session: Session = Depends(db.get_db),
):
    """List all jobs, optionally filtered by status."""
    jobs = services.list_jobs(session, status=status, limit=limit)
    return jobs


@router.get("/{job_id}", response_model=schemas.JobRead)
def get_job(job_id: str, session: Session = Depends(db.get_db)):
    """Get a single job by ID."""
    job = services.get_job(session, job_id)
    return job


@router.post("/{job_id}/process", response_model=schemas.JobRead)
def process_job(job_id: str, session: Session = Depends(db.get_db)):
    """Process a job: claim a pending job (PENDING -> RUNNING)."""
    job = services.process_job(session, job_id)
    return job


@router.post("/{job_id}/complete", response_model=schemas.JobRead)
def complete_job(
    job_id: str,
    complete_req: schemas.CompleteJobRequest,
    session: Session = Depends(db.get_db),
):
    """Complete a running job: transitions RUNNING -> COMPLETED with optional result."""
    job = services.complete_job(session, job_id, complete_req)
    return job


@router.post("/{job_id}/fail", response_model=schemas.JobRead)
def fail_job(
    job_id: str,
    reason: Optional[str] = None,
    session: Session = Depends(db.get_db),
):
    """Mark a job as FAILED with an optional reason."""
    job = services.fail_job(session, job_id, reason=reason)
    return job