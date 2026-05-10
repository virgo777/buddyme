---
name: deployment-patterns
description: Deployment workflows, CI/CD pipeline patterns, Docker containerization, health checks, rollback strategies, and production readiness checklists for web applications.
origin: ECC
---

# 部署模式 (Deployment Patterns)

生产部署工作流与 CI/CD 最佳实践。

## 何时激活

- 设置 CI/CD 流水线 (Pipelines)
- 对应用程序进行 Docker 容器化
- 规划部署策略（蓝绿部署、金丝雀部署、滚动更新）
- 实现健康检查 (Health Checks) 与就绪探针 (Readiness Probes)
- 准备生产发布
- 配置环境特定的设置

## 部署策略 (Deployment Strategies)

### 滚动部署 (Rolling Deployment) - 默认

逐渐替换实例 —— 在滚动更新期间，旧版本和新版本同时运行。

```
实例 1: v1 → v2  (首先更新)
实例 2: v1        (仍在运行 v1)
实例 3: v1        (仍在运行 v1)

实例 1: v2
实例 2: v1 → v2  (其次更新)
实例 3: v1

实例 1: v2
实例 2: v2
实例 3: v1 → v2  (最后更新)
```

**优点：** 零停机时间，渐进式推出
**缺点：** 两个版本同时运行 —— 要求变更必须向后兼容
**适用场景：** 标准部署，向后兼容的变更

### 蓝绿部署 (Blue-Green Deployment)

运行两个完全相同的环境。原子化地切换流量。

```
蓝色环境 (v1) ← 流量接入
绿色环境 (v2)   空闲，运行新版本

# 验证后：
蓝色环境 (v1)   空闲 (变为备用)
绿色环境 (v2) ← 流量接入
```

**优点：** 瞬时回滚（切换回蓝色环境），干净的切割
**缺点：** 部署期间需要 2 倍的基础设施资源
**适用场景：** 关键服务，对问题零容忍

### 金丝雀部署 (Canary Deployment)

首先将小部分比例的流量路由到新版本。

```
v1: 95% 流量
v2:  5% 流量  (金丝雀)

# 如果指标良好：
v1: 50% 流量
v2: 50% 流量

# 最终：
v2: 100% 流量
```

**优点：** 在全量推出前通过真实流量发现问题
**缺点：** 需要流量切分基础设施和监控
**适用场景：** 高流量服务，高风险变更，特性标志 (Feature Flags)

## Docker

### 多阶段 Dockerfile (Node.js)

```dockerfile
# 阶段 1: 安装依赖
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --production=false

# 阶段 2: 构建
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build
RUN npm prune --production

# 阶段 3: 生产镜像
FROM node:22-alpine AS runner
WORKDIR /app

RUN addgroup -g 1001 -S appgroup && adduser -S appuser -u 1001
USER appuser

COPY --from=builder --chown=appuser:appgroup /app/node_modules ./node_modules
COPY --from=builder --chown=appuser:appgroup /app/dist ./dist
COPY --from=builder --chown=appuser:appgroup /app/package.json ./

ENV NODE_ENV=production
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["node", "dist/server.js"]
```

### 多阶段 Dockerfile (Go)

```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /server ./cmd/server

FROM alpine:3.19 AS runner
RUN apk --no-cache add ca-certificates
RUN adduser -D -u 1001 appuser
USER appuser

COPY --from=builder /server /server

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost:8080/health || exit 1
CMD ["/server"]
```

### 多阶段 Dockerfile (Python/Django)

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

FROM python:3.12-slim AS runner
WORKDIR /app

RUN useradd -r -u 1001 appuser
USER appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/')" || exit 1
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
```

### Docker 最佳实践

```
# 推荐做法 (GOOD practices)
- 使用具体的版本标签 (node:22-alpine, 而非 node:latest)
- 使用多阶段构建以最小化镜像大小
- 以非 root 用户运行
- 首先复制依赖文件（利用层缓存）
- 使用 .dockerignore 排除 node_modules, .git, tests
- 添加 HEALTHCHECK 指令
- 在 docker-compose 或 k8s 中设置资源限制

# 错误做法 (BAD practices)
- 以 root 用户运行
- 使用 :latest 标签
- 在一个 COPY 层中复制整个仓库
- 在生产镜像中安装开发依赖
- 在镜像中存储机密信息（应使用环境变量或机密管理器）
```

## CI/CD 流水线 (CI/CD Pipeline)

### GitHub Actions (标准流水线)

```yaml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm test -- --coverage
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: coverage
          path: coverage/

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
      - name: Deploy to production
        run: |
          # 平台特定的部署命令
          # Railway: railway up
          # Vercel: vercel --prod
          # K8s: kubectl set image deployment/app app=ghcr.io/${{ github.repository }}:${{ github.sha }}
          echo "Deploying ${{ github.sha }}"
```

### 流水线阶段 (Pipeline Stages)

```
PR 开启:
  代码扫描 (lint) → 类型检查 (typecheck) → 单元测试 → 集成测试 → 预览部署

合并到 main:
  代码扫描 (lint) → 类型检查 (typecheck) → 单元测试 → 集成测试 → 构建镜像 → 部署到预发环境 → 冒烟测试 → 部署到生产环境
```

## 健康检查 (Health Checks)

### 健康检查接口

```typescript
// 简单健康检查
app.get("/health", (req, res) => {
  res.status(200).json({ status: "ok" });
});

// 详细健康检查 (用于内部监控)
app.get("/health/detailed", async (req, res) => {
  const checks = {
    database: await checkDatabase(),
    redis: await checkRedis(),
    externalApi: await checkExternalApi(),
  };

  const allHealthy = Object.values(checks).every(c => c.status === "ok");

  res.status(allHealthy ? 200 : 503).json({
    status: allHealthy ? "ok" : "degraded",
    timestamp: new Date().toISOString(),
    version: process.env.APP_VERSION || "unknown",
    uptime: process.uptime(),
    checks,
  });
});

async function checkDatabase(): Promise<HealthCheck> {
  try {
    await db.query("SELECT 1");
    return { status: "ok", latency_ms: 2 };
  } catch (err) {
    return { status: "error", message: "Database unreachable" };
  }
}
```

### Kubernetes 探针 (Probes)

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 3000
  initialDelaySeconds: 10
  periodSeconds: 30
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health
    port: 3000
  initialDelaySeconds: 5
  periodSeconds: 10
  failureThreshold: 2

startupProbe:
  httpGet:
    path: /health
    port: 3000
  initialDelaySeconds: 0
  periodSeconds: 5
  failureThreshold: 30    # 30 * 5s = 150s 最大启动时间
```

## 环境配置 (Environment Configuration)

### 云原生应用 (Twelve-Factor App) 模式

```bash
# 所有配置通过环境变量传递 —— 严禁写死在代码中
DATABASE_URL=postgres://user:pass@host:5432/db
REDIS_URL=redis://host:6379/0
API_KEY=${API_KEY}           # 由机密管理器注入
LOG_LEVEL=info
PORT=3000

# 环境特定行为
NODE_ENV=production          # 或 staging, development
APP_ENV=production           # 显式应用环境
```

### 配置验证

```typescript
import { z } from "zod";

const envSchema = z.object({
  NODE_ENV: z.enum(["development", "staging", "production"]),
  PORT: z.coerce.number().default(3000),
  DATABASE_URL: z.string().url(),
  REDIS_URL: z.string().url(),
  JWT_SECRET: z.string().min(32),
  LOG_LEVEL: z.enum(["debug", "info", "warn", "error"]).default("info"),
});

// 启动时验证 —— 如果配置错误则立即崩溃 (fail fast)
export const env = envSchema.parse(process.env);
```

## 回滚策略 (Rollback Strategy)

### 瞬时回滚

```bash
# Docker/Kubernetes: 指向之前的镜像
kubectl rollout undo deployment/app

# Vercel: 提升之前的部署版本
vercel rollback

# Railway: 重新部署之前的提交
railway up --commit <previous-sha>

# 数据库: 回滚迁移 (如果可逆)
npx prisma migrate resolve --rolled-back <migration-name>
```

### 回滚自检清单

- [ ] 之前的镜像/产物可用且已标记标签
- [ ] 数据库迁移向后兼容（无破坏性变更）
- [ ] 特性标志 (Feature flags) 可以在不部署的情况下禁用新功能
- [ ] 已针对错误率激增配置监控告警
- [ ] 在生产发布前已在预发环境测试过回滚

## 生产就绪自检清单 (Production Readiness Checklist)

在任何生产部署之前：

### 应用程序
- [ ] 所有测试均通过（单元测试、集成测试、E2E）
- [ ] 代码或配置文件中没有硬编码的机密信息
- [ ] 错误处理覆盖了所有边界情况
- [ ] 日志是结构化的 (JSON) 且不包含个人身份信息 (PII)
- [ ] 健康检查接口返回有意义的状态

### 基础设施
- [ ] Docker 镜像构建具有可复现性（固定版本）
- [ ] 环境变量已记录并在启动时验证
- [ ] 已设置资源限制 (CPU, 内存)
- [ ] 已配置水平扩展（最小/最大实例数）
- [ ] 所有接口均启用了 SSL/TLS

### 监控
- [ ] 已导出应用指标（请求率、延迟、错误率）
- [ ] 已针对 错误率 > 阈值 配置告警
- [ ] 已设置日志聚合（结构化日志，可搜索）
- [ ] 已对健康检查接口进行可用性 (Uptime) 监控

### 安全
- [ ] 已对依赖项进行 CVE 漏洞扫描
- [ ] 已针对允许的源配置 CORS
- [ ] 公共接口已启用速率限制 (Rate limiting)
- [ ] 身份验证 (Authentication) 和授权 (Authorization) 已验证
- [ ] 已设置安全响应头 (CSP, HSTS, X-Frame-Options)

### 运维
- [ ] 回滚计划已记录并经过测试
- [ ] 数据库迁移已针对生产规模的数据进行过测试
- [ ] 针对常见失败场景的运行手册 (Runbook)
- [ ] 已定义值班 (On-call) 轮换和升级路径
