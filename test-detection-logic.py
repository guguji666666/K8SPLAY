#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pod Cleaner Detection Logic Test Script

This script validates the core detection logic used by Pod Cleaner to identify
unhealthy Kubernetes pods. It tests the detection algorithms without requiring
a real Kubernetes cluster, and can optionally verify against actual cluster state.

Purpose:
- Validate detection logic correctness through unit-style tests
- Verify detection patterns match expected behaviors
- Provide quick feedback during development
- Optionally audit real cluster pod health

Usage:
    python3 test-detection-logic.py                    # Run logic tests only (no K8s required)
    python3 test-detection-logic.py --k8s              # Check actual cluster pods
    python3 test-detection-logic.py --k8s -n test-failures  # Check specific namespace

Exit Codes:
    0 - Logic tests passed OR unhealthy pods found in cluster
    1 - Logic tests failed
"""

import argparse
import sys
from typing import Dict, Any, List, Optional

# -----------------------------------------------------------------------------
# Kubernetes Client Import
# -----------------------------------------------------------------------------
# The kubernetes Python client is optional for logic-only testing.
# If not installed, K8s-related features will be disabled with graceful fallback.

try:
    # Official Python client for Kubernetes API
    # Provides typed interfaces for all K8s resources
    from kubernetes import client, config

    K8S_AVAILABLE = True
except ImportError:
    # Fallback when kubernetes package not installed
    # Logic tests will still work, but K8s cluster checks will be disabled
    K8S_AVAILABLE = False


# -----------------------------------------------------------------------------
# Container Health Detection
# -----------------------------------------------------------------------------


def is_container_healthy(container: Dict[str, Any]) -> bool:
    """
    Determine if a container is in a healthy state.

    This function checks container status to identify unhealthy patterns:
    1. Container in 'waiting' state - typically indicates startup failures
       - CrashLoopBackOff: Container repeatedly crashes and restarts
       - ImagePullBackOff: Failed to pull container image
       - CreateContainerConfigError: Missing config/secrets

    2. Container in 'terminated' state with non-zero exit code
       - Exit code 0 = normal/successful exit
       - Exit code 1 = application error (most common)
       - Exit codes 128+ = signal-related exits (e.g., OOMKilled)

    Args:
        container: Dictionary containing container state information
                  Expected format: {'state': {'waiting': {...}} or
                                   {'state': {'terminated': {'exitCode': N}}}}

    Returns:
        bool: True if container appears healthy, False otherwise
    """
    # Get the state dictionary from container status
    # Default to empty dict if not present (shouldn't happen in real K8s)
    state = container.get("state", {})

    # Check for 'waiting' state - this is the primary indicator of problems
    # CrashLoopBackOff, ImagePullBackOff, CreateContainerConfigError all use 'waiting'
    if state.get("waiting"):
        return False

    # Check for 'terminated' state - container has exited
    # Exit code 0 = normal exit (expected for completed jobs)
    # Any non-zero exit code indicates failure
    terminated = state.get("terminated")
    if terminated and terminated.get("exitCode", 0) != 0:
        return False

    # If we reach here, container is either:
    # - Running (normal operation)
    # - Terminated with exit code 0 (completed successfully)
    return True


def is_pod_healthy(phase: str) -> bool:
    """
    Perform preliminary screening based on pod phase.

    Kubernetes pod phases:
    - Pending: Pod accepted but waiting for scheduling
    - Running: Pod bound to node, at least one container running
    - Succeeded: All containers terminated successfully (job-like workloads)
    - Failed: At least one container terminated with failure
    - Unknown: Pod state cannot be determined

    Note: Pod phase alone is insufficient for health judgment.
    A pod can be 'Running' while containers are in CrashLoopBackOff.

    Args:
        phase: Kubernetes pod phase string

    Returns:
        bool: True if phase indicates potential health, False if clearly failed
    """
    # We only process pods in Running/Init/Succeeded phases
    # Failed pods are already terminal and won't benefit from restart
    # Pending/Unknown pods may have scheduling/image issues
    return phase in ["Running", "Init", "Succeeded"]


def check_pod_health(pod_status: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive pod health assessment combining phase and container analysis.

    This is the core detection function that Pod Cleaner uses to identify
    pods requiring restart intervention.

    Detection Strategy:
    1. Skip pods with obviously terminal phases (Failed, Unknown)
    2. Skip pods that haven't started yet (Pending)
    3. For Running/Init pods, analyze container-level states
    4. Collect specific failure reasons for alerting

    Args:
        pod_status: Dictionary containing:
            - phase: Pod phase string (Running, Pending, Failed, etc.)
            - container_statuses: List of container status dictionaries

    Returns:
        Dict with keys:
            - healthy (bool): Overall health determination
            - reasons (List[str]): Specific failure reasons found
    """
    # Initialize result with healthy state
    result = {"healthy": True, "reasons": []}

    # Step 1: Phase-level screening
    # Get phase with safe default for malformed data
    phase = pod_status.get("phase", "Unknown")

    # Skip obviously failed pods early
    # We focus on Running/Init pods that appear OK at phase level
    # but may have container-level issues
    if not is_pod_healthy(phase):
        result["healthy"] = False
        result["reasons"].append(f"Phase: {phase}")
        return result

    # Step 2: Container-level deep inspection
    # This is where we catch the tricky cases:
    # - Pod phase = Running but container = CrashLoopBackOff
    # - Pod phase = Running but container = terminated with error
    container_statuses = pod_status.get("container_statuses", [])

    for i, container in enumerate(container_statuses):
        if not is_container_healthy(container):
            result["healthy"] = False
            state = container.get("state", {})

            # Record waiting state reasons (CrashLoopBackOff, etc.)
            if state.get("waiting"):
                reason = state.get("waiting", {}).get("reason", "Unknown")
                result["reasons"].append(f"Container {i}: {reason}")

            # Record terminated state with exit code
            elif state.get("terminated"):
                exit_code = state.get("terminated", {}).get("exitCode", 0)
                result["reasons"].append(
                    f"Container {i}: terminated with exitCode={exit_code}"
                )

    return result


# -----------------------------------------------------------------------------
# Logic Testing (Simulation Mode)
# -----------------------------------------------------------------------------


def run_logic_tests() -> bool:
    """
    Execute unit-style tests for detection logic.

    Tests cover the following scenarios:
    1. CrashLoopBackOff - Container in waiting state
    2. Normal Running - Container actively running
    3. Normal Termination - Container completed successfully
    4. Abnormal Termination - Container exited with error code
    5. ImagePullBackOff - Container waiting for image pull

    Each test validates that our detection logic correctly classifies
    pod health states.

    Returns:
        bool: True if all tests pass, False otherwise
    """
    print("=" * 60)
    print("Pod Cleaner Detection Logic Tests (Local Simulation)")
    print("=" * 60)

    # Define test cases with expected outcomes
    # Each test simulates a pod status structure that would come from K8s API
    test_cases = [
        {
            "name": "CrashLoopBackOff",
            "phase": "Running",
            "container_statuses": [
                {"state": {"waiting": {"reason": "CrashLoopBackOff"}}}
            ],
            "expected_healthy": False,
        },
        {
            "name": "Normal Running",
            "phase": "Running",
            "container_statuses": [{"state": {"running": {}}}],
            "expected_healthy": True,
        },
        {
            "name": "Normal Terminated (exitCode 0)",
            "phase": "Succeeded",
            "container_statuses": [{"state": {"terminated": {"exitCode": 0}}}],
            "expected_healthy": True,
        },
        {
            "name": "Abnormal Terminated (exitCode 1)",
            "phase": "Running",
            "container_statuses": [{"state": {"terminated": {"exitCode": 1}}}],
            "expected_healthy": False,
        },
        {
            "name": "ImagePullBackOff",
            "phase": "Pending",
            "container_statuses": [
                {"state": {"waiting": {"reason": "ImagePullBackOff"}}}
            ],
            "expected_healthy": False,
        },
    ]

    passed = failed = 0

    # Execute each test case
    for i, test in enumerate(test_cases, 1):
        # Construct pod status from test case
        pod_status = {
            "phase": test["phase"],
            "container_statuses": test["container_statuses"],
        }

        # Run detection
        result = check_pod_health(pod_status)
        actual_healthy = result["healthy"]

        # Verify against expected outcome
        status = "✅ PASS" if actual_healthy == test["expected_healthy"] else "❌ FAIL"
        if actual_healthy == test["expected_healthy"]:
            passed += 1
        else:
            failed += 1

        # Display results
        print(f"\nTest {i}: {test['name']}")
        print(f"  Phase: {test['phase']}")
        print(f"  Status: {status}")

    # Summary
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    # Return True if all tests passed
    return failed == 0


# -----------------------------------------------------------------------------
# Kubernetes Cluster Verification
# -----------------------------------------------------------------------------


def check_k8s_pods(namespace: Optional[str] = None) -> bool:
    """
    Connect to Kubernetes cluster and audit pod health.

    This function performs real cluster analysis by:
    1. Loading Kubernetes configuration (kubeconfig or in-cluster)
    2. Fetching pod list (filtered by namespace if specified)
    3. Running detection logic on each pod
    4. Reporting unhealthy pods with failure reasons

    Args:
        namespace: Optional namespace filter. If None, checks all namespaces.
                 Useful for focusing on specific test environments.

    Returns:
        bool: True if unhealthy pods found (audit success), False if all healthy
    """
    # Check kubernetes client availability
    if not K8S_AVAILABLE:
        print("❌ kubernetes package not installed: pip install kubernetes")
        return False

    # -----------------------------------------------------------------------------
    # Configuration Loading
    # -----------------------------------------------------------------------------
    # Kubernetes client supports multiple configuration methods:
    # 1. kubeconfig file (local development, kubectl default)
    # 2. In-cluster config (when running inside a Pod with ServiceAccount)
    # 3. Various cloud provider loaders (GKE, EKS, AKS)

    try:
        # Try local kubeconfig first (development scenario)
        config.load_kube_config()
        print("✅ Loaded kubeconfig")
        config_loaded = True
    except Exception:
        config_loaded = False

    if not config_loaded:
        try:
            # Fall back to in-cluster config (production scenario)
            # Uses mounted ServiceAccount token and KUBERNETES_SERVICE_HOST
            config.load_incluster_config()
            print("✅ Loaded in-cluster config")
        except Exception as e:
            print(f"❌ Failed to load Kubernetes config: {e}")
            return False

    # Create CoreV1Api client for pod operations
    # client module is guaranteed to be imported here (K8S_AVAILABLE check above)
    v1 = client.CoreV1Api()

    # -----------------------------------------------------------------------------
    # Pod List Retrieval
    # -----------------------------------------------------------------------------
    # list_namespaced_pod: Get pods in specific namespace
    # list_pod_for_all_namespaces: Get pods across entire cluster

    try:
        if namespace:
            pods = v1.list_namespaced_pod(namespace).items
            print(f"\n📋 Namespace: {namespace}")
        else:
            pods = v1.list_pod_for_all_namespaces().items
            print(f"\n📋 All Namespaces")
    except Exception as e:
        print(f"❌ Failed to get pod list: {e}")
        return False

    # -----------------------------------------------------------------------------
    # System Namespace Exclusion
    # -----------------------------------------------------------------------------
    # We intentionally skip system namespaces because:
    # 1. System pods (kube-proxy, etcd, etc.) are critical infrastructure
    # 2. They often have special restart behaviors managed by K8s itself
    # 3. Restarting them could destabilize the cluster

    excluded_namespaces = ["kube-system"]

    unhealthy_pods = []

    print(f"\n🔍 Checking {len(pods)} pods...")
    print("-" * 60)

    # -----------------------------------------------------------------------------
    # Pod Health Analysis
    # -----------------------------------------------------------------------------
    # For each pod, we construct a status dictionary compatible with
    # our detection logic, then run the health check.

    for pod in pods:
        ns = pod.metadata.namespace
        name = pod.metadata.name

        # Skip excluded namespaces
        if ns in excluded_namespaces:
            continue

        # Construct pod status from K8s API response
        # The K8s Python client uses attribute-style access
        pod_status = {"phase": pod.status.phase, "container_statuses": []}

        # Extract container states from K8s API response
        # container_statuses is a list of V1ContainerStatus objects
        for container_status in pod.status.container_statuses or []:
            state_dict = {}

            # Extract waiting state (CrashLoopBackOff, etc.)
            if container_status.state.waiting:
                state_dict["waiting"] = {
                    "reason": container_status.state.waiting.reason
                }
            # Extract terminated state (exit codes)
            elif container_status.state.terminated:
                state_dict["terminated"] = {
                    "exitCode": container_status.state.terminated.exit_code
                }
            # Extract running state (active execution)
            elif container_status.state.running:
                state_dict["running"] = {}

            pod_status["container_statuses"].append({"state": state_dict})

        # Run detection logic on this pod
        result = check_pod_health(pod_status)

        # Collect unhealthy pods for reporting
        if not result["healthy"]:
            unhealthy_pods.append(
                {
                    "namespace": ns,
                    "name": name,
                    "phase": pod_status["phase"],
                    "reasons": result["reasons"],
                }
            )

    # -----------------------------------------------------------------------------
    # Results Reporting
    # -----------------------------------------------------------------------------

    if unhealthy_pods:
        print(f"\n⚠️ Found {len(unhealthy_pods)} unhealthy pod(s):")
        print("-" * 60)
        for pod in unhealthy_pods:
            print(f"  ❌ {pod['namespace']}/{pod['name']}")
            print(f"     Phase: {pod['phase']}")
            for reason in pod["reasons"]:
                print(f"     {reason}")
            print()
    else:
        print(f"\n✅ All pods healthy (excluded {excluded_namespaces})")

    # Return True if unhealthy pods were found
    # This indicates successful audit (we found something to report)
    return len(unhealthy_pods) > 0


# -----------------------------------------------------------------------------
# Command Line Interface
# -----------------------------------------------------------------------------


def main():
    """
    Entry point for the detection logic test script.

    Parses command line arguments and executes appropriate test mode:
    --k8s: Connect to real Kubernetes cluster for live auditing
    -n/--namespace: Filter K8s check to specific namespace

    Examples:
        python3 test-detection-logic.py
            Run logic validation tests only (no cluster connection)

        python3 test-detection-logic.py --k8s
            Audit all pods in cluster for health issues

        python3 test-detection-logic.py --k8s -n production
            Audit only production namespace pods
    """
    parser = argparse.ArgumentParser(description="Pod Cleaner Detection Logic Test")

    parser.add_argument(
        "--k8s", action="store_true", help="Connect to K8s cluster to check actual pods"
    )
    parser.add_argument(
        "-n", "--namespace", help="Specify namespace (only valid with --k8s)"
    )

    args = parser.parse_args()

    if args.k8s:
        # Kubernetes cluster audit mode
        # Returns True if unhealthy pods found (audit found issues)
        success = check_k8s_pods(args.namespace)
        sys.exit(0 if success else 0)
    else:
        # Logic test mode (simulation)
        # Returns True if all logic tests pass
        success = run_logic_tests()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
