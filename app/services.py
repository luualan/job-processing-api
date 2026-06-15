from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .queue import queue as job_queue


def ensure_job_exists(job: models.Job | None, job_id: str) -> models.Job:
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


def create_job(db: Session, job_in: schemas.JobCreate) -> models.Job:
    job = crud.create_job(db, job_in)
    try:
        job_queue.enqueue(job)
    except Exception:
        # Queue is best-effort in-memory; do not fail job creation on queue issues
        pass
    return job


def list_jobs(db: Session, status: models.JobStatus | None = None, limit: int = 100):
    return crud.list_jobs(db, status=status, limit=limit)


def get_job(db: Session, job_id: str) -> models.Job:
    job = crud.get_job(db, job_id)
    return ensure_job_exists(job, job_id)


def process_job(db: Session, job_id: str) -> models.Job:
    job = crud.get_job(db, job_id)
    job = ensure_job_exists(job, job_id)

    if job.status == models.JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Completed jobs cannot be processed again")
    if job.status == models.JobStatus.FAILED:
        raise HTTPException(status_code=400, detail="Failed jobs cannot be processed again")
    if job.status != models.JobStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending jobs can be processed")

    try:
        # Claim the job and mark it RUNNING atomically.
        job = crud.start_job_if_pending(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    # Return the claimed (RUNNING) job. Completion is handled by `complete_job`.
    return job


def complete_job(db: Session, job_id: str, complete_in: schemas.CompleteJobRequest) -> models.Job:
    job = crud.get_job(db, job_id)
    job = ensure_job_exists(job, job_id)

    if job.status == models.JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job is already completed")
    if job.status == models.JobStatus.FAILED:
        raise HTTPException(status_code=400, detail="Failed jobs cannot be completed")
    if job.status != models.JobStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Only running jobs can be completed")

    return crud.update_job_status(db, job, models.JobStatus.COMPLETED, result=complete_in.result)


def fail_job(db: Session, job_id: str, reason: str | None = None) -> models.Job:
    job = crud.get_job(db, job_id)
    job = ensure_job_exists(job, job_id)

    if job.status == models.JobStatus.COMPLETED: 
        raise HTTPException(status_code=400, detail="Completed jobs cannot be failed")
    if job.status == models.JobStatus.FAILED: 
        raise HTTPException(status_code=400, detail="Job is already failed")

    result = {"reason": reason} if reason else None
    return crud.update_job_status(db, job, models.JobStatus.FAILED, result=result)


def get_job_summary(db: Session) -> dict[str, int]:
    return crud.get_job_summary(db)
