# 🧪 明日测试计划 - Pod Cleaner Recovery Verification

**日期**: 2026 年 3 月 5 日 周四  
**功能**: Recovery Verification with Persistent Issue Detection  
**状态**: ✅ 代码完成 | ⏳ PR 待创建 | 📋 测试待执行

---

## 📋 晨间任务清单

### 1️⃣ 创建 GitHub PR (优先)

**方式 A - 网页创建** (推荐，无需 CLI 认证):

```
1. 访问：https://github.com/guguji666666/K8SPLAY/pulls
2. 点击 "New pull request"
3. base: main ← compare: main (已推送)
4. 标题：feat: Add recovery verification with persistent issue detection
5. 描述：复制 RECOVERY_FEATURE_PR.md 内容
6. 提交 PR
```

**方式 B - CLI 创建** (需先认证):

```bash
# 认证 GitHub CLI
gh auth login

# 创建 PR
cd /Users/guguji/.openclaw/workspace/pod-cleaner-ENG
gh pr create --title "feat: Add recovery verification with persistent issue detection" --body-file RECOVERY_FEATURE_PR.md
```

---

## 🧪 测试环境部署

### 前置检查

```bash
# 1. 确认 Kubernetes 集群可访问
kubectl cluster-info

# 2. 确认命名空间存在
kubectl get ns default

# 3. 确认 Pod Cleaner 配置
cat /Users/guguji/.openclaw/workspace/pod-cleaner-ENG/.env
```

### 部署测试用故障 Pod

```bash
cd /Users/guguji/.openclaw/workspace/pod-cleaner-ENG

# 部署始终失败的 Pod (CrashLoopBackOff)
kubectl apply -f test-always-failed-pods.yaml

# 验证 Pod 状态
kubectl get pods -l app=always-failed-test -w
```

### 运行 Pod Cleaner

```bash
cd /Users/guguji/.openclaw/workspace/pod-cleaner-ENG

# 激活虚拟环境 (如有)
source venv/bin/activate 2>/dev/null || true

# 运行 Pod Cleaner
python3 src/main.py
```

---

## 📊 预期行为验证

### 阶段 1: Pod 删除跟踪 (0-2 分钟)

**预期日志**:
```
🗑️  Deleted pod detected: always-failed-test-xxxxx
    Namespace: default
    Reason: CrashLoopBackOff
    Attempt: 1
    Tracking started...
```

**验证点**:
- [ ] Pod 删除被检测到
- [ ] 状态文件创建 (`/var/lib/pod-cleaner/state.json` 或配置的路径)
- [ ] 尝试次数 = 1

---

### 阶段 2: 恢复验证 (2-4 分钟)

**预期日志**:
```
🔍  Recovery verification started for always-failed-test-xxxxx
    Waiting for new pod creation (timeout: 120s)...
    New pod detected: always-failed-test-xxxxx
    Health check: ❌ Unhealthy (CrashLoopBackOff)
    Attempt: 2
```

**验证点**:
- [ ] 等待新 Pod 创建 (120 秒)
- [ ] 检测到新 Pod
- [ ] 健康检查识别 CrashLoopBackOff
- [ ] 尝试次数递增

---

### 阶段 3: 升级告警 (第 3 次尝试后)

**预期日志**:
```
🔥  ESCALATION: Persistent issue detected!
    Pod: default/always-failed-test-xxxxx
    Attempt: 3/3
    First detected: 2026-03-05T09:00:00
    
    📋 History:
      1. 09:00:00 - CrashLoopBackOff
      2. 09:02:00 - CrashLoopBackOff
      3. 09:04:00 - CrashLoopBackOff
    
    ⚠️  Manual intervention required
```

**验证点**:
- [ ] 达到最大尝试次数 (3)
- [ ] 触发升级告警
- [ ] Bark 通知发送 (如配置)
- [ ] 完整历史记录包含在告警中

---

### 阶段 4: 恢复报告 (可选)

**预期日志**:
```
🔍  Recovery Verification Report
    Total tracked: 1
    ✅ Recovered: 0
    ⚠️  Still unhealthy: 1
    🔥  Persistent issues: 1
```

**验证点**:
- [ ] 报告格式正确
- [ ] 统计数据准确

---

## 🧹 清理步骤

```bash
# 删除测试 Pod
kubectl delete -f test-always-failed-pods.yaml

# 验证 Pod 已删除
kubectl get pods -l app=always-failed-test

# (可选) 清除状态文件
rm /var/lib/pod-cleaner/state.json 2>/dev/null || true
```

---

## ✅ 验收标准

| 功能 | 预期结果 | 状态 |
|------|----------|------|
| Pod 删除跟踪 | 记录 UID、命名空间、原因、时间戳 | ⏳ |
| 恢复验证 | 等待新 Pod 并检查健康状态 | ⏳ |
| 持续问题检测 | 3 次后触发升级告警 | ⏳ |
| Bark 通知 | 收到升级告警通知 | ⏳ |
| 状态持久化 | 重启后保持跟踪状态 | ⏳ |
| 自动清理 | 24 小时后清理旧条目 | ⏳ |

---

## 🔧 故障排查

### 问题: Pod Cleaner 未检测到 Pod 删除

**检查**:
```bash
# 确认 Pod Cleaner 有权限监控 Pod
kubectl auth can-i get pods --all-namespaces

# 查看 Pod Cleaner 日志
kubectl logs -l app=pod-cleaner --tail=100
```

### 问题: Bark 通知未发送

**检查**:
```bash
# 确认 .env 中 Bark URL 配置
grep BARK_URL /Users/guguji/.openclaw/workspace/pod-cleaner-ENG/.env

# 测试 Bark URL 可达性
curl -X POST "YOUR_BARK_URL" -d "title=Test&body=Test notification"
```

### 问题: 状态文件未创建

**检查**:
```bash
# 确认目录存在且有写权限
ls -la /var/lib/pod-cleaner/ 2>/dev/null || echo "Directory not found"

# 检查配置的 PERSISTENCE_FILE 路径
grep PERSISTENCE_FILE /Users/guguji/.openclaw/workspace/pod-cleaner-ENG/.env
```

---

## 📝 测试报告模板

```markdown
## 测试执行报告

**日期**: 2026-03-05  
**执行人**: [姓名]  
**环境**: [集群名称/版本]

### 测试结果

| 测试项 | 预期 | 实际 | 状态 |
|--------|------|------|------|
| Pod 删除跟踪 | 记录完整信息 | | |
| 恢复验证 | 等待并检测 | | |
| 升级告警 | 3 次后触发 | | |
| Bark 通知 | 收到通知 | | |

### 问题记录

[记录任何发现的问题]

### 结论

[通过/不通过/需要修复]
```

---

## 🎯 下一步

测试通过后:
1. ✅ 合并 PR
2. 📦 更新 Docker 镜像
3. 🚀 部署到生产环境
4. 📊 监控实际运行效果

---

**🦞 测试驱动质量，质量保证价值！**
