# ============================================================
# Dockerfile - Pod Cleaner Container Image Build
# ============================================================
# Build command: docker build -t pod-cleaner:latest .
# Run command: docker run -d pod-cleaner
# ============================================================

# 1. Use Python official image as base image
# slim version is small (~150MB), suitable for production
FROM python:3.11-slim

# 2. Set image metadata
# LABEL describes image info for management and查询
LABEL maintainer="GOKU" \
      description="Kubernetes Pod Auto-Cleaner" \
      version="1.0.0"

# 3. Set working directory
# All subsequent commands execute in /app directory
WORKDIR /app

# 4. Copy dependency file
# First copy requirements.txt, then install dependencies
# Use Docker cache layer to speed up build
COPY requirements.txt .

# 5. Install Python dependencies
# -q: Quiet mode, less output
# --no-cache-dir: Don't use cache, reduce image size
RUN pip install --no-cache-dir -q -r requirements.txt

# 6. Copy application code
# Copy all files from src/ to /app
COPY src/ .

# 7. Set environment variables
# Environment variables take effect at runtime, control program behavior
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Variable details:
# - PYTHONUNBUFFERED=1
#   Effect: Disable Python output buffering, ensure logs write to stdout immediately
#   Scenario: Important for viewing real-time logs in container, otherwise logs delayed
#   Principle: Python uses line buffering by default, docker logs may not receive real-time output
#
# - PYTHONDONTWRITEBYTECODE=1
#   Effect: Disable Python .pyc bytecode file generation
#   Scenario: Container is read-only, writing .pyc causes error; reduce image size
#   Principle: Python compiles to .pyc on first import, disabled to compile in memory

# 8. Set container startup command
# ENTRYPOINT defines command executed at container startup, CMD defines default arguments

# Startup method comparison:
# ┌─────────────────────────────────────────────────────────────────────┐
# │ Method 1: CMD (not recommended)                                     │
# ├─────────────────────────────────────────────────────────────────────┤
# │ CMD ["python", "main.py"]                                           │
# │                                                                      │
# │ Characteristics:                                                    │
# │ - Command easily overwritten by docker run arguments                │
# │ - No signal support (SIGTERM)                                       │
# │ - When container receives stop signal, Python may not shutdown gracefully│
# └─────────────────────────────────────────────────────────────────────┘
#
# ┌─────────────────────────────────────────────────────────────────────┐
# │ Method 2: ENTRYPOINT + exec format (recommended)                    │
# ├─────────────────────────────────────────────────────────────────────┤
# │ ENTRYPOINT ["python", "-u", "main.py"]                              │
# │                                                                      │
# │ Characteristics:                                                    │
# │ - Use exec format, PID 1 process is Python                          │
# │ - Signal support: docker stop sends SIGTERM                         │
# │ - Program can handle graceful shutdown (KeyboardInterrupt)          │
# │ - "-u" parameter: Force stdin/stdout/stderr unbuffered (same as PYTHONUNBUFFERED)│
# └─────────────────────────────────────────────────────────────────────┘
#
# Why use exec format?
# - Docker container's PID 1 process is responsible for receiving signals
# - If using shell format ["sh", "-c", "python main.py"], PID 1 is shell
# - Shell won't forward signals to Python, docker stop becomes force kill
# - Exec format lets Python become PID 1 directly, can respond to SIGTERM correctly

# Graceful shutdown flow:
# 1. docker stop sends SIGTERM (default 10 second wait)
# 2. Python receives SIGTERM, triggers KeyboardInterrupt
# 3. Program executes finally block, cleans up resources
# 4. Program exits normally (exit code 0)

ENTRYPOINT ["python", "-u", "main.py"]

# 9. Optional: Expose port
# If program provides HTTP/HTTPS service, need to expose port
# Note: EXPOSE is documentation only, actual port mapping controlled by docker run -p
#
# Use scenarios:
# - Program has health check endpoint /health
# - Program provides metrics endpoint /metrics
# - Program is HTTP service
#
# Deployment port mapping:
# docker run -d -p 8080:8080 pod-cleaner
#
# If program has no network service, delete this line
# EXPOSE 8080

# ============================================================
# Build Instructions:
# 1. Build image: docker build -t pod-cleaner:latest .
# 2. Local test: docker run --rm pod-cleaner
# 3. Push to registry: docker tag pod-cleaner:latest your-registry/pod-cleaner:v1
#                       docker push your-registry/pod-cleaner:v1
# ============================================================
