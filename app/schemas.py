from datetime import datetime
from typing import Any, Dict, Optional
from .models import JobStatus
from pydantic import BaseModel, ConfigDict, Field



class JobCreate(BaseModel):
    job_type: str = Field(..., alias="type", min_length=1, max_length=100)
    payload: Optional[Dict[str, Any]] = None
    priority: Optional[int] = Field(default=0, ge=0)

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
    )


class JobRead(BaseModel):
    id: str
    job_type: str = Field(..., alias="type")
    payload: Optional[Dict[str, Any]] = None
    priority: Optional[int] = None
    status: JobStatus
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
    )


class CompleteJobRequest(BaseModel):
    result: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        extra="forbid",
    )


class JobSummary(BaseModel):
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0

    model_config = ConfigDict(
        extra="forbid",
    )


class QueueEntry(BaseModel):
    job_id: str
    priority: int
    created_at: datetime

    model_config = ConfigDict(
        extra="forbid",
    )