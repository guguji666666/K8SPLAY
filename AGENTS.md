# AGENTS.md - Pod Cleaner Development Guide

This file provides guidelines for agentic coding agents working on the Pod Cleaner project.

## Project Overview

Pod Cleaner is a Python-based Kubernetes utility that detects and restarts unhealthy pods. It uses the Kubernetes Python client and sends Bark notifications for alerts.

## Build, Lint, and Test Commands

### Installation
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies (if any)
pip install pytest pytest-cov black flake8 mypy
```

### Running Tests
```bash
# Run all tests
python3 test-detection-logic.py

# Run tests with K8s cluster verification
python3 test-detection-logic.py --k8s

# Run tests for specific namespace
python3 test-detection-logic.py --k8s -n <namespace>

# Run with pytest (if added)
pytest tests/ -v
pytest tests/ -v --cov=src --cov-report=html
pytest tests/test_detection.py::test_crashloop -v  # Single test
```

### Code Quality
```bash
# Format code (Black)
black src/ tests/

# Lint code (Flake8)
flake8 src/ tests/ --max-line-length=100

# Type checking (Mypy)
mypy src/ --ignore-missing-imports
mypy src/ --strict  # Full strict mode

# All checks before commit
black src/ tests/ && flake8 src/ tests/ && mypy src/ --ignore-missing-imports
```

### Docker Operations
```bash
# Build Docker image
docker build -t pod-cleaner:latest .

# Run container locally
docker run -d \
  -e BARK_BASE_URL="https://..." \
  -e BARK_ENABLED="true" \
  -v ~/.kube/config:/root/.kube/config:ro \
  pod-cleaner:latest
```

### Kubernetes Deployment
```bash
# Helm deployment
helm install pod-cleaner ./helm/pod-cleaner \
  --set image.repository=guguji666/pod-cleaner \
  --set image.tag=v2.6 \
  --set config.barkBaseUrl="https://..." \
  --set config.barkEnabled=true

# Native manifest
kubectl apply -f k8s-manifest.yaml
```

## Code Style Guidelines

### File Headers
All Python files must include encoding and module docstring:
```python
# -*- coding: utf-8 -*-
"""
Module Name
Brief description of module purpose

Features:
- Feature 1
- Feature 2

Usage:
    import this_module
"""
```

### Imports (Alphabetical Order)
```python
# Standard library imports first
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

# Third-party imports
import requests
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

# Local application imports (relative paths)
from .config import Config
from .kube_client import KubernetesClient
```

### Type Annotations
Use type hints for all function signatures:
```python
from typing import Dict, List, Optional, Any

def get_pods_in_namespace(
    namespace: str,
    label_selector: Optional[str] = None,
    field_selector: Optional[str] = None,
    limit: int = 500
) -> List[client.V1Pod]:
    """Get pod list in specified namespace."""
    ...

def check_pod_health(pod_status: Dict[str, Any]) -> Dict[str, Any]:
    """Comprehensive pod health check."""
    result: Dict[str, Any] = {
        "healthy": True,
        "reasons": []
    }
    return result
```

### Naming Conventions
```python
# Classes: PascalCase
class KubernetesClient:
    ...

class BarkNotifier:
    ...

# Functions and variables: snake_case
def get_all_namespaces() -> List[str]:
    ...

def should_skip_namespace(namespace: str) -> bool:
    ...

log_level = "INFO"
bark_base_url = ""
```

### Error Handling
Use try/except with specific exceptions, return False or empty collection on failure:
```python
try:
    config.load_kube_config()
    print("✅ Loaded kubeconfig")
except config.ConfigException:
    try:
        config.load_incluster_config()
        print("✅ Loaded in-cluster config")
    except Exception as e:
        raise RuntimeError(f"Failed to load Kubernetes config: {e}")

try:
    response = requests.post(url, json=payload, timeout=10)
    if response.status_code == 200:
        return True
    else:
        print(f"❌ Request failed: {response.status_code}")
        return False
except Exception as e:
    print(f"❌ Request error: {e}")
    return False
```

### Logging and Output
Use print statements with emoji indicators and structured logging:
```python
# For initialization
print("✅ Kubernetes client initialized")
print(f"   URL: {self.bark_url}")
print(f"   Enabled: {'Yes' if self.enabled else 'No'}")

# For operations
print("🔍 Checking pods...")
print(f"   Found {len(unhealthy_pods)} unhealthy pod(s)")

# For errors
print(f"❌ Failed to get namespace list: {e}")
print(f"⚠️  Notification disabled, skipping")
```

### Configuration Pattern
Use class-based configuration with environment variable support:
```python
class Config:
    """Configuration class for Pod Cleaner."""
    
    EXCLUDED_NAMESPACES = ["kube-system"]
    HEALTHY_POD_PHASES = ["Running", "Init", "Succeeded"]
    RUN_INTERVAL_SECONDS = 600
    LOG_LEVEL = "INFO"
    
    @classmethod
    def get_log_level(cls) -> str:
        """Get log level from environment variable."""
        return os.getenv("LOG_LEVEL", cls.LOG_LEVEL)

def should_skip_namespace(namespace: str) -> bool:
    """Check if namespace should be skipped."""
    return namespace in Config.EXCLUDED_NAMESPACES
```

### Docstrings
Use Google-style docstrings with Parameters and Returns sections:
```python
def restart_pods(pods: List[Dict]) -> Dict:
    """
    Batch restart unhealthy pods.

    Parameters:
        pods: List[Dict] - List of unhealthy pod info

    Returns:
        Dict with keys:
            - success: Number of successful restarts
            - failed: Number of failed restarts
            - details: Detailed information
    """
```

### Function Length
Keep functions focused and under 100 lines. Extract helper functions when logic grows complex.

### Constants
Use UPPER_SNAKE_CASE for constants:
```python
EXCLUDED_NAMESPACES = ["kube-system"]
HEALTHY_POD_PHASES = ["Running", "Init", "Succeeded"]
RUN_INTERVAL_SECONDS = 600
LOG_FORMAT = "%Y-%m-%d %H:%M:%S"
```

## Key Files and Locations

| Path | Purpose |
|------|---------|
| `src/main.py` | Main entry point, cleanup loop |
| `src/kube_client.py` | Kubernetes API operations |
| `src/notifier.py` | Bark notification logic |
| `src/config.py` | Configuration and utilities |
| `test-detection-logic.py` | Test script for detection logic |
| `helm/pod-cleaner/` | Helm chart for K8s deployment |

## Development Workflow

1. **Create virtual environment** and install dependencies
2. **Make changes** to source files
3. **Run tests** with `python3 test-detection-logic.py`
4. **Verify code quality** with linting tools
5. **Test in Docker** before K8s deployment
6. **Deploy with Helm** for production use
