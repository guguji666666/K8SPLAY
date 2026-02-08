#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# Pod Cleaner Main Program - Orchestration Entry Point
# =============================================================================
# This is the main entry point for the Pod Cleaner application.
#
# WHAT THIS PROGRAM DOES:
# 1. Initializes all components (K8s client, notification service)
# 2. Runs an infinite loop that:
#    a. Gets all namespaces
#    b. Finds unhealthy pods
#    c. Restarts unhealthy pods
#    d. Sends cleanup reports
#    e. Verifies pod recovery (Bonus)
#    f. Waits for next run
#
# FILE STRUCTURE:
# - Imports: Standard library + local modules
# - setup_logging(): Configure logging system
# - format_pod_list(): Format pod list for display
# - main(): Main orchestration loop
#
# PROGRAM FLOW:
#   START
#     ↓
#   Initialize K8s client (kube_client.py)
#     ↓
#   Initialize notifier (notifier.py)
#     ↓
#   WHILE TRUE (infinite loop):
#     ├─ Step 1: Get namespaces
#     ├─ Step 2: Find unhealthy pods
#     ├─ Step 3: Restart unhealthy pods
#     ├─ Step 4: Send cleanup report
#     ├─ Step 5: Verify recovery (polling)
#     ├─ Step 6: Log run results
#     └─ Step 7: Wait for next run
#     ↓
#   END (never reached, Ctrl+C to stop)
#
# RELATED FILES:
# - kube_client.py: Kubernetes API operations
# - notifier.py: Bark notification service
# - config.py: Configuration settings
# =============================================================================

# -----------------------------------------------------------------------------
# STANDARD LIBRARY IMPORTS
# -----------------------------------------------------------------------------
# 'time' module: Time-related functions
# - time.sleep(): Pause execution for specified seconds
import time

# 'logging' module: Python's built-in logging system
# - logging.basicConfig(): Configure logging format and level
# - Used instead of print() for production-grade logging
import logging

# 'datetime' module: Date/time handling
# - datetime.now(): Get current date/time
# - Used for timestamps in logging
from datetime import datetime

# 'typing' module: Type hints
# - List[T]: List of type T
# - Dict[K, V]: Dictionary with key/value types
from typing import List, Dict


# -----------------------------------------------------------------------------
# LOCAL IMPORTS
# -----------------------------------------------------------------------------
# Import from sibling modules (same src/ directory)
#
# kube_client.py:
# - KubernetesClient: Main class for K8s operations
# - Used to: get namespaces, find unhealthy pods, restart pods
from kube_client import KubernetesClient

# notifier.py:
# - BarkNotifier: Notification service class
# - Used to: send cleanup reports and alerts
from notifier import BarkNotifier

# config.py:
# - Config: Configuration class
# - Used to: get log level, run interval, etc.
from config import Config


# =============================================================================
# LOGGING SETUP FUNCTION
# =============================================================================
# CONCEPT: Why configure logging instead of using print()?
# - Logging can be directed to files, syslog, etc.
# - Supports different severity levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
# - Can be filtered (e.g., only show WARNING and above)
# - Standard practice in production software
#
# LOGGING vs PRINT:
# - print() goes to stdout only
# - logging can go to files, network, multiple destinations
# - logging supports severity filtering
# - logging has timestamps and metadata built-in
#
# RELATED:
# - Config.get_log_level(): Gets log level from environment/config
# - Config.LOG_FORMAT: Format string for timestamps
def setup_logging():
    """
    Configure the Python logging system.

    WHAT THIS CODE DOES:
    1. Gets desired log level from config (default INFO)
    2. Calls basicConfig() to set up logging
    3. Sets format: "TIMESTAMP - LEVEL - MESSAGE"

    LOGGING LEVELS:
    - DEBUG: Detailed debugging info (most verbose)
    - INFO: General operational messages
    - WARNING: Issues that don't prevent operation
    - ERROR: Errors that may affect operation
    - CRITICAL: Severe errors, program may terminate

    EXAMPLE OUTPUT:
        2026-02-08 14:30:45 - INFO - Found 3 unhealthy pods
        2026-02-08 14:30:46 - WARNING - Pod restart failed: my-app-abc123

    RELATED:
    - Called by: main() at startup
    - Config values: LOG_LEVEL, LOG_FORMAT
    """
    # Get log level from config (or default)
    log_level = Config.get_log_level()

    # Configure logging system
    # - level: Minimum severity to log
    # - format: Template for each log message
    # - datefmt: Format for timestamp
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt=Config.LOG_FORMAT,
    )


# =============================================================================
# POD LIST FORMATTING FUNCTION
# =============================================================================
def format_pod_list(pods: List[Dict]) -> str:
    """
    Format a list of pods as a readable string.

    PURPOSE:
    - Converts list of pod dictionaries to formatted string
    - Used for logging and display

    PARAMETERS:
    - pods: List of pod dictionaries (from find_unhealthy_pods)

    WHAT THIS CODE DOES:
    1. If list is empty, return "None"
    2. For each pod, format as "  - namespace/name (phase)"
    3. Join all lines with newlines

    EXAMPLE INPUT:
        [
            {"name": "app-pod", "namespace": "default", "phase": "Running"},
            {"name": "db-pod", "namespace": "production", "phase": "Failed"}
        ]

    EXAMPLE OUTPUT:
        "  - default/app-pod (Running)
         - production/db-pod (Failed)"

    RELATED:
    - Called by: (currently not used, reserved for future)
    - Input from: find_unhealthy_pods() in kube_client.py
    """
    # Handle empty list
    if not pods:
        return "None"

    # Format each pod
    lines = []
    for pod in pods:
        lines.append(f"  - {pod['namespace']}/{pod['name']} ({pod['phase']})")

    # Join with newlines
    return "\n".join(lines)


# =============================================================================
# MAIN FUNCTION - Program Entry Point
# =============================================================================
# CONCEPT: What is the main function?
# - Entry point for the program
# - All scripts should have a main() function
# - Allows importing without running (if __name__ == "__main__": guard)

def main():
    """
    Main orchestration function - program entry point.

    PROGRAM STRUCTURE:
    This function runs the entire cleanup workflow:
    1. Initialize components
    2. Enter infinite loop:
       - Get namespaces
       - Find unhealthy pods
       - Restart pods
       - Send notifications
       - Verify recovery
       - Log results
       - Wait for next run

    STEP-BY-STEP FLOW:

    Step 1: Get Namespaces
    -------------
    - Call: kube_client.get_all_namespaces()
    - Returns: List of namespace names
    - Used in: All subsequent steps

    Step 2: Find Unhealthy Pods
    -----------------------
    - Call: kube_client.find_unhealthy_pods(namespaces)
    - Returns: List of pods needing restart
    - Detection logic:
      * Pod phase not in Running/Init/Succeeded
      * Container in CrashLoopBackOff
      * Container terminated with non-zero exit code

    Step 3: Restart Unhealthy Pods
    ----------------------------
    - Call: kube_client.restart_pods(unhealthy_pods)
    - Returns: Statistics (success/failed counts)
    - Effect: Deletes pods, triggering ReplicaSet recreation

    Step 4: Send Cleanup Report
    -------------------------
    - Call: notifier.send_cleanup_report()
    - Sends: Summary of cleanup results
    - Content: Success count, failed count, details

    Step 5: Verify Recovery (Bonus)
    ----------------------------
    - Call: kube_client.wait_for_pods_ready()
    - Features:
      * Polls pods at intervals
      * Early exit if all recovered
      * Budget protection (max wait time)
    - Cluster-size awareness:
      * SMALL (≤50 ns): 180s budget, 30s interval
      * MEDIUM (≤200 ns): 150s budget, 30s interval
      * LARGE (>200 ns): 120s budget, 60s interval

    Step 6: Log Results
    ----------------
    - Creates structured log entry with run statistics
    - Used for: Monitoring, debugging, analysis

    Step 7: Wait for Next Run
    ------------------------
    - Calculates sleep time based on run duration
    - Sleeps for remaining time to maintain 10-minute cadence
    - Minimum sleep guard: 30 seconds

    ERROR HANDLING:
    - KeyboardInterrupt (Ctrl+C): Clean exit
    - Exception: Log error and re-raise

    RELATED:
    - Called by: if __name__ == "__main__": guard at bottom
    - Imports: KubernetesClient, BarkNotifier, Config
    """
    # ==========================================================================
    # INITIALIZATION PHASE
    # ==========================================================================
    
    # Print startup banner
    print("\n" + "=" * 60)
    print(" Pod Cleaner Started")
    print("=" * 60 + "\n")

    # Configure logging system
    # This sets up the logging module with configured level/format
    setup_logging()

    # Initialize Kubernetes client
    # This:
    # - Tries in-cluster config first (production)
    # - Falls back to local kubeconfig (development)
    # - Creates CoreV1Api instance for API calls
    print(" Initializing Kubernetes client...")
    kube_client = KubernetesClient()

    # Initialize notification service
    # This:
    # - Gets Bark URL from config
    # - Checks if notifications are enabled
    print(" Initializing Bark notifier...")
    notifier = BarkNotifier()

    print("\nOK Initialization complete, starting...\n")

    # Initialize run counter
    # Tracks how many cleanup cycles have run
    run_count = 0

    # ==========================================================================
    # MAIN INFINITE LOOP
    # ==========================================================================
    while True:
        # Increment run counter
        run_count += 1
        run_start_time = datetime.now()

        # Print run header
        print("=" * 60)
        print(f" Run #{run_count}")
        print(f" Start time: {run_start_time.strftime(Config.LOG_FORMAT)}")
        print("=" * 60)

        # ======================================================================
        # STEP 1: GET ALL NAMESPACES
        # ======================================================================
        print("\n Step 1: Getting namespaces...")
        
        # Call kube_client to get all namespaces
        # Returns: List of namespace name strings
        namespaces = kube_client.get_all_namespaces()
        
        print(f"   Found {len(namespaces)} namespaces")

        # ======================================================================
        # STEP 2: FIND UNHEALTHY PODS
        # ======================================================================
        print("\n Step 2: Finding unhealthy pods...")
        
        # Call kube_client to find pods needing restart
        # Checks: phase, container states
        # Returns: List of pod dictionaries with details
        unhealthy_pods = kube_client.find_unhealthy_pods(namespaces)
        
        unhealthy_count = len(unhealthy_pods)

        # ======================================================================
        # INITIALIZE RESULT VARIABLES
        # ======================================================================
        # These must be initialized before the if-else
        # They have default values for when there are no unhealthy pods
        
        # restart_result: Statistics from restart operation
        # Structure: {"success": int, "failed": int, "details": [...]}
        restart_result = {"success": 0, "failed": 0, "details": []}
        
        # recovery_result: Results from recovery verification
        # Structure: {"still_unhealthy": [...], "all_recovered": bool}
        recovery_result = {"still_unhealthy": [], "all_recovered": True}

        # ======================================================================
        # STEP 3: RESTART UNHEALTHY PODS (if any)
        # ======================================================================
        if unhealthy_count == 0:
            # No unhealthy pods found
            print("   OK No unhealthy pods found, no cleanup needed")
        else:
            # Found unhealthy pods
            print(f"   WARNING Found {unhealthy_count} unhealthy pod(s)")

            # Restart all unhealthy pods
            print("\n Step 3: Restarting unhealthy pods...")
            
            # Call kube_client to restart pods
            # This deletes each pod, triggering ReplicaSet recreation
            restart_result = kube_client.restart_pods(unhealthy_pods)
            
            # Print statistics
            print(
                f"   Success: {restart_result['success']}, Failed: {restart_result['failed']}"
            )

            # ==================================================================
            # STEP 4: SEND CLEANUP REPORT
            # ==================================================================
            print("\n Step 4: Sending cleanup report...")
            
            # Only send if notifications are enabled
            if notifier.enabled:
                notifier.send_cleanup_report(
                    cleaned_count=restart_result["success"],
                    failed_count=restart_result["failed"],
                    details=restart_result["details"],
                )

            # ==================================================================
            # STEP 5: VERIFY POD RECOVERY (Bonus Feature)
            # ==================================================================
            # Only verify if we actually restarted some pods
            if restart_result["success"] > 0:
                print("\n Step 5: Verifying pod recovery (polling mode)...")

                # --- CLUSTER SIZE DETECTION ---
                # Determine cluster size based on namespace count
                # This helps set appropriate time budgets
                ns_count = len(namespaces)

                if ns_count <= 50:
                    # SMALL CLUSTER
                    cluster_tier = "SMALL"
                    RECOVERY_BUDGET_SECONDS = 180  # 3 minutes
                    CHECK_INTERVAL_SECONDS = 30     # Check every 30s
                    
                elif ns_count <= 200:
                    # MEDIUM CLUSTER
                    cluster_tier = "MEDIUM"
                    RECOVERY_BUDGET_SECONDS = 150  # 2.5 minutes
                    CHECK_INTERVAL_SECONDS = 30     # Check every 30s
                    
                else:
                    # LARGE CLUSTER
                    # Larger budget to avoid false positives
                    cluster_tier = "LARGE"
                    RECOVERY_BUDGET_SECONDS = 120  # 2 minutes
                    CHECK_INTERVAL_SECONDS = 60     # Check every 60s

                # Print strategy
                print(f"   Cluster tier: {cluster_tier} (namespaces={ns_count})")
                print(
                    f"   Budget: {RECOVERY_BUDGET_SECONDS}s, Poll interval: {CHECK_INTERVAL_SECONDS}s"
                )

                # --- CALL RECOVERY VERIFICATION ---
                # Call kube_client to verify pod recovery with polling
                # This:
                # - Checks pods at intervals
                # - Exits early if all recovered
                # - Returns list of still-unhealthy pods
                recovery_result = kube_client.wait_for_pods_ready(
                    namespaces=namespaces,
                    check_interval=CHECK_INTERVAL_SECONDS,
                    max_wait_time=RECOVERY_BUDGET_SECONDS,
                )

                # --- HANDLE RECOVERY RESULTS ---
                if not recovery_result["all_recovered"]:
                    # Some pods still unhealthy after restart
                    unhealthy = recovery_result["still_unhealthy"]
                    print(
                        f"   WARNING: Found {len(unhealthy)} pod(s) still unhealthy after restart"
                    )

                    # Build alert message
                    alert_body = (
                        f"The following pods are still unhealthy after restart "
                        f"(verification budget={RECOVERY_BUDGET_SECONDS}s, poll={CHECK_INTERVAL_SECONDS}s):\n\n"
                    )

                    # Add details for each unhealthy pod
                    for pod in unhealthy:
                        # Get container reason and message
                        container_reason = pod.get("container_reason", "Unknown")
                        container_message = pod.get("container_message", "No message")

                        # Format pod info
                        alert_body += (
                            f"Pod: {pod['namespace']}/{pod['name']}\n"
                            f"Phase: {pod.get('phase', 'Unknown')}\n"
                            f"Container Reason: {container_reason}\n"
                            f"Details: {container_message[:100]}{'...' if len(container_message) > 100 else ''}\n"
                            + "-" * 40
                            + "\n"
                        )

                    # Send alert notification
                    notifier.send_alert(
                        pod_name="Multiple Pods",
                        namespace="Multiple",
                        phase="Various",
                        reason=f"{len(unhealthy)} pods still unhealthy",
                        message=alert_body,
                    )
                else:
                    # All pods recovered successfully
                    print("   OK All restarted pods recovered successfully")
            else:
                # No pods were successfully restarted
                print(
                    "\n Step 5: Skipped recovery check (no pods restarted successfully)"
                )

        # ======================================================================
        # STEP 6: LOG RUN RESULTS
        # ======================================================================
        print("\n Step 6: Logging run results...")

        # Calculate run duration
        run_end_time = datetime.now()
        duration_seconds = (run_end_time - run_start_time).total_seconds()

        # Create structured log entry
        # This is useful for monitoring and debugging
        log_entry = {
            "run_count": run_count,
            "start_time": run_start_time.isoformat(),
            "end_time": run_end_time.isoformat(),
            "duration_seconds": duration_seconds,
            "namespaces_count": len(namespaces),
            "unhealthy_pods_count": unhealthy_count,
            "restart_success": restart_result["success"],
            "restart_failed": restart_result["failed"],
            "all_recovered": recovery_result.get("all_recovered", True),
            "still_unhealthy_count": len(recovery_result.get("still_unhealthy", [])),
        }

        # Print log entry
        print(f"   Run log: {log_entry}")

        # ======================================================================
        # STEP 7: WAIT FOR NEXT RUN
        # ======================================================================
        print("\n Step 7: Waiting for next run...")
        print(f"   Target interval: {Config.RUN_INTERVAL_SECONDS} seconds\n")

        # Calculate elapsed time
        elapsed = (datetime.now() - run_start_time).total_seconds()

        # Calculate sleep time
        # sleep_time = interval - elapsed
        sleep_time = Config.RUN_INTERVAL_SECONDS - elapsed

        # Minimum sleep guard
        # Prevents tight loops if something goes wrong
        MIN_SLEEP_SECONDS = 30

        if sleep_time <= 0:
            # Run took longer than target interval
            # Use minimum sleep to avoid hammering API
            sleep_time = MIN_SLEEP_SECONDS
            print(
                f"   ⚠️ Run exceeded interval (elapsed={elapsed:.2f}s). Min sleep: {MIN_SLEEP_SECONDS}s."
            )
        else:
            # Normal case: sleep the remainder
            # Enforce minimum to prevent tight loops
            sleep_time = max(MIN_SLEEP_SECONDS, sleep_time)

        # Print and execute sleep
        print(f"   Sleeping: {sleep_time:.2f}s\n")
        time.sleep(sleep_time)


# =============================================================================
# PROGRAM ENTRY POINT GUARD
# =============================================================================
# CONCEPT: What is if __name__ == "__main__": ?
# - When Python runs a script, it sets __name__ = "__main__"
# - When Python imports a module, __name__ = module name
# - This guard allows code to be imported without running
#
# EXAMPLE:
#     $ python main.py          # __name__ = "__main__", runs main()
#     $ python -c "import main" # __name__ = "main", doesn't run main()
#
# This is standard Python practice for reusable modules

if __name__ == "__main__":
    """
    Program entry point.

    WHAT THIS CODE DOES:
    1. Calls main() function
    2. Catches KeyboardInterrupt (Ctrl+C)
    3. Catches other exceptions and re-raises

    ERROR HANDLING:
    - KeyboardInterrupt: Clean exit with message
    - Exception: Log error and re-raise (traceback for debugging)

    RELATED:
    - main(): The main orchestration function above
    """
    try:
        main()
    except KeyboardInterrupt:
        # User pressed Ctrl+C
        print("\n\n User interrupted, exiting")
    except Exception as e:
        # Unexpected error
        print(f"\nERROR Program crashed: {e}")
        raise
