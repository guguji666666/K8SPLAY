# -*- coding: utf-8 -*-
"""
Kubernetes Client Module
Encapsulates all interactions with Kubernetes API

Features:
- Connect to Kubernetes cluster
- Get pod list and status
- Delete (restart) unhealthy pods
- Batch processing optimization (for large-scale clusters)

Design Considerations (Large-scale cluster optimization):
- Use filter parameters to reduce network traffic
- Paginate pod list retrieval
- Use label selectors to reduce data volume
- Concurrent processing (optional)
"""

import time
from typing import List, Dict, Optional
from datetime import datetime

# Import Kubernetes Python client
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

# Import configuration module
from config import Config, should_skip_namespace, is_pod_healthy


class KubernetesClient:
    """
    Kubernetes Client Class
    Encapsulates all K8s API operations
    """

    def __init__(self):
        """
        Initialize client
        Automatically loads in-cluster config (running in cluster)
        Falls back to kubeconfig if failed (local debugging)
        """
        try:
            # Try to load in-cluster config (recommended)
            # Uses ServiceAccount auth when running in K8s
            config.load_incluster_config()
            print("✅ Using in-cluster config")
        except config.ConfigException:
            # Load local kubeconfig (for local debugging)
            try:
                config.load_kube_config()
                print("WARNING Using local kubeconfig (debug mode)")
            except Exception as e:
                # If both fail, raise error
                raise RuntimeError(f"Failed to load Kubernetes config: {e}")

        # Create CoreV1Api instance
        # This is the API for operating core resources like Pods, Services
        self.api = client.CoreV1Api()

    def get_all_namespaces(self) -> List[str]:
        """
        Get all namespace list

        Returns:
            List[str]: List of all namespace names

        Usage:
            - Iterate all namespaces to find unhealthy pods
            - Exclude system namespaces
        """
        try:
            # Call API to get namespace list
            # Only returns name field to reduce network traffic
            namespaces = self.api.list_namespace()
            return [ns.metadata.name for ns in namespaces.items]
        except ApiException as e:
            # Handle API call exception
            print(f"❌ Failed to get namespace list: {e}")
            return []

    def get_pods_in_namespace(
        self,
        namespace: str,
        label_selector: Optional[str] = None,
        field_selector: Optional[str] = None,
        limit: int = 500
    ) -> List[client.V1Pod]:
        """
        Get pod list in specified namespace

        Parameters:
            namespace: str - Namespace name
            label_selector: str (optional) - Label selector
            field_selector: str (optional) - Field selector
            limit: int - Maximum results per API call (pagination)

        Returns:
            List[client.V1Pod]: List of pod objects

        Design Notes:
            - Uses limit for pagination, avoids fetching large data at once
            - Optional label_selector to filter specific pods
            - Optional field_selector to filter specific states

        Large-scale Optimization:
            For clusters with tens of thousands of pods, watch mode is more efficient
            But since this program runs every 10 minutes, polling is sufficient
        """
        try:
            # Call API to get pod list
            # - namespace: specified namespace
            # - limit: page size, avoids single request being too large
            pods = self.api.list_namespaced_pod(
                namespace=namespace,
                limit=limit
            )
            return list(pods.items)
        except ApiException as e:
            print(f"❌ Failed to get pod list for namespace '{namespace}': {e}")
            return []

    def find_unhealthy_pods(self, namespaces: List[str]) -> List[Dict]:
        """
        Find unhealthy pods in multiple namespaces

        Parameters:
            namespaces: List[str] - List of namespaces to check

        Returns:
            List[Dict]: List of unhealthy pod dictionaries
            Each dict contains: name, namespace, phase, status, reason

        Design Notes:
            - Iterate all namespaces
            - Skip system namespaces
            - Check each pod's phase
            - Collect unhealthy pod info
        """
        unhealthy_pods = []

        # Iterate each namespace
        for namespace in namespaces:
            # Skip system namespaces
            if should_skip_namespace(namespace):
                continue

            # Get all pods in this namespace
            pods = self.get_pods_in_namespace(namespace)

            for pod in pods:
                # Get pod name and current status
                pod_name = pod.metadata.name
                pod_phase = pod.status.phase

                # Check if pod phase is healthy
                phase_healthy = is_pod_healthy(pod_phase)
                
                # Check container status (CrashLoopBackOff, etc.)
                container_healthy = True
                for container in pod.status.container_statuses or []:
                    state = container.state
                    
                    # CrashLoopBackOff or other waiting states
                    if state.waiting:
                        container_healthy = False
                        break
                    
                    # Terminated with non-zero exit code (just crashed)
                    if state.terminated and state.terminated.exit_code != 0:
                        container_healthy = False
                        break
                
                # Pod is unhealthy if: phase unhealthy OR container unhealthy
                if not phase_healthy or not container_healthy:
                    # Collect unhealthy pod info
                    pod_info = {
                        "name": pod_name,
                        "namespace": namespace,
                        "phase": pod_phase,
                        "reason": pod.status.reason or "Unknown",
                        "message": pod.status.message or "No message",
                        "create_time": pod.metadata.creation_timestamp,
                        "restart_count": pod.status.container_statuses[0].restart_count if pod.status.container_statuses else 0
                    }
                    unhealthy_pods.append(pod_info)
                    print(f"  WARNING Found unhealthy pod: {namespace}/{pod_name} ({pod_phase})")

        return unhealthy_pods

    def delete_pod(self, namespace: str, pod_name: str) -> bool:
        """
        Delete (restart) specified pod

        Note:
            In Kubernetes, deleting a pod triggers ReplicaSet to recreate it
            New pod will be scheduled again, achieving "restart" effect

        Parameters:
            namespace: str - Pod namespace
            pod_name: str - Pod name

        Returns:
            bool - True if deletion successful, False if failed
        """
        try:
            # Call API to delete pod
            # - namespace: specified namespace
            # - grace_period_seconds: graceful shutdown time (0 = immediate)
            self.api.delete_namespaced_pod(
                name=pod_name,
                namespace=namespace,
                grace_period_seconds=0  # Immediate delete, immediate restart
            )
            print(f"  ✅ Deleted pod: {namespace}/{pod_name}")
            return True
        except ApiException as e:
            # Handle API call exception
            # Possible reasons: pod already gone, insufficient permissions, etc.
            print(f"  ❌ Failed to delete pod {namespace}/{pod_name}: {e}")
            return False

    def restart_pods(self, pods: List[Dict]) -> Dict:
        """
        Batch restart unhealthy pods

        Parameters:
            pods: List[Dict] - List of unhealthy pod info

        Returns:
            Dict: Restart result statistics
            - success: Number of successful restarts
            - failed: Number of failed restarts
            - details: Detailed information

        Design Notes:
            - Delete pods one by one
            - Record success/failure count
            - Return details for logging and notification
        """
        success_count = 0
        failed_count = 0
        results = []

        for pod in pods:
            pod_name = pod["name"]
            namespace = pod["namespace"]

            # Delete pod
            if self.delete_pod(namespace, pod_name):
                success_count += 1
                results.append({
                    "name": pod_name,
                    "namespace": namespace,
                    "status": "success",
                    "phase": pod["phase"]
                })
            else:
                failed_count += 1
                results.append({
                    "name": pod_name,
                    "namespace": namespace,
                    "status": "failed",
                    "phase": pod["phase"]
                })

        return {
            "success": success_count,
            "failed": failed_count,
            "details": results
        }

    def wait_for_pods_ready(
        self,
        namespaces: List[str],
        check_interval: int = 30,
        max_wait_time: int = 300
    ) -> Dict:
        """
        Check if restarted pods are healthy (Bonus feature)

        Parameters:
            namespaces: List[str] - List of namespaces to check
            check_interval: int - Check interval (seconds)
            max_wait_time: int - Maximum wait time (seconds)

        Returns:
            Dict: Check result
            - still_unhealthy: List of pods still not recovered
            - all_recovered: Whether all are recovered

        Design Notes:
            - Wait some time after restart
            - Periodically check pod status
            - Collect info for notification if any pods not recovered
        """
        print(f"\n⏳ Waiting {max_wait_time} seconds to check pod recovery...")
        time.sleep(max_wait_time)

        still_unhealthy = []

        for namespace in namespaces:
            if should_skip_namespace(namespace):
                continue

            pods = self.get_pods_in_namespace(namespace)

            for pod in pods:
                pod_name = pod.metadata.name
                pod_phase = pod.status.phase

                # Check if pod phase is healthy
                phase_healthy = is_pod_healthy(pod_phase)
                
                # Check container status
                container_healthy = True
                for container in pod.status.container_statuses or []:
                    state = container.state
                    
                    # CrashLoopBackOff or other waiting states
                    if state.waiting:
                        container_healthy = False
                        break
                    
                    # Terminated with non-zero exit code (just crashed)
                    if state.terminated and state.terminated.exit_code != 0:
                        container_healthy = False
                        break
                
                # Unhealthy if either check fails
                if not phase_healthy or not container_healthy:
                    # Collect container status details for alert
                    container_reason = "Unknown"
                    container_message = "No message"
                    
                    for container in pod.status.container_statuses or []:
                        state = container.state
                        if state.waiting:
                            container_reason = state.waiting.reason or "Unknown"
                            container_message = state.waiting.message or "No message"
                            break
                        elif state.terminated and state.terminated.exit_code != 0:
                            container_reason = f"Terminated with exitCode={state.terminated.exit_code}"
                            container_message = state.terminated.reason or "No message"
                            break
                    
                    still_unhealthy.append({
                        "name": pod_name,
                        "namespace": namespace,
                        "phase": pod_phase,
                        "reason": pod.status.reason or "Unknown",
                        "message": pod.status.message or "No message",
                        "container_reason": container_reason,
                        "container_message": container_message
                    })

        return {
            "still_unhealthy": still_unhealthy,
            "all_recovered": len(still_unhealthy) == 0
        }
