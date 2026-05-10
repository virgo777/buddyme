---
name: search-first
description: Research-before-coding workflow. Search for existing tools, libraries, and patterns before writing custom code. Invokes the researcher agent.
origin: ECC
---

# /search-first — 编码前先调研（Research Before You Code）

将“在实现前搜索现有解决方案”的工作流系统化。

## 触发条件（Trigger）

在以下场景使用此技能（Skill）：
- 开始开发一个很可能已有现成解决方案的新功能
- 添加依赖项或集成
- 用户要求“添加 X 功能”且你正准备编写代码
- 在创建新的工具类（Utility）、辅助函数（Helper）或抽象层之前

## 工作流（Workflow）

```
┌─────────────────────────────────────────────┐
│  1. 需求分析 (NEED ANALYSIS)                 │
│     定义所需功能                             │
│     识别语言/框架约束                        │
├─────────────────────────────────────────────┤
│  2. 并行搜索 (调研智能体 researcher agent)    │
│     ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│     │  npm /   │ │  MCP /   │ │  GitHub / │  │
│     │  PyPI    │ │  技能    │ │  Web      │  │
│     └──────────┘ └──────────┘ └──────────┘  │
├─────────────────────────────────────────────┤
│  3. 评估 (EVALUATE)                         │
│     为候选方案打分（功能、维护、             │
│     社区、文档、许可证、依赖）               │
├─────────────────────────────────────────────┤
│  4. 决策 (DECIDE)                           │
│     ┌─────────┐  ┌──────────┐  ┌─────────┐  │
│     │  采用   │  │   扩展   │  │   自研  │  │
│     │ (Adopt) │  │  (Extend)│  │ (Build) │  │
│     └─────────┘  └──────────┘  └─────────┘  │
├─────────────────────────────────────────────┤
│  5. 实施 (IMPLEMENT)                        │
│     安装包 / 配置 MCP /                     │
│     编写最少量的自定义代码                   │
└─────────────────────────────────────────────┘
```

## 决策矩阵（Decision Matrix）

| 信号 | 行动 |
|--------|--------|
| 完全匹配、维护良好、MIT/Apache 协议 | **采用 (Adopt)** — 直接安装并使用 |
| 部分匹配、基础良好 | **扩展 (Extend)** — 安装 + 编写轻量封装层 |
| 多个弱匹配项 | **组合 (Compose)** — 结合 2-3 个小型包 |
| 未找到合适方案 | **自研 (Build)** — 编写自定义代码，但基于调研结论 |

## 如何使用

### 快速模式（行内使用）

在编写工具类或添加功能前，大脑中先过一遍：

0. 仓库中是否已存在？→ 先通过 `rg` 搜索相关的模块/测试
1. 这是一个常见问题吗？→ 搜索 npm/PyPI
2. 是否有相关的 MCP？→ 检查 `~/.claude/settings.json` 并搜索
3. 是否有相关的技能（Skill）？→ 检查 `~/.claude/skills/`
4. 是否有 GitHub 实现/模板？→ 在编写全新代码前，针对维护良好的开源软件（OSS）运行 GitHub 代码搜索

### 完整模式（智能体代理）

对于非平凡的功能，启动调研智能体（Researcher Agent）：

```
Task(subagent_type="general-purpose", prompt="
  调研现有的工具，针对：[功能描述]
  语言/框架：[LANG]
  约束条件：[ANY]

  搜索范围：npm/PyPI, MCP 服务器, Claude Code 技能, GitHub
  返回结果：带建议的结构化对比报告
")
```

## 按类别搜索快捷方式

### 开发工具（Development Tooling）
- 代码检查（Linting）→ `eslint`, `ruff`, `textlint`, `markdownlint`
- 格式化（Formatting）→ `prettier`, `black`, `gofmt`
- 测试（Testing）→ `jest`, `pytest`, `go test`
- Pre-commit → `husky`, `lint-staged`, `pre-commit`

### AI/LLM 集成
- Claude SDK → 参考 Context7 获取最新文档
- 提示词管理（Prompt management）→ 检查 MCP 服务器
- 文档处理 → `unstructured`, `pdfplumber`, `mammoth`

### 数据与 API
- HTTP 客户端 → `httpx` (Python), `ky`/`got` (Node)
- 验证（Validation）→ `zod` (TS), `pydantic` (Python)
- 数据库 → 优先检查 MCP 服务器

### 内容与发布
- Markdown 处理 → `remark`, `unified`, `markdown-it`
- 图像优化 → `sharp`, `imagemin`

## 集成点（Integration Points）

### 与规划智能体（Planner Agent）集成
规划器应在第一阶段（架构审查 Architecture Review）之前调用调研员：
- 调研员识别可用工具
- 规划器将它们纳入实施计划
- 避免在计划中“重复造轮子”

### 与架构智能体（Architect Agent）集成
架构师应就以下内容咨询调研员：
- 技术栈决策
- 集成模式发现
- 现有参考架构

### 与迭代检索技能（Iterative-retrieval Skill）集成
结合使用进行渐进式发现：
- 第 1 轮：广泛搜索 (npm, PyPI, MCP)
- 第 2 轮：详细评估首选候选方案
- 第 3 轮：测试与项目约束的兼容性

## 示例

### 示例 1：“添加死链检查”
```
需求：检查 markdown 文件中的损坏链接
搜索：npm "markdown dead link checker"
发现：textlint-rule-no-dead-link (得分: 9/10)
行动：采用 (ADOPT) — npm install textlint-rule-no-dead-link
结果：零自定义代码，经受过实战检验的解决方案
```

### 示例 2：“添加 HTTP 客户端封装层”
```
需求：具备重试和超时处理能力的弹性 HTTP 客户端
搜索：npm "http client retry", PyPI "httpx retry"
发现：带重试插件的 got (Node), 内置重试的 httpx (Python)
行动：采用 (ADOPT) — 直接使用带重试配置的 got/httpx
结果：零自定义代码，生产环境验证过的库
```

### 示例 3：“添加配置文件 Linter”
```
需求：根据 Schema 验证项目配置文件
搜索：npm "config linter schema", "json schema validator cli"
发现：ajv-cli (得分: 8/10)
行动：采用 + 扩展 (ADOPT + EXTEND) — 安装 ajv-cli，编写项目特定的 schema
结果：1 个包 + 1 个 schema 文件，无需自定义验证逻辑
```

## 反模式（Anti-Patterns）

- **直接编码**：不检查是否存在现成工具就编写工具类
- **忽视 MCP**：不检查 MCP 服务器是否已经提供了该功能
- **过度自定义**：对库进行过重封装，导致其丧失原有优势
- **依赖膨胀**：为了一个很小的功能安装庞大的包
