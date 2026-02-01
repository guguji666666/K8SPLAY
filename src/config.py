# Kubernetes Pod Cleaner Configuration
# Detects and restarts unhealthy pods automatically

import os


class Config:
    """
    Configuration class for Pod Cleaner
    Manages all configurable parameters with environment variable support
    """

    # ============================================================
    # Kubernetes Configuration
    # ============================================================

    # System namespaces to exclude from cleaning
    EXCLUDED_NAMESPACES = ["kube-system"]

    # Pod phases considered healthy
    HEALTHY_POD_PHASES = ["Running", "Init", "Succeeded"]

    # ============================================================
    # Scheduling Configuration
    # ============================================================

    # Run interval in seconds (10 minutes = 600 seconds)
    RUN_INTERVAL_SECONDS = 600

    # ============================================================
    # Bark Push Notification Configuration
    # ============================================================

    # Bark service base URL
    # MUST be set via BARK_BASE_URL environment variable
    # Format: https://your-bark-domain/device-key/
    BARK_BASE_URL = ""

    # Enable/disable Bark notifications
    # MUST be set via BARK_ENABLED environment variable
    BARK_ENABLED = True

    # ============================================================
    # Logging Configuration
    # ============================================================

    # Log level: DEBUG > INFO > WARNING > ERROR > CRITICAL (can be overridden by LOG_LEVEL env var)
    LOG_LEVEL = "INFO"

    # Log time format
    LOG_FORMAT = "%Y-%m-%d %H:%M:%S"

    # ============================================================
    # Environment Variable Methods
    # ============================================================

    @classmethod
    def get_bark_base_url(cls) -> str:
        """Get Bark URL from environment variable (required)"""
        url = os.getenv("BARK_BASE_URL", "").rstrip('/')
        if not url:
            raise ValueError(
                "BARK_BASE_URL environment variable is required. "
                "Set it with: export BARK_BASE_URL='https://your-bark-server.com/DEVICE_KEY'"
            )
        return url

    @classmethod
    def get_bark_enabled(cls) -> bool:
        """Get Bark enabled from environment variable or default"""
        value = os.getenv("BARK_ENABLED", str(cls.BARK_ENABLED))
        return value.lower() in ("true", "1", "yes")

    @classmethod
    def get_log_level(cls) -> str:
        """Get log level from environment variable or default"""
        return os.getenv("LOG_LEVEL", cls.LOG_LEVEL)


def get_bark_push_url():
    """
    Get the full Bark push API URL

    Returns:
        str: Complete Bark push URL
             Format: https://<your-bark-server-url>/<device key>/push
    """
    base_url = Config.get_bark_base_url().rstrip('/')
    return f"{base_url}/push"


def should_skip_namespace(namespace: str) -> bool:
    """
    Check if a namespace should be skipped

    Parameters:
        namespace: str - Namespace name

    Returns:
        bool - True if namespace should be skipped

    Examples:
        should_skip_namespace("kube-system")  # Returns True, skip
        should_skip_namespace("default")       # Returns False, process
    """
    return namespace in Config.EXCLUDED_NAMESPACES


def is_pod_healthy(phase: str) -> bool:
    """
    Check if a pod is in a healthy state based on its phase

    Parameters:
        phase: str - Pod phase

    Returns:
        bool - True if healthy, False if unhealthy

    Pod Phase Reference:
        - Running: Pod assigned to node and running
        - Init: Pod initializing
        - Pending: Pod waiting for scheduling
        - Succeeded: Pod completed successfully (Job type)
        - Failed: Pod failed
        - Unknown: Unknown status (API Server communication issue)
    """
    return phase in Config.HEALTHY_POD_PHASES
