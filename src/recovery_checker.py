# -*- coding: utf-8 -*-
"""
Recovery Checker Module
Verifies pod recovery after restart

Features:
- Wait for new pod creation after deletion
- Check new pod health status
- Detect persistent issues
- Trigger escalation when needed
"""

import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from kube_client import KubernetesClient
from persistence_store import PersistenceStore
from config import Config


class RecoveryChecker:
    """
    Recovery Checker Class
    Monitors pod recovery after automatic restart
    """

    def __init__(
        self,
        kube_client: KubernetesClient,
        store: PersistenceStore,
        config: Config = None
    ):
        """
        Initialize recovery checker

        Parameters:
            kube_client: KubernetesClient - K8s client
            store: PersistenceStore - State persistence store
            config: Config - Configuration (optional)
        """
        self.kube_client = kube_client
        self.store = store
        self.config = config or Config

        # Recovery configuration
        self.wait_seconds = getattr(Config, 'RECOVERY_WAIT_SECONDS', 120)
        self.max_attempts = getattr(Config, 'RECOVERY_MAX_ATTEMPTS', 3)
        self.check_interval = getattr(Config, 'RECOVERY_CHECK_INTERVAL', 10)

        print(f"🔍 Recovery Checker initialized")
        print(f"   Wait time: {self.wait_seconds}s")
        print(f"   Max attempts: {self.max_attempts}")
        print(f"   Check interval: {self.check_interval}s")

    def find_new_pod(
        self,
        namespace: str,
        pod_name_prefix: str,
        timeout_seconds: int = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find newly created pod after deletion

        Parameters:
            namespace: str - Namespace
            pod_name_prefix: str - Pod name prefix (without random suffix)
            timeout_seconds: int - Timeout in seconds

        Returns:
            Optional[Dict[str, Any]] - New pod info or None
        """
        timeout = timeout_seconds or self.wait_seconds
        start_time = time.time()

        print(f"   ⏳ Waiting for new pod creation ({pod_name_prefix}*)...")

        while time.time() - start_time < timeout:
            # Get all pods in namespace
            pods = self.kube_client.get_pods_in_namespace(namespace)

            # Find matching pod
            for pod in pods:
                if pod['name'].startswith(pod_name_prefix):
                    print(f"   ✅ Found new pod: {pod['name']}")
                    return pod

            # Wait before next check
            time.sleep(self.check_interval)

        print(f"   ⚠️ Timeout waiting for new pod")
        return None

    def check_pod_health(self, pod: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Check if a pod is healthy

        Parameters:
            pod: Dict[str, Any] - Pod info

        Returns:
            Tuple[bool, str, str] - (is_healthy, reason, message)
        """
        phase = pod.get('phase', 'Unknown')

        # Check terminal phases first
        if phase == 'Succeeded':
            return True, 'Succeeded', 'Pod completed successfully'

        if phase == 'Failed':
            return False, 'Failed', 'Pod failed'

        if phase == 'Unknown':
            return False, 'Unknown', 'Unknown pod status'

        if phase == 'Pending':
            return False, 'Pending', 'Pod is still scheduling'

        # For Running pods, check container status in detail
        if phase == 'Running':
            container_statuses = pod.get('container_statuses', [])
            if container_statuses:
                for status in container_statuses:
                    state = status.get('state', {})

                    # Check for waiting state (CrashLoopBackOff, ImagePullBackOff, etc.)
                    if 'waiting' in state:
                        wait_reason = state['waiting'].get('reason', 'Unknown')
                        wait_message = state['waiting'].get('message', 'No message')
                        return False, wait_reason, wait_message

                    # Check for terminated state with error
                    if 'terminated' in state:
                        term = state['terminated']
                        if term.get('exit_code', 0) != 0:
                            return False, 'Terminated', f"Exit code: {term.get('exit_code')}"

            return True, 'Running', 'Pod is healthy'

        return True, phase, 'Pod appears healthy'

    def verify_recovery(
        self,
        pod_uid: str,
        tracking_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verify recovery for a tracked pod

        Parameters:
            pod_uid: str - Pod UID
            tracking_info: Dict[str, Any] - Tracking information

        Returns:
            Dict[str, Any] - Verification result
        """
        namespace = tracking_info['namespace']
        pod_name = tracking_info['name']
        reason = tracking_info['reason']

        print(f"\n🔍 Verifying recovery for {namespace}/{pod_name}...")

        # Extract pod name prefix (remove random suffix)
        # Kubernetes pod names from deployments usually have format: <deployment>-<random>
        pod_name_prefix = '-'.join(pod_name.split('-')[:-1]) if '-' in pod_name else pod_name

        # Wait for new pod
        new_pod = self.find_new_pod(namespace, pod_name_prefix)

        if not new_pod:
            return {
                'success': False,
                'recovered': False,
                'reason': 'New pod not found',
                'message': f'Timeout waiting for new pod after {self.wait_seconds}s',
                'persistent_issue': False
            }

        # Check new pod health
        is_healthy, health_reason, health_message = self.check_pod_health(new_pod)

        if is_healthy:
            print(f"   ✅ Pod recovered successfully: {new_pod['name']}")
            return {
                'success': True,
                'recovered': True,
                'new_pod_name': new_pod['name'],
                'reason': health_reason,
                'message': health_message,
                'persistent_issue': False
            }
        else:
            # Check if this is a persistent issue
            attempt = tracking_info.get('attempt', 1)
            is_persistent = attempt >= self.max_attempts

            print(f"   ⚠️ New pod still unhealthy: {health_reason}")
            print(f"   Attempt: {attempt}/{self.max_attempts}")

            return {
                'success': True,
                'recovered': False,
                'new_pod_name': new_pod['name'],
                'reason': health_reason,
                'message': health_message,
                'attempt': attempt,
                'max_attempts': self.max_attempts,
                'persistent_issue': is_persistent
            }

    def verify_all_tracked(self) -> Dict[str, Any]:
        """
        Verify recovery for all tracked pods

        Returns:
            Dict[str, Any] - Summary of verification results
        """
        tracked = self.store.get_all_tracked()

        if not tracked:
            return {
                'total': 0,
                'recovered': 0,
                'still_unhealthy': 0,
                'persistent_issues': 0,
                'results': []
            }

        results = []
        recovered_count = 0
        unhealthy_count = 0
        persistent_count = 0

        for uid, tracking_info in tracked.items():
            result = self.verify_recovery(uid, tracking_info)
            result['uid'] = uid
            result['tracking_info'] = tracking_info
            results.append(result)

            if result['recovered']:
                recovered_count += 1
                self.store.remove_tracking(uid)
            elif result.get('persistent_issue'):
                persistent_count += 1
                unhealthy_count += 1
            else:
                unhealthy_count += 1

        # Cleanup old entries
        self.store.cleanup_old_entries()

        summary = {
            'total': len(tracked),
            'recovered': recovered_count,
            'still_unhealthy': unhealthy_count,
            'persistent_issues': persistent_count,
            'results': results
        }

        print(f"\n📊 Recovery Verification Summary:")
        print(f"   Total tracked: {summary['total']}")
        print(f"   Recovered: {summary['recovered']}")
        print(f"   Still unhealthy: {summary['still_unhealthy']}")
        print(f"   Persistent issues: {summary['persistent_issues']}")

        return summary

    def is_persistent_issue(self, pod_uid: str) -> bool:
        """
        Check if a pod has a persistent issue

        Parameters:
            pod_uid: str - Pod UID

        Returns:
            bool - True if persistent issue
        """
        tracking = self.store.get_tracking(pod_uid)
        if not tracking:
            return False
        return tracking.get('attempt', 0) >= self.max_attempts

    def get_escalation_info(self, pod_uid: str) -> Optional[Dict[str, Any]]:
        """
        Get escalation information for a persistent issue

        Parameters:
            pod_uid: str - Pod UID

        Returns:
            Optional[Dict[str, Any]] - Escalation info or None
        """
        tracking = self.store.get_tracking(pod_uid)
        if not tracking:
            return None

        return {
            'uid': pod_uid,
            'name': tracking['name'],
            'namespace': tracking['namespace'],
            'attempt': tracking.get('attempt', 1),
            'reason': tracking['reason'],
            'first_deleted_at': tracking['deleted_at'],
            'history': tracking.get('history', [])
        }
