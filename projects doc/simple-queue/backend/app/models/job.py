import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, Float
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    job_type = Column(String(100), nullable=False)   # e.g. "report", "email", "export"
    status = Column(String(50), default="pending")   # pending | running | success | failed
    result = Column(Text, nullable=True)             # JSON string of the result
    error = Column(Text, nullable=True)
    progress = Column(Float, default=0.0)            # 0–100
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    celery_task_id = Column(String(255), nullable=True)  # links row ↔ Celery task
