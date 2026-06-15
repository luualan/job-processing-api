from fastapi import FastAPI

from . import db, models
from .routers import jobs

# Create database tables at startup
db.Base.metadata.create_all(bind=db.engine)

app = FastAPI(
    title="Job Processing API",
    description="Simple job processing API for interview practice",
    version="1.0.0",
)

# Include routers
app.include_router(jobs.router)
