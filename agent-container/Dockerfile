FROM ubuntu:22.04

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Display server and VNC
    xvfb \
    x11vnc \
    novnc \
    websockify \
    openbox \
    # Development tools
    python3 \
    python3-pip \
    nodejs \
    npm \
    git \
    curl \
    wget \
    # GUI automation
    xdotool \
    xautomation \
    # Text editors and utilities
    vim \
    nano \
    htop \
    tree \
    # Build tools
    build-essential \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install \
    jupyter \
    jupyterlab \
    notebook \
    ipykernel \
    fastapi \
    uvicorn \
    requests \
    psutil \
    docker \
    aiofiles

# Install Node.js packages globally
RUN npm install -g \
    typescript \
    ts-node \
    @types/node \
    create-react-app \
    vite

# Create workspace directory
WORKDIR /workspace

# Copy agent code
COPY agent/ /app/agent/
COPY scripts/ /app/scripts/

# Create VNC password
RUN mkdir -p ~/.vnc && \
    x11vnc -storepasswd agent ~/.vnc/passwd

# Create startup script
COPY scripts/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose ports
EXPOSE 8888 6080 5900

# Set up Jupyter config
RUN jupyter notebook --generate-config && \
    echo "c.NotebookApp.ip = '0.0.0.0'" >> ~/.jupyter/jupyter_notebook_config.py && \
    echo "c.NotebookApp.allow_root = True" >> ~/.jupyter/jupyter_notebook_config.py && \
    echo "c.NotebookApp.token = ''" >> ~/.jupyter/jupyter_notebook_config.py

CMD ["/app/start.sh"]