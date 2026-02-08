# -*- coding: utf-8 -*-
# =============================================================================
# Notification Module - Bark Push Service Integration
# =============================================================================
# This module encapsulates all Bark push notification logic.
#
# FEATURES:
# - Send cleanup completion notifications
# - Send anomaly alert notifications
# - Support multiple notification types (info, alert, recovery)
#
# ABOUT BARK:
# - Bark is an iOS push notification service (self-hosted available)
# - Simple REST API: POST https://<server>/<device-key>/push
# - Supports custom title, body, icon, and urgency levels
#
# FILE STRUCTURE:
# - BarkNotifier CLASS: Main notification class
#   - __init__(): Initialize with config from config.py
#   - send_notification(): Low-level HTTP POST to Bark API
#   - send_cleanup_report(): Format and send cleanup summary
#   - send_alert(): Format and send anomaly alerts
#   - send_recovery_success(): Optional recovery notification
#
# RELATED FILES:
# - config.py: Imports Config and get_bark_push_url()
# - main.py: Imports BarkNotifier, calls send_cleanup_report() and send_alert()
# =============================================================================

# -----------------------------------------------------------------------------
# STANDARD LIBRARY IMPORTS
# -----------------------------------------------------------------------------
# 'json' module: Used for JSON encoding/decoding
# - HTTP requests often send/receive JSON data
# - Though requests library handles this automatically with json= parameter
import json

# 'requests' module: Third-party HTTP library
# - Simpler than Python's built-in urllib
# - Used to send HTTP POST to Bark server
import requests

# 'datetime' module: Date/time handling
# - Used to generate timestamps for notification content
from datetime import datetime

# 'typing' module: Type hints for better code documentation
# - List[Dict]: List containing dictionaries
# - Optional[T]: Type that can be T or None
from typing import List, Dict, Optional


# -----------------------------------------------------------------------------
# LOCAL IMPORTS
# -----------------------------------------------------------------------------
# Import configuration from sibling module (config.py)
# These imports provide:
# - Config: Access to BARK_BASE_URL, BARK_ENABLED settings
# - get_bark_push_url(): Function to construct full Bark API URL
from config import Config, get_bark_push_url


# =============================================================================
# BarkNotifier CLASS - Notification encapsulation
# =============================================================================
# CONCEPT: What is a class for notifications?
# - Encapsulates all notification-related state and behavior
# - Stores configuration (URL, enabled status) as instance attributes
# - Provides high-level methods for different notification scenarios
#
# DESIGN PATTERN: Service Class Pattern
# - Represents a "service" (notification service)
# - Single instance created in main.py during initialization
# - Multiple methods for different notification purposes
#
# INSTANCE vs CLASS:
# - Instance attributes (self.url): Per-object state
# - Class attributes: Shared by all instances (not used here)
class BarkNotifier:
    """
    Bark Notifier Class - Encapsulates all Bark push notification logic.

    INSTANCE ATTRIBUTES:
    - bark_url: The full Bark API URL (from get_bark_push_url())
    - enabled: Boolean indicating if notifications are enabled

    CONSTRUCTOR FLOW (__init__):
    1. Get Bark URL from config.py:get_bark_push_url()
    2. Get enabled status from config.py:Config.get_bark_enabled()
    3. Print initialization status (informational)

    RELATED:
    - Created in: main.py:main() at startup
    - Used for: main.py:send_cleanup_report() and main.py:send_alert()
    """

    def __init__(self):
        """
        Initialize the Bark notifier.

        WHAT THIS CODE DOES:
        1. Gets the Bark push URL from config.py helper function
           - This internally calls Config.get_bark_base_url()
           - Then appends "/push" endpoint
        2. Gets the enabled flag from Config class
           - Checks BARK_ENABLED environment variable
           - Defaults to True if not set
        3. Prints initialization info (for debugging)

        CONCEPT: Constructor/Initializer
        - __init__() is called when you create an instance: BarkNotifier()
        - It's used to set up the object's initial state
        - Python calls this automatically; you never call it directly

        EXAMPLE:
            notifier = BarkNotifier()  # Calls __init__()

        RELATED:
        - get_bark_push_url(): Implemented in config.py
        - Config.get_bark_enabled(): Class method in config.py
        """
        # Get full Bark API URL from config.py helper
        self.bark_url = get_bark_push_url()
        
        # Get enabled status from config.py class
        self.enabled = Config.get_bark_enabled()
        
        # Print initialization status
        print(f"Bark notifier initialized")
        print(f"   URL: {self.bark_url}")
        print(f"   Enabled: {'Yes' if self.enabled else 'No'}")

    # ==========================================================================
    # LOW-LEVEL NOTIFICATION METHOD
    # ==========================================================================
    def send_notification(
        self,
        title: str,
        body: str,
        level: str = "active",
        icon: str = "https://cdn-icons-png.flaticon.com/512/2907/2907253.png"
    ) -> bool:
        """
        Send a Bark push notification (low-level method).

        CONCEPT: HTTP POST Request
        - POST method sends data to the server
        - JSON body contains: title, body, icon, level, isarchive
        - Server responds with 200 (success) or error code

        NOTIFICATION URGENCY LEVELS:
        - passive: Silent notification, no sound, no badge update
        - active: Normal notification with sound
        - timeSensitive: High priority, repeated reminders
        - critical: Highest priority, breaks through Do Not Disturb

        BARK API FIELDS:
        - title: Notification headline
        - body: Main notification text
        - icon: URL to custom icon image
        - level: Urgency level (passive/active/timeSensitive/critical)
        - isarchive: Whether to save to history (1=yes, 0=no)
        - url: Link to open when notification is tapped (optional)

        WHAT THIS CODE DOES:
        1. Checks if notifications are enabled (skip if disabled)
        2. Constructs JSON payload with notification data
        3. Sends HTTP POST to Bark server
        4. Checks response status code
        5. Returns True on success, False on failure

        RELATED:
        - Called by: send_cleanup_report(), send_alert(), send_recovery_success()
        - HTTP library: requests.post() from requests module
        """
        # Early return if notifications disabled
        if not self.enabled:
            print(f"⚠️ Notification disabled, skipping")
            return False

        try:
            # Construct the JSON payload
            # json= parameter automatically sets Content-Type header
            payload = {
                "title": title,
                "body": body,
                "icon": icon,
                "level": level,
                "isarchive": 1  # Save to notification history
            }

            # Send HTTP POST request
            # - url: The Bark API endpoint
            # - json=payload: Automatically JSON-encode and set Content-Type
            # - timeout=10: Fail after 10 seconds (prevent hanging)
            response = requests.post(
                self.bark_url,
                json=payload,
                timeout=10  # 10 second timeout
            )

            # Check if request was successful
            # Bark API returns 200 on success
            if response.status_code == 200:
                print(f"✅ Notification sent: {title}")
                return True
            else:
                # Non-200 response indicates an error
                print(f"❌ Notification failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            # Catch any exception (network error, timeout, etc.)
            # This prevents the entire program from crashing
            print(f"❌ Notification error: {e}")
            return False

    # ==========================================================================
    # CLEANUP REPORT METHOD
    # ==========================================================================
    def send_cleanup_report(
        self,
        cleaned_count: int,
        failed_count: int,
        details: List[Dict]
    ) -> bool:
        """
        Send a cleanup completion report notification.

        PURPOSE:
        - Called at the end of each cleanup cycle
        - Summarizes what happened during this run
        - Includes counts of successful/failed cleanups

        PARAMETERS:
        - cleaned_count: Number of pods successfully restarted
        - failed_count: Number of pods that failed to restart
        - details: List of dicts with per-pod information

        REPORT FORMAT:
        - Title: "Pod Cleaner Report"
        - Body: Timestamp + Success/Failed counts + Failed pod details

        WHAT THIS CODE DOES:
        1. Generates current timestamp
        2. Builds summary string with counts
        3. If failures exist, lists failed pods (max 10)
        4. Calls send_notification() with constructed message

        RELATED:
        - Called by: main.py:main() in Step 4
        - Parameters come from: kube_client.py:restart_pods() return value
        """
        # Generate timestamp for the report
        # datetime.now() gets current time
        # strftime() formats it as string
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build the summary text
        summary = f"🧹 Pod Cleaner Report\n"
        summary += f"⏰ Time: {timestamp}\n"
        summary += f"✅ Success: {cleaned_count}\n"
        summary += f"❌ Failed: {failed_count}"

        # If there are failed pods, add details
        # Only show up to 10 to avoid overly long notifications
        if failed_count > 0:
            # Filter details to only failed pods
            failed_pods = [d for d in details if d["status"] == "failed"]
            
            # Format each failed pod as a line
            failed_details = "\n".join([
                f"  - {p['namespace']}/{p['name']}" for p in failed_pods[:10]
            ])
            
            # Add ellipsis if more than 10
            if len(failed_pods) > 10:
                failed_details += f"\n  ... and {len(failed_pods) - 10} more"
            
            # Append to summary
            summary += f"\n\nFailed Details:\n{failed_details}"

        # Send the notification
        # level="active" means normal notification with sound
        return self.send_notification(
            title=f"Pod Cleaner Report",
            body=summary,
            level="active"
        )

    # ==========================================================================
    # ALERT NOTIFICATION METHOD
    # ==========================================================================
    def send_alert(
        self,
        pod_name: str,
        namespace: str,
        phase: str,
        reason: str,
        message: str
    ) -> bool:
        """
        Send an anomaly alert notification (Bonus feature).

        PURPOSE:
        - Called when a pod remains unhealthy after restart attempt
        - Provides detailed diagnostic information
        - Urges manual intervention

        PARAMETERS:
        - pod_name: Name of the unhealthy pod
        - namespace: Namespace containing the pod
        - phase: Current pod phase (Running, Pending, Failed, etc.)
        - reason: Why the pod is unhealthy (CrashLoopBackOff, etc.)
        - message: Detailed status message from Kubernetes

        ALERT FORMAT:
        - Title: "🚨 Pod Alert: <pod-name>"
        - Body: Namespace, Phase, Reason, Details, Warning

        NOTIFICATION LEVEL:
        - level="timeSensitive" for higher urgency
        - This causes iOS to repeat reminders

        RELATED:
        - Called by: main.py:main() when recovery verification fails
        - Pod info comes from: kube_client.py:wait_for_pods_ready() return value
        """
        # Build the alert message body
        body = f"Namespace: {namespace}\n"
        body += f"Current State: {phase}\n"
        body += f"Reason: {reason}\n"
        body += f"Details: {message}\n\n"
        body += "⚠️ Manual inspection required"

        # Send with timeSensitive level (higher urgency)
        # Use warning icon URL
        return self.send_notification(
            title=f"🚨 Pod Alert: {pod_name}",
            body=body,
            level="timeSensitive",  # Higher urgency
            icon="https://cdn-icons-png.flaticon.com/512/564/564619.png"  # Warning icon
        )

    # ==========================================================================
    # RECOVERY SUCCESS NOTIFICATION METHOD
    # ==========================================================================
    def send_recovery_success(self, pod_name: str, namespace: str) -> bool:
        """
        Send a pod recovery success notification (optional feature).

        PURPOSE:
        - Notifies when a pod successfully recovered after restart
        - Lower urgency than alerts (passive notification)

        PARAMETERS:
        - pod_name: Name of the recovered pod
        - namespace: Namespace containing the pod

        NOTIFICATION LEVEL:
        - level="passive" for silent notification
        - No sound, no badge update
        - Just records in notification history

        RELATED:
        - Currently not used in main.py (reserved for future enhancement)
        """
        # Simple success message
        body = f"Pod {namespace}/{pod_name} has recovered"

        # Send with passive level (silent)
        return self.send_notification(
            title=f"✅ Pod Recovered",
            body=body,
            level="passive"  # Silent notification
        )
