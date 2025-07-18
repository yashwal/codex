#!/bin/bash

set -e

echo "Building Coding Agent System..."

# Build agent container
echo "Building agent container..."
cd agent-container
docker build -t coding-agent:latest .
cd ..

# Build orchestrator image
echo "Building orchestrator image..."
cat > orchestrator/Dockerfile << EOF
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    docker.io \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the orchestrator
CMD ["python", "-m", "orchestrator.main"]
EOF

docker build -t coding-agent-orchestrator:latest orchestrator/

echo "Build completed successfully!"
echo ""
echo "Available images:"
docker images | grep coding-agent

echo ""
echo "Next steps:"
echo "1. Start the orchestrator: docker run -p 8000:8000 -v /var/run/docker.sock:/var/run/docker.sock coding-agent-orchestrator:latest"
echo "2. Or use docker-compose: docker-compose up"
echo "3. Or deploy to Kubernetes: kubectl apply -f k8s/"