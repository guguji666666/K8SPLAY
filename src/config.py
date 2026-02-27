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
    # Recovery Verification Configuration
    # ============================================================

    # Enable/disable recovery verification
    RECOVERY_CHECK_ENABLED = True

    # Wait time for new pod creation after deletion (seconds)
    RECOVERY_WAIT_SECONDS = 120

    # Maximum retry attempts before escalating
    RECOVERY_MAX_ATTEMPTS = 3

    # Check interval when waiting for new pod (seconds)
    RECOVERY_CHECK_INTERVAL = 10

    # State file path for persistence
    PERSISTENCE_FILE = "/var/lib/pod-cleaner/state.json"

    # Cleanup old entries after (hours)
    PERSISTENCE_MAX_AGE_HOURS = 24

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

    @classmethod
    def get_recovery_enabled(cls) -> bool:
        """Get recovery check enabled from environment variable or default"""
        value = os.getenv("RECOVERY_CHECK_ENABLED", str(cls.RECOVERY_CHECK_ENABLED))
        return value.lower() in ("true", "1", "yes")

    @classmethod
    def get_recovery_wait_seconds(cls) -> int:
        """Get recovery wait time from environment variable or default"""
        return int(os.getenv("RECOVERY_WAIT_SECONDS", str(cls.RECOVERY_WAIT_SECONDS)))

    @classmethod
    def get_recovery_max_attempts(cls) -> int:
        """Get max retry attempts from environment variable or default"""
        return int(os.getenv("RECOVERY_MAX_ATTEMPTS", str(cls.RECOVERY_MAX_ATTEMPTS)))

    @classmethod
    def get_recovery_check_interval(cls) -> int:
        """Get recovery check interval from environment variable or default"""
        return int(os.getenv("RECOVERY_CHECK_INTERVAL", str(cls.RECOVERY_CHECK_INTERVAL)))

    @classmethod
    def get_persistence_file(cls) -> str:
        """Get persistence file path from environment variable or default"""
        return os.getenv("PERSISTENCE_FILE", cls.PERSISTENCE_FILE)

    @classmethod
    def get_persistence_max_age_hours(cls) -> int:
        """Get persistence max age from environment variable or default"""
        return int(os.getenv("PERSISTENCE_MAX_AGE_HOURS", str(cls.PERSISTENCE_MAX_AGE_HOURS)))


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
