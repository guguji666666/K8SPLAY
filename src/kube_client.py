# -*- coding: utf-8 -*-
# =============================================================================
# Kubernetes Client Module - K8s API Operations
# =============================================================================
# This module encapsulates all interactions with the Kubernetes API.
#
# FEATURES:
# - Connect to Kubernetes cluster (in-cluster or local kubeconfig)
# - Get namespace list and pod lists
# - Detect unhealthy pods
# - Delete (restart) unhealthy pods
# - Verify pod recovery after restart (with polling)
#
# FILE STRUCTURE:
# - KubernetesClient CLASS: Main class for all K8s operations
#   - __init__(): Initialize API client
#   - get_all_namespaces(): List all namespaces
#   - get_pods_in_namespace(): List pods with pagination support
#   - find_unhealthy_pods(): Detect pods needing restart
#   - delete_pod(): Delete a single pod
#   - restart_pods(): Batch restart multiple pods
#   - wait_for_pods_ready(): Verify recovery with polling
#
# RELATED FILES:
# - config.py: Imports should_skip_namespace(), is_pod_healthy(), Config
# - main.py: Imports KubernetesClient, calls all methods
# =============================================================================

# -----------------------------------------------------------------------------
# STANDARD LIBRARY IMPORTS
# -----------------------------------------------------------------------------
# 'time' module: Time-related functions
# - time.time(): Get current timestamp (for elapsed time calculation)
# - time.sleep(): Pause execution (for polling intervals)
import time

# 'datetime' module: Date/time handling
# - datetime.now(): Get current date/time
# Used for logging timestamps
from datetime import datetime

# 'typing' module: Type hints
# - List[T]: List of type T
# - Optional[T]: T or None
from typing import List, Dict, Optional


# -----------------------------------------------------------------------------
# KUBERNETES CLIENT IMPORTS
# -----------------------------------------------------------------------------
# Official Kubernetes Python client library
# INSTALL: pip install kubernetes
#
# MODULES USED:
# - client: Contains API client classes (CoreV1Api, AppsV1Api, etc.)
# - config: Contains config loading functions
#
# WHY USE THE OFFICIAL CLIENT?
# - Handles all API versioning and serialization
# - Provides type-safe objects (V1Pod, V1Namespace, etc.)
# - Automatically handles authentication
from kubernetes import client, config

# Exception handling for K8s API errors
# ApiException is raised when API calls fail
from kubernetes.client.exceptions import ApiException


# -----------------------------------------------------------------------------
# LOCAL IMPORTS
# -----------------------------------------------------------------------------
# Import from sibling module (config.py)
# These provide:
# - Config: Class with EXCLUDED_NAMESPACES, HEALTHY_POD_PHASES
# - should_skip_namespace(): Function to check if ns should be skipped
# - is_pod_healthy(): Function to check if pod phase is healthy
from config import Config, should_skip_namespace, is_pod_healthy


# =============================================================================
# KubernetesClient CLASS - All K8s Operations
# =============================================================================
# CONCEPT: Why a dedicated client class?
# - Encapsulates Kubernetes API complexity
# - Provides clean interface for the main program
# - Handles connection configuration (in-cluster vs local)
#
# DESIGN PATTERN: Repository Pattern
# - Provides abstraction over data source (K8s API)
# - Main program doesn't need to know API details
# - Easy to test with mock objects
#
# API CLIENT SELECTION:
# - CoreV1Api: Handles core resources (Pods, Services, Namespaces, etc.)
# - AppsV1Api: Handles Deployment, StatefulSet, ReplicaSet
# - We only need CoreV1Api for pod operations
class KubernetesClient:
    """
    Kubernetes Client Class - Encapsulates all Kubernetes API operations.

    INSTANCE ATTRIBUTES:
    - api: CoreV1Api instance for making API calls
         (created in __init__ after successful config load)

    INITIALIZATION FLOW:
    1. Try in-cluster config (ServiceAccount mounted in K8s pod)
    2. If that fails (not running in K8s), try local kubeconfig
    3. If both fail, raise RuntimeError

    AUTHENTICATION METHODS:
    - In-cluster: Uses ServiceAccount token mounted at
      /var/run/secrets/kubernetes.io/serviceaccount/
    - Local: Uses ~/.kube/config file

    RELATED:
    - Created in: main.py:main() during startup
    - Used throughout: main.py for all K8s operations
    """

    def __init__(self):
        """
        Initialize the Kubernetes client.

        CONCEPT: Dual Configuration Loading
        - This class tries two configuration sources
        - In-cluster first (preferred for production)
        - Local kubeconfig fallback (for development/testing)

        CONFIGURATION LOADING:
        1. config.load_incluster_config():
           - Automatically discovers cluster when running in K8s
           - Uses ServiceAccount credentials
           - Works in any K8s deployment

        2. config.load_kube_config():
           - Loads kubectl's configuration file
           - Typically at ~/.kube/config
           - Used for local development

        WHAT THIS CODE DOES:
        1. Try to load in-cluster config (preferred)
        2. If ConfigException (not in cluster), try local kubeconfig
        3. If both fail, raise RuntimeError with error message
        4. Create CoreV1Api client for API calls

        ERROR HANDLING:
        - ConfigException: Not running in Kubernetes
        - Exception: General config loading error

        EXAMPLE:
            # In Kubernetes pod:
            # Uses ServiceAccount credentials automatically
            kube_client = KubernetesClient()
            # Output: "✅ Using in-cluster config"

            # Local development:
            # Uses ~/.kube/config
            kube_client = KubernetesClient()
            # Output: "WARNING Using local kubeconfig (debug mode)"
        """
        try:
            # Attempt to load in-cluster configuration
            # This works when running inside a Kubernetes cluster
            # Uses ServiceAccount mounted at standard path
            config.load_incluster_config()
            print("✅ Using in-cluster config")

        except config.ConfigException:
            # ConfigException means we're not running in Kubernetes
            # Fall back to local kubeconfig for development
            try:
                config.load_kube_config()
                print("WARNING Using local kubeconfig (debug mode)")

            except Exception as e:
                # If both methods fail, raise an error
                # This prevents the program from running without K8s access
                raise RuntimeError(f"Failed to load Kubernetes config: {e}")

        # Create the CoreV1Api client
        # This is the primary API for interacting with core K8s resources
        # - Pods, Services, Endpoints, Namespaces, etc.
        self.api = client.CoreV1Api()

    # ==========================================================================
    # NAMESPACE OPERATIONS
    # ==========================================================================
    def get_all_namespaces(self) -> List[str]:
        """
        Get a list of all namespace names in the cluster.

        CONCEPT: What is a Namespace?
        - Namespaces provide a way to divide cluster resources
        - They act like virtual clusters within the physical cluster
        - Resources in different namespaces can have the same name

        WHAT THIS CODE DOES:
        1. Calls list_namespace() API to get all namespaces
        2. Extracts just the names from metadata
        3. Returns list of namespace name strings

        API CALL:
        - Method: list_namespace()
        - Returns: V1NamespaceList object with items array
        - Each item has metadata.name with the namespace name

        ERROR HANDLING:
        - ApiException: API call failed (permissions, network, etc.)
        - Returns empty list on error (fails gracefully)

        EXAMPLE RETURN VALUE:
            ["default", "kube-system", "kube-public", "my-app", "production"]

        RELATED:
        - Called by: main.py:main() in Step 1
        - Used in: find_unhealthy_pods() to iterate all namespaces
        """
        try:
            # Call Kubernetes API to list all namespaces
            namespaces = self.api.list_namespace()

            # Extract just the names using list comprehension
            # [ns.metadata.name for ns in namespaces.items]
            # This iterates over each namespace object and gets its name
            return [ns.metadata.name for ns in namespaces.items]

        except ApiException as e:
            # Log the error and return empty list
            # This allows the program to continue with fewer namespaces
            print(f"❌ Failed to get namespace list: {e}")
            return []

    # ==========================================================================
    # POD LISTING WITH PAGINATION
    # ==========================================================================
    def get_pods_in_namespace(
        self,
        namespace: str,
        label_selector: Optional[str] = None,
        field_selector: Optional[str] = None,
        limit: int = 500,
    ) -> List[client.V1Pod]:
        """
        Get all pods in a namespace with proper pagination.

        CONCEPT: Why Pagination?
        - Kubernetes API limits response size
        - limit=500 means "max 500 items per request"
        - If more items exist, API returns a "continue token"
        - You must use this token to get the next page

        PAGINATION MECHANISM:
        - First request: _continue=None
        - API returns: items + _continue token (if more data)
        - Next request: _continue=<token from previous response>
        - Repeat until _continue is None/empty

        PARAMETERS:
        - namespace: Which namespace to query (required)
        - label_selector: Filter by labels (e.g., "app=nginx")
        - field_selector: Filter by fields (e.g., "status.phase=Running")
        - limit: Max items per API request (default 500)

        WHAT THIS CODE DOES:
        1. Initialize empty list to collect all pods
        2. Initialize continue_token to None
        3. Loop: Call API with current token
        4. Add returned pods to collection
        5. Update token from response metadata
        6. Exit loop when token is empty (no more pages)
        7. Return complete list

        API CALL:
        - Method: list_namespaced_pod(namespace=..., limit=..., _continue=...)
        - Returns: V1PodList with items array and metadata._continue

        EXAMPLE:
            # Small namespace (< 500 pods):
            # One API call returns all pods

            # Large namespace (1500 pods):
            # API call 1: Returns 500 pods + _continue="token123"
            # API call 2: Returns 500 pods + _continue="token456"
            # API call 3: Returns 500 pods + _continue=None
            # Total: 3 calls, 1500 pods

        PERFORMANCE NOTE:
        - Pagination prevents timeout on large namespaces
        - Each API call has a size limit, not just count limit
        - Total time is similar but success rate is higher

        RELATED:
        - Called by: find_unhealthy_pods(), wait_for_pods_ready()
        """
        # Initialize collection for all pods
        all_pods: List[client.V1Pod] = []

        # Pagination cursor
        # None means "first page"
        continue_token: Optional[str] = None

        # Pagination loop
        while True:
            try:
                # Make API call with pagination
                # Parameters explained:
                # - namespace: Which namespace to query
                # - label_selector: Filter by labels (optional)
                # - field_selector: Filter by fields (optional)
                # - limit: Items per page (500 is K8s default max)
                # - _continue: Token from previous response (None for first)
                resp = self.api.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=label_selector,
                    field_selector=field_selector,
                    limit=limit,
                    _continue=continue_token,
                )

                # Add this page's pods to collection
                # resp.items contains the pods for this page
                all_pods.extend(resp.items)

                # Get continue token for next page
                # resp.metadata._continue is a string or None
                # getattr() safely handles missing attribute
                continue_token = getattr(resp.metadata, "_continue", None)

                # Check if more pages exist
                # Empty string or None means this was the last page
                if not continue_token:
                    # No more data, exit loop
                    break
                # Otherwise, loop continues to fetch next page

            except ApiException as e:
                # API call failed (RBAC, network, etc.)
                # Log error and break to avoid infinite retry
                print(f"❌ Failed to get pod list for namespace '{namespace}': {e}")
                break

        # Return complete list of all pods
        return all_pods

    # ==========================================================================
    # UNHEALTHY POD DETECTION
    # ==========================================================================
    def find_unhealthy_pods(self, namespaces: List[str]) -> List[Dict]:
        """
        Find all pods that need to be restarted.

        CONCEPT: What makes a pod "unhealthy"?
        1. Pod phase is not healthy:
           - Not Running, Init, or Succeeded
           - e.g., Pending, Failed, Unknown

        2. Container is in bad state:
           - waiting state (CrashLoopBackOff, ImagePullBackOff)
           - terminated with non-zero exit code

        CONCEPT: Why check both phase AND container?
        - Pod phase can be Running even if containers are crashed
        - Kubernetes only marks phase Failed if ALL containers exit non-zero
        - CrashLoopBackOff keeps phase Running but container is not working

        WHAT THIS CODE DOES:
        1. Iterate over all namespaces
        2. Skip excluded namespaces (kube-system)
        3. Get all pods in each namespace
        4. For each pod:
           a. Check if phase is healthy
           b. Check each container's state
           c. If either check fails, add to unhealthy list
        5. Return list of unhealthy pods with details

        RETURN VALUE STRUCTURE:
            [
                {
                    "name": "my-app-pod-abc123",
                    "namespace": "production",
                    "phase": "Running",
                    "reason": "CrashLoopBackOff",
                    "message": "Back-off 5m0s restarting...",
                    "create_time": "2026-02-08T10:00:00Z",
                    "restart_count": 5
                },
                ...
            ]

        RELATED:
        - Called by: main.py:main() in Step 2
        - Helper functions: should_skip_namespace(), is_pod_healthy()
        - Output used by: restart_pods() to restart identified pods
        """
        # Initialize empty list for unhealthy pods
        unhealthy_pods = []

        # Iterate over all namespaces
        for namespace in namespaces:
            # Skip excluded namespaces
            if should_skip_namespace(namespace):
                continue

            # Get all pods in this namespace
            # This returns list of V1Pod objects
            pods = self.get_pods_in_namespace(namespace)

            # Check each pod
            for pod in pods:
                # Extract basic info from pod metadata
                pod_name = pod.metadata.name
                pod_phase = pod.status.phase

                # Step 1: Check if phase is healthy
                # Uses config.py:is_pod_healthy() function
                # Returns True for Running, Init, Succeeded
                phase_healthy = is_pod_healthy(pod_phase)

                # Step 2: Check each container's state
                # Assume healthy until proven otherwise
                container_healthy = True

                # Iterate over container statuses
                # pod.status.container_statuses is list or None
                for container in pod.status.container_statuses or []:
                    # Get container's current state
                    state = container.state

                    # Check for waiting state (bad)
                    # waiting means container is not running
                    # Common reasons: CrashLoopBackOff, ImagePullBackOff
                    if state.waiting:
                        container_healthy = False
                        break  # No need to check more containers

                    # Check for terminated state (bad if exit code != 0)
                    # terminated means container finished execution
                    if state.terminated and state.terminated.exit_code != 0:
                        container_healthy = False
                        break

                # Step 3: Determine if pod is unhealthy
                # Pod is unhealthy if phase is bad OR container is bad
                # This catches Running pods with CrashLoopBackOff containers
                if not phase_healthy or not container_healthy:
                    # Collect detailed information about unhealthy pod
                    pod_info = {
                        "name": pod_name,
                        "namespace": namespace,
                        "phase": pod_phase,
                        "reason": pod.status.reason or "Unknown",
                        "message": pod.status.message or "No message",
                        "create_time": pod.metadata.creation_timestamp,
                        "restart_count": pod.status.container_statuses[0].restart_count
                        if pod.status.container_statuses
                        else 0,
                    }

                    # Add to unhealthy list
                    unhealthy_pods.append(pod_info)

                    # Log the finding
                    print(
                        f"  WARNING Found unhealthy pod: {namespace}/{pod_name} ({pod_phase})"
                    )

        # Return list of all unhealthy pods
        return unhealthy_pods

    # ==========================================================================
    # POD DELETION (RESTART)
    # ==========================================================================
    def delete_pod(self, namespace: str, pod_name: str) -> bool:
        """
        Delete a single pod (triggering restart via ReplicaSet).

        CONCEPT: Why delete to restart?
        - Kubernetes pods are ephemeral
        - They are managed by higher-level controllers
        - Controllers (Deployment, ReplicaSet) maintain desired state
        - Deleting a pod causes controller to create replacement
        - Replacement pod gets new resources (restart effect)

        CONCEPT: Grace Period (grace_period_seconds)
        - When deleting a pod, you can specify shutdown time
        - 0 means immediate kill (SIGKILL)
        - Default (30s) allows graceful shutdown (SIGTERM)
        - We use 0 for fast restart (pod-cleaner logic)

        WHAT THIS CODE DOES:
        1. Call delete_namespaced_pod() API
        2. Pass namespace and pod name
        3. Set grace_period_seconds=0 for immediate restart
        4. Return True on success, False on failure

        API CALL:
        - Method: delete_namespaced_pod(name=..., namespace=..., grace_period_seconds=...)
        - Returns: V1Status object with operation result

        ERROR HANDLING:
        - ApiException with status 404: Pod already gone (success for our purpose)
        - ApiException with status 403: Permission denied
        - Other exceptions: Log and return False

        EXAMPLE:
            # Pod "my-app-abc123" in namespace "production"
            delete_pod("production", "my-app-abc123")
            # Output: "✅ Deleted pod: production/my-app-abc123"
            # Effect: ReplicaSet creates new pod to replace this one

        RELATED:
        - Called by: restart_pods() in batch restart
        - Called from: main.py via kube_client.delete_pod()
        """
        try:
            # Call Kubernetes API to delete pod
            # Parameters:
            # - name: Pod name to delete
            # - namespace: Namespace containing the pod
            # - grace_period_seconds=0: Immediate deletion (no graceful shutdown)
            self.api.delete_namespaced_pod(
                name=pod_name,
                namespace=namespace,
                grace_period_seconds=0,  # Immediate restart
            )

            # Log success
            print(f"  ✅ Deleted pod: {namespace}/{pod_name}")
            return True

        except ApiException as e:
            # API call failed
            # Log the error and return False
            print(f"  ❌ Failed to delete pod {namespace}/{pod_name}: {e}")
            return False

    # ==========================================================================
    # BATCH RESTART
    # ==========================================================================
    def restart_pods(self, pods: List[Dict]) -> Dict:
        """
        Restart multiple unhealthy pods and return results.

        CONCEPT: Batch Processing
        - Process multiple items in a loop
        - Collect statistics (success/failure counts)
        - Return detailed results for logging

        WHAT THIS CODE DOES:
        1. Initialize counters and results list
        2. For each pod in input list:
           a. Extract name and namespace
           b. Call delete_pod()
           c. Update counters
           d. Add to results list
        3. Return summary dict with counts and details

        INPUT STRUCTURE (from find_unhealthy_pods):
            [
                {"name": "pod1", "namespace": "ns1", ...},
                {"name": "pod2", "namespace": "ns2", ...},
            ]

        RETURN VALUE STRUCTURE:
            {
                "success": 5,           # Number of successful restarts
                "failed": 1,            # Number of failed restarts
                "details": [...]        # Per-pod results
            }

        DETAILS STRUCTURE:
            [
                {
                    "name": "pod1",
                    "namespace": "ns1",
                    "status": "success",  # or "failed"
                    "phase": "Running"
                },
                ...
            ]

        RELATED:
        - Called by: main.py:main() in Step 3
        - Input from: find_unhealthy_pods()
        - Output used by: send_cleanup_report() and recovery verification
        """
        # Initialize counters
        success_count = 0
        failed_count = 0
        results = []

        # Process each pod
        for pod in pods:
            # Extract info from pod dict
            pod_name = pod["name"]
            namespace = pod["namespace"]

            # Delete the pod
            if self.delete_pod(namespace, pod_name):
                # Success
                success_count += 1
                results.append(
                    {
                        "name": pod_name,
                        "namespace": namespace,
                        "status": "success",
                        "phase": pod["phase"],
                    }
                )
            else:
                # Failure
                failed_count += 1
                results.append(
                    {
                        "name": pod_name,
                        "namespace": namespace,
                        "status": "failed",
                        "phase": pod["phase"],
                    }
                )

        # Return summary
        return {"success": success_count, "failed": failed_count, "details": results}

    # ==========================================================================
    # RECOVERY VERIFICATION WITH POLLING
    # ==========================================================================
    def wait_for_pods_ready(
        self, namespaces: List[str], check_interval: int = 30, max_wait_time: int = 300
    ) -> Dict:
        """
        Verify pod recovery with intelligent polling and early exit.

        ==========================================================================
        EXECUTION FLOW DIAGRAM
        ==========================================================================

            ┌─────────────────────────────────────────────────────────────┐
            │                    START OF FUNCTION                      │
            └─────────────────────────┬───────────────────────────────────┘
                                      │
                                      ▼
            ┌─────────────────────────────────────────────────────────────┐
            │  1. Record start_time = time.time()                       │
            │  2. Print "Checking pod recovery..."                       │
            └─────────────────────────┬───────────────────────────────────┘
                                      │
                                      ▼
            ┌─────────────────────────────────────────────────────────────┐
            │              ENTER POLLING LOOP (while True)               │
            │                     │                                      │
            │                     ▼                                      │
            │  3. elapsed = time.time() - start_time                    │
            │                     │                                      │
            │                     ▼                                      │
            │  CHECK: elapsed >= max_wait_time?                           │
            │          │                        │                         │
            │         YES                       NO                        │
            │          │                        │                         │
            │          ▼                        ▼                         │
            │  Print "budget exhausted"    Check pods in                │
            │  BREAK ─────────────────► namespaces                       │
            │         ↑                        │                         │
            │         │                        ▼                         │
            │         │    Check ALL pods in ALL namespaces              │
            │         │    Build current_unhealthy list                  │
            │         │                        │                         │
            │         │                        ▼                         │
            │         │    CHECK: current_unhealthy empty?              │
            │         │    │              │                             │
            │         │   YES             NO                            │
            │         │    │              │                             │
            │         │    ▼              ▼                             │
            │         │  Print "All      Log progress                   │
            │         │  recovered!"     "X pods still unhealthy"      │
            │         │    │              │                             │
            │         │    │              ▼                             │
            │         │    │    ┌──────────────────┐                    │
            │         │    │    │ remaining <=     │                    │
            │         │    │    │ check_interval?  │                    │
            │         │    │    │    │        │      │                    │
            │         │    │   YES        NO      │                    │
            │         │    │    │        │         │                    │
            │         │    │    ▼        ▼         │                    │
            │         │    │  Print     SLEEP     │                    │
            │         │    │  "final    check_interval"                 │
            │         │    │  check"    seconds      │                    │
            │         │    │    │        │         │                    │
            │         │    │    │        └─────────┘                    │
            │         │    │    │          │                             │
            │         │    │    └─────────┴─────────────────────────────┘
            │         │    │                      │                      │
            │         │    └──────────────────────┼────────────────────┘
            │         │                               │
            │         └──────────────────────────────┼──────────────────┐
            │                                                │           │
            │                                    ◄─────────┘           │
            │                                           (loop back)     │
            │                                                            │
            │  EXIT FROM LOOP VIA:                                       │
            │  1. BREAK at line ~709 (budget exhausted)                  │
            │  2. BREAK at line ~792 (budget nearly exhausted)          │
            │  3. RETURN at line ~776 (all recovered early)             │
            │                                                            │
            │  AFTER BREAK: Execution jumps to line ~798                 │
            │  "Return final status"                                    │
            │                                                            │
            └─────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
            ┌─────────────────────────────────────────────────────────────┐
            │           RETURN {"still_unhealthy": [...],               │
            │                  "all_recovered": True/False}             │
            │                    END OF FUNCTION                        │
            └─────────────────────────────────────────────────────────────┘

        ==========================================================================
        PARAMETERS
        ==========================================================================
        - namespaces: List of namespace names to check (e.g., ["default", "prod"])
        - check_interval: Seconds to sleep between checks (default: 30 seconds)
                         THIS VALUE CONTROLS: Line ~795 (time.sleep(check_interval))
        - max_wait_time: Maximum total time budget in seconds (default: 300 = 5 minutes)

        WHERE CHECK_INTERVAL IS USED:
        ┌─────────────────────────────────────────────────────────────────┐
        │ LINE 795: time.sleep(check_interval)                           │
        │                                                              │
        │     if remaining <= check_interval:                          │
        │         print("final check...")                              │
        │         still_unhealthy = ...                                │
        │         BREAK ──────────────────────► skip sleep, exit loop  │
        │     else:                                                     │
        │         time.sleep(check_interval) ◄─── SLEEP HERE (interval)│
        │                                                              │
        │ Flow: Check → Unhealthy → Log → Check budget → Sleep         │
        │       ↑                                      │                │
        │       └──────────────────────────────────────┘                │
        │                  (loop back to check again)                   │
        └─────────────────────────────────────────────────────────────────┘

        WHERE BREAK JUMPS TO:
        ┌─────────────────────────────────────────────────────────────────┐
        │ BREAK at line 709 (budget exhausted):                         │
        │     Execution jumps directly to line 798 (return statement)    │
        │                                                              │
        │ BREAK at line 792 (budget nearly exhausted):                  │
        │     Execution jumps directly to line 798 (return statement)    │
        │                                                              │
        │ IMPORTANT: After either break, the code at line 795          │
        │ (time.sleep) is SKIPPED - we exit the loop immediately       │
        └─────────────────────────────────────────────────────────────────┘

        ==========================================================================
        WHAT THIS CODE DOES (STEP BY STEP)
        ==========================================================================
        STEP 1: Initialize
        ┌─────────────────────────────────────────────────────────────────┐
        │ start_time = time.time()          # Record when we started   │
        │ still_unhealthy = []               # Prepare empty list        │
        │ print(...)                        # Log "Checking recovery..."│
        └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
        STEP 2: Enter Polling Loop (while True - infinite loop until we return/break)
                                    │
                                    ▼
        STEP 3: Calculate elapsed time
        ┌─────────────────────────────────────────────────────────────────┐
        │ elapsed = time.time() - start_time                             │
        │ # Example: If 45 seconds have passed, elapsed = 45.0            │
        └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
        STEP 4: Check if time budget exhausted
        ┌─────────────────────────────────────────────────────────────────┐
        │ if elapsed >= max_wait_time:                                   │
        │     print("budget exhausted")                                  │
        │     BREAK ──────────► jumps to STEP 8 (return)                 │
        └─────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                   NO                              YES
                    │                               │
                    ▼                               ▼
        STEP 5: Check all pods in all namespaces                    STEP 8: Return
        ┌─────────────────────────────────────────────────────────┐   ┌─────────────────┐
        │ for namespace in namespaces:                              │   │                 │
        │     if should_skip_namespace(namespace):                  │   │ return {        │
        │         continue                                          │   │     "still_unhealthy": still_unhealthy,│
        │     pods = self.get_pods_in_namespace(namespace)          │   │     "all_recovered": len(...) == 0  │
        │     for pod in pods:                                      │   │ }               │
        │         Check phase and container status                  │   │                 │
        │         If unhealthy: add to current_unhealthy list       │   └─────────────────┘
        └─────────────────────────────────────────────────────────┘
                                    │
                                    ▼
        STEP 6: Check if all pods recovered (EARLY EXIT condition)
        ┌─────────────────────────────────────────────────────────────────┐
        │ if not current_unhealthy:  # List is empty = all healthy      │
        │     print("All pods recovered!")                               │
        │     return {"still_unhealthy": [], "all_recovered": True}     │
        │                          │                                     │
        │                          │ (IMMEDIATE EXIT - no break needed) │
        │                          ▼                                     │
        │                 FUNCTION ENDS HERE                             │
        └─────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                   NO                              YES
                    │                               │
                    ▼                               ▼
        STEP 7: Log progress and decide whether to sleep or exit
        ┌─────────────────────────────────────────────────────────────────┐
        │ remaining = max_wait_time - elapsed                           │
        │ print(f"{len(current_unhealthy)} pods still unhealthy...")    │
        │                                                               │
        │ if remaining <= check_interval:                               │
        │     print("Budget nearly exhausted, doing final check...")   │
        │     still_unhealthy = current_unhealthy                        │
        │     BREAK ──────────► jumps to STEP 8 (return)                │
        │                          │                                     │
        │                          │ (skips sleep, exits loop)           │
        │                          ▼                                     │
        │     LINE 795 (time.sleep) IS SKIPPED!                         │
        │     Execution jumps directly to return statement              │
        │                                                               │
        │ else:                                                         │
        │     time.sleep(check_interval) ◄─── WAIT HERE (interval)     │
        │          │                                                    │
        │          │ (blocks for 30 seconds by default)                 │
        │          │                                                    │
        │          ▼                                                    │
        │     LOOP BACK TO STEP 2 (while True loop)                    │
        │                          │                                     │
        │                          └─────────────────────────────┬───────┘
        │                                                    │
        │                                    ◄────────────────┘
        │                                           (check again after sleep)
        │
        └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
        STEP 8: Return final status (after any break or early exit)
        ┌─────────────────────────────────────────────────────────────────┐
        │ return {                                                       │
        │     "still_unhealthy": still_unhealthy,  # List of failed pods│
        │     "all_recovered": len(still_unhealthy) == 0                │
        │ }                                                              │
        └─────────────────────────────────────────────────────────────────┘

        ==========================================================================
        EXAMPLE TIMELINE
        ==========================================================================
        Scenario: 3 unhealthy pods at start, max_wait_time=180s, check_interval=30s

        Time    │ Action                                      │ Loop State
        ─────────┼────────────────────────────────────────────┼───────────────
        0s      │ Start checking (3 unhealthy)                │ ─────────────
        0s      │ Check pods                                  │ Iteration 1
        0s      │ 3 unhealthy, log progress                   │    │
        0s      │ remaining=180 > 30, so SLEEP 30s           │    │ time.sleep(30)
        ─────────┼────────────────────────────────────────────┼──────────────
        30s     │ Loop back to top                            │ ─────────────
        30s     │ elapsed=30, Check pods                      │ Iteration 2
        30s     │ 2 unhealthy, log progress                   │    │
        30s     │ remaining=150 > 30, so SLEEP 30s            │    │ time.sleep(30)
        ─────────┼────────────────────────────────────────────┼──────────────
        60s     │ Loop back to top                            │ ─────────────
        60s     │ elapsed=60, Check pods                      │ Iteration 3
        60s     │ 1 unhealthy, log progress                   │    │
        60s     │ remaining=120 > 30, so SLEEP 30s            │    │ time.sleep(30)
        ─────────┼────────────────────────────────────────────┼──────────────
        90s     │ Loop back to top                            │ ─────────────
        90s     │ elapsed=90, Check pods                      │ Iteration 4
        90s     │ 0 unhealthy! Return early!                 │    │ EARLY EXIT
        ─────────┼────────────────────────────────────────────┘    │ no break
        90s     │ FUNCTION RETURNS HERE                       │    ▼
              TOTAL TIME: 90s (instead of full 180s budget)  │ EXIT

        ==========================================================================
        CLUSTER SIZE AWARENESS (parameters set in main.py based on cluster size)
        ==========================================================================
        ┌──────────┬────────────────┬────────────────┬────────────────────────┐
        │ Cluster  │ max_wait_time │ check_interval │ Number of checks       │
        │  Size    │ (time budget) │ (sleep after  │ (180s / 30s = 6)      │
        │          │               │  each check)  │                        │
        ├──────────┼────────────────┼────────────────┼────────────────────────┤
        │ SMALL    │     180s       │      30s      │ ~6 checks (early exit) │
        │ (≤50 ns) │                │                │                        │
        ├──────────┼────────────────┼────────────────┼────────────────────────┤
        │ MEDIUM   │     150s       │      30s      │ ~5 checks (early exit) │
        │ (≤200 ns)│                │                │                        │
        ├──────────┼────────────────┼────────────────┼────────────────────────┤
        │ LARGE    │     120s       │      60s      │ ~2 checks (early exit) │
        │ (>200 ns)│                │                │ Longer interval for    │
        │          │                │                │ large clusters         │
        └──────────┴────────────────┴────────────────┴────────────────────────┘

        ==========================================================================
        RETURN VALUE STRUCTURE
        ==========================================================================
        {
            "still_unhealthy": [
                {
                    "name": "my-app-pod-abc123",
                    "namespace": "production",
                    "phase": "Running",
                    "reason": "CrashLoopBackOff",
                    "message": "Back-off restarting failed container",
                    "container_reason": "CrashLoopBackOff",
                    "container_message": "Back-off restarting failed container"
                },
            ],
            "all_recovered": False  # True if all pods healthy
        }

        ==========================================================================
        RELATED
        ==========================================================================
        - Called by: main.py:main() after restart_pods() in recovery verification step
        - Parameters set in: main.py based on cluster namespace count
        - Output used by: send_alert() if any pods still unhealthy after budget exhausted
        """
        # =========================================================================
        # STEP 1: INITIALIZATION
        # Record start time for budget tracking
        # =========================================================================
        start_time = time.time()  # Reference point for all time calculations
        still_unhealthy = []  # Will hold pods that never recovered

        # Log start of recovery verification
        print(
            f"\n⏳ Checking pod recovery (budget={max_wait_time}s, interval={check_interval}s)..."
        )

        # =========================================================================
        # STEP 2: ENTER POLLING LOOP
        # This is an infinite loop (while True) that only exits via:
        #   1. RETURN at line ~776 (all pods recovered - early exit)
        #   2. BREAK at line ~709 (time budget exhausted)
        #   3. BREAK at line ~792 (budget nearly exhausted, skip sleep)
        # =========================================================================
        while True:
            # =====================================================================
            # STEP 3: CALCULATE ELAPSED TIME
            # How many seconds have passed since we started checking?
            # =====================================================================
            elapsed = time.time() - start_time  # Floating point seconds

            # =====================================================================
            # STEP 4: CHECK IF TIME BUDGET EXHAUSTED
            # If we've used up our time budget, stop checking and return results
            # =====================================================================
            if elapsed >= max_wait_time:
                print(
                    f"   ⏰ Recovery budget exhausted ({elapsed:.1f}s), doing final check..."
                )
                # EXECUTION JUMPS HERE AFTER BREAK:
                # After this break, code continues at line ~798 (return statement)
                # The time.sleep() at line ~795 is SKIPPED entirely
                break

            # =====================================================================
            # STEP 5: CHECK ALL PODS IN ALL NAMESPACES
            # Iterate through each namespace and check every pod's health
            # Build a list of pods that are still unhealthy
            # =====================================================================
            current_unhealthy = []  # Reset for this iteration

            for namespace in namespaces:
                # Skip excluded namespaces (e.g., kube-system)
                if should_skip_namespace(namespace):
                    continue

                # Get all pods in this namespace from Kubernetes API
                pods = self.get_pods_in_namespace(namespace)

                # Examine each pod individually
                for pod in pods:
                    pod_name = pod.metadata.name
                    pod_phase = pod.status.phase

                    # Check if pod phase is healthy (Running/Init/Succeeded)
                    phase_healthy = is_pod_healthy(pod_phase)

                    # Check all container statuses within the pod
                    container_healthy = True
                    for container in pod.status.container_statuses or []:
                        state = container.state

                        # Container is in waiting state (CrashLoopBackOff, etc.)
                        if state.waiting:
                            container_healthy = False
                            break  # Exit container loop early, pod is unhealthy

                        # Container terminated with non-zero exit code (error)
                        if state.terminated and state.terminated.exit_code != 0:
                            container_healthy = False
                            break  # Exit container loop early, pod is unhealthy

                    # If either pod phase or container is unhealthy, record it
                    if not phase_healthy or not container_healthy:
                        # Extract detailed reason for logging/alerting
                        container_reason = "Unknown"
                        container_message = "No message"

                        for container in pod.status.container_statuses or []:
                            state = container.state
                            if state.waiting:
                                container_reason = state.waiting.reason or "Unknown"
                                container_message = (
                                    state.waiting.message or "No message"
                                )
                                break
                            elif state.terminated and state.terminated.exit_code != 0:
                                container_reason = (
                                    f"exitCode={state.terminated.exit_code}"
                                )
                                container_message = (
                                    state.terminated.reason or "No message"
                                )
                                break

                        # Add to list of unhealthy pods for this iteration
                        current_unhealthy.append(
                            {
                                "name": pod_name,
                                "namespace": namespace,
                                "phase": pod_phase,
                                "reason": pod.status.reason or "Unknown",
                                "message": pod.status.message or "No message",
                                "container_reason": container_reason,
                                "container_message": container_message,
                            }
                        )

            # =====================================================================
            # STEP 6: CHECK IF ALL PODS RECOVERED (EARLY EXIT)
            # If no unhealthy pods found, return success immediately
            # This is the EARLY EXIT - we don't wait for full time budget
            # =====================================================================
            if not current_unhealthy:
                # current_unhealthy is empty = all pods healthy!
                print(f"   ✅ All pods recovered! (elapsed={elapsed:.1f}s)")
                # RETURN IMMEDIATELY - function ends here
                # No break needed, return exits the function directly
                return {"still_unhealthy": [], "all_recovered": True}

            # =====================================================================
            # STEP 7: LOG PROGRESS AND DECIDE NEXT ACTION
            # Either sleep and continue, or exit if budget nearly exhausted
            # =====================================================================
            remaining = max_wait_time - elapsed  # Seconds left in our budget

            print(
                f"   ⚠️ {len(current_unhealthy)} pods still unhealthy, {remaining:.0f}s remaining..."
            )

            # Decide: should we continue polling or exit the loop?
            if remaining <= check_interval:
                # Not enough time for another full check + sleep cycle
                # Exit the loop and return results
                print("   ⏰ Budget nearly exhausted, doing final check...")
                still_unhealthy = current_unhealthy
                # EXECUTION JUMPS HERE AFTER BREAK:
                # After this break, code continues at line ~798 (return statement)
                # The time.sleep() below is SKIPPED entirely
                # This break is at line ~792
                break
            else:
                # Enough time remaining, sleep for one interval then check again
                # THIS IS WHERE THE WAITING INTERVAL TAKES EFFECT
                # Line ~795: Sleep for check_interval seconds (default: 30s)
                # During sleep, the function is blocked - no CPU usage
                # After sleep completes, loop continues from the top (STEP 2)
                time.sleep(check_interval)
                # After sleep finishes, execution continues at STEP 2
                # (the while True loop continues)

        # =========================================================================
        # STEP 8: RETURN FINAL STATUS
        # This is where execution lands after:
        #   - BREAK at line 709 (budget exhausted)
        #   - BREAK at line 792 (budget nearly exhausted)
        # The time.sleep() at line 795 is NEVER executed after a break
        # =========================================================================
        return {
            "still_unhealthy": still_unhealthy,
            "all_recovered": len(still_unhealthy) == 0,
        }
