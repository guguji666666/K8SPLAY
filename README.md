# Pod Cleaner — Kubernetes Pod Auto-Cleanup Tool

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
- 🔁 Optional “recovery check” after restart (if implemented in code)

---

## 🧠 Detection Logic (What counts as “unhealthy”?)

Pod Cleaner focuses on pods that appear “normal” at a glance but are actually broken:

- Pod in `Running`/`Init` **but** container state is:
  - `waiting` with reasons like `CrashLoopBackOff`, `ImagePullBackOff`, etc.
  - `terminated` with non-zero exit code
- Restart count spikes / repeated abnormal states (based on your logic)

> This avoids the common trap: **phase == Running** doesn’t mean the container is healthy.

---

## 🚫 Exclusion Rules

- Skip namespace: `kube-system`
- Only evaluate pods in: `Running` and `Init` (as per your current design)

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---:|---|---|
| `BARK_BASE_URL` | ✅ Yes (if Bark enabled) | - | Bark push base URL with device key |
| `BARK_ENABLED` | No | `true` | Enable/disable Bark notifications |
| `LOG_LEVEL` | No | `INFO` | `DEBUG/INFO/WARNING/ERROR` |
| `RUN_INTERVAL_SECONDS` | No | `600` | Interval between runs in seconds |

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

Pod Cleaner can send push notifications via Bark.

### Use Public Bark

Install **Bark** from the iOS App Store, get your device key, then set:

```bash
export BARK_BASE_URL="https://api.day.app/YOUR_DEVICE_KEY"
export BARK_ENABLED="true"
```

### Self-host Bark Server (Docker Compose)

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

### 1) `test-detection-logic.py` — Detection Logic Validator

Validates pod health detection logic without a real cluster (and optionally against a real cluster).

```bash
# Run logic tests only
python3 test-detection-logic.py

# Check real cluster
python3 test-detection-logic.py --k8s

# Check a namespace
python3 test-detection-logic.py --k8s -n test-failed-pods
```

Covered cases:

* CrashLoopBackOff (waiting)
* ImagePullBackOff (waiting)
* Abnormal terminated (exitCode != 0)
* Normal running / normal terminated (exitCode 0)

### 2) `test-always-failed-pods.yaml` — Always-failing pods

Creates a pod that exits with code `1` after 10 seconds, producing CrashLoopBackOff.

```bash
kubectl apply -f test-always-failed-pods.yaml
kubectl get pods -n test-failed-pods -w
```

Expected:

```text
STATUS: CrashLoopBackOff
RESTARTS: keeps increasing
```

---

## ☸️ Kubernetes Deployment

### Method A: Helm (Recommended)

```bash
helm install pod-cleaner ./helm/pod-cleaner \
  --set image.repository=YOUR_REGISTRY/pod-cleaner \
  --set image.tag=v2.6.0 \
  --set config.barkBaseUrl="https://your-bark-server.com/DEVICE_KEY" \
  --set config.barkEnabled=true \
  --set config.logLevel="INFO"

kubectl get deployment pod-cleaner
kubectl logs -l app=pod-cleaner -f
```

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

## 🧩 Interview Highlights (Design Talking Points)

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

## 🗺️ Roadmap

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

## 📄 License

MIT

