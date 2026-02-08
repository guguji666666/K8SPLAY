# =============================================================================
# Kubernetes Pod Cleaner Configuration Module
# =============================================================================
# This module manages all configuration settings for the Pod Cleaner application.
# It provides both hardcoded defaults and environment variable overrides.
#
# FILE STRUCTURE:
# - Config CLASS: Contains all configurable parameters
# - Helper FUNCTIONS: Utility functions for namespace/pod checks
#
# RELATED FILES:
# - main.py: Imports Config to get run interval and log settings
# - notifier.py: Imports Config for Bark notification settings
# - kube_client.py: Imports Config for namespace filtering rules
# =============================================================================

# -----------------------------------------------------------------------------
# STANDARD LIBRARY IMPORTS
# -----------------------------------------------------------------------------
# 'os' module: Used to read environment variables at runtime
# This allows configuration to be set without modifying code
import os


# =============================================================================
# CONFIG CLASS - Central Configuration Management
# =============================================================================
# CONCEPT: Why use a class for configuration?
# - Class attributes provide default values that can be overridden
# - @classmethod methods allow reading environment variables
# - Single source of truth for all settings
#
# DESIGN PATTERN: This uses the "Configuration Class" pattern common in Python
# where a class groups related configuration rather than global variables.
class Config:
    """
    Configuration class for Pod Cleaner.

    This class manages all configurable parameters with environment variable support.

    CONCEPT - Environment Variables:
    - Environment variables are OS-level settings that persist across sessions
    - They allow secrets (like API keys) to be set outside the code
    - They enable different configurations for dev/staging/prod environments

    EXAMPLE:
        In Kubernetes, you set env vars in the Deployment manifest:
        env:
          - name: BARK_BASE_URL
            value: "https://your-bark-server.com/DEVICE_KEY"

    Connection to other files:
    - main.py: Reads LOG_LEVEL, RUN_INTERVAL_SECONDS
    - notifier.py: Reads BARK_BASE_URL, BARK_ENABLED
    - kube_client.py: Reads EXCLUDED_NAMESPACES, HEALTHY_POD_PHASES
    """

    # ==========================================================================
    # KUBERNETES NAMESPACE CONFIGURATION
    # ==========================================================================
    # CONCEPT: What is a Kubernetes Namespace?
    # - Namespaces provide a mechanism for isolating groups of resources
    # - They act like "virtual clusters" within a physical cluster
    # - Default namespaces: default, kube-system, kube-public
    #
    # WHY EXCLUDE kube-system?
    # - kube-system contains critical Kubernetes system components
    # - Deleting these pods would crash the cluster
    # - Components include: etcd, API server, scheduler, DNS, etc.
    #
    # RELATED: should_skip_namespace() function below uses this constant
    EXCLUDED_NAMESPACES = ["kube-system"]
    """
    List of namespace names that should NOT be processed.
    kube-system is always excluded because it contains critical cluster components.
    """

    # ==========================================================================
    # POD HEALTH PHASE CONFIGURATION
    # ==========================================================================
    # CONCEPT: What is a Pod Phase?
    # - phase is a high-level summary of where a pod is in its lifecycle
    # - Kubernetes sets the phase based on the conditions of its containers
    #
    # POD PHASE REFERENCE:
    # - Pending: Pod has been accepted but not yet scheduled to a node
    # - Running: Pod has been bound to a node and at least one container is running
    # - Succeeded: All containers in the pod have terminated successfully
    # - Failed: At least one container terminated with a non-zero exit code
    # - Unknown: Pod state cannot be determined (API server communication issue)
    #
    # WHY "Init" IS HEALTHY:
    # - Init containers are running their initialization logic
    # - This is a normal transient state during pod startup
    #
    # Connection to other files:
    # - kube_client.py: is_pod_healthy() function checks if phase is in this list
    HEALTHY_POD_PHASES = ["Running", "Init", "Succeeded"]
    """
    Pod phases that indicate a healthy pod state.
    Used by is_pod_healthy() in kube_client.py to filter pods.
    """


    # ==========================================================================
    # SCHEDULING CONFIGURATION
    # ==========================================================================
    # CONCEPT: Why a fixed 10-minute interval?
    # - Frequent enough to catch issues quickly (10 minutes is standard)
    # - Not too frequent to avoid overwhelming the API server
    # - Gives pods reasonable time to restart and stabilize
    #
    # Connection to other files:
    # - main.py: Uses this to calculate sleep time between runs
    RUN_INTERVAL_SECONDS = 600
    """
    How often to run the cleanup cycle, in seconds.
    Default: 600 seconds = 10 minutes.
    """


    # ==========================================================================
    # BARK NOTIFICATION CONFIGURATION
    # ==========================================================================
    # CONCEPT: What is Bark?
    # - Bark is an iOS push notification service
    # - Self-hosted option available for privacy/sensitivity requirements
    # - Simple HTTP API: POST to <url>/<device-key>/push
    #
    # WHY ENVIRONMENT VARIABLES FOR SECRETS?
    # - API keys and URLs should never be hardcoded in source code
    # - Environment variables keep secrets out of version control
    # - They can be rotated without code changes
    #
    # Connection to other files:
    # - notifier.py: Uses get_bark_base_url() to construct the push URL
    BARK_BASE_URL = ""
    """
    Bark server base URL with device key.
    Format: https://your-bark-domain/device-key
    MUST be set via BARK_BASE_URL environment variable.
    """

    BARK_ENABLED = True
    """
    Boolean flag to enable/disable Bark notifications.
    Can be overridden with BARK_ENABLED environment variable.
    Set to "true", "1", or "yes" to enable (case-insensitive).
    """


    # ==========================================================================
    # LOGGING CONFIGURATION
    # ==========================================================================
    # CONCEPT: Python Logging Levels (ordered by severity):
    # - DEBUG: Detailed info, typically only needed when debugging
    # - INFO: General operational messages (default for production)
    # - WARNING: Something unexpected but not critical
    # - ERROR: Something failed but the program continues
    # - CRITICAL: Severe error, program may terminate
    #
    # WHY DEFAULT TO INFO?
    # - INFO level provides enough detail for production monitoring
    # - It doesn't include verbose debug output
    # - It captures warnings and errors for alerting
    #
    # Connection to other files:
    # - main.py: Uses get_log_level() in setup_logging() function
    LOG_LEVEL = "INFO"
    """
    Minimum severity level for log messages.
    Overridden by LOG_LEVEL environment variable.
    """

    LOG_FORMAT = "%Y-%m-%d %H:%M:%S"
    """
    Format string for timestamps in log output.
    %Y = 4-digit year, %m = month, %d = day, %H:%M:%S = hour:minute:second
    Example output: "2026-02-08 14:30:45"
    """


    # ==========================================================================
    # ENVIRONMENT VARIABLE GETTERS
    # ==========================================================================
    # CONCEPT: Why @classmethod?
    # - @classmethod allows calling the method on the class itself
    #   without creating an instance (Config.get_log_level() vs config.get_log_level())
    # - This is the standard pattern for configuration getters
    #
    # CONCEPT: os.getenv() function:
    # - Takes two arguments: variable name, default value
    # - Returns the environment variable value if set
    # - Returns the default value if not set
    #
    # DESIGN PATTERN: Fail-fast for required settings
    # - get_bark_base_url() raises an error if not set
    # - This prevents silent failures in production
    @classmethod
    def get_bark_base_url(cls) -> str:
        """
        Retrieve Bark URL from environment variable.

        CONCEPT: Type hint -> str
        - The -> str indicates this function returns a string
        - This is for documentation and IDE support (type checking)

        WHAT THIS CODE DOES:
        1. Gets BARK_BASE_URL from environment (empty string if not set)
        2. Removes trailing slash with .rstrip('/')
           Why? To ensure consistent URL formatting when appending /push
        3. Raises ValueError if empty (fail-fast for missing required config)

        RELATED:
        - get_bark_push_url() in this file uses this to construct full URL
        - notifier.py: Uses get_bark_push_url() to send notifications
        """
        # Get from environment, default to empty string
        url = os.getenv("BARK_BASE_URL", "").rstrip('/')
        
        # Check if URL was provided (fail-fast)
        if not url:
            raise ValueError(
                "BARK_BASE_URL environment variable is required. "
                "Set it with: export BARK_BASE_URL='https://your-bark-server.com/DEVICE_KEY'"
            )
        
        return url

    @classmethod
    def get_bark_enabled(cls) -> bool:
        """
        Retrieve Bark notification enabled status from environment variable.

        CONCEPT: Boolean parsing
        - Environment variables are always strings
        - We need to convert "true"/"false" strings to Python booleans
        - .lower() makes the check case-insensitive

        WHAT THIS CODE DOES:
        1. Gets BARK_ENABLED from environment (default "True" from class attr)
        2. Converts to lowercase for case-insensitive comparison
        3. Returns True if value is "true", "1", or "yes"
        4. Returns False for any other value

        RELATED:
        - notifier.py: Checks this in send_notification() to skip if disabled
        """
        # Get value, convert to lowercase, check for truthy values
        value = os.getenv("BARK_ENABLED", str(cls.BARK_ENABLED))
        return value.lower() in ("true", "1", "yes")

    @classmethod
    def get_log_level(cls) -> str:
        """
        Retrieve log level from environment variable.

        CONCEPT: Default value fallback
        - If LOG_LEVEL env var is not set, use class default
        - This allows partial configuration (set only what you need)

        RELATED:
        - main.py: Calls this in setup_logging() to configure logging
        """
        return os.getenv("LOG_LEVEL", cls.LOG_LEVEL)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
# CONCEPT: Why standalone functions?
# - They're simpler than class methods for pure utility operations
# - They can be imported directly without instantiating a class
# - They're commonly used in Python for simple transformations


def get_bark_push_url() -> str:
    """
    Construct the full Bark push API URL.

    CONCEPT: URL Construction
    - Bark API requires: <base-url>/push endpoint
    - We separate the base URL (from env var) from the endpoint path
    - This separation allows for cleaner configuration

    WHAT THIS CODE DOES:
    1. Gets base URL from Config.get_bark_base_url()
    2. Removes trailing slash (if present)
    3. Appends "/push" for the API endpoint
    4. Returns complete URL like: https://api.day.app/ABC123/push

    EXAMPLE:
        Input:  BARK_BASE_URL="https://api.day.app/ABC123"
        Output: https://api.day.app/ABC123/push

    RELATED:
        Called by: notifier.py:BarkNotifier.__init__()
    """
    # Get base URL and ensure no trailing slash
    base_url = Config.get_bark_base_url().rstrip('/')
    
    # Append push endpoint
    return f"{base_url}/push"


def should_skip_namespace(namespace: str) -> bool:
    """
    Determine if a namespace should be excluded from processing.

    CONCEPT: Namespace Filtering
    - This is a security/safety mechanism
    - Prevents accidental deletion of critical system components
    - kube-system must always be protected

    WHAT THIS CODE DOES:
    1. Takes a namespace name as input
    2. Checks if it's in the EXCLUDED_NAMESPACES list
    3. Returns True (skip) if found, False (process) if not found

    EXAMPLE:
        should_skip_namespace("kube-system")  # Returns True
        should_skip_namespace("default")       # Returns False

    PERFORMANCE NOTE:
    - Using 'in' with a list is O(n) but n is very small (1 item)
    - For larger lists, a set would be more efficient

    RELATED:
        Called by:
        - kube_client.py:find_unhealthy_pods()
        - kube_client.py:wait_for_pods_ready()
    """
    return namespace in Config.EXCLUDED_NAMESPACES


def is_pod_healthy(phase: str) -> bool:
    """
    Check if a pod's phase indicates it is healthy.

    CONCEPT: Pod Phase as Health Indicator
    - The phase is Kubernetes' high-level summary of pod state
    - Not all non-Running phases are unhealthy
    - Some phases (Init, Succeeded) are expected transient states

    WHAT THIS CODE DOES:
    1. Takes a pod phase string as input
    2. Checks if it's in the HEALTHY_POD_PHASES list
    3. Returns True if healthy, False if unhealthy

    POD PHASE DETAILS:
    - Running: Pod is running (good)
    - Init: Init containers are running (normal startup)
    - Succeeded: All containers exited successfully (normal for Jobs)
    - Pending: Waiting to be scheduled (potentially problematic)
    - Failed: At least one container failed (bad)
    - Unknown: Cannot determine state (potentially bad)

    EXAMPLE:
        is_pod_healthy("Running")     # Returns True
        is_pod_healthy("Failed")      # Returns False

    RELATED:
        Called by:
        - kube_client.py:find_unhealthy_pods()
        - kube_client.py:wait_for_pods_ready()
    """
    return phase in Config.HEALTHY_POD_PHASES
