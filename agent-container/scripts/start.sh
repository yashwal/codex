#!/bin/bash

# Start Xvfb (virtual framebuffer)
echo "Starting Xvfb..."
Xvfb :1 -screen 0 1024x768x16 &
sleep 2

# Start window manager
echo "Starting Openbox..."
DISPLAY=:1 openbox &
sleep 1

# Start VNC server
echo "Starting VNC server..."
DISPLAY=:1 x11vnc -forever -usepw -shared -rfbport 5900 &
sleep 2

# Start noVNC
echo "Starting noVNC..."
cd /usr/share/novnc
./utils/launch.sh --vnc localhost:5900 --listen 6080 &
sleep 2

# Start Jupyter Lab
echo "Starting Jupyter Lab..."
cd /workspace
jupyter lab --port=8888 --ip=0.0.0.0 --allow-root --no-browser &

# Start the coding agent
echo "Starting Coding Agent..."
cd /app
python3 -m agent.main &

# Keep container running
echo "All services started. Container is ready."
echo "VNC: http://localhost:6080/vnc.html"
echo "Jupyter: http://localhost:8888"
tail -f /dev/null