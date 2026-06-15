import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, Integer, JSON, String

from .db import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=True)
    priority = Column(Integer, nullable=True, default=0)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
