---
name: iterative-retrieval
description: 逐步优化上下文检索以解决子智能体（subagent）上下文问题的模式。
origin: ECC
---

# 迭代检索模式（Iterative Retrieval Pattern）

解决了多智能体工作流（multi-agent workflows）中的“上下文问题”——子智能体（subagent）在开始工作前往往不知道自己需要哪些上下文。

## 何时激活

- 生成需要事先无法完全预测的代码库上下文（codebase context）的子智能体时
- 构建上下文需要逐步优化的多智能体工作流时
- 在智能体任务中遇到“上下文过大”或“缺失上下文”的失败时
- 为代码探索设计类 RAG 的检索流水线时
- 优化智能体编排（agent orchestration）中的 Token 使用时

## 问题背景（The Problem）

生成的子智能体通常只带有有限的上下文。它们并不清楚：
- 哪些文件包含相关的代码
- 代码库中存在哪些模式（patterns）
- 项目使用了哪些术语

标准方法往往会失败：
- **全部发送**：超出上下文限制。
- **什么都不发**：智能体缺少关键信息。
- **猜测需求**：经常猜错。

## 解决方案：迭代检索（The Solution: Iterative Retrieval）

一个由 4 个阶段组成的循环，用于逐步优化上下文：

```
┌─────────────────────────────────────────────┐
│                                             │
│   ┌──────────┐      ┌──────────┐            │
│   │   派发   │─────▶│   评估   │            │
│   │ DISPATCH │      │ EVALUATE │            │
│   └──────────┘      └──────────┘            │
│        ▲                  │                 │
│        │                  ▼                 │
│   ┌──────────┐      ┌──────────┐            │
│   │   循环   │◀─────│   优化   │            │
│   │   LOOP   │      │  REFINE  │            │
│   └──────────┘      └──────────┘            │
│                                             │
│        最多 3 个周期，然后继续              │
└─────────────────────────────────────────────┘
```

### 阶段 1：派发（DISPATCH）

初始的广泛查询，用于收集候选文件：

```javascript
// 从高层意图开始
const initialQuery = {
  patterns: ['src/**/*.ts', 'lib/**/*.ts'],
  keywords: ['authentication', 'user', 'session'],
  excludes: ['*.test.ts', '*.spec.ts']
};

// 派发给检索智能体
const candidates = await retrieveFiles(initialQuery);
```

### 阶段 2：评估（EVALUATE）

评估检索到的内容的相关性：

```javascript
function evaluateRelevance(files, task) {
  return files.map(file => ({
    path: file.path,
    relevance: scoreRelevance(file.content, task),
    reason: explainRelevance(file.content, task),
    missingContext: identifyGaps(file.content, task)
  }));
}
```

评分标准：
- **高 (0.8-1.0)**：直接实现了目标功能
- **中 (0.5-0.7)**：包含相关的模式或类型
- **低 (0.2-0.4)**：间接相关
- **无 (0-0.2)**：不相关，排除

### 阶段 3：优化（REFINE）

根据评估结果更新搜索条件：

```javascript
function refineQuery(evaluation, previousQuery) {
  return {
    // 添加在高度相关文件中发现的新模式
    patterns: [...previousQuery.patterns, ...extractPatterns(evaluation)],

    // 添加在代码库中发现的术语
    keywords: [...previousQuery.keywords, ...extractKeywords(evaluation)],

    // 排除已确认为不相关的路径
    excludes: [...previousQuery.excludes, ...evaluation
      .filter(e => e.relevance < 0.2)
      .map(e => e.path)
    ],

    // 针对特定的缺口
    focusAreas: evaluation
      .flatMap(e => e.missingContext)
      .filter(unique)
  };
}
```

### 阶段 4：循环（LOOP）

使用优化后的条件重复执行（最多 3 个周期）：

```javascript
async function iterativeRetrieve(task, maxCycles = 3) {
  let query = createInitialQuery(task);
  let bestContext = [];

  for (let cycle = 0; cycle < maxCycles; cycle++) {
    const candidates = await retrieveFiles(query);
    const evaluation = evaluateRelevance(candidates, task);

    // 检查是否已有足够的上下文
    const highRelevance = evaluation.filter(e => e.relevance >= 0.7);
    if (highRelevance.length >= 3 && !hasCriticalGaps(evaluation)) {
      return highRelevance;
    }

    // 优化并继续
    query = refineQuery(evaluation, query);
    bestContext = mergeContext(bestContext, highRelevance);
  }

  return bestContext;
}
```

## 实践案例

### 案例 1：Bug 修复上下文

```
任务："修复身份验证令牌过期 bug"

周期 1:
  派发 (DISPATCH)：在 src/** 中搜索 "token", "auth", "expiry"
  评估 (EVALUATE)：发现 auth.ts (0.9), tokens.ts (0.8), user.ts (0.3)
  优化 (REFINE)：添加 "refresh", "jwt" 关键词；排除 user.ts

周期 2:
  派发 (DISPATCH)：搜索优化后的术语
  评估 (EVALUATE)：发现 session-manager.ts (0.95), jwt-utils.ts (0.85)
  优化 (REFINE)：上下文已足够（2 个高度相关文件）

结果：auth.ts, tokens.ts, session-manager.ts, jwt-utils.ts
```

### 案例 2：功能实现

```
任务："为 API 端点添加速率限制 (rate limiting)"

周期 1:
  派发 (DISPATCH)：在 routes/** 中搜索 "rate", "limit", "api"
  评估 (EVALUATE)：无匹配项 —— 代码库使用的是 "throttle" 术语
  优化 (REFINE)：添加 "throttle", "middleware" 关键词

周期 2:
  派发 (DISPATCH)：搜索优化后的术语
  评估 (EVALUATE)：发现 throttle.ts (0.9), middleware/index.ts (0.7)
  优化 (REFINE)：需要路由器模式

周期 3:
  派发 (DISPATCH)：搜索 "router", "express" 模式
  评估 (EVALUATE)：发现 router-setup.ts (0.8)
  优化 (REFINE)：上下文已足够

结果：throttle.ts, middleware/index.ts, router-setup.ts
```

## 与智能体（Agents）集成

在智能体提示词中使用：

```markdown
在为此任务检索上下文时：
1. 从广泛的关键词搜索开始
2. 评估每个文件的相关性（0-1 等级）
3. 识别仍然缺失的上下文
4. 优化搜索条件并重复执行（最多 3 个周期）
5. 返回相关性 >= 0.7 的文件
```

## 最佳实践

1. **由广入深，逐步缩小范围** —— 初始查询不要过于具体。
2. **学习代码库术语** —— 第一个周期通常能揭示命名规范。
3. **追踪缺失内容** —— 明确的缺口识别是驱动优化的关键。
4. **见好就收** —— 3 个高度相关的文件优于 10 个平庸的文件。
5. **果断排除** —— 低相关性的文件通常不会突然变得相关。

## 相关资源

- [长篇指南 (The Longform Guide)](https://x.com/affaanmustafa/status/2014040193557471352) —— 子智能体编排部分
- `continuous-learning` 技能 —— 用于随时间改进的模式
- `~/.claude/agents/` 中的智能体定义
