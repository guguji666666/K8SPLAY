# Pod Cleaner - Recovery Verification Feature

## 🎯 目标
为 pod-cleaner 添加重启验证功能，形成完整的监控闭环。

## 📋 需求

### 当前问题
- pod-cleaner 只负责删除异常 pod
- 无法验证删除后新创建的 pod 是否健康
- 如果问题持续存在（如配置错误、镜像问题），会陷入无限循环

### 解决方案
添加 recovery verification 机制：
1. 删除异常 pod 后，记录 pod 信息（name, namespace, UID, 异常原因）
2. 等待新 pod 创建（通过 watch API 或轮询）
3. 检查新 pod 的健康状态
4. 如果仍然异常：
   - 标记为 "persistent issue"
   - 发送升级告警（包含历史信息）
   - 可选：暂停对该 pod 的自动处理，等待人工介入
5. 如果健康：
   - 记录 recovery 成功
   - 清除历史记录

## 🏗️ 实现方案

### 新增文件
```
src/
├── recovery_checker.py    # Recovery 验证逻辑
├── persistence_store.py   # 本地状态存储（JSON file 或 in-memory）
```

### 配置项 (config.py)
```python
# Recovery Verification Configuration
RECOVERY_CHECK_ENABLED = True
RECOVERY_WAIT_SECONDS = 120  # 等待新 pod 创建的时间
RECOVERY_MAX_ATTEMPTS = 3    # 最大重试次数 before escalating
PERSISTENCE_FILE = "/var/lib/pod-cleaner/state.json"
```

### 核心逻辑 (伪代码)
```python
class RecoveryChecker:
    def __init__(self, kube_client, config):
        self.kube_client = kube_client
        self.config = config
        self.state = self.load_state()
    
    def track_deletion(self, pod_info):
        """记录 pod 删除事件"""
        self.state[pod_info.uid] = {
            'name': pod_info.name,
            'namespace': pod_info.namespace,
            'reason': pod_info.failure_reason,
            'deleted_at': timestamp,
            'attempt': 1
        }
        self.save_state()
    
    def check_recovery(self, namespace, pod_name):
        """检查重启后的 pod 是否健康"""
        # 1. 查找新 pod（通过 name prefix 或 label）
        # 2. 检查 container state
        # 3. 返回健康状态
        
    def escalate(self, pod_info):
        """升级告警"""
        # 发送包含历史记录的告警
        # 可选：添加到 exclusion list
```

### 集成到 main.py
```python
# 在 main loop 中
for pod in unhealthy_pods:
    if recovery_checker.is_persistent_issue(pod):
        logger.warning(f"Persistent issue detected: {pod.name}")
        notifier.send_escalation(pod)
        continue
    
    # 删除 pod
    kube_client.delete_pod(pod)
    
    # 跟踪删除事件
    recovery_checker.track_deletion(pod)

# 定期检查 recovery 状态
recovery_checker.verify_all_tracked()
```

## ✅ 测试计划

### 单元测试
- [ ] `test_recovery_checker.py`
  - 测试状态加载/保存
  - 测试 persistent issue 检测
  - 测试 escalation 逻辑

### 集成测试
- [ ] `test-recovery-scenario.yaml`
  - 创建一个会 CrashLoopBackOff 的 pod
  - 验证 pod-cleaner 检测到并删除
  - 验证 recovery checker 跟踪
  - 验证多次失败后 escalation

### 手动测试
```bash
# 1. 部署测试 pod
kubectl apply -f test-always-failed-pods.yaml

# 2. 运行 pod-cleaner
python -m src.main

# 3. 观察日志和告警
```

## 📝 交付清单
- [ ] 实现 `recovery_checker.py`
- [ ] 实现 `persistence_store.py`
- [ ] 更新 `config.py` 添加配置项
- [ ] 更新 `main.py` 集成 recovery check
- [ ] 更新 `notifier.py` 添加 escalation 方法
- [ ] 添加单元测试
- [ ] 更新 `README.md`
- [ ] 更新 `.env.example`
- [ ] 创建 PR

## 🔗 相关资源
- Kubernetes Watch API: https://kubernetes.io/docs/reference/using-api/api-concepts/#efficient-detection-of-updates
- Pod Lifecycle: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/
