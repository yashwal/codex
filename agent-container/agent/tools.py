import subprocess
import os
import tempfile
import json
import shutil
from typing import Dict, Any, List, Optional
from pathlib import Path
import time
import signal
from contextlib import contextmanager

class SecurityError(Exception):
    """Raised when a security violation is detected"""
    pass

class ToolExecutor:
    """Base class for tool execution with security controls"""
    
    def __init__(self, workspace_dir: str = "/workspace"):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(exist_ok=True)
        
        # Security: Define allowed paths and commands
        self.allowed_paths = {
            self.workspace_dir,
            Path("/tmp"),
            Path("/app"),
        }
        
        self.forbidden_commands = {
            'rm -rf /', 'sudo', 'su', 'passwd', 'chown', 'chmod 777',
            'wget', 'curl', 'nc', 'netcat', 'ssh', 'scp'
        }
    
    def _validate_path(self, path: Path) -> bool:
        """Validate that path is within allowed directories"""
        try:
            abs_path = path.resolve()
            return any(abs_path.is_relative_to(allowed) for allowed in self.allowed_paths)
        except:
            return False
    
    def _validate_command(self, command: str) -> bool:
        """Validate that command is safe to execute"""
        command_lower = command.lower()
        return not any(forbidden in command_lower for forbidden in self.forbidden_commands)

class ShellTool(ToolExecutor):
    """Secure shell command execution"""
    
    def execute(self, command: str, timeout: int = 30, cwd: Optional[str] = None) -> Dict[str, Any]:
        """Execute shell command with security restrictions"""
        if not self._validate_command(command):
            raise SecurityError(f"Command not allowed: {command}")
        
        if cwd:
            cwd_path = Path(cwd)
            if not self._validate_path(cwd_path):
                raise SecurityError(f"Directory not allowed: {cwd}")
        else:
            cwd = str(self.workspace_dir)
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, 'PATH': '/usr/local/bin:/usr/bin:/bin'}
            )
            
            return {
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'command': command,
                'success': result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                'stdout': '',
                'stderr': f'Command timed out after {timeout} seconds',
                'returncode': -1,
                'command': command,
                'success': False
            }
        except Exception as e:
            return {
                'stdout': '',
                'stderr': str(e),
                'returncode': -1,
                'command': command,
                'success': False
            }

class CodeExecutor(ToolExecutor):
    """Execute code in various languages with context management"""
    
    def __init__(self, workspace_dir: str = "/workspace"):
        super().__init__(workspace_dir)
        self.execution_count = 0
    
    def execute_python(self, code: str, timeout: int = 60) -> Dict[str, Any]:
        """Execute Python code in a controlled environment"""
        self.execution_count += 1
        
        # Create isolated execution file
        exec_file = self.workspace_dir / f"temp_exec_{self.execution_count}.py"
        
        try:
            with open(exec_file, 'w') as f:
                f.write(code)
            
            result = subprocess.run(
                ['python3', str(exec_file)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace_dir)
            )
            
            return {
                'output': result.stdout,
                'error': result.stderr,
                'returncode': result.returncode,
                'language': 'python',
                'success': result.returncode == 0
            }
        
        except subprocess.TimeoutExpired:
            return {
                'output': '',
                'error': f'Execution timed out after {timeout} seconds',
                'returncode': -1,
                'language': 'python',
                'success': False
            }
        finally:
            # Cleanup
            if exec_file.exists():
                exec_file.unlink()
    
    def execute_typescript(self, code: str, timeout: int = 60) -> Dict[str, Any]:
        """Execute TypeScript code"""
        self.execution_count += 1
        
        exec_file = self.workspace_dir / f"temp_exec_{self.execution_count}.ts"
        
        try:
            with open(exec_file, 'w') as f:
                f.write(code)
            
            # Compile and run
            compile_result = subprocess.run(
                ['npx', 'tsc', str(exec_file), '--outDir', str(self.workspace_dir)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if compile_result.returncode != 0:
                return {
                    'output': '',
                    'error': f'Compilation error: {compile_result.stderr}',
                    'returncode': compile_result.returncode,
                    'language': 'typescript',
                    'success': False
                }
            
            js_file = exec_file.with_suffix('.js')
            result = subprocess.run(
                ['node', str(js_file)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace_dir)
            )
            
            return {
                'output': result.stdout,
                'error': result.stderr,
                'returncode': result.returncode,
                'language': 'typescript',
                'success': result.returncode == 0
            }
        
        except subprocess.TimeoutExpired:
            return {
                'output': '',
                'error': f'Execution timed out after {timeout} seconds',
                'returncode': -1,
                'language': 'typescript',
                'success': False
            }
        finally:
            # Cleanup
            for ext in ['.ts', '.js']:
                cleanup_file = exec_file.with_suffix(ext)
                if cleanup_file.exists():
                    cleanup_file.unlink()

class XDotTool(ToolExecutor):
    """GUI automation using xdotool"""
    
    def __init__(self, workspace_dir: str = "/workspace"):
        super().__init__(workspace_dir)
        self.display = os.environ.get('DISPLAY', ':1')
    
    def click(self, x: int, y: int) -> Dict[str, Any]:
        """Click at coordinates"""
        try:
            result = subprocess.run(
                ['xdotool', 'mousemove', str(x), str(y), 'click', '1'],
                capture_output=True,
                text=True,
                env={**os.environ, 'DISPLAY': self.display}
            )
            
            return {
                'action': 'click',
                'x': x,
                'y': y,
                'success': result.returncode == 0,
                'error': result.stderr if result.returncode != 0 else None
            }
        except Exception as e:
            return {
                'action': 'click',
                'x': x,
                'y': y,
                'success': False,
                'error': str(e)
            }
    
    def type_text(self, text: str) -> Dict[str, Any]:
        """Type text"""
        try:
            result = subprocess.run(
                ['xdotool', 'type', text],
                capture_output=True,
                text=True,
                env={**os.environ, 'DISPLAY': self.display}
            )
            
            return {
                'action': 'type',
                'text': text,
                'success': result.returncode == 0,
                'error': result.stderr if result.returncode != 0 else None
            }
        except Exception as e:
            return {
                'action': 'type',
                'text': text,
                'success': False,
                'error': str(e)
            }
    
    def key_combo(self, keys: str) -> Dict[str, Any]:
        """Send key combination (e.g., 'ctrl+c', 'alt+Tab')"""
        try:
            result = subprocess.run(
                ['xdotool', 'key', keys],
                capture_output=True,
                text=True,
                env={**os.environ, 'DISPLAY': self.display}
            )
            
            return {
                'action': 'key_combo',
                'keys': keys,
                'success': result.returncode == 0,
                'error': result.stderr if result.returncode != 0 else None
            }
        except Exception as e:
            return {
                'action': 'key_combo',
                'keys': keys,
                'success': False,
                'error': str(e)
            }
    
    def get_window_info(self) -> Dict[str, Any]:
        """Get information about current windows"""
        try:
            result = subprocess.run(
                ['xdotool', 'search', '--onlyvisible', '--name', '.*'],
                capture_output=True,
                text=True,
                env={**os.environ, 'DISPLAY': self.display}
            )
            
            window_ids = result.stdout.strip().split('\n') if result.stdout.strip() else []
            windows = []
            
            for window_id in window_ids:
                if window_id:
                    name_result = subprocess.run(
                        ['xdotool', 'getwindowname', window_id],
                        capture_output=True,
                        text=True,
                        env={**os.environ, 'DISPLAY': self.display}
                    )
                    windows.append({
                        'id': window_id,
                        'name': name_result.stdout.strip()
                    })
            
            return {
                'action': 'get_windows',
                'windows': windows,
                'success': True
            }
        except Exception as e:
            return {
                'action': 'get_windows',
                'windows': [],
                'success': False,
                'error': str(e)
            }

class FileSystemTool(ToolExecutor):
    """Secure filesystem operations"""
    
    def create_file(self, path: str, content: str = "") -> Dict[str, Any]:
        """Create a new file"""
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self.workspace_dir / file_path
        
        if not self._validate_path(file_path):
            raise SecurityError(f"Path not allowed: {path}")
        
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as f:
                f.write(content)
            
            return {
                'action': 'create_file',
                'path': str(file_path),
                'success': True,
                'size': len(content)
            }
        except Exception as e:
            return {
                'action': 'create_file',
                'path': str(file_path),
                'success': False,
                'error': str(e)
            }
    
    def read_file(self, path: str) -> Dict[str, Any]:
        """Read file content"""
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self.workspace_dir / file_path
        
        if not self._validate_path(file_path):
            raise SecurityError(f"Path not allowed: {path}")
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            return {
                'action': 'read_file',
                'path': str(file_path),
                'content': content,
                'success': True,
                'size': len(content)
            }
        except Exception as e:
            return {
                'action': 'read_file',
                'path': str(file_path),
                'success': False,
                'error': str(e)
            }
    
    def edit_file(self, path: str, content: str) -> Dict[str, Any]:
        """Edit existing file or create new one"""
        return self.create_file(path, content)
    
    def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete a file"""
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self.workspace_dir / file_path
        
        if not self._validate_path(file_path):
            raise SecurityError(f"Path not allowed: {path}")
        
        try:
            if file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                return {
                    'action': 'delete_file',
                    'path': str(file_path),
                    'success': False,
                    'error': 'Path does not exist'
                }
            
            return {
                'action': 'delete_file',
                'path': str(file_path),
                'success': True
            }
        except Exception as e:
            return {
                'action': 'delete_file',
                'path': str(file_path),
                'success': False,
                'error': str(e)
            }
    
    def list_directory(self, path: str = ".") -> Dict[str, Any]:
        """List directory contents"""
        dir_path = Path(path)
        if not dir_path.is_absolute():
            dir_path = self.workspace_dir / dir_path
        
        if not self._validate_path(dir_path):
            raise SecurityError(f"Path not allowed: {path}")
        
        try:
            items = []
            for item in dir_path.iterdir():
                items.append({
                    'name': item.name,
                    'type': 'directory' if item.is_dir() else 'file',
                    'size': item.stat().st_size if item.is_file() else None,
                    'modified': item.stat().st_mtime
                })
            
            return {
                'action': 'list_directory',
                'path': str(dir_path),
                'items': sorted(items, key=lambda x: (x['type'], x['name'])),
                'success': True
            }
        except Exception as e:
            return {
                'action': 'list_directory',
                'path': str(dir_path),
                'success': False,
                'error': str(e)
            }
    
    def move_file(self, src: str, dst: str) -> Dict[str, Any]:
        """Move/rename a file"""
        src_path = Path(src)
        dst_path = Path(dst)
        
        if not src_path.is_absolute():
            src_path = self.workspace_dir / src_path
        if not dst_path.is_absolute():
            dst_path = self.workspace_dir / dst_path
        
        if not (self._validate_path(src_path) and self._validate_path(dst_path)):
            raise SecurityError(f"Paths not allowed: {src} -> {dst}")
        
        try:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst_path))
            
            return {
                'action': 'move_file',
                'src': str(src_path),
                'dst': str(dst_path),
                'success': True
            }
        except Exception as e:
            return {
                'action': 'move_file',
                'src': str(src_path),
                'dst': str(dst_path),
                'success': False,
                'error': str(e)
            }