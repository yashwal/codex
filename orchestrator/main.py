import asyncio
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pathlib import Path

from .models import TaskRequest, JobResponse, StatusResponse, JobStatus
from .job_manager import JobManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Coding Agent Orchestrator",
    description="Orchestration layer for sandboxed coding agent system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize job manager
job_manager = JobManager(max_concurrent_jobs=5)

@app.on_event("startup")
async def startup_event():
    logger.info("Coding Agent Orchestrator starting up...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Coding Agent Orchestrator shutting down...")

@app.get("/")
async def root():
    """Health check endpoint"""
    stats = job_manager.get_stats()
    return {
        "message": "Coding Agent Orchestrator is running",
        "version": "1.0.0",
        "stats": stats
    }

@app.post("/schedule", response_model=JobResponse)
async def schedule_task(task_request: TaskRequest):
    """
    Schedule a new coding task
    
    Accepts a plain-text task and returns a job ID.
    Spins up a container in the background to complete the task.
    """
    try:
        # Create and queue the job
        job = await job_manager.create_job(task_request)
        
        logger.info(f"Scheduled new job {job.id}: {task_request.task}")
        
        return JobResponse(
            job_id=job.id,
            status=job.status,
            message=f"Task scheduled successfully. Job ID: {job.id}"
        )
    
    except Exception as e:
        logger.error(f"Failed to schedule task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule task: {str(e)}")

@app.get("/status/{job_id}", response_model=StatusResponse)
async def get_job_status(job_id: str):
    """
    Get the status of a job
    
    Returns the current status and when complete, provides a download link.
    """
    try:
        job = await job_manager.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Build download URL if job is completed and has output
        download_url = None
        if job.status == JobStatus.COMPLETED and job.output_path:
            download_url = f"/download/{job_id}"
        
        # Build VNC URL if container is running
        vnc_url = None
        if job.status == JobStatus.RUNNING and job.container_id:
            container_status = await job_manager.container_manager.get_container_status(job_id)
            if container_status['success']:
                vnc_url = container_status.get('vnc_url')
        
        return StatusResponse(
            job_id=job.id,
            status=job.status,
            task=job.task,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            progress=job.progress,
            result=job.result,
            error=job.error,
            download_url=download_url,
            vnc_url=vnc_url
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")

@app.get("/download/{job_id}")
async def download_job_output(job_id: str):
    """
    Download the output files for a completed job
    """
    try:
        job = await job_manager.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Job not completed")
        
        if not job.output_path or not Path(job.output_path).exists():
            raise HTTPException(status_code=404, detail="Output file not found")
        
        return FileResponse(
            path=job.output_path,
            filename=f"job_{job_id}_output.zip",
            media_type="application/zip"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download output for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download output: {str(e)}")

@app.post("/cancel/{job_id}")
async def cancel_job(job_id: str):
    """
    Cancel a running or pending job
    """
    try:
        success = await job_manager.cancel_job(job_id)
        
        if not success:
            raise HTTPException(status_code=400, detail="Job cannot be cancelled")
        
        return {"message": f"Job {job_id} cancelled successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")

@app.get("/jobs")
async def list_jobs(limit: int = 50, status: str = None):
    """
    List all jobs with optional filtering
    """
    try:
        all_jobs = await job_manager.get_all_jobs()
        
        # Filter by status if provided
        if status:
            all_jobs = [job for job in all_jobs if job.status == status]
        
        # Sort by creation time (newest first)
        all_jobs.sort(key=lambda x: x.created_at, reverse=True)
        
        # Limit results
        jobs = all_jobs[:limit]
        
        return {
            "jobs": [
                {
                    "job_id": job.id,
                    "task": job.task,
                    "status": job.status,
                    "created_at": job.created_at,
                    "started_at": job.started_at,
                    "completed_at": job.completed_at
                }
                for job in jobs
            ],
            "total": len(all_jobs),
            "returned": len(jobs)
        }
    
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")

@app.get("/stats")
async def get_system_stats():
    """
    Get system statistics
    """
    try:
        return job_manager.get_stats()
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.get("/logs/{job_id}")
async def get_job_logs(job_id: str, tail: int = 100):
    """
    Get container logs for a job
    """
    try:
        if job_id not in job_manager.running_jobs:
            raise HTTPException(status_code=404, detail="Job not running or not found")
        
        container_status = await job_manager.container_manager.get_container_status(job_id)
        
        if not container_status['success']:
            raise HTTPException(status_code=500, detail=container_status['error'])
        
        return {
            "job_id": job_id,
            "logs": container_status['logs'],
            "container_status": container_status['status']
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get logs for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")

def main():
    """Main entry point"""
    uvicorn.run(
        "orchestrator.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()