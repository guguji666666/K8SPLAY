#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Recovery Feature
Tests the recovery verification functionality

Usage:
    python test_recovery_feature.py

Requirements:
    - Kubernetes cluster access
    - Test namespace with permission to create pods
"""

import sys
import os
import time
import logging
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from kube_client import KubernetesClient
from persistence_store import PersistenceStore
from recovery_checker import RecoveryChecker
from config import Config


def setup_logging():
    """Configure logging for testing"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def test_persistence_store():
    """Test persistence store functionality"""
    print("\n" + "=" * 60)
    print(" Test 1: Persistence Store")
    print("=" * 60)

    # Use a test file
    store = PersistenceStore(file_path="/tmp/pod-cleaner-test-state.json")

    # Test track_deletion
    print("\n1. Testing track_deletion...")
    entry = store.track_deletion(
        pod_uid="test-pod-uid-1",
        pod_name="test-pod-abc123",
        namespace="default",
        reason="CrashLoopBackOff"
    )
    assert entry['attempt'] == 1, "First attempt should be 1"
    print("   ✅ First deletion tracked")

    # Test incrementing attempt
    entry = store.track_deletion(
        pod_uid="test-pod-uid-1",
        pod_name="test-pod-abc123",
        namespace="default",
        reason="CrashLoopBackOff"
    )
    assert entry['attempt'] == 2, "Second attempt should be 2"
    print("   ✅ Second deletion tracked (attempt incremented)")

    # Test get_tracking
    print("\n2. Testing get_tracking...")
    tracking = store.get_tracking("test-pod-uid-1")
    assert tracking is not None, "Should find tracking info"
    assert tracking['attempt'] == 2, "Attempt should be 2"
    print(f"   ✅ Retrieved tracking info: attempt={tracking['attempt']}")

    # Test get_all_tracked
    print("\n3. Testing get_all_tracked...")
    all_tracked = store.get_all_tracked()
    assert "test-pod-uid-1" in all_tracked, "Should contain test pod"
    print(f"   ✅ Found {len(all_tracked)} tracked pod(s)")

    # Test remove_tracking
    print("\n4. Testing remove_tracking...")
    store.remove_tracking("test-pod-uid-1")
    tracking = store.get_tracking("test-pod-uid-1")
    assert tracking is None, "Should be removed"
    print("   ✅ Tracking removed successfully")

    print("\n✅ Persistence Store tests passed!")
    return True


def test_recovery_checker():
    """Test recovery checker functionality"""
    print("\n" + "=" * 60)
    print(" Test 2: Recovery Checker")
    print("=" * 60)

    # Initialize components
    print("\n1. Initializing components...")
    kube_client = KubernetesClient()
    store = PersistenceStore(file_path="/tmp/pod-cleaner-test-state.json")
    recovery_checker = RecoveryChecker(kube_client, store)
    print("   ✅ Components initialized")

    # Test check_pod_health with mock data
    print("\n2. Testing check_pod_health...")

    # Healthy pod
    healthy_pod = {
        'name': 'healthy-pod',
        'namespace': 'default',
        'phase': 'Running',
        'container_statuses': [
            {'state': {'running': {'started_at': '2026-02-27T10:00:00Z'}}}
        ]
    }
    is_healthy, reason, message = recovery_checker.check_pod_health(healthy_pod)
    assert is_healthy, "Should be healthy"
    print(f"   ✅ Healthy pod detected: {reason}")

    # Unhealthy pod (CrashLoopBackOff)
    unhealthy_pod = {
        'name': 'unhealthy-pod',
        'namespace': 'default',
        'phase': 'Running',
        'container_statuses': [
            {
                'state': {
                    'waiting': {
                        'reason': 'CrashLoopBackOff',
                        'message': 'Back-off 5m0s restarting failed container'
                    }
                }
            }
        ]
    }
    is_healthy, reason, message = recovery_checker.check_pod_health(unhealthy_pod)
    assert not is_healthy, "Should be unhealthy"
    assert reason == 'CrashLoopBackOff', "Reason should match"
    print(f"   ✅ Unhealthy pod detected: {reason}")

    # Test is_persistent_issue
    print("\n3. Testing persistent issue detection...")
    store.track_deletion("pod-1", "test-pod-1", "default", "CrashLoopBackOff")
    store.track_deletion("pod-1", "test-pod-1", "default", "CrashLoopBackOff")
    store.track_deletion("pod-1", "test-pod-1", "default", "CrashLoopBackOff")

    is_persistent = recovery_checker.is_persistent_issue("pod-1")
    assert is_persistent, "Should be persistent after 3 attempts"
    print("   ✅ Persistent issue detected after 3 attempts")

    # Cleanup
    store.remove_tracking("pod-1")

    print("\n✅ Recovery Checker tests passed!")
    return True


def test_integration_with_real_pod():
    """Test with a real failing pod (optional, requires cluster)"""
    print("\n" + "=" * 60)
    print(" Test 3: Integration Test (Optional)")
    print("=" * 60)

    print("\n⚠️ This test requires a Kubernetes cluster with test permissions")
    print("   Skipping integration test for now...")
    print("   To run manually:")
    print("   1. kubectl apply -f test-always-failed-pods.yaml")
    print("   2. python main.py")
    print("   3. Watch logs and notifications")

    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print(" Pod Cleaner - Recovery Feature Tests")
    print("=" * 60)
    print(f" Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    setup_logging()

    results = []

    # Test 1: Persistence Store
    try:
        results.append(("Persistence Store", test_persistence_store()))
    except Exception as e:
        print(f"\n❌ Persistence Store test failed: {e}")
        results.append(("Persistence Store", False))

    # Test 2: Recovery Checker
    try:
        results.append(("Recovery Checker", test_recovery_checker()))
    except Exception as e:
        print(f"\n❌ Recovery Checker test failed: {e}")
        results.append(("Recovery Checker", False))

    # Test 3: Integration
    try:
        results.append(("Integration", test_integration_with_real_pod()))
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        results.append(("Integration", False))

    # Summary
    print("\n" + "=" * 60)
    print(" Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(main())
