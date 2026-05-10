---
name: configure-ecc
description: Everything Claude Code 的交互式安装程序 —— 引导用户选择并将技能（Skills）和规则（Rules）安装到用户级或项目级目录，验证路径，并可选地优化已安装的文件。
origin: ECC
---

# 配置 Everything Claude Code (ECC)

一个针对 Everything Claude Code 项目的交互式分步安装向导。使用 `AskUserQuestion` 引导用户选择性地安装技能（Skills）和规则（Rules），然后验证正确性并提供优化建议。

## 何时激活

- 用户说 "configure ecc"、"install ecc"、"setup everything claude code" 或类似指令时
- 用户想要从本项目中选择性安装技能（Skills）或规则（Rules）时
- 用户想要验证或修复现有的 ECC 安装时
- 用户想要为他们的项目优化已安装的技能（Skills）或规则（Rules）时

## 前提条件

此技能（Skill）在激活前必须可被 Claude Code 访问。有两种引导方式：
1. **通过插件**：`/plugin install everything-claude-code` —— 插件会自动加载此技能
2. **手动方式**：仅将此技能复制到 `~/.claude/skills/configure-ecc/SKILL.md`，然后通过说 "configure ecc" 来激活

---

## 步骤 0：克隆 ECC 仓库

在进行任何安装之前，先将最新的 ECC 源码克隆到 `/tmp`：

```bash
rm -rf /tmp/everything-claude-code
git clone https://github.com/affaan-m/everything-claude-code.git /tmp/everything-claude-code
```

设置 `ECC_ROOT=/tmp/everything-claude-code` 作为后续所有复制操作的源路径。

如果克隆失败（网络问题等），使用 `AskUserQuestion` 请用户提供现有 ECC 克隆的本地路径。

---

## 步骤 1：选择安装层级

使用 `AskUserQuestion` 询问用户安装位置：

```
问题："ECC 组件应该安装在哪里？"
选项：
  - "用户级 (~/.claude/)" —— "适用于你所有的 Claude Code 项目"
  - "项目级 (.claude/)" —— "仅适用于当前项目"
  - "两者皆有" —— "通用/共享项安装在用户级，项目特定项安装在项目级"
```

将选择结果存储为 `INSTALL_LEVEL`。设置目标目录：
- 用户级：`TARGET=~/.claude`
- 项目级：`TARGET=.claude`（相对于当前项目根目录）
- 两者皆有：`TARGET_USER=~/.claude`，`TARGET_PROJECT=.claude`

如果目标目录不存在，则创建它们：
```bash
mkdir -p $TARGET/skills $TARGET/rules
```

---

## 步骤 2：选择并安装技能（Skills）

### 2a：选择范围（核心 vs 小众）

默认为 **核心（Core，推荐新用户使用）** —— 复制 `.agents/skills/*` 以及 `skills/search-first/` 以支持研究优先的工作流。该组合包涵盖了工程、评测（Evals）、验证、安全、战略压缩、前端设计以及 Anthropic 跨职能技能（文章写作、内容引擎、市场调研、前端演示文稿）。

使用 `AskUserQuestion`（单选）：
```
问题："仅安装核心技能，还是包含小众/框架扩展包？"
选项：
  - "仅核心（推荐）" —— "tdd, e2e, evals, verification, research-first, security, frontend patterns, compacting, 跨职能 Anthropic 技能"
  - "核心 + 选定的小众技能" —— "在核心技能之后添加框架/领域特定技能"
  - "仅小众技能" —— "跳过核心，安装特定的框架/领域技能"
默认：仅核心
```

如果用户选择小众技能或核心 + 小众技能，继续进行下方的类别选择，并仅包含他们挑选的那些小众技能。

### 2b：选择技能类别

共有 27 个技能被组织在 4 个类别中。使用 `AskUserQuestion` 并设置 `multiSelect: true`：

```
问题："你想安装哪些技能类别？"
选项：
  - "框架与语言" —— "Django, Spring Boot, Go, Python, Java, 前端, 后端模式"
  - "数据库" —— "PostgreSQL, ClickHouse, JPA/Hibernate 模式"
  - "工作流与质量" —— "TDD, 验证, 学习, 安全审查, 压缩"
  - "所有技能" —— "安装所有可用技能"
```

### 2c：确认单个技能

对于每个选定的类别，打印下方的完整技能列表，并要求用户确认或取消选择特定的技能。如果列表超过 4 项，将列表作为文本打印，并使用 `AskUserQuestion` 提供“安装所有列出的项”选项，以及“其他”选项供用户粘贴特定名称。

**类别：框架与语言 (17 个技能)**

| 技能 (Skill) | 描述 |
|-------|-------------|
| `backend-patterns` | 后端架构、API 设计、Node.js/Express/Next.js 的服务端最佳实践 |
| `coding-standards` | TypeScript、JavaScript、React、Node.js 的通用代码标准 |
| `django-patterns` | Django 架构、使用 DRF 的 REST API、ORM、缓存、信号（signals）、中间件 |
| `django-security` | Django 安全：认证、CSRF、SQL 注入、XSS 防护 |
| `django-tdd` | 使用 pytest-django、factory_boy、mocking、coverage 进行 Django 测试 |
| `django-verification` | Django 验证循环：迁移、lint 检查、测试、安全扫描 |
| `frontend-patterns` | React、Next.js、状态管理、性能、UI 模式 |
| `frontend-slides` | 零依赖的 HTML 演示文稿、样式预览以及 PPTX 转 Web 功能 |
| `golang-patterns` | 地道的 Go 模式，构建健壮 Go 应用的惯例 |
| `golang-testing` | Go 测试：表格驱动测试、子测试、基准测试、模糊测试 |
| `java-coding-standards` | Spring Boot 的 Java 代码标准：命名、不可变性、Optional、流（streams） |
| `python-patterns` | Pythonic 惯用语、PEP 8、类型提示、最佳实践 |
| `python-testing` | 使用 pytest 进行 Python 测试，包含 TDD、fixtures、mocking、参数化 |
| `springboot-patterns` | Spring Boot 架构、REST API、分层服务、缓存、异步 |
| `springboot-security` | Spring Security：认证/授权、验证、CSRF、机密信息、限流 |
| `springboot-tdd` | 使用 JUnit 5、Mockito、MockMvc、Testcontainers 进行 Spring Boot TDD |
| `springboot-verification` | Spring Boot 验证：构建、静态分析、测试、安全扫描 |

**类别：数据库 (3 个技能)**

| 技能 (Skill) | 描述 |
|-------|-------------|
| `clickhouse-io` | ClickHouse 模式、查询优化、分析、数据工程 |
| `jpa-patterns` | JPA/Hibernate 实体设计、关系、查询优化、事务 |
| `postgres-patterns` | PostgreSQL 查询优化、模式设计、索引、安全 |

**类别：工作流与质量 (8 个技能)**

| 技能 (Skill) | 描述 |
|-------|-------------|
| `continuous-learning` | 从会话中自动提取可复用的模式作为学到的技能 |
| `continuous-learning-v2` | 基于直觉（Instinct）的学习，带有置信度评分，可演变为技能/命令/智能体 |
| `eval-harness` | 用于评测驱动开发（EDD）的正式评测框架 |
| `iterative-retrieval` | 针对子智能体（subagent）上下文问题的渐进式上下文精炼 |
| `security-review` | 安全清单：认证、输入、机密信息、API、支付功能 |
| `strategic-compact` | 在逻辑间隔处建议手动压缩上下文（Context） |
| `tdd-workflow` | 强制执行 TDD，覆盖率 80%+：单元测试、集成测试、E2E |
| `verification-loop` | 验证与质量循环模式 |

**类别：业务与内容 (5 个技能)**

| 技能 (Skill) | 描述 |
|-------|-------------|
| `article-writing` | 使用笔记、示例或源文档，以提供的语调进行长文写作 |
| `content-engine` | 多平台社交内容、脚本及内容再利用工作流 |
| `market-research` | 带有来源归因的市场、竞争对手、基金和技术研究 |
| `investor-materials` | 融资路演包（Pitch decks）、单页简介（One-pagers）、投资者备忘录和财务模型 |
| `investor-outreach` | 个性化的投资者开发信（Cold emails）、熟人介绍（Warm intros）及跟进邮件 |

**独立项**

| 技能 (Skill) | 描述 |
|-------|-------------|
| `project-guidelines-example` | 创建项目特定技能的模板 |

### 2d：执行安装

对于每个选定的技能，复制整个技能目录：
```bash
cp -r $ECC_ROOT/skills/<skill-name> $TARGET/skills/
```

注意：`continuous-learning` 和 `continuous-learning-v2` 包含额外文件（config.json、hooks、scripts）—— 确保复制整个目录，而不仅仅是 SKILL.md。

---

## 步骤 3：选择并安装规则（Rules）

使用 `AskUserQuestion` 并设置 `multiSelect: true`：

```
问题："你想安装哪些规则集？"
选项：
  - "通用规则（推荐）" —— "与语言无关的原则：代码风格、git 工作流、测试、安全等（8 个文件）"
  - "TypeScript/JavaScript" —— "TS/JS 模式、Hooks、使用 Playwright 的测试（5 个文件）"
  - "Python" —— "Python 模式、pytest、black/ruff 格式化（5 个文件）"
  - "Go" —— "Go 模式、表格驱动测试、gofmt/staticcheck（5 个文件）"
```

执行安装：
```bash
# 通用规则（扁平复制到 rules/）
cp -r $ECC_ROOT/rules/common/* $TARGET/rules/

# 语言特定规则（扁平复制到 rules/）
cp -r $ECC_ROOT/rules/typescript/* $TARGET/rules/   # 如果选中
cp -r $ECC_ROOT/rules/python/* $TARGET/rules/        # 如果选中
cp -r $ECC_ROOT/rules/golang/* $TARGET/rules/        # 如果选中
```

**重要提示**：如果用户选择了任何语言特定规则但没有选择通用规则，请提醒他们：
> "语言特定规则是对通用规则的扩展。在不安装通用规则的情况下安装可能会导致覆盖不完整。是否也安装通用规则？"

---

## 步骤 4：安装后验证

安装完成后，执行以下自动检查：

### 4a：验证文件是否存在

列出所有已安装的文件并确认它们存在于目标位置：
```bash
ls -la $TARGET/skills/
ls -la $TARGET/rules/
```

### 4b：检查路径引用

扫描所有已安装的 `.md` 文件中的路径引用：
```bash
grep -rn "~/.claude/" $TARGET/skills/ $TARGET/rules/
grep -rn "../common/" $TARGET/rules/
grep -rn "skills/" $TARGET/skills/
```

**对于项目级安装**，标记任何指向 `~/.claude/` 路径的引用：
- 如果一个技能引用了 `~/.claude/settings.json` —— 这通常没问题（设置始终是用户级的）
- 如果一个技能引用了 `~/.claude/skills/` 或 `~/.claude/rules/` —— 如果仅安装在项目级，这可能会失效
- 如果一个技能通过名称引用了另一个技能 —— 检查被引用的技能是否也已安装

### 4c：检查技能间的交叉引用

某些技能会引用其他技能。验证这些依赖关系：
- `django-tdd` 可能会引用 `django-patterns`
- `springboot-tdd` 可能会引用 `springboot-patterns`
- `continuous-learning-v2` 引用了 `~/.claude/homunculus/` 目录
- `python-testing` 可能会引用 `python-patterns`
- `golang-testing` 可能会引用 `golang-patterns`
- 语言特定规则引用了 `common/` 对应的规则

### 4d：报告问题

对于发现的每个问题，报告以下内容：
1. **文件**：包含问题引用的文件
2. **行号**：所在行号
3. **问题描述**：哪里出错了（例如 "引用了 ~/.claude/skills/python-patterns 但 python-patterns 未安装"）
4. **建议修复方案**：该怎么做（例如 "安装 python-patterns 技能" 或 "将路径更新为 .claude/skills/"）

---

## 步骤 5：优化已安装的文件（可选）

使用 `AskUserQuestion`：

```
问题："你想为你的项目优化已安装的文件吗？"
选项：
  - "优化技能（Skills）" —— "移除无关章节，调整路径，适配你的技术栈"
  - "优化规则（Rules）" —— "调整覆盖率目标，添加项目特定模式，自定义工具配置"
  - "优化两者" —— "对所有安装文件进行全面优化"
  - "跳过" —— "保持原样"
```

### 如果优化技能：
1. 读取每个已安装的 SKILL.md
2. 询问用户的项目技术栈（如果尚不清楚）
3. 对于每个技能，建议移除无关章节
4. 在安装目标位置（而非源码仓库）就地编辑 SKILL.md 文件
5. 修复步骤 4 中发现的任何路径问题

### 如果优化规则：
1. 读取每个已安装的规则 .md 文件
2. 询问用户的偏好：
   - 测试覆盖率目标（默认 80%）
   - 首选的格式化工具
   - Git 工作流惯例
   - 安全要求
3. 在安装目标位置就地编辑规则文件

**关键提示**：仅修改安装目标（`$TARGET/`）中的文件，绝不要修改源 ECC 仓库（`$ECC_ROOT/`）中的文件。

---

## 步骤 6：安装总结

从 `/tmp` 中清理克隆的仓库：

```bash
rm -rf /tmp/everything-claude-code
```

然后打印一份总结报告：

```
## ECC 安装完成

### 安装目标
- 层级：[用户级 / 项目级 / 两者皆有]
- 路径：[目标路径]

### 已安装技能 ([数量])
- skill-1, skill-2, skill-3, ...

### 已安装规则 ([数量])
- 通用规则 (8 个文件)
- typescript (5 个文件)
- ...

### 验证结果
- 发现 [数量] 个问题，已修复 [数量] 个
- [列出任何剩余问题]

### 已应用的优化
- [列出所做的更改，或 "无"]
```

---

## 故障排除

### "技能未被 Claude Code 识别"
- 验证技能目录包含 `SKILL.md` 文件（而不仅仅是分散的 .md 文件）
- 对于用户级：检查 `~/.claude/skills/<skill-name>/SKILL.md` 是否存在
- 对于项目级：检查 `.claude/skills/<skill-name>/SKILL.md` 是否存在

### "规则不生效"
- 规则应为扁平文件，不应放在子目录中：`$TARGET/rules/coding-style.md`（正确）vs `$TARGET/rules/common/coding-style.md`（对于扁平安装是错误的）
- 安装规则后重启 Claude Code

### "项目级安装后出现路径引用错误"
- 某些技能假定路径为 `~/.claude/`。运行步骤 4 的验证来发现并修复这些问题。
- 对于 `continuous-learning-v2`，`~/.claude/homunculus/` 目录始终是用户级的 —— 这是预期的，不是错误。
