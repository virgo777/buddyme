---
name: autonomous-loops
description: "自主运行 Claude Code 循环的模式与架构 —— 从简单的顺序流水线到 RFC 驱动的多智能体 DAG 系统。"
origin: ECC
---

# 自主循环技能 (Autonomous Loops Skill)

用于自主运行 Claude Code 循环的模式、架构和参考实现。涵盖了从简单的 `claude -p` 流水线到完整的 RFC 驱动多智能体（multi-agent）DAG 编排的所有内容。

## 适用场景

- 设置无需人工干预即可运行的自主开发工作流（Workflows）
- 为你的问题选择合适的循环架构（简单 vs 复杂）
- 构建 CI/CD 风格的持续开发流水线
- 运行具有合并协调机制的并行智能体（Agents）
- 在循环迭代之间实现上下文（Context）持久化
- 为自主工作流添加质量门禁（Quality gates）和清理环节

## 循环模式频谱 (Loop Pattern Spectrum)

从最简单到最复杂：

| 模式 | 复杂度 | 最适用于 |
|---------|-----------|----------|
| [顺序流水线 (Sequential Pipeline)](#1-sequential-pipeline-claude--p) | 低 | 日常开发步骤、脚本化工作流 |
| [NanoClaw REPL](#2-nanoclaw-repl) | 低 | 交互式持久化会话 |
| [无限智能体循环 (Infinite Agentic Loop)](#3-infinite-agentic-loop) | 中 | 并行内容生成、规约驱动的工作 |
| [持续 Claude PR 循环 (Continuous Claude PR Loop)](#4-continuous-claude-pr-loop) | 中 | 带有 CI 门禁的多日迭代项目 |
| [去杂质模式 (De-Sloppify Pattern)](#5-the-de-sloppify-pattern) | 附加项 | 任何实现步骤后的质量清理 |
| [Ralphinho / RFC 驱动的 DAG](#6-ralphinho--rfc-driven-dag-orchestration) | 高 | 大型功能、带合并队列的多单元并行工作 |

---

## 1. 顺序流水线 (Sequential Pipeline, `claude -p`)

**最简单的循环。** 将日常开发分解为一系列非交互式的 `claude -p` 调用。每次调用都是一个带有明确提示词（Prompt）的专注步骤。

### 核心见解

> 如果你无法理解这样的循环，那就意味着你甚至无法在交互模式下驱动 LLM 修复你的代码。

`claude -p` 标志（flag）以非交互方式运行 Claude Code 并提供提示词，完成后退出。通过链式调用构建流水线：

```bash
#!/bin/bash
# daily-dev.sh — 功能分支的顺序流水线

set -e

# 第 1 步：实现功能
claude -p "阅读 docs/auth-spec.md 中的规约。在 src/auth/ 中实现 OAuth2 登录。先写测试 (TDD)。不要创建任何新的文档文件。"

# 第 2 步：去杂质 (De-sloppify, 清理环节)
claude -p "检查上一次提交更改的所有文件。删除任何不必要的类型测试、过度防御性的检查或对语言特性的测试（例如，测试 TypeScript 泛型是否工作）。保留真实的业务逻辑测试。清理后运行测试套件。"

# 第 3 步：验证
claude -p "运行完整的构建、代码检查（lint）、类型检查和测试套件。修复任何失败。不要添加新功能。"

# 第 4 步：提交
claude -p "为所有暂存的更改创建一个约定式提交（conventional commit）。使用 'feat: add OAuth2 login flow' 作为消息。"
```

### 关键设计原则

1. **每个步骤都是隔离的** — 每次 `claude -p` 调用都有一个新的上下文窗口（Context window），这意味着步骤之间不会有上下文污染。
2. **顺序很重要** — 步骤按顺序执行。每一步都建立在前一步留下的文件系统状态之上。
3. **负面指令是危险的** — 不要说“不要测试类型系统”。相反，添加一个单独的清理步骤（参见 [去杂质模式](#5-the-de-sloppify-pattern)）。
4. **退出码会传播** — `set -e` 会在失败时停止流水线。

### 变体

**使用模型路由 (Model Routing)：**
```bash
# 使用 Opus 进行调研（深度推理）
claude -p --model opus "分析代码库架构并编写添加缓存的计划..."

# 使用 Sonnet 进行实现（快速且强大）
claude -p "根据 docs/caching-plan.md 中的计划实现缓存层..."

# 使用 Opus 进行审查（彻底）
claude -p --model opus "检查所有更改是否存在安全问题、竞态条件和边界情况..."
```

**带有环境上下文：**
```bash
# 通过文件传递上下文，而不是增加提示词长度
echo "重点领域：auth 模块，API 速率限制" > .claude-context.md
claude -p "阅读 .claude-context.md 获取优先级信息。按顺序处理它们。"
rm .claude-context.md
```

**带有 `--allowedTools` 限制：**
```bash
# 只读分析阶段
claude -p --allowedTools "Read,Grep,Glob" "审计此代码库的安全漏洞..."

# 只写实现阶段
claude -p --allowedTools "Read,Write,Edit,Bash" "实现 security-audit.md 中的修复方案..."
```

---

## 2. NanoClaw REPL

**ECC 内置的持久化循环。** 一个具有会话意识的 REPL，它同步调用 `claude -p` 并带有完整的对话历史。

```bash
# 启动默认会话
node scripts/claw.js

# 带有技能上下文的命名会话
CLAW_SESSION=my-project CLAW_SKILLS=tdd-workflow,security-review node scripts/claw.js
```

### 工作原理

1. 从 `~/.claude/claw/{session}.md` 加载对话历史。
2. 每个用户消息都会发送给 `claude -p`，并将完整历史作为上下文。
3. 响应会追加到会话文件（Markdown 作为数据库）。
4. 会话在重启后依然持久存在。

### NanoClaw 与顺序流水线对比

| 使用场景 | NanoClaw | 顺序流水线 |
|----------|----------|-------------------|
| 交互式探索 | 是 | 否 |
| 脚本自动化 | 否 | 是 |
| 会话持久化 | 内置 | 手动 |
| 上下文累积 | 随轮次增长 | 每个步骤都是新的 |
| CI/CD 集成 | 较差 | 优秀 |

详见 `/claw` 命令文档。

---

## 3. 无限智能体循环 (Infinite Agentic Loop)

**双提示词系统**，用于协调并行子智能体（sub-agents）进行规约驱动的生成。由 disler 开发（致谢：@disler）。

### 架构：双提示词系统

```
提示词 1 (编排器 Orchestrator)              提示词 2 (子智能体 Sub-Agents)
┌─────────────────────┐             ┌──────────────────────┐
│ 解析规约文件         │             │ 接收完整上下文        │
│ 扫描输出目录         │    部署     │ 读取分配的编号        │
│ 计划迭代             │────────────│ 严格遵守规约          │
│ 分配创意方向         │  N 个智能体 │ 生成唯一的输出        │
│ 管理波次             │             │ 保存到输出目录        │
└─────────────────────┘             └──────────────────────┘
```

### 模式

1. **规约分析** — 编排器读取定义生成内容的规约文件（Markdown）。
2. **目录侦察** — 扫描现有输出以找到最高的迭代编号。
3. **并行部署** — 启动 N 个子智能体，每个子智能体都获得：
   - 完整的规约
   - 唯一的创意方向
   - 特定的迭代编号（无冲突）
   - 现有迭代的快照（用于确保唯一性）
4. **波次管理** — 对于无限模式，部署 3-5 个智能体为一个波次，直到上下文耗尽。

### 通过 Claude Code 命令实现

创建 `.claude/commands/infinite.md`：

```markdown
从 $ARGUMENTS 解析以下参数：
1. spec_file — 规约 markdown 的路径
2. output_dir — 保存迭代结果的位置
3. count — 整数 1-N 或 "infinite"

阶段 1：阅读并深度理解规约。
阶段 2：列出 output_dir，找到最高的迭代编号。从 N+1 开始。
阶段 3：计划创意方向 — 每个智能体获得不同的主题/方法。
阶段 4：并行部署子智能体（Task 工具）。每个子智能体接收：
  - 完整规约文本
  - 当前目录快照
  - 分配给他们的迭代编号
  - 他们唯一的创意方向
阶段 5 (无限模式)：以 3-5 个为一波次循环，直到上下文过低。
```

**调用：**
```bash
/project:infinite specs/component-spec.md src/ 5
/project:infinite specs/component-spec.md src/ infinite
```

### 分批策略

| 数量 | 策略 |
|-------|----------|
| 1-5 | 所有智能体同时运行 |
| 6-20 | 每批 5 个 |
| infinite | 3-5 个一波，逐步提升复杂度 |

### 关键见解：通过分配确保唯一性

不要指望智能体自我区分。编排器会**分配**给每个智能体特定的创意方向和迭代编号。这可以防止并行智能体之间出现重复的概念。

---

## 4. 持续 Claude PR 循环 (Continuous Claude PR Loop)

**生产级 Shell 脚本**，在持续循环中运行 Claude Code，创建 PR、等待 CI 并自动合并。由 AnandChowdhary 开发（致谢：@AnandChowdhary）。

### 核心循环

```
┌─────────────────────────────────────────────────────┐
│  持续 CLAUDE 迭代 (CONTINUOUS CLAUDE ITERATION)     │
│                                                     │
│  1. 创建分支 (continuous-claude/iteration-N)        │
│  2. 使用增强提示词运行 claude -p                    │
│  3. (可选) 审查者阶段 — 独立的 claude -p             │
│  4. 提交更改 (Claude 生成提交消息)                  │
│  5. 推送并创建 PR (gh pr create)                    │
│  6. 等待 CI 检查 (轮询 gh pr checks)                │
│  7. CI 失败？ → 自动修复阶段 (claude -p)            │
│  8. 合并 PR (squash/merge/rebase)                   │
│  9. 返回 main 分支 → 重复                           │
│                                                     │
│  限制条件：--max-runs N | --max-cost $X             │
│            --max-duration 2h | 完成信号             │
└─────────────────────────────────────────────────────┘
```

### 安装

```bash
curl -fsSL https://raw.githubusercontent.com/AnandChowdhary/continuous-claude/HEAD/install.sh | bash
```

### 使用

```bash
# 基础：10 次迭代
continuous-claude --prompt "为所有未测试的函数添加单元测试" --max-runs 10

# 限制成本
continuous-claude --prompt "修复所有 linter 错误" --max-cost 5.00

# 限制时间
continuous-claude --prompt "提高测试覆盖率" --max-duration 8h

# 带有代码审查阶段
continuous-claude \
  --prompt "添加身份验证功能" \
  --max-runs 10 \
  --review-prompt "运行 npm test && npm run lint，修复任何失败"

# 通过工作树 (worktrees) 并行运行
continuous-claude --prompt "添加测试" --max-runs 5 --worktree tests-worker &
continuous-claude --prompt "重构代码" --max-runs 5 --worktree refactor-worker &
wait
```

### 跨迭代上下文：`SHARED_TASK_NOTES.md`

关键创新：一个在迭代之间持久存在的 `SHARED_TASK_NOTES.md` 文件：

```markdown
## 进度
- [x] 为 auth 模块添加了测试 (迭代 1)
- [x] 修复了 token 刷新的边界情况 (迭代 2)
- [ ] 仍需：速率限制测试，错误边界测试

## 下一步
- 下一步专注于速率限制模块
- tests/helpers.ts 中的 mock 设置可以复用
```

Claude 在迭代开始时阅读此文件，并在迭代结束时更新它。这弥合了独立 `claude -p` 调用之间的上下文差距。

### CI 失败恢复

当 PR 检查失败时，Continuous Claude 会自动：
1. 通过 `gh run list` 获取失败的运行 ID。
2. 使用 CI 修复上下文启动一个新的 `claude -p`。
3. Claude 通过 `gh run view` 检查日志、修复代码、提交并推送。
4. 重新等待检查（最多重试 `--ci-retry-max` 次）。

### 完成信号

Claude 可以通过输出一个魔术短语来发出“我完成了”的信号：

```bash
continuous-claude \
  --prompt "修复问题跟踪器中的所有 bug" \
  --completion-signal "CONTINUOUS_CLAUDE_PROJECT_COMPLETE" \
  --completion-threshold 3  # 连续 3 次信号后停止
```

连续三次迭代发出完成信号将停止循环，防止在已完成的工作上浪费额度。

### 关键配置

| 标志 (Flag) | 用途 |
|------|---------|
| `--max-runs N` | 在 N 次成功迭代后停止 |
| `--max-cost $X` | 花费 $X 后停止 |
| `--max-duration 2h` | 经过指定时间后停止 |
| `--merge-strategy squash` | 合并策略：squash, merge, 或 rebase |
| `--worktree <name>` | 通过 git 工作树并行执行 |
| `--disable-commits` | 演练模式（不进行 git 操作） |
| `--review-prompt "..."` | 为每次迭代添加审查者阶段 |
| `--ci-retry-max N` | 自动修复 CI 失败（默认：1） |

---

## 5. 去杂质模式 (The De-Sloppify Pattern)

**适用于任何循环的附加模式。** 在每个实现者（Implementer）步骤之后添加一个专门的清理/重构步骤。

### 问题所在

当你要求 LLM 通过 TDD 实现功能时，它对“编写测试”的理解可能过于死板：
- 测试 TypeScript 的类型系统是否工作（测试 `typeof x === 'string'`）
- 为类型系统已经保证的事情编写过度防御性的运行时检查
- 测试框架行为而不是业务逻辑
- 过度的错误处理掩盖了实际代码

### 为什么不使用负面指令？

在实现者提示词中添加“不要测试类型系统”或“不要添加不必要的检查”会有副作用：
- 模型会对所有测试都变得犹豫不决
- 它会跳过合理的边界情况测试
- 质量会不可预测地下降

### 解决方案：独立的清理阶段

与其限制实现者，不如让它彻底发挥。然后添加一个专注的清理智能体：

```bash
# 第 1 步：实现（让它彻底发挥）
claude -p "通过完整的 TDD 实现该功能。测试要彻底。"

# 第 2 步：去杂质 (独立的上下文，专注的清理)
claude -p "审查工作树中的所有更改。删除：
- 验证语言/框架行为而不是业务逻辑的测试
- 类型系统已经强制执行的冗余类型检查
- 对不可能状态的过度防御性错误处理
- Console.log 语句
- 被注释掉的代码

保留所有业务逻辑测试。清理后运行测试套件以确保没有破坏任何功能。"
```

### 在循环上下文中使用

```bash
for feature in "${features[@]}"; do
  # 实现
  claude -p "通过 TDD 实现 $feature。"

  # 去杂质
  claude -p "清理阶段：审查更改，删除测试/代码杂质，运行测试。"

  # 验证
  claude -p "运行构建 + lint + 测试。修复任何失败。"

  # 提交
  claude -p "提交并附带消息：feat: add $feature"
done
```

### 关键见解

> 与其添加会影响下游质量的负面指令，不如添加一个独立的去杂质阶段。两个专注的智能体优于一个受限的智能体。

---

## 6. Ralphinho / RFC 驱动的 DAG 编排 (RFC-Driven DAG Orchestration)

**最复杂的模式。** 一个由 RFC 驱动的多智能体流水线，它将规约分解为依赖 DAG（有向无环图），通过分层质量流水线运行每个单元，并通过智能体驱动的合并队列（Merge queue）落地。由 enitrat 开发（致谢：@enitrat）。

### 架构概览

```
RFC/PRD 文档
       │
       ▼
  分解 DECOMPOSITION (AI)
  将 RFC 分解为具有依赖 DAG 的工作单元
       │
       ▼
┌──────────────────────────────────────────────────────┐
│  RALPH 循环 (最多 3 次迭代)                          │
│                                                      │
│  对于每个 DAG 层（按依赖关系顺序执行）：             │
│                                                      │
│  ┌── 质量流水线 (单元之间并行运行) ───────────────┐  │
│  │  每个单元在自己的工作树中：                     │  │
│  │  调研 → 计划 → 实现 → 测试 → 审查              │  │
│  │  (深度根据复杂度层级而异)                      │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌── 合并队列 Merge Queue ────────────────────────┐  │
│  │  变基到 main → 运行测试 → 落地或剔除 (Evict)    │  │
│  │  被剔除的单元带着冲突上下文重新进入循环         │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### RFC 分解

AI 阅读 RFC 并生成工作单元：

```typescript
interface WorkUnit {
  id: string;              // kebab-case 标识符
  name: string;            // 人类可读的名称
  rfcSections: string[];   // 该单元处理哪些 RFC 章节
  description: string;     // 详细描述
  deps: string[];          // 依赖项（其他单元 ID）
  acceptance: string[];    // 具体的验收标准
  tier: "trivial" | "small" | "medium" | "large"; // 复杂度层级
}
```

**分解规则：**
- 倾向于更少且内聚的单元（尽量减少合并风险）
- 尽量减少跨单元的文件重叠（避免冲突）
- 将测试与实现保持在一起（绝不要将“实现 X”和“测试 X”分开）
- 仅在存在真实代码依赖时才建立依赖关系

依赖 DAG 决定执行顺序：
```
第 0 层: [unit-a, unit-b]     ← 无依赖，并行运行
第 1 层: [unit-c]             ← 依赖于 unit-a
第 2 层: [unit-d, unit-e]     ← 依赖于 unit-c
```

### 复杂度层级 (Complexity Tiers)

不同的层级对应不同的流水线深度：

| 层级 | 流水线阶段 |
|------|----------------|
| **trivial (琐碎)** | 实现 → 测试 |
| **small (小型)** | 实现 → 测试 → 代码审查 |
| **medium (中型)** | 调研 → 计划 → 实现 → 测试 → PRD 审查 + 代码审查 → 审查修复 |
| **large (大型)** | 调研 → 计划 → 实现 → 测试 → PRD 审查 + 代码审查 → 审查修复 → 最终审查 |

这可以防止在简单的更改上进行昂贵的操作，同时确保架构更改得到彻底审查。

### 独立的上下文窗口 (消除作者偏见)

每个阶段都在自己的智能体进程中运行，具有自己的上下文窗口：

| 阶段 | 模型 | 用途 |
|-------|-------|---------|
| 调研 | Sonnet | 阅读代码库 + RFC，生成上下文文档 |
| 计划 | Opus | 设计实现步骤 |
| 实现 | Codex | 按照计划编写代码 |
| 测试 | Sonnet | 运行构建 + 测试套件 |
| PRD 审查 | Sonnet | 规约合规性检查 |
| 代码审查 | Opus | 质量 + 安全检查 |
| 审查修复 | Codex | 处理审查中发现的问题 |
| 最终审查 | Opus | 质量门禁（仅限大型层级） |

**核心设计：** 审查者绝不是编写代码的人。这消除了作者偏见（author bias）—— 这是自我审查中最常见的疏漏来源。

### 带有剔除机制的合并队列 (Merge Queue with Eviction)

质量流水线完成后，单元进入合并队列：

```
单元分支
    │
    ├─ 变基 (Rebase) 到 main
    │   └─ 冲突？ → 剔除 (EVICT)（捕获冲突上下文）
    │
    ├─ 运行构建 + 测试
    │   └─ 失败？ → 剔除 (EVICT)（捕获测试输出）
    │
    └─ 通过 → 快进 (Fast-forward) main，推送，删除分支
```

**文件重叠智能：**
- 非重叠单元以推测方式并行落地
- 重叠单元逐个落地，每次都进行变基

**剔除恢复：**
被剔除时，完整的上下文（冲突文件、diff、测试输出）会被捕获，并在下一次 Ralph 循环中反馈给实现者：

```markdown
## 合并冲突 — 在下次落地前解决

你之前的实现与先落地的另一个单元冲突。
请重构你的更改，以避开下面的冲突文件/行。

{带有 diff 的完整剔除上下文}
```

### 阶段间的数据流

```
research.contextFilePath ──────────────────→ plan
plan.implementationSteps ──────────────────→ implement
implement.{filesCreated, whatWasDone} ─────→ test, reviews
test.failingSummary ───────────────────────→ reviews, implement (下一次迭代)
reviews.{feedback, issues} ────────────────→ review-fix → implement (下一次迭代)
final-review.reasoning ────────────────────→ implement (下一次迭代)
evictionContext ───────────────────────────→ implement (合并冲突后)
```

### 工作树隔离 (Worktree Isolation)

每个单元都在隔离的工作树中运行（使用 jj/Jujutsu，而非 git）：
```
/tmp/workflow-wt-{unit-id}/
```

同一单元的流水线阶段**共享**一个工作树，从而在调研 → 计划 → 实现 → 测试 → 审查的整个过程中保留状态（上下文文件、计划文件、代码更改）。

### 关键设计原则

1. **确定性执行** — 前置分解锁定了并行性和顺序。
2. **杠杆点上的人工审查** — 工作计划是最高杠杆的干预点。
3. **关注点分离** — 每个阶段都在独立的上下文窗口中由独立的智能体执行。
4. **带有上下文的冲突恢复** — 完整的剔除上下文实现了智能重新运行，而非盲目重试。
5. **层级驱动的深度** — 琐碎的更改跳过调研/审查；大型更改获得最大程度的审视。
6. **可恢复的工作流** — 完整状态持久化到 SQLite；可从任何点恢复。

### 何时使用 Ralphinho vs 简单模式

| 信号 | 使用 Ralphinho | 使用简单模式 |
|--------|--------------|-------------------|
| 多个相互依赖的工作单元 | 是 | 否 |
| 需要并行实现 | 是 | 否 |
| 合并冲突可能性大 | 是 | 否 (顺序执行即可) |
| 单文件更改 | 否 | 是 (顺序流水线) |
| 多日项目 | 是 | 可能是 (continuous-claude) |
| 规约/RFC 已写好 | 是 | 可能是 |
| 快速迭代某件事 | 否 | 是 (NanoClaw 或流水线) |

---

## 选择合适的模式

### 决策矩阵

```
任务是否为单个专注的更改？
├─ 是 → 顺序流水线 (Sequential Pipeline) 或 NanoClaw
└─ 否 → 是否有书面的规约/RFC？
         ├─ 是 → 是否需要并行实现？
         │        ├─ 是 → Ralphinho (DAG 编排)
         │        └─ 否 → Continuous Claude (迭代式 PR 循环)
         └─ 否 → 是否需要同一事物的多个变体？
                  ├─ 是 → 无限智能体循环 (Infinite Agentic Loop, 规约驱动生成)
                  └─ 否 → 带去杂质阶段的顺序流水线
```

### 模式组合

这些模式可以很好地组合使用：

1. **顺序流水线 + 去杂质** — 最常见的组合。每个实现步骤都有一个清理阶段。

2. **Continuous Claude + 去杂质** — 在每次迭代中为 `--review-prompt` 添加去杂质指令。

3. **任何循环 + 验证** — 在提交前使用 ECC 的 `/verify` 命令或 `verification-loop` 技能作为关卡。

4. **简单循环中借鉴 Ralphinho 的分层方法** — 即使在顺序流水线中，你也可以将简单任务交给 Haiku，复杂任务交给 Opus：
   ```bash
   # 简单的格式化修复
   claude -p --model haiku "修复 src/utils.ts 中的导入顺序"

   # 复杂的架构更改
   claude -p --model opus "重构 auth 模块以使用策略模式"
   ```

---

## 反模式 (Anti-Patterns)

### 常见错误

1. **没有退出条件的死循环** — 务必设置 max-runs、max-cost、max-duration 或完成信号。

2. **迭代之间没有上下文桥梁** — 每次 `claude -p` 调用都是全新的。使用 `SHARED_TASK_NOTES.md` 或文件系统状态来桥接上下文。

3. **重复相同的失败** — 如果迭代失败，不要只是重试。捕获错误上下文并将其提供给下一次尝试。

4. **负面指令代替清理阶段** — 不要说“不要做 X”。添加一个删除 X 的独立阶段。

5. **所有智能体共用一个上下文窗口** — 对于复杂的工作流，将关注点分离到不同的智能体进程中。审查者绝不应该是作者。

6. **在并行工作中忽略文件重叠** — 如果两个并行智能体可能编辑同一个文件，你需要一个合并策略（顺序落地、变基或冲突解决）。

---

## 参考资料

| 项目 | 作者 | 链接 |
|---------|--------|------|
| Ralphinho | enitrat | 致谢：@enitrat |
| Infinite Agentic Loop | disler | 致谢：@disler |
| Continuous Claude | AnandChowdhary | 致谢：@AnandChowdhary |
| NanoClaw | ECC | 本仓库中的 `/claw` 命令 |
| Verification Loop | ECC | 本仓库中的 `skills/verification-loop/` |
