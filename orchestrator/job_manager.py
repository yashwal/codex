import asyncio
import time
import json
from typing import Dict, List, Optional
from pathlib import Path
import logging
from concurrent.futures import ThreadPoolExecutor

from .models import Job, JobStatus, TaskRequest
from .container_manager import ContainerManager

logger = logging.getLogger(__name__)

class JobManager:
    """
    Manages job lifecycle: scheduling, execution, and result collection
    """
    
    def __init__(self, max_concurrent_jobs: int = 5):
        self.jobs: Dict[str, Job] = {}
        self.container_manager = ContainerManager()
        self.max_concurrent_jobs = max_concurrent_jobs
        self.job_queue: asyncio.Queue = asyncio.Queue()
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_jobs)
        self.running_jobs = set()
        
        # Start background tasks
        asyncio.create_task(self._job_processor())
        asyncio.create_task(self._cleanup_task())
    
    async def create_job(self, task_request: TaskRequest) -> Job:
        """Create a new job and add it to the queue"""
        job = Job.create(task_request)
        self.jobs[job.id] = job
        
        # Add to queue
        await self.job_queue.put(job.id)
        
        logger.info(f"Created job {job.id}: {job.task}")
        return job
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        return self.jobs.get(job_id)
    
    async def get_all_jobs(self) -> List[Job]:
        """Get all jobs"""
        return list(self.jobs.values())
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        if job_id not in self.jobs:
            return False
        
        job = self.jobs[job_id]
        
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return False
        
        job.status = JobStatus.CANCELLED
        job.completed_at = time.time()
        
        # Stop container if running
        if job_id in self.running_jobs:
            await self.container_manager.stop_container(job_id)
            self.running_jobs.discard(job_id)
        
        logger.info(f"Cancelled job {job_id}")
        return True
    
    async def _job_processor(self):
        """Background task to process jobs from the queue"""
        while True:
            try:
                # Wait for job or timeout
                try:
                    job_id = await asyncio.wait_for(self.job_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # Check if we can run more jobs
                if len(self.running_jobs) >= self.max_concurrent_jobs:
                    # Put back in queue and wait
                    await self.job_queue.put(job_id)
                    await asyncio.sleep(5)
                    continue
                
                # Execute job
                asyncio.create_task(self._execute_job(job_id))
                
            except Exception as e:
                logger.error(f"Error in job processor: {e}")
                await asyncio.sleep(1)
    
    async def _execute_job(self, job_id: str):
        """Execute a single job"""
        if job_id not in self.jobs:
            return
        
        job = self.jobs[job_id]
        self.running_jobs.add(job_id)
        
        try:
            # Update job status
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            
            logger.info(f"Starting execution of job {job_id}")
            
            # Start container
            container_result = await self.container_manager.start_container(job)
            
            if not container_result['success']:
                raise Exception(f"Failed to start container: {container_result['error']}")
            
            job.container_id = container_result['container_id']
            
            # Add progress update
            job.progress.append({
                'timestamp': time.time(),
                'message': 'Container started successfully',
                'vnc_url': container_result.get('vnc_url'),
                'jupyter_url': container_result.get('jupyter_url')
            })
            
            # Execute task
            execution_result = await self.container_manager.execute_task_in_container(job)
            
            if execution_result['success']:
                job.result = execution_result['result']
                job.status = JobStatus.COMPLETED
                
                job.progress.append({
                    'timestamp': time.time(),
                    'message': 'Task completed successfully'
                })
                
                logger.info(f"Job {job_id} completed successfully")
            else:
                job.error = execution_result['error']
                job.status = JobStatus.FAILED
                
                job.progress.append({
                    'timestamp': time.time(),
                    'message': f'Task failed: {execution_result["error"]}'
                })
                
                logger.error(f"Job {job_id} failed: {execution_result['error']}")
            
            # Stop container and get output
            stop_result = await self.container_manager.stop_container(job_id)
            if stop_result['success'] and stop_result.get('output_path'):
                job.output_path = stop_result['output_path']
                
                job.progress.append({
                    'timestamp': time.time(),
                    'message': 'Output archive created'
                })
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            
            job.progress.append({
                'timestamp': time.time(),
                'message': f'Job execution failed: {str(e)}'
            })
            
            logger.error(f"Job {job_id} execution failed: {e}")
            
            # Try to stop container
            try:
                await self.container_manager.stop_container(job_id)
            except:
                pass
        
        finally:
            job.completed_at = time.time()
            self.running_jobs.discard(job_id)
    
    async def _cleanup_task(self):
        """Background task for cleanup"""
        while True:
            try:
                # Cleanup old containers
                await self.container_manager.cleanup_old_containers()
                
                # Cleanup old job data (keep for 7 days)
                current_time = time.time()
                old_jobs = []
                
                for job_id, job in self.jobs.items():
                    if job.completed_at and (current_time - job.completed_at) > (7 * 24 * 3600):
                        old_jobs.append(job_id)
                
                for job_id in old_jobs:
                    # Remove output file if exists
                    job = self.jobs[job_id]
                    if job.output_path and Path(job.output_path).exists():
                        Path(job.output_path).unlink()
                    
                    del self.jobs[job_id]
                    logger.info(f"Cleaned up old job {job_id}")
                
                await asyncio.sleep(3600)  # Run every hour
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)
    
    def get_stats(self) -> Dict[str, any]:
        """Get system statistics"""
        total_jobs = len(self.jobs)
        pending_jobs = sum(1 for job in self.jobs.values() if job.status == JobStatus.PENDING)
        running_jobs = len(self.running_jobs)
        completed_jobs = sum(1 for job in self.jobs.values() if job.status == JobStatus.COMPLETED)
        failed_jobs = sum(1 for job in self.jobs.values() if job.status == JobStatus.FAILED)
        
        return {
            'total_jobs': total_jobs,
            'pending_jobs': pending_jobs,
            'running_jobs': running_jobs,
            'completed_jobs': completed_jobs,
            'failed_jobs': failed_jobs,
            'queue_size': self.job_queue.qsize(),
            'max_concurrent_jobs': self.max_concurrent_jobs,
            'running_containers': self.container_manager.get_running_containers()
        }