#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pod Cleaner Detection Logic Test Script
Validates CrashLoopBackOff and abnormal termination pod detection logic

Usage:
    python3 test-detection-logic.py                    # Test logic only
    python3 test-detection-logic.py --k8s              # Check actual cluster
    python3 test-detection-logic.py --k8s -n test-failed-pods  # Check specific namespace
"""

import argparse
import sys
from typing import Dict, Any, List, Optional

# Kubernetes client
try:
    from kubernetes import client, config
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False


def is_container_healthy(container: Dict[str, Any]) -> bool:
    """Check if container is healthy"""
    state = container.get('state', {})

    if state.get('waiting'):
        return False

    terminated = state.get('terminated')
    if terminated and terminated.get('exitCode', 0) != 0:
        return False

    return True


def is_pod_healthy(phase: str) -> bool:
    """Check if pod phase is healthy"""
    return phase in ["Running", "Init", "Succeeded"]


def check_pod_health(pod_status: Dict[str, Any]) -> Dict[str, Any]:
    """Comprehensive pod health check"""
    result = {
        "healthy": True,
        "reasons": []
    }

    phase = pod_status.get('phase', 'Unknown')
    if not is_pod_healthy(phase):
        result["healthy"] = False
        result["reasons"].append(f"Phase: {phase}")

    container_statuses = pod_status.get('container_statuses', [])
    for i, container in enumerate(container_statuses):
        if not is_container_healthy(container):
            result["healthy"] = False
            state = container.get('state', {})
            if state.get('waiting'):
                reason = state.get('waiting', {}).get('reason', 'Unknown')
                result["reasons"].append(f"Container {i}: {reason}")
            elif state.get('terminated'):
                exit_code = state.get('terminated', {}).get('exitCode', 0)
                result["reasons"].append(f"Container {i}: terminated with exitCode={exit_code}")

    return result


def run_logic_tests() -> bool:
    """Run logic tests"""
    print("=" * 60)
    print("Pod Cleaner Detection Logic Tests (Local Simulation)")
    print("=" * 60)

    test_cases = [
        {
            "name": "CrashLoopBackOff",
            "phase": "Running",
            "container_statuses": [{"state": {"waiting": {"reason": "CrashLoopBackOff"}}}],
            "expected_healthy": False
        },
        {
            "name": "Normal Running",
            "phase": "Running",
            "container_statuses": [{"state": {"running": {}}}],
            "expected_healthy": True
        },
        {
            "name": "Normal Terminated (exitCode 0)",
            "phase": "Succeeded",
            "container_statuses": [{"state": {"terminated": {"exitCode": 0}}}],
            "expected_healthy": True
        },
        {
            "name": "Abnormal Terminated (exitCode 1)",
            "phase": "Running",
            "container_statuses": [{"state": {"terminated": {"exitCode": 1}}}],
            "expected_healthy": False
        },
        {
            "name": "ImagePullBackOff",
            "phase": "Pending",
            "container_statuses": [{"state": {"waiting": {"reason": "ImagePullBackOff"}}}],
            "expected_healthy": False
        },
    ]

    passed = failed = 0

    for i, test in enumerate(test_cases, 1):
        pod_status = {
            "phase": test["phase"],
            "container_statuses": test["container_statuses"]
        }

        result = check_pod_health(pod_status)
        actual_healthy = result["healthy"]

        status = "✅ PASS" if actual_healthy == test["expected_healthy"] else "❌ FAIL"
        if actual_healthy == test["expected_healthy"]:
            passed += 1
        else:
            failed += 1

        print(f"\nTest {i}: {test['name']}")
        print(f"  Phase: {test['phase']}")
        print(f"  Status: {status}")

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


def check_k8s_pods(namespace: Optional[str] = None) -> bool:
    """Check unhealthy pods in Kubernetes cluster"""
    if not K8S_AVAILABLE:
        print("❌ kubernetes package not installed: pip install kubernetes")
        return False

    # Load configuration
    try:
        config.load_kube_config()
        print("✅ Loaded kubeconfig")
    except Exception:
        try:
            config.load_incluster_config()
            print("✅ Loaded in-cluster config")
        except Exception as e:
            print(f"❌ Failed to load Kubernetes config: {e}")
            return False

    v1 = client.CoreV1Api()

    # Get pod list
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

    # System namespaces to exclude
    excluded_namespaces = ["kube-system"]

    unhealthy_pods = []

    print(f"\n🔍 Checking {len(pods)} pods...")
    print("-" * 60)

    for pod in pods:
        ns = pod.metadata.namespace
        name = pod.metadata.name

        # Skip system namespaces
        if ns in excluded_namespaces:
            continue

        # Build status object
        pod_status = {
            "phase": pod.status.phase,
            "container_statuses": []
        }

        for container_status in pod.status.container_statuses or []:
            state_dict = {}
            
            if container_status.state.waiting:
                state_dict["waiting"] = {"reason": container_status.state.waiting.reason}
            elif container_status.state.terminated:
                state_dict["terminated"] = {"exitCode": container_status.state.terminated.exit_code}
            elif container_status.state.running:
                state_dict["running"] = {}
            
            pod_status["container_statuses"].append({
                "state": state_dict
            })

        # Check health
        result = check_pod_health(pod_status)

        if not result["healthy"]:
            unhealthy_pods.append({
                "namespace": ns,
                "name": name,
                "phase": pod_status["phase"],
                "reasons": result["reasons"]
            })

    # Print results
    if unhealthy_pods:
        print(f"\n⚠️ Found {len(unhealthy_pods)} unhealthy pod(s):")
        print("-" * 60)
        for pod in unhealthy_pods:
            print(f"  ❌ {pod['namespace']}/{pod['name']}")
            print(f"     Phase: {pod['phase']}")
            for reason in pod['reasons']:
                print(f"     {reason}")
            print()
    else:
        print(f"\n✅ All pods healthy (excluded {excluded_namespaces})")

    return len(unhealthy_pods) > 0


def main():
    parser = argparse.ArgumentParser(description="Pod Cleaner Detection Logic Test")
    parser.add_argument("--k8s", action="store_true", help="Connect to K8s cluster to check actual pods")
    parser.add_argument("-n", "--namespace", help="Specify namespace (only valid with --k8s)")

    args = parser.parse_args()

    if args.k8s:
        # K8S mode
        success = check_k8s_pods(args.namespace)
        sys.exit(0 if success else 0)  # Returns 0 if unhealthy pods found (success)
    else:
        # Logic test mode
        success = run_logic_tests()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
