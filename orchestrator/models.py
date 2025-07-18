from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum
import time
import uuid

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskRequest(BaseModel):
    task: str
    priority: int = 1
    timeout: int = 3600  # 1 hour default
    container_config: Optional[Dict[str, Any]] = None

class Job(BaseModel):
    id: str
    task: str
    status: JobStatus
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    priority: int
    timeout: int
    container_id: Optional[str] = None
    vm_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: List[Dict[str, Any]] = []
    output_path: Optional[str] = None
    
    @classmethod
    def create(cls, task_request: TaskRequest) -> "Job":
        return cls(
            id=str(uuid.uuid4()),
            task=task_request.task,
            status=JobStatus.PENDING,
            created_at=time.time(),
            priority=task_request.priority,
            timeout=task_request.timeout
        )

class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str

class StatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    task: str
    created_at: float
    started_at: Optional[float]
    completed_at: Optional[float]
    progress: List[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    download_url: Optional[str] = None
    vnc_url: Optional[str] = None