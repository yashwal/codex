# Sandboxed Coding Agent System

A scalable coding agent with sandboxing, context management, and orchestration layer.

## Architecture

### Components

1. **Agent Container** (`agent-container/`)
   - Docker image with display server, xdot, VNC, Jupyter
   - Sandboxed execution environment
   - Context management system

2. **Orchestration Server** (`orchestrator/`)
   - FastAPI server for job scheduling
   - Firecracker VM management
   - Status tracking and file delivery

3. **Shared** (`shared/`)
   - Common utilities and models
   - Context management interfaces

## Quick Start

```bash
# Build agent container
cd agent-container
docker build -t coding-agent .

# Start orchestrator
cd ../orchestrator
pip install -r requirements.txt
python main.py

# Submit a job
curl -X POST http://localhost:8000/schedule \
  -H "Content-Type: application/json" \
  -d '{"task": "Build me a todo app in React"}'

# Check status
curl http://localhost:8000/status/{job_id}
```

## Features

- **Sandboxed Execution**: Secure isolated environment
- **Context Management**: Handles >1M token contexts via intelligent pruning
- **GUI Support**: xdot integration for GUI automation
- **VNC Access**: Remote desktop via noVNC
- **Scalable**: Ready for container orchestration
- **Security**: Multi-layer isolation with Firecracker VMs