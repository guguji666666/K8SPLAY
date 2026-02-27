# Pod Cleaner - Kubernetes Pod Auto-Cleanup Tool

A lightweight Kubernetes utility that **detects abnormal pods (even when phase is `Running`)** and **forces a restart by deleting the pod** (ReplicaSet/Deployment will recreate it).
Optional: send **Bark** notifications with detailed failure reasons.

---

## 🎯 Why Pod Cleaner?

| Pain Point | What Pod Cleaner Does |
|---|---|
| CrashLoopBackOff keeps restarting but never recovers | Detects + deletes the pod to trigger a clean recreation |
| Pod phase shows `Running` but container is actually crashed | Checks **pod phase + container state** (waiting/terminated) |
| Manual monitoring is required | Runs automatically on an interval (default **10 minutes**) |
| No visibility into pod issues | Sends Bark alerts with reason/message/restart count |
| Testing requires a real cluster | Provides local test scripts to validate detection logic |
| Notification config gets hardcoded | Uses env vars (`BARK_BASE_URL`, `BARK_ENABLED`) |
| Large clusters (10k+ pods) are slow to scan | Uses pagination (`limit=500`) to reduce API pressure |

---

## ✨ Features

### Core
- ✅ Periodic execution (default every **600s / 10min**)
- ✅ Detect unhealthy pods beyond phase checks
- ✅ Restart unhealthy pods by deletion (controller will recreate)
- ✅ Logs every detection + cleanup action
- ✅ Optimized for large clusters with pagination

### Bonus
- 🛎️ Bark push notifications with detailed context
- 🔁 **Recovery Verification** - Automatically verify pod health after restart
- 🚨 **Persistent Issue Detection** - Detect and escalate pods that fail repeatedly
- 📊 **Recovery Reports** - Get summary notifications after each verification cycle

---

## 🧠 Detection Logic (What counts as "unhealthy"?)

Pod Cleaner focuses on pods that appear "normal" at a glance but are actually broken:

- Pod in `Running`/`Init` **but** container state is:
  - `waiting` with reasons like `CrashLoopBackOff`, `ImagePullBackOff`, etc.
  - `terminated` with non-zero exit code
- Restart count spikes / repeated abnormal states (based on your logic)

> This avoids the common trap: **phase == Running** doesn't mean the container is healthy.

---

## 🚫 Exclusion Rules

- Skip namespace: `kube-system`
- Only evaluate pods in: `Running` and `Init` (as per current design)

---

## 🔄 Recovery Verification (NEW!)

Pod Cleaner now includes **automatic recovery verification** to close the monitoring loop:

### How It Works

1. **Track Deletion**: When an unhealthy pod is deleted, Pod Cleaner records:
   - Pod name, namespace, UID
   - Failure reason
   - Deletion timestamp
   - Attempt count

2. **Wait for Recreation**: Waits for the controller (Deployment/ReplicaSet) to create a new pod

3. **Verify Health**: Checks if the new pod is healthy:
   - ✅ **Healthy**: Removes tracking, sends success notification
   - ⚠️ **Still Unhealthy**: Increments attempt counter
   - 🔥 **Persistent Issue** (≥3 attempts): Sends escalation alert with full history

4. **Cleanup**: Automatically removes old tracking entries (>24h)

### Benefits

- **Prevents Infinite Loops**: Detects when auto-restart isn't solving the problem
- **Escalation Alerts**: Notifies you when manual intervention is needed
- **Historical Context**: Includes full restart history in escalation alerts
- **Automatic Cleanup**: No manual state management required

### Configuration

| Variable | Default | Description |
|---|---|---|
| `RECOVERY_CHECK_ENABLED` | `true` | Enable/disable recovery verification |
| `RECOVERY_WAIT_SECONDS` | `120` | Wait time for new pod creation |
| `RECOVERY_MAX_ATTEMPTS` | `3` | Max retries before escalation |
| `RECOVERY_CHECK_INTERVAL` | `10` | Check interval when waiting |
| `PERSISTENCE_FILE` | `/var/lib/pod-cleaner/state.json` | State file path |
| `PERSISTENCE_MAX_AGE_HOURS` | `24` | Cleanup old entries after |

### Example Escalation Alert

```
🔥 ESCALATION: my-app-pod-abc123

Pod: default/my-app-pod-abc123
Attempt: 3
Reason: CrashLoopBackOff
First detected: 2026-02-27T10:30:00

📋 History (3 restarts):
  1. 2026-02-27T10:30:00 - CrashLoopBackOff
  2. 2026-02-27T10:35:00 - CrashLoopBackOff
  3. 2026-02-27T10:40:00 - CrashLoopBackOff

⚠️ Manual intervention required
🔧 Check pod configuration, logs, and events
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---:|---|---|
| `BARK_BASE_URL` | ✅ Yes (if Bark enabled) | - | Bark push base URL with device key |
| `BARK_ENABLED` | No | `true` | Enable/disable Bark notifications |
| `LOG_LEVEL` | No | `INFO` | `DEBUG/INFO/WARNING/ERROR` |
| `RUN_INTERVAL_SECONDS` | No | `600` | Interval between runs in seconds |
| `RECOVERY_CHECK_ENABLED` | No | `true` | Enable recovery verification |
| `RECOVERY_WAIT_SECONDS` | No | `120` | Wait time for new pod (seconds) |
| `RECOVERY_MAX_ATTEMPTS` | No | `3` | Max retries before escalation |
| `PERSISTENCE_FILE` | No | `/var/lib/pod-cleaner/state.json` | State file path |

---

## 🚀 Quick Start

### 1) Local Run (Debug)

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate    # Windows

pip install -r requirements.txt

cp .env.example .env
# edit .env and set BARK_BASE_URL (optional if you disable Bark)
source .env

python src/main.py
````

### Required (if Bark enabled)

You MUST set `BARK_BASE_URL`:

```bash
# Option A: export env vars
export BARK_BASE_URL="https://your-bark-server.com/DEVICE_KEY"
export BARK_ENABLED="true"
python src/main.py

# Option B: one-liner
BARK_BASE_URL="https://your-bark-server.com/DEVICE_KEY" \
BARK_ENABLED="true" \
python src/main.py
```

### kubeconfig note

During local debugging, the Kubernetes Python client loads kubeconfig from your machine:

```bash
kubectl config current-context
kubectl config view
```

---

## 🛎️ Bark Notifications (Optional)
### [Bark github](https://github.com/Finb/bark-server)
### [Bark request methods](https://bark.day.app/#/en-us/tutorial?id=request-methods)

Pod Cleaner can send push notifications via Bark.

### Use Public Bark

Install **Bark** from the iOS App Store, get your device key, then set:

```bash
export BARK_BASE_URL="https://api.day.app/YOUR_DEVICE_KEY"
export BARK_ENABLED="true"
```

### Self-host Bark Server (Docker Compose) for quick test

```yaml
version: "3.8"
services:
  bark-server:
    image: finab/bark-server
    container_name: bark-server
    restart: always
    volumes:
      - ./data:/data
    ports:
      - "8080:8080"
```

```bash
docker compose up -d
# then open: http://localhost:8080 to get your device key
```

### Quick test

```bash
curl -X POST "${BARK_BASE_URL}" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","body":"Pod Cleaner test notification"}'
```

---

## 🐳 Docker Build & Run (Single Instance Testing)

**Goal:** run Pod Cleaner in Docker without Helm/K8s deployment.

### Option A: Build & Run

```bash
docker build -t pod-cleaner:latest .

docker run -d \
  --name pod-cleaner \
  -e BARK_BASE_URL="https://your-bark-server.com/DEVICE_KEY" \
  -e BARK_ENABLED="true" \
  -e LOG_LEVEL="INFO" \
  -v ~/.kube/config:/root/.kube/config:ro \
  pod-cleaner:latest

docker logs -f pod-cleaner
```

### Option B: Pre-built Image

```bash
docker run -d \
  --name pod-cleaner \
  -e BARK_BASE_URL="https://your-bark-server.com/DEVICE_KEY" \
  -e BARK_ENABLED="true" \
  -v ~/.kube/config:/root/.kube/config:ro \
  guguji666/pod-cleaner:v2.6
```

**Windows kubeconfig mount example**

```bash
docker run -d ^
  --name pod-cleaner ^
  -e BARK_BASE_URL="https://your-bark-server.com/DEVICE_KEY" ^
  -e BARK_ENABLED="true" ^
  -v C:\Users\YOUR_USER\.kube\config:/root/.kube/config:ro ^
  guguji666/pod-cleaner:v2.6
```

---

## 🧪 Testing

### 1) `test-detection-logic.py` - Detection Logic Validator

Validates pod health detection logic without a real cluster (and optionally against a real cluster).

```bash
# Run logic tests only
python3 test-detection-logic.py

# Check real cluster
python3 test-detection-logic.py --k8s

# Check a namespace
python3 test-detection-logic.py --k8s -n test-failed-pods
```

screenshot for `python3 test-detection-logic.py --k8s` <br>
<img width="1158" height="486" alt="image" src="https://github.com/user-attachments/assets/f760f79c-8a36-4609-bc00-9aeec9916825" />

Covered cases:

* CrashLoopBackOff (waiting)
* ImagePullBackOff (waiting)
* Abnormal terminated (exitCode != 0)
* Normal running / normal terminated (exitCode 0)

screenshot for Step 4: Send cleanup notification after restarting unhealthy pods in main.py <br>
<img width="1206" height="2622" alt="image" src="https://github.com/user-attachments/assets/3c8509fd-2a6e-4224-afc0-9f7623b8ebc4" />

screenshot for Step 5: trigger notifications if some pods still failed to start  in main.py <br>
<img width="1206" height="2622" alt="image" src="https://github.com/user-attachments/assets/f04a327e-3254-4da8-a6d1-af02485acccb" />

### 2) `test-always-failed-pods.yaml` — Always-failing pods

Creates a pod that exits with code `1` after 10 seconds, producing CrashLoopBackOff.

```bash
kubectl apply -f test-always-failed-pods.yaml
kubectl get pods -n test-failed-pods -w
```

### 3) `test-recovery-feature.py` - Recovery Verification Tests (NEW!)

Tests the recovery verification functionality:

```bash
# Run unit tests (no cluster required for basic tests)
python3 test-recovery-feature.py

# Tests cover:
# - Persistence store (track deletion, increment attempts, cleanup)
# - Recovery checker (health detection, persistent issue detection)
# - Integration test outline (requires cluster)
```

### 4) Full Recovery Flow Test

To test the complete recovery verification flow:

```bash
# 1. Create a failing pod
kubectl apply -f test-always-failed-pods.yaml

# 2. Run Pod Cleaner
python src/main.py

# 3. Watch the logs:
# - First deletion: tracked (attempt #1)
# - Recovery check: new pod still unhealthy
# - Second deletion: tracked (attempt #2)
# - Third deletion: tracked (attempt #3)
# - Escalation: persistent issue detected!

# 4. Check notifications:
# - Cleanup report after each run
# - Escalation alert after 3 failed attempts
# - Recovery verification summary

# 5. Cleanup
kubectl delete -f test-always-failed-pods.yaml
rm /var/lib/pod-cleaner/state.json  # Reset state
```

Expected:

```text
STATUS: CrashLoopBackOff
RESTARTS: keeps increasing
```

---

## ☸️ Kubernetes Deployment

### Method A: Helm (Recommended)

if you build your own docker image
```bash
helm install pod-cleaner ./helm/pod-cleaner \
  --set image.repository=<your repo> \
  --set image.tag=<your image tag> \
  --set config.barkBaseUrl="https://your-bark-server.com/DEVICE_KEY" \
  --set config.barkEnabled=true \
  --set config.logLevel="INFO"

kubectl get deployment pod-cleaner
kubectl logs -l app=pod-cleaner -f
```

if you want to use existing docker image
```bash
helm install pod-cleaner ./helm/pod-cleaner \
  --set image.repository=guguji666/pod-cleaner \
  --set image.tag=v2.6 \
  --set config.barkBaseUrl="https://your-bark-server.com/DEVICE_KEY" \
  --set config.barkEnabled=true \
  --set config.logLevel="INFO"

kubectl get deployment pod-cleaner
kubectl logs -l app=pod-cleaner -f
```

if you want to check the logs of pod-cleaner lively
```bash
kubectl get pods
kubectl logs -f <pod id>
```
<img width="2934" height="1892" alt="image" src="https://github.com/user-attachments/assets/c437ce4c-aa28-42a5-aa1a-0574e036878b" />


### Method B: Native Manifest

```bash
# edit image in k8s-manifest.yaml first
kubectl apply -f k8s-manifest.yaml

kubectl get pods -l app=pod-cleaner
kubectl logs -l app=pod-cleaner -f
```

---

## 📁 Project Structure

```text
pod-cleaner/
├── src/
│   ├── main.py
│   ├── config.py
│   ├── kube_client.py
│   └── notifier.py
├── Dockerfile
├── requirements.txt
├── k8s-manifest.yaml
├── helm/pod-cleaner/
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── deployment.yaml
│       ├── rbac.yaml
│       └── _helpers.tpl
├── test-detection-logic.py
├── test-always-failed-pods.yaml
└── README.md
```

---

## 🧩 Design points

### 1) Large-scale performance

* Pagination (`limit=500`) to reduce API load
* Skip `kube-system`
* Optional: label selector narrowing
* Delete pods one-by-one (lower burst load on apiserver)
* Advanced idea: watch mode instead of polling

### 2) Idempotency / Safety

* Deleting a pod is idempotent for ReplicaSet-managed workloads
* Avoid cleaning the same pod repeatedly by tracking run state (if implemented)
* Optional: support dry-run mode in future

### 3) Security

* RBAC least privilege
* Never delete across all namespaces blindly
* Namespace exclusions to avoid system impact

---

## 🗺️ Roadmap for improvement in future 

* [ ] Slack webhook notifications
* [ ] Email (SMTP) notifications
* [ ] DingTalk webhook
* [ ] Severity-based routing
* [ ] Retry / backoff for notifications
* [ ] Prometheus metrics
* [ ] Health endpoints (`/health`, `/ready`)
* [ ] JSON structured logs
* [ ] Whitelist / namespace filter
* [ ] Rate-limited batch operations

---


