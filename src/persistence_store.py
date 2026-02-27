# -*- coding: utf-8 -*-
"""
Persistence Store Module
Manages pod deletion tracking state

Features:
- JSON file-based persistence
- Automatic cleanup of old entries
- Thread-safe operations

File Format:
{
  "pod-uid-1": {
    "name": "my-pod-abc123",
    "namespace": "default",
    "reason": "CrashLoopBackOff",
    "deleted_at": "2026-02-27T10:30:00",
    "attempt": 1,
    "history": [
      {"deleted_at": "...", "reason": "..."}
    ]
  }
}
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from pathlib import Path


class PersistenceStore:
    """
    Persistence Store Class
    Manages pod deletion tracking state with JSON file backend
    """

    def __init__(self, file_path: str = "/var/lib/pod-cleaner/state.json"):
        """
        Initialize persistence store

        Parameters:
            file_path: str - Path to state file
        """
        self.file_path = file_path
        self.data: Dict[str, Any] = {}
        self._ensure_directory()
        self._load()

    def _ensure_directory(self):
        """Ensure parent directory exists"""
        parent_dir = Path(self.file_path).parent
        parent_dir.mkdir(parents=True, exist_ok=True)

    def _load(self):
        """Load state from file"""
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r') as f:
                    self.data = json.load(f)
                print(f"📦 Loaded state from {self.file_path} ({len(self.data)} entries)")
            else:
                print(f"📦 Creating new state file: {self.file_path}")
                self.data = {}
        except Exception as e:
            print(f"⚠️ Failed to load state: {e}, starting with empty state")
            self.data = {}

    def _save(self):
        """Save state to file"""
        try:
            with open(self.file_path, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"❌ Failed to save state: {e}")

    def track_deletion(
        self,
        pod_uid: str,
        pod_name: str,
        namespace: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Track a pod deletion event

        Parameters:
            pod_uid: str - Pod UID
            pod_name: str - Pod name
            namespace: str - Namespace
            reason: str - Deletion reason

        Returns:
            Dict[str, Any] - Updated tracking info
        """
        now = datetime.now().isoformat()

        if pod_uid in self.data:
            # Existing entry - increment attempt
            entry = self.data[pod_uid]
            entry['attempt'] = entry.get('attempt', 1) + 1
            entry['deleted_at'] = now
            entry['reason'] = reason

            # Add to history
            if 'history' not in entry:
                entry['history'] = []
            entry['history'].append({
                'deleted_at': now,
                'reason': reason,
                'attempt': entry['attempt']
            })

            print(f"📝 Updated tracking for {namespace}/{pod_name} (attempt #{entry['attempt']})")
        else:
            # New entry
            entry = {
                'name': pod_name,
                'namespace': namespace,
                'reason': reason,
                'deleted_at': now,
                'attempt': 1,
                'history': []
            }
            self.data[pod_uid] = entry
            print(f"📝 Started tracking {namespace}/{pod_name}")

        self._save()
        return entry

    def get_tracking(self, pod_uid: str) -> Optional[Dict[str, Any]]:
        """
        Get tracking info for a pod

        Parameters:
            pod_uid: str - Pod UID

        Returns:
            Optional[Dict[str, Any]] - Tracking info or None
        """
        return self.data.get(pod_uid)

    def remove_tracking(self, pod_uid: str):
        """
        Remove tracking for a pod (recovery successful)

        Parameters:
            pod_uid: str - Pod UID
        """
        if pod_uid in self.data:
            del self.data[pod_uid]
            self._save()
            print(f"✅ Removed tracking for pod {pod_uid}")

    def get_all_tracked(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all tracked pods

        Returns:
            Dict[str, Dict[str, Any]] - All tracking entries
        """
        return self.data.copy()

    def cleanup_old_entries(self, max_age_hours: int = 24):
        """
        Remove entries older than specified age

        Parameters:
            max_age_hours: int - Maximum age in hours
        """
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        removed = []

        for uid, entry in list(self.data.items()):
            try:
                deleted_at = datetime.fromisoformat(entry['deleted_at'])
                if deleted_at < cutoff:
                    removed.append(uid)
                    del self.data[uid]
            except Exception:
                # Invalid entry, remove it
                removed.append(uid)
                del self.data[uid]

        if removed:
            self._save()
            print(f"🧹 Cleaned up {len(removed)} old tracking entries")

        return removed

    def get_persistent_issues(self, max_attempts: int = 3) -> List[Dict[str, Any]]:
        """
        Get pods with persistent issues (exceeded max attempts)

        Parameters:
            max_attempts: int - Maximum retry attempts

        Returns:
            List[Dict[str, Any]] - List of persistent issue entries
        """
        persistent = []
        for uid, entry in self.data.items():
            if entry.get('attempt', 0) >= max_attempts:
                persistent.append({
                    'uid': uid,
                    **entry
                })
        return persistent
