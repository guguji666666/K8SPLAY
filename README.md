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
- ✅ Recovery verification with polling (cluster-size aware)

---

## 🧠 Detection Logic & Recovery Verification

### Pod Health Detection

Pod Cleaner focuses on pods that appear "normal" at a glance but are actually broken:

- Pod in `Running`/`Init` **but** container state is:
  - `waiting` with reasons like `CrashLoopBackOff`, `ImagePullBackOff`, etc.
  - `terminated` with non-zero exit code

### Recovery Verification (Bonus)

After restarting unhealthy pods, the tool verifies recovery with intelligent polling:

- **Polling with early exit**: Stops checking once all pods recover
- **Cluster-size awareness**:
  - SMALL (≤50 namespaces): 180s budget, 30s interval
  - MEDIUM (≤200 namespaces): 150s budget, 30s interval
  - LARGE (>200 namespaces): 120s budget, 60s interval
- **Budget protection**: Maximum verification time prevents schedule overruns

> This avoids the common trap: **phase == Running** doesn't mean the container is healthy.

---

## 🚫 Exclusion Rules

- Skip namespace: `kube-system`
- Only evaluate pods in: `Running` and `Init` (as per current design)

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

### Self-host Bark Server (Kubernetes) for production

For production deployments, deploy Bark server to Kubernetes using the provided manifest:

```bash
# Deploy Bark server to Kubernetes
kubectl apply -f bark-server.yaml

# Check deployment status
kubectl get deployment bark-server
kubectl get svc bark-server

# Get external IP or NodePort to access the Bark UI
kubectl get svc bark-server -o jsonpath='{.spec.ports[0].nodePort}'
```

**Expected output:**
```
NAME           READY   UP-TO-DATE   AVAILABLE   AGE
bark-server    1/1     1            1           30s

NAME           TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
bark-server    NodePort   10.96.XXX.XXX   <none>        8080:30080/TCP   30s
```

**Access Bark UI:**
- If using NodePort: `http://<node-ip>:30080`
- If using LoadBalancer: `http://<loadbalancer-ip>:8080`

**Get device key:**
1. Open Bark UI in browser
2. Register device to get your device key
3. Use the key in `BARK_BASE_URL`

**Cleanup:**
```bash
kubectl delete -f bark-server.yaml
```

### Quick test

```bash
curl -X POST "${BARK_BASE_URL}" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","body":"Pod Cleaner test notification"}'
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
python3 test-detection-logic.py --k8s -n test-failures
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


### 2) `100-namespace.yaml` — Cluster Scale Simulation

Creates 100 test namespaces (`test-001` to `test-100`) to simulate cluster scale testing. Each namespace contains a simple nginx deployment.

**Purpose:** Test pod-cleaner performance and behavior under large-scale cluster conditions.

```bash
# Deploy 100 namespaces with nginx
kubectl apply -f 100-namespace.yaml

# Verify namespaces created
kubectl get ns | grep test- | head -20
# Expected: test-001, test-002, ... test-100

# Check pod distribution
kubectl get pods -n test-001  # Should show nginx deployment

# Cleanup
kubectl delete -f 100-namespace.yaml
```

**Expected observations:**

| Metric | Expected Value |
|--------|---------------|
| Namespace count | 100 (test-001 to test-100) |
| Pods per namespace | 1 nginx pod |
| Total pods | 100 nginx pods |
| Detection time | ~30-60s (depends on cluster size) |

---

### 3) `test-failure-pods.yaml` — Failure Simulation Pods

Creates 6 types of failing pods for testing pod-cleaner detection:

| Type | Failure Pattern | Pod Phase | Container State |
|------|----------------|-----------|-----------------|
| CrashLoopBackOff | Exits immediately, restarts repeatedly | Running | waiting (CrashLoopBackOff) |
| ErrorExit | Runs 30s then exits with code 1 | Running | terminated (exitCode=1) |
| InitFailure | Init container fails | Init:Error | N/A |
| Mixed | One healthy + one failing container | Running | Mixed states |
| ImagePullBackOff | Non-existent image | Pending | N/A |
| OOMKilled | Memory limit exceeded | Running | OOMKilled |

```bash
kubectl apply -f test-failure-pods.yaml
kubectl get pods -n test-failures -w
```

Expected observations:

| Pod Type | Expected Status | Restart Behavior |
|----------|----------------|-----------------|
| crashloop-pod | CrashLoopBackOff | RESTARTS increasing |
| error-exit-pod | Running → Error | RESTARTS 0→1+ |
| init-failure-pod | Init:Error | RESTARTS 1+ |
| mixed-pod | Running | One container restarting |
| image-pull-fail-pod | Pending/ImagePullBackOff | No restarts |
| oom-pod | Error/OOMKilled | RESTARTS 1+ |

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
  --set image.tag=latest \
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

## 🏗️ Architecture & Implementation


### Runtime Dependencies

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Runtime Dependencies                         │
└─────────────────────────────────────────────────────────────────────────┘

                           ┌─────────────────────┐
                           │   src/main.py       │  ← Entry point
                           └──────────┬──────────┘
                                      │
                                      │ imports
                                      ▼
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
    ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
    │  src/config.py  │   │ kube_client.py   │   │  src/notifier.py │
    │  (Configuration)│   │  (K8s Client)   │   │  (Notifications)│
    └─────────────────┘   └─────────────────┘   └─────────────────┘
              │                       │                       │
              │                       │                       │
              └───────────────────────┴───────────────────────┘
                                      │
                                      ▼
                        ┌─────────────────────────┐
                        │   Kubernetes API       │
                        │   Bark Server          │
                        └─────────────────────────┘
```

### Build & Deployment Dependencies

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Build & Deployment Flow                        │
└─────────────────────────────────────────────────────────────────────────┘

requirements.txt ──────► Dockerfile ──────► pod-cleaner:latest (Image)
      │                      │
      │                      │ references
      ▼                      ▼
┌─────────────────┐   ┌─────────────────┐
│ Python deps     │   │ Image build     │
│ - kubernetes    │   │ - Base image   │
│ - requests      │   │ - Install deps  │
└─────────────────┘   │ - Copy src/     │
                      └────────┬────────┘
                               │
                               ▼
                    ┌──────────────────────────┐
                    │   Push to registry       │
                    └──────────┬───────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │ k8s-manifest.yaml│ │ Helm values.yaml│ │ Helm Chart.yaml │
    │ (Native K8s)    │ │  (Helm params)  │ │  (Chart meta)   │
    └────────┬────────┘ └────────┬────────┘ └─────────────────┘
             │                   │
             │ references        │ references
             ▼                   ▼
    ┌─────────────────┐ ┌─────────────────────────┐
    │ Helm templates/  │ │ Image URL at deployment │
    │ - deployment.yaml │ └─────────────────────────┘
    │ - rbac.yaml     │
    └─────────────────┘

README.md (Documentation)
```

### Core Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Runtime Data Flow                            │
└─────────────────────────────────────────────────────────────────────────┘

1️⃣  STARTUP
    main.py → config.py → Read configuration (Bark URL, interval, etc.)

2️⃣  CONNECT TO CLUSTER
    main.py → kube_client.py → Kubernetes API
                                 │
                                 ▼
                         Get all namespaces

3️⃣  FIND UNHEALTHY PODS
    kube_client.py → Iterate each namespace
                      → Check each pod's phase
                      → Filter out non-Running/Init pods

4️⃣  CLEANUP PODS
    kube_client.py → delete_namespaced_pod() → Delete unhealthy pods

5️⃣  SEND NOTIFICATIONS
    main.py → notifier.py → Bark Server
                                  │
                                  ▼
                          Push notification to phone

6️⃣  CHECK RECOVERY (Bonus)
    kube_client → wait_for_pods_ready() → Wait and recheck
                  → If still unhealthy → notifier.send_alert()
```

### File Function Quick Reference

| File | Responsibility | Dependencies |
|------|----------------|--------------|
| `src/main.py` | Main loop, orchestration | Entry point (no dependencies) |
| `src/config.py` | Configuration parameters | main, kube_client, notifier |
| `kube_client.py` | Kubernetes API operations | main |
| `src/notifier.py` | Bark push notifications | main |
| `Dockerfile` | Container image build | CI/CD |
| `k8s-manifest.yaml` | Native K8s deployment | kubectl |
| `helm/*.yaml` | Helm deployment | helm |
| `README.md` | Documentation | Developers |


### Main Loop Flow Chart

```
main.py
│
├── main()                                # Program entry point
│   │
│   ├── setup_logging()                  # Initialize logging system
│   │
│   ├── KubernetesClient()               # Initialize K8s API client
│   │   └── load_incluster_config()      # Use Pod ServiceAccount for auth
│   │
│   ├── BarkNotifier()                   # Initialize notification module
│   │   └── Config.get_bark_base_url()   # Read Bark push URL from config
│   │
│   └── while True:                      # Main daemon loop
│       │
│       ├── get_all_namespaces()          # Fetch all cluster namespaces
│       │
│       ├── find_unhealthy_pods()       # Core detection logic
│       │   │
│       │   ├── should_skip_namespace()   # Exclude system namespaces (kube-system)
│       │   │
│       │   ├── is_pod_healthy()        # Pod phase screening (Running/Init/Succeeded)
│       │   │
│       │   └── check container state    # Container real status check
│       │       ├── waiting              # CrashLoopBackOff / ImagePullBackOff
│       │       └── terminated(exit!=0)  # Abnormal exit with non-zero code
│       │
│       ├── restart_pods()                # Batch self-healing (delete pods)
│       │   └── delete_pod()            # Call K8s API to delete single pod
│       │
│       ├── send_cleanup_report()        # Send cleanup execution report
│       │
│       ├── wait_for_pods_ready()       # Wait + recovery confirmation (Bonus)
│       │
│       └── send_alert()                 # Alert if pods still unhealthy
│
└── sleep(RUN_INTERVAL_SECONDS)           # Wait before next cycle
```

### Key Processing Steps

| Step | Function | Purpose |
|------|----------|---------|
| 1 | `get_all_namespaces()` | List all namespaces to inspect |
| 2 | `find_unhealthy_pods()` | Detect pods needing restart |
| 3 | `restart_pods()` | Delete unhealthy pods (trigger ReplicaSet recreation) |
| 4 | `send_cleanup_report()` | Notify cleanup summary |
| 5 | `wait_for_pods_ready()` | Verify recovery with polling |
| 6 | `send_alert()` | Alert if still unhealthy |
| 7 | `sleep()` | Maintain 10-minute cadence |



### Implementation Details

| Feature | Location | Key Code |
|---------|----------|-----------|
| **Pagination** | `src/kube_client.py:88-117` | `list_namespaced_pod(limit=500)` |
| **Skip kube-system** | `src/config.py:29` | `EXCLUDED_NAMESPACES = ["kube-system"]` |
| **Idempotency** | `src/main.py:76-127` | Re-check status every cycle |
| **RBAC Least Privilege** | `k8s-manifest.yaml:23-35` | `verbs: ["get","list","delete"]` |
| **ServiceAccount** | `k8s-manifest.yaml:8-15` | `serviceAccountName: pod-cleaner-sa` |
| **NonRoot** | `k8s-manifest.yaml:87-90` | `runAsUser: 1000`, `runAsNonRoot: true` |
| **Graceful Restart** | `src/kube_client.py:256-259` | `grace_period_seconds=0` |
| **10min Interval** | `src/config.py:41` | `RUN_INTERVAL_SECONDS = 600` |

### Code Highlights

#### 1) Pagination (kube_client.py)

```python
# Each API call returns max 500 pods
# Loop continues while _continue token exists
while True:
    resp = self.api.list_namespaced_pod(
        namespace=namespace,
        limit=500,
        _continue=continue_token  #下一页的凭证
    )
    all_pods.extend(resp.items)
    continue_token = resp.metadata._continue
    if not continue_token:
        break  # No more pages
```

#### 2) Skip kube-system (config.py)

```python
class Config:
    EXCLUDED_NAMESPACES = ["kube-system"]  # Don't touch system pods!

def should_skip_namespace(namespace: str) -> bool:
    return namespace in Config.EXCLUDED_NAMESPACES
```

#### 3) Restart with RBAC (kube_client.py)

```python
def delete_pod(self, namespace: str, pod_name: str) -> bool:
    # RBAC: requires "delete" permission on "pods" resource
    self.api.delete_namespaced_pod(
        name=pod_name,
        namespace=namespace,
        grace_period_seconds=0  # Immediate restart
    )
```

#### 4) 10-Minute Scheduler (main.py)

```python
# Calculate sleep to maintain 10-minute cadence
elapsed = (datetime.now() - run_start_time).total_seconds()
sleep_time = max(0, Config.RUN_INTERVAL_SECONDS - elapsed)
time.sleep(sleep_time)
```

---

## 🧩 Design points

### 1) Large-scale performance

* Pagination (`limit=500`) to reduce API load
* Skip `kube-system`
* Optional: label selector narrowing
* Delete pods one-by-one (lower burst load on apiserver)
* Recovery verification with polling (early exit on success)
* Cluster-size aware verification intervals

### 2) Idempotency / Safety

* Deleting a pod is idempotent for ReplicaSet-managed workloads
* Recovery verification protects against false positives
* Configurable verification budget per cluster size
* Dry-run mode support (future)

### 3) Security

* RBAC least privilege (pods: get, list, delete)
* Namespace exclusions to avoid system impact
* Non-root container execution

### 4) Observability

* Structured logging for easy parsing
* Bark notifications for critical alerts
* Recovery verification status in logs

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
├── test-failure-pods.yaml
└── README.md
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
  guguji666/pod-cleaner:latest
```

**Windows kubeconfig mount example**

```bash
docker run -d ^
  --name pod-cleaner ^
  -e BARK_BASE_URL="https://your-bark-server.com/DEVICE_KEY" ^
  -e BARK_ENABLED="true" ^
  -v C:\Users\YOUR_USER\.kube\config:/root/.kube/config:ro ^
  guguji666/pod-cleaner:latest
```

---

## 🐳 Docker Build Files

```
Files used during Docker build:
├── requirements.txt   → Installed via pip
├── Dockerfile         → Build instructions
└── src/              → Copied into image
    ├── main.py
    ├── config.py
    ├── kube_client.py
    └── notifier.py

Files NOT in image:
├── k8s-manifest.yaml  → kubectl apply -f (not in container)
├── helm/              → helm install (not in container)
├── README.md          → Documentation only
└── test-*.py          → Testing tools only
```

### RBAC Permissions Summary

```yaml
# pod-cleaner-clusterrole (k8s-manifest.yaml)
rules:
# Pod operations
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]     # Read pod status
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["delete"]          # Restart pods

# Namespace read
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list"]

# NOT granted (security):
# - create/update/patch → Can't create new pods
# - exec → Can't enter containers
# - secrets/configmaps → Can't access sensitive data
```

### Key Design Decisions

| Decision | Reason |
|----------|--------|
| Delete instead of restart | K8s has no "restart" API; deleting triggers ReplicaSet recreation |
| grace_period_seconds=0 | CrashLoopBackOff pods won't recover; force immediate restart |
| Skip kube-system | System pods (etcd, API server) must never be deleted |
| Pagination limit=500 | Balances API load vs single-request timeout |
| Cluster-size aware polling | Large clusters need longer budgets, longer intervals |

---


---

## 🗺️ Roadmap for improvement in future 

### Completed ✅
- ✅ Recovery verification with polling
- ✅ Cluster-size awareness
- ✅ Structured logging

### Planned
- [ ] Slack webhook notifications
- [ ] Email (SMTP) notifications
- [ ] DingTalk webhook
- [ ] Severity-based routing
- [ ] Retry / backoff for notifications
- [ ] Prometheus metrics
- [ ] Health endpoints (`/health`, `/ready`)
- [ ] JSON structured logs
- [ ] Namespace whitelist filter
- [ ] Rate-limited batch operations

---