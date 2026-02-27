#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pod Cleaner Main Program
Kubernetes Pod Automatic Cleanup Tool

Features:
- Runs every 10 minutes
- Finds and restarts unhealthy pods (not in Running or Init state)
- Logs all cleanup operations
- Bark notification support (Bonus)

Usage:
1. Run directly (local debugging): python main.py
2. Docker run: docker run pod-cleaner
3. Kubernetes deploy: kubectl apply -f helm/

Author: ZIO
Date: 2026-01-31
"""

import time
import logging
from datetime import datetime
from typing import List, Dict

# Import custom modules
from kube_client import KubernetesClient
from notifier import BarkNotifier
from config import Config
from persistence_store import PersistenceStore
from recovery_checker import RecoveryChecker


def setup_logging():
    """
    Configure logging system

    Features:
    - Set log level
    - Configure log format
    - Output to console

    Log Levels:
    - DEBUG: Detailed debug info
    - INFO: General info
    - WARNING: Warnings
    - ERROR: Errors
    - CRITICAL: Critical errors
    """
    log_level = Config.get_log_level()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt=Config.LOG_FORMAT
    )


def format_pod_list(pods: List[Dict]) -> str:
    """
    Format pod list as string

    Parameters:
        pods: List[Dict] - Pod info list

    Returns:
        str: Formatted string
    """
    if not pods:
        return "None"

    lines = []
    for pod in pods:
        lines.append(f"  - {pod['namespace']}/{pod['name']} ({pod['phase']})")
    return "\n".join(lines)


def main():
    """
    Main function

    Program entry point:
    1. Initialize components (K8s client, notifier)
    2. Enter main loop
    3. Execute cleanup every 10 minutes
    """
    print("\n" + "=" * 60)
    print(" Pod Cleaner Started")
    print("=" * 60 + "\n")

    # Configure logging
    setup_logging()

    # Initialize Kubernetes client
    print(" Initializing Kubernetes client...")
    kube_client = KubernetesClient()

    # Initialize notifier
    print(" Initializing Bark notifier...")
    notifier = BarkNotifier()

    # Initialize persistence store
    print(" Initializing persistence store...")
    persistence_file = Config.get_persistence_file()
    store = PersistenceStore(file_path=persistence_file)

    # Initialize recovery checker
    print(" Initializing recovery checker...")
    recovery_enabled = Config.get_recovery_enabled()
    recovery_checker = RecoveryChecker(
        kube_client=kube_client,
        store=store,
        config=Config
    ) if recovery_enabled else None

    print(f"\nOK Initialization complete, starting...\n")
    print(f"   Recovery verification: {'Enabled' if recovery_checker else 'Disabled'}")

    # ============================================================
    # Main Loop
    # ============================================================
    # Notes:
    # - Uses while True for continuous operation
    # - Waits 10 minutes after each cleanup task
    # - If task takes longer than 10 minutes, starts next immediately
    # ============================================================

    run_count = 0  # Run counter

    while True:
        run_count += 1
        run_start_time = datetime.now()

        print("=" * 60)
        print(f" Run #{run_count}")
        print(f" Start time: {run_start_time.strftime(Config.LOG_FORMAT)}")
        print("=" * 60)

        # Step 1: Get all namespaces
        print("\n Step 1: Getting namespaces...")
        namespaces = kube_client.get_all_namespaces()
        print(f"   Found {len(namespaces)} namespaces")

        # Step 2: Find unhealthy pods
        print("\n Step 2: Finding unhealthy pods...")
        unhealthy_pods = kube_client.find_unhealthy_pods(namespaces)
        unhealthy_count = len(unhealthy_pods)

        if unhealthy_count == 0:
            print("   OK No unhealthy pods found, no cleanup needed")
        else:
            print(f"   WARNING Found {unhealthy_count} unhealthy pod(s)")

            # Step 3: Restart unhealthy pods and track for recovery verification
            print("\n Step 3: Restarting unhealthy pods...")
            
            if recovery_checker:
                # Track each pod before deletion for recovery verification
                for pod in unhealthy_pods:
                    pod_uid = pod.get('uid', pod['name'])  # Use UID if available
                    store.track_deletion(
                        pod_uid=pod_uid,
                        pod_name=pod['name'],
                        namespace=pod['namespace'],
                        reason=pod.get('reason', 'Unhealthy')
                    )
            
            restart_result = kube_client.restart_pods(unhealthy_pods)
            print(f"   Success: {restart_result['success']}, Failed: {restart_result['failed']}")

            # Step 4: Send cleanup report (Bonus)
            print("\n Step 4: Sending cleanup report...")
            if notifier.enabled:
                notifier.send_cleanup_report(
                    cleaned_count=restart_result['success'],
                    failed_count=restart_result['failed'],
                    details=restart_result['details']
                )

            # Step 5: Recovery verification (NEW FEATURE)
            if recovery_checker:
                print("\n🔍 Step 5: Verifying pod recovery...")
                
                # Wait for new pods to be created
                wait_time = Config.get_recovery_wait_seconds()
                print(f"   Waiting {wait_time}s for new pod creation...")
                time.sleep(wait_time)
                
                # Verify recovery for all tracked pods
                verification_result = recovery_checker.verify_all_tracked()
                
                # Handle persistent issues
                if verification_result['persistent_issues'] > 0:
                    print(f"\n🔥 Found {verification_result['persistent_issues']} persistent issue(s)")
                    
                    for result in verification_result['results']:
                        if result.get('persistent_issue'):
                            tracking = result.get('tracking_info', {})
                            esc_info = recovery_checker.get_escalation_info(result['uid'])
                            
                            if esc_info:
                                # Send escalation notification
                                notifier.send_escalation(
                                    pod_name=esc_info['name'],
                                    namespace=esc_info['namespace'],
                                    attempt=esc_info['attempt'],
                                    reason=esc_info['reason'],
                                    first_deleted_at=esc_info['first_deleted_at'],
                                    history=esc_info['history']
                                )
                                print(f"   🔥 Escalation sent for {esc_info['namespace']}/{esc_info['name']}")
                
                # Send verification report
                if notifier.enabled and verification_result['total'] > 0:
                    notifier.send_recovery_verification_report(verification_result)
            else:
                # Legacy recovery check (wait 5 minutes)
                print("\n⚠️ Step 5: Checking restart status (legacy mode, waiting 5 minutes)...")
                time.sleep(300)  # Wait 5 minutes

                recovery_result = kube_client.wait_for_pods_ready(
                    namespaces=namespaces,
                    check_interval=30,
                    max_wait_time=120  # Wait another 2 minutes
                )

                if not recovery_result['all_recovered']:
                    unhealthy = recovery_result['still_unhealthy']
                    print(f"   WARNING: Found {len(unhealthy)} unrecovered pod(s)")

                    # Aggregate all unhealthy pods into one notification
                    alert_title = f"WARNING: {len(unhealthy)} Pods Unhealthy"
                    alert_body = f"Found {len(unhealthy)} pods still unhealthy after restart:\n\n"

                    for pod in unhealthy:
                        container_reason = pod.get('container_reason', 'Unknown')
                        container_message = pod.get('container_message', 'No message')
                        
                        alert_body += f"Pod: {pod['namespace']}/{pod['name']}\n"
                        alert_body += f"Phase: {pod['phase']}\n"
                        alert_body += f"Reason: {container_reason}\n"
                        alert_body += f"Details: {container_message[:100]}{'...' if len(container_message) > 100 else ''}\n"
                        alert_body += "-" * 40 + "\n"

                    # Send single aggregated notification
                    notifier.send_alert(
                        pod_name="Multiple Pods",
                        namespace="Multiple",
                        phase="Various",
                        reason=f"{len(unhealthy)} pods unhealthy",
                        message=alert_body
                    )
                else:
                    print("   OK All pods recovered")

        # Step 6: Log run results
        print("\n Step 6: Logging run results...")
        run_end_time = datetime.now()
        duration = (run_end_time - run_start_time).total_seconds()

        log_entry = {
            "run_count": run_count,
            "start_time": run_start_time.isoformat(),
            "end_time": run_end_time.isoformat(),
            "duration_seconds": duration,
            "unhealthy_pods_count": unhealthy_count,
            "restart_success": restart_result['success'] if unhealthy_count > 0 else 0,
            "restart_failed": restart_result['failed'] if unhealthy_count > 0 else 0
        }
        print(f"   Run log: {log_entry}")

        # Step 7: Wait for next run
        print("\n Step 7: Waiting for next run...")
        print(f"   Interval: {Config.RUN_INTERVAL_SECONDS} seconds")
        print(f"   Next run: Every 10 minutes\n")

        # Wait 10 minutes
        elapsed = (datetime.now() - run_start_time).total_seconds()
        sleep_time = max(0, Config.RUN_INTERVAL_SECONDS - elapsed)
        time.sleep(sleep_time)


if __name__ == "__main__":
    """
    Program entry point
    """
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n User interrupted, exiting")
    except Exception as e:
        print(f"\nERROR Program crashed: {e}")
        raise
