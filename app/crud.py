from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, schemas


def create_job(db: Session, job_in: schemas.JobCreate) -> models.Job:
    job = models.Job(
        job_type=job_in.job_type,
        payload=job_in.payload,
        priority=job_in.priority,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: str) -> Optional[models.Job]:
    return db.query(models.Job).filter(models.Job.id == job_id).first()


def start_job_if_pending(db: Session, job_id: str) -> models.Job:
    """Atomically claim a pending job so only one processor can start it."""
    rows_updated = (
        db.query(models.Job)
        .filter(models.Job.id == job_id, models.Job.status == models.JobStatus.PENDING)
        .update(
            {
                models.Job.status: models.JobStatus.RUNNING,
                models.Job.started_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
    )
    if rows_updated != 1:
        raise ValueError("Job is no longer pending")

    db.commit()
    return get_job(db, job_id)


def list_jobs(
    db: Session,
    status: Optional[models.JobStatus] = None,
    limit: int = 100,
):
    query = db.query(models.Job)
    if status is not None:
        query = query.filter(models.Job.status == status)
    return query.order_by(models.Job.created_at.desc()).limit(limit).all()


def update_job_status(
    db: Session,
    job: models.Job,
    status: models.JobStatus,
    result: Optional[dict] = None,
) -> models.Job:
    job.status = status
    if status == models.JobStatus.RUNNING:
        job.started_at = datetime.now(timezone.utc)
    if status in (models.JobStatus.COMPLETED, models.JobStatus.FAILED):
        job.completed_at = datetime.now(timezone.utc)
    if result is not None:
        job.result = result
    # db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job_summary(db: Session) -> dict[str, int]:
    rows = db.query(models.Job.status, func.count(models.Job.id)).group_by(models.Job.status).all()
    counts = {status.value: count for status, count in rows}
    for status in models.JobStatus:
        counts.setdefault(status.value, 0)
    return counts
