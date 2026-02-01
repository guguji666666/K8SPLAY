# -*- coding: utf-8 -*-
"""
Notification Module
Encapsulates Bark push service

Features:
- Send cleanup completion notification
- Send anomaly alert notification
- Support multiple notification types (success, failure, alert)

About Bark:
- iOS push notification service
- Self-hosted deployment, privacy safe
- Support custom title, content, icon, etc.

API Format:
POST https://<your-bark-server-url>/<device-key>/push
Body: {"title": "Title", "body": "Content", "icon": "..."}
"""

import json
import requests
from datetime import datetime
from typing import List, Dict, Optional

# Import configuration module
from config import Config, get_bark_push_url


class BarkNotifier:
    """
    Bark Notifier Class
    Encapsulates all Bark push logic
    """

    def __init__(self):
        """
        Initialize notifier
        Get Bark URL from config (supports environment variables)
        """
        self.bark_url = get_bark_push_url()
        self.enabled = Config.get_bark_enabled()
        print(f"Bark notifier initialized")
        print(f"   URL: {self.bark_url}")
        print(f"   Enabled: {'Yes' if self.enabled else 'No'}")

    def send_notification(
        self,
        title: str,
        body: str,
        level: str = "active",
        icon: str = "https://cdn-icons-png.flaticon.com/512/2907/2907253.png"
    ) -> bool:
        """
        Send Bark push notification

        Parameters:
            title: str - Notification title
            body: str - Notification body
            level: str - Notification level (passive, active, timeSensitive, critical)
            icon: str - Notification icon URL

        Returns:
            bool - True if send successful, False if failed

        Notification Level Notes:
        - passive: Silent notification, no sound
        - active: Normal notification, with sound
        - timeSensitive: Time-sensitive notification, repeated reminders
        - critical: Urgent notification, repeated with high volume

        Bark API Parameters:
        - title: Notification title
        - body: Notification body
        - icon: Custom icon
        - level: Notification level
        - url: Link to open when notification is tapped
        """
        if not self.enabled:
            print(f"⚠️ Notification disabled, skipping")
            return False

        try:
            # Build request body
            payload = {
                "title": title,
                "body": body,
                "icon": icon,
                "level": level,
                "isarchive": 1  # Save to history
            }

            # Send POST request
            response = requests.post(
                self.bark_url,
                json=payload,
                timeout=10  # Timeout 10 seconds
            )

            # Check response
            if response.status_code == 200:
                print(f"✅ Notification sent: {title}")
                return True
            else:
                print(f"❌ Notification failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            # Handle network exception
            print(f"❌ Notification error: {e}")
            return False

    def send_cleanup_report(
        self,
        cleaned_count: int,
        failed_count: int,
        details: List[Dict]
    ) -> bool:
        """
        Send cleanup completion report (called at end of daily run)

        Parameters:
            cleaned_count: int - Number of successfully cleaned pods
            failed_count: int - Number of failed cleanups
            details: List[Dict] - Detailed pod list

        Returns:
            bool - Whether send was successful
        """
        # Build notification content
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Generate summary
        summary = f"🧹 Pod Cleaner Report\n"
        summary += f"⏰ Time: {timestamp}\n"
        summary += f"✅ Success: {cleaned_count}\n"
        summary += f"❌ Failed: {failed_count}"

        # If there are failed pods, add details
        if failed_count > 0:
            failed_pods = [d for d in details if d["status"] == "failed"]
            failed_details = "\n".join([
                f"  - {p['namespace']}/{p['name']}" for p in failed_pods[:10]
            ])
            if len(failed_pods) > 10:
                failed_details += f"\n  ... and {len(failed_pods) - 10} more"
            summary += f"\n\nFailed Details:\n{failed_details}"

        # Send notification
        return self.send_notification(
            title=f"Pod Cleaner Report",
            body=summary,
            level="active"
        )

    def send_alert(
        self,
        pod_name: str,
        namespace: str,
        phase: str,
        reason: str,
        message: str
    ) -> bool:
        """
        Send anomaly alert (Bonus feature)

        Sends alert when pod is still unhealthy after restart

        Parameters:
            pod_name: str - Pod name
            namespace: str - Namespace
            phase: str - Current status
            reason: str - Anomaly reason
            message: str - Status message

        Returns:
            bool - Whether send was successful
        """
        # Build alert content
        body = f"Namespace: {namespace}\n"
        body += f"Current State: {phase}\n"
        body += f"Reason: {reason}\n"
        body += f"Details: {message}\n\n"
        body += "⚠️ Manual inspection required"

        return self.send_notification(
            title=f"🚨 Pod Alert: {pod_name}",
            body=body,
            level="timeSensitive",  # Time-sensitive notification
            icon="https://cdn-icons-png.flaticon.com/512/564/564619.png"  # Warning icon
        )

    def send_recovery_success(self, pod_name: str, namespace: str) -> bool:
        """
        Send pod recovery success notification (optional feature)

        Parameters:
            pod_name: str - Pod name
            namespace: str - Namespace

        Returns:
            bool - Whether send was successful
        """
        body = f"Pod {namespace}/{pod_name} has recovered"

        return self.send_notification(
            title=f"✅ Pod Recovered",
            body=body,
            level="passive"  # Silent notification
        )
