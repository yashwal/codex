import docker
import asyncio
import json
import time
import shutil
import tempfile
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

from .models import Job, JobStatus

logger = logging.getLogger(__name__)

class ContainerManager:
    """
    Manages Docker containers for agent execution.
    In production, this would interface with Firecracker VMs.
    """
    
    def __init__(self, agent_image: str = "coding-agent:latest"):
        self.docker_client = docker.from_env()
        self.agent_image = agent_image
        self.running_containers: Dict[str, dict] = {}
        self.output_dir = Path("/tmp/agent_outputs")
        self.output_dir.mkdir(exist_ok=True)
        
        # Ensure agent image exists
        self._ensure_agent_image()
    
    def _ensure_agent_image(self):
        """Ensure the agent image is available"""
        try:
            self.docker_client.images.get(self.agent_image)
            logger.info(f"Agent image {self.agent_image} found")
        except docker.errors.ImageNotFound:
            logger.warning(f"Agent image {self.agent_image} not found. Building...")
            # In a real implementation, this would pull or build the image
            pass
    
    async def start_container(self, job: Job) -> Dict[str, Any]:
        """Start a container for the job"""
        try:
            # Create job workspace
            job_workspace = self.output_dir / job.id
            job_workspace.mkdir(exist_ok=True)
            
            # Container configuration
            container_config = {
                'image': self.agent_image,
                'name': f"agent-job-{job.id}",
                'detach': True,
                'environment': {
                    'JOB_ID': job.id,
                    'TASK': job.task,
                    'DISPLAY': ':1'
                },
                'volumes': {
                    str(job_workspace): {'bind': '/workspace', 'mode': 'rw'}
                },
                'ports': {
                    '8888/tcp': None,  # Jupyter
                    '6080/tcp': None,  # noVNC
                    '5900/tcp': None   # VNC
                },
                'mem_limit': '2g',
                'cpu_count': 2,
                'security_opt': ['no-new-privileges'],
                'cap_drop': ['ALL'],
                'cap_add': ['DAC_OVERRIDE', 'FOWNER'],
                'read_only': False,
                'tmpfs': {'/tmp': 'size=1g,exec'}
            }
            
            # Start container
            container = self.docker_client.containers.run(**container_config)
            
            # Get port mappings
            container.reload()
            ports = container.attrs['NetworkSettings']['Ports']
            
            # Extract mapped ports
            jupyter_port = None
            vnc_port = None
            novnc_port = None
            
            if '8888/tcp' in ports and ports['8888/tcp']:
                jupyter_port = ports['8888/tcp'][0]['HostPort']
            if '5900/tcp' in ports and ports['5900/tcp']:
                vnc_port = ports['5900/tcp'][0]['HostPort']
            if '6080/tcp' in ports and ports['6080/tcp']:
                novnc_port = ports['6080/tcp'][0]['HostPort']
            
            container_info = {
                'container': container,
                'job_id': job.id,
                'workspace': str(job_workspace),
                'jupyter_port': jupyter_port,
                'vnc_port': vnc_port,
                'novnc_port': novnc_port,
                'started_at': time.time()
            }
            
            self.running_containers[job.id] = container_info
            
            logger.info(f"Started container {container.id} for job {job.id}")
            
            return {
                'success': True,
                'container_id': container.id,
                'jupyter_url': f"http://localhost:{jupyter_port}" if jupyter_port else None,
                'vnc_url': f"http://localhost:{novnc_port}/vnc.html" if novnc_port else None,
                'workspace': str(job_workspace)
            }
            
        except Exception as e:
            logger.error(f"Failed to start container for job {job.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def execute_task_in_container(self, job: Job) -> Dict[str, Any]:
        """Execute the task inside the container"""
        if job.id not in self.running_containers:
            return {'success': False, 'error': 'Container not found'}
        
        container_info = self.running_containers[job.id]
        container = container_info['container']
        
        try:
            # Wait for container to be ready
            await asyncio.sleep(10)
            
            # Execute the task via the agent API
            exec_result = container.exec_run([
                'python3', '-c', f'''
import sys
sys.path.append("/app")
from agent.main import CodingAgent
import json

agent = CodingAgent("/workspace")
result = agent.execute_task("{job.task}")
print(json.dumps(result))
'''
            ], workdir='/workspace')
            
            # Parse result
            if exec_result.exit_code == 0:
                try:
                    result = json.loads(exec_result.output.decode())
                    return {
                        'success': True,
                        'result': result
                    }
                except json.JSONDecodeError:
                    return {
                        'success': False,
                        'error': 'Failed to parse agent output',
                        'raw_output': exec_result.output.decode()
                    }
            else:
                return {
                    'success': False,
                    'error': f'Agent execution failed with exit code {exec_result.exit_code}',
                    'output': exec_result.output.decode()
                }
        
        except Exception as e:
            logger.error(f"Failed to execute task in container {job.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def stop_container(self, job_id: str) -> Dict[str, Any]:
        """Stop and cleanup container"""
        if job_id not in self.running_containers:
            return {'success': False, 'error': 'Container not found'}
        
        container_info = self.running_containers[job_id]
        container = container_info['container']
        
        try:
            # Create output archive
            output_path = await self._create_output_archive(job_id)
            
            # Stop container
            container.stop(timeout=10)
            container.remove()
            
            del self.running_containers[job_id]
            
            logger.info(f"Stopped and removed container for job {job_id}")
            
            return {
                'success': True,
                'output_path': output_path
            }
            
        except Exception as e:
            logger.error(f"Failed to stop container for job {job_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _create_output_archive(self, job_id: str) -> Optional[str]:
        """Create a zip archive of the job output"""
        try:
            container_info = self.running_containers[job_id]
            workspace = Path(container_info['workspace'])
            
            if not workspace.exists():
                return None
            
            # Create archive
            archive_path = self.output_dir / f"job_{job_id}_output.zip"
            shutil.make_archive(str(archive_path.with_suffix('')), 'zip', workspace)
            
            return str(archive_path)
            
        except Exception as e:
            logger.error(f"Failed to create output archive for job {job_id}: {e}")
            return None
    
    async def get_container_status(self, job_id: str) -> Dict[str, Any]:
        """Get container status and logs"""
        if job_id not in self.running_containers:
            return {'success': False, 'error': 'Container not found'}
        
        container_info = self.running_containers[job_id]
        container = container_info['container']
        
        try:
            container.reload()
            status = container.status
            
            # Get recent logs
            logs = container.logs(tail=100).decode('utf-8', errors='ignore')
            
            return {
                'success': True,
                'status': status,
                'logs': logs,
                'jupyter_url': f"http://localhost:{container_info['jupyter_port']}" if container_info['jupyter_port'] else None,
                'vnc_url': f"http://localhost:{container_info['novnc_port']}/vnc.html" if container_info['novnc_port'] else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get container status for job {job_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def cleanup_old_containers(self, max_age_hours: int = 24):
        """Cleanup containers older than max_age_hours"""
        current_time = time.time()
        to_cleanup = []
        
        for job_id, container_info in self.running_containers.items():
            age_hours = (current_time - container_info['started_at']) / 3600
            if age_hours > max_age_hours:
                to_cleanup.append(job_id)
        
        for job_id in to_cleanup:
            await self.stop_container(job_id)
            logger.info(f"Cleaned up old container for job {job_id}")
    
    def get_running_containers(self) -> List[Dict[str, Any]]:
        """Get list of running containers"""
        return [
            {
                'job_id': job_id,
                'started_at': info['started_at'],
                'jupyter_url': f"http://localhost:{info['jupyter_port']}" if info['jupyter_port'] else None,
                'vnc_url': f"http://localhost:{info['novnc_port']}/vnc.html" if info['novnc_port'] else None
            }
            for job_id, info in self.running_containers.items()
        ]