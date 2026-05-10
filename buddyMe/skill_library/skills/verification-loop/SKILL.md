---
name: verification-loop
description: "Claude Code 会话的全方位验证系统。"
origin: ECC
---

# 验证循环技能（Verification Loop Skill）

Claude Code 会话的全方位验证系统。

## 何时使用

在以下场景调用此技能（Skill）：
- 完成功能开发或重大代码变更后
- 在创建拉取请求（PR）之前
- 当你想确保通过质量门禁时
- 重构之后

## 验证阶段

### 阶段 1：构建验证
```bash
# 检查项目是否构建成功
npm run build 2>&1 | tail -20
# 或者
pnpm build 2>&1 | tail -20
```

如果构建失败，请**停止**并修复后方可继续。

### 阶段 2：类型检查
```bash
# TypeScript 项目
npx tsc --noEmit 2>&1 | head -30

# Python 项目
pyright . 2>&1 | head -30
```

报告所有类型错误。在继续之前修复关键错误。

### 阶段 3：Lint 检查
```bash
# JavaScript/TypeScript
npm run lint 2>&1 | head -30

# Python
ruff check . 2>&1 | head -30
```

### 阶段 4：测试套件
```bash
# 运行带覆盖率的测试
npm run test -- --coverage 2>&1 | tail -50

# 检查覆盖率阈值
# 目标：最低 80%
```

报告：
- 测试总数：X
- 通过：X
- 失败：X
- 覆盖率：X%

### 阶段 5：安全扫描
```bash
# 检查密钥/机密
grep -rn "sk-" --include="*.ts" --include="*.js" . 2>/dev/null | head -10
grep -rn "api_key" --include="*.ts" --include="*.js" . 2>/dev/null | head -10

# 检查 console.log
grep -rn "console.log" --include="*.ts" --include="*.tsx" src/ 2>/dev/null | head -10
```

### 阶段 6：变更审查（Diff Review）
```bash
# 显示变更内容
git diff --stat
git diff HEAD~1 --name-only
```

审查每个变更的文件：
- 非预期的变更
- 缺失的错误处理
- 潜在的边缘情况

## 输出格式

运行所有阶段后，生成验证报告：

```
验证报告（VERIFICATION REPORT）
==================

构建 (Build):     [通过/失败]
类型 (Types):     [通过/失败] (X 个错误)
Lint:            [通过/失败] (X 个警告)
测试 (Tests):     [通过/失败] (X/Y 通过, Z% 覆盖率)
安全 (Security):  [通过/失败] (X 个问题)
变更 (Diff):      [X 个文件已变更]

总体评价:   [已就绪/未就绪] 提交 PR

待修复问题:
1. ...
2. ...
```

## 持续模式

对于较长的会话，每 15 分钟或在重大更改后运行验证：

```markdown
设定心智检查点：
- 完成每个函数后
- 完成一个组件后
- 在进入下一个任务前

运行：/verify
```

## 与钩子（Hooks）集成

此技能是 `PostToolUse` 钩子（Hooks）的补充，但提供更深入的验证。
钩子能立即捕捉问题；此技能则提供全方位的审查。
