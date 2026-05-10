---
name: plankton-code-quality
description: "使用 Plankton 实现编写时代码质量强制执行 —— 通过钩子在每次文件编辑时进行自动格式化、代码检查，并由 Claude 驱动自动修复。"
origin: community
---

# Plankton 代码质量技能（Plankton Code Quality Skill）

Plankton（感谢 @alxfazio）的集成参考，这是一个针对 Claude Code 的编写时（Write-time）代码质量强制执行系统。Plankton 通过工具调用后钩子（PostToolUse hooks）在每次文件编辑时运行格式化程序和 Linter，然后启动 Claude 子进程（Subprocess）来修复智能体（Agent）未捕捉到的违规项。

## 适用场景

- 你希望在每次文件编辑时（而不只是提交时）自动进行格式化和代码检查。
- 你需要防御智能体通过修改 Linter 配置来绕过检查，而不是真正修复代码。
- 你希望针对修复任务进行分级模型路由（Haiku 用于简单样式，Sonnet 用于逻辑，Opus 用于类型）。
- 你使用多种语言进行开发（Python, TypeScript, Shell, YAML, JSON, TOML, Markdown, Dockerfile）。

## 工作原理

### 三阶段架构

每当 Claude Code 编辑或写入文件时，Plankton 的 `multi_linter.sh` 工具调用后钩子（PostToolUse hook）就会运行：

```
阶段 1: 自动格式化 (静默)
├─ 运行格式化程序 (ruff format, biome, shfmt, taplo, markdownlint)
├─ 静默修复 40-50% 的问题
└─ 不向主智能体输出任何内容

阶段 2: 收集违规项 (JSON)
├─ 运行 Linter 并收集无法自动修复的违规项
├─ 返回结构化 JSON: {line, column, code, message, linter}
└─ 仍不向主智能体输出任何内容

阶段 3: 委派 + 验证
├─ 启动带有违规 JSON 的 claude -p 子进程
├─ 根据违规复杂性路由到不同层级的模型：
│   ├─ Haiku: 格式化、导入、样式 (E/W/F 代码) — 120s 超时
│   ├─ Sonnet: 复杂性、重构 (C901, PLR 代码) — 300s 超时
│   └─ Opus: 类型系统、深度推理 (unresolved-attribute) — 600s 超时
├─ 重新运行阶段 1+2 以验证修复结果
└─ 如果清理完成则 Exit 0，如果仍存在违规项则 Exit 2（报告给主智能体）
```

### 主智能体看到的内容

| 场景 | 智能体看到的内容 | 钩子退出码 |
|----------|-----------|-----------|
| 无违规项 | 无 | 0 |
| 子进程修复了所有问题 | 无 | 0 |
| 子进程处理后仍存在违规 | `[hook] N violation(s) remain` | 2 |
| 建议性信息 (重复、旧工具) | `[hook:advisory] ...` | 0 |

主智能体只看到子进程无法修复的问题。大多数质量问题都会被透明地解决。

### 配置保护 (防御规则博弈)

LLM 有时会尝试修改 `.ruff.toml` 或 `biome.json` 来禁用规则，而不是修复代码。Plankton 通过三层防护来阻止这种情况：

1. **工具调用前钩子（PreToolUse hook）** — `protect_linter_configs.sh` 在修改发生前阻止对所有 Linter 配置的编辑。
2. **停止钩子（Stop hook）** — `stop_config_guardian.sh` 在会话结束时通过 `git diff` 检测配置更改。
3. **受保护文件列表** — 包括 `.ruff.toml`, `biome.json`, `.shellcheckrc`, `.yamllint`, `.hadolint.yaml` 等。

### 包管理器强制执行

Bash 上的工具调用前钩子（PreToolUse hook）会阻止使用旧版包管理器：
- `pip`, `pip3`, `poetry`, `pipenv` → 已阻止 (请使用 `uv`)
- `npm`, `yarn`, `pnpm` → 已阻止 (请使用 `bun`)
- 允许的例外情况: `npm audit`, `npm view`, `npm publish`

## 设置

### 快速开始

```bash
# 将 Plankton 克隆到你的项目（或共享位置）
# 注: Plankton 由 @alxfazio 开发
git clone https://github.com/alexfazio/plankton.git
cd plankton

# 安装核心依赖
brew install jaq ruff uv

# 安装 Python linter
uv sync --all-extras

# 启动 Claude Code — 钩子将自动激活
claude
```

无需安装命令，无需插件配置。当你向在 Plankton 目录中运行 Claude Code 时，`.claude/settings.json` 中的钩子会自动被加载。

### 针对单个项目的集成

要在你自己的项目中使用 Plankton 钩子：

1. 将 `.claude/hooks/` 目录复制到你的项目。
2. 复制 `.claude/settings.json` 中的钩子配置。
3. 复制 Linter 配置文件 (`.ruff.toml`, `biome.json` 等)。
4. 为你的语言安装相应的 Linter。

### 特定语言的依赖项

| 语言 | 必需 | 可选 |
|----------|----------|----------|
| Python | `ruff`, `uv` | `ty` (类型), `vulture` (死代码), `bandit` (安全) |
| TypeScript/JS | `biome` | `oxlint`, `semgrep`, `knip` (死导出) |
| Shell | `shellcheck`, `shfmt` | — |
| YAML | `yamllint` | — |
| Markdown | `markdownlint-cli2` | — |
| Dockerfile | `hadolint` (>= 2.12.0) | — |
| TOML | `taplo` | — |
| JSON | `jaq` | — |

## 与 ECC 配合使用

### 互补而非重叠

| 关注点 | ECC | Plankton |
|---------|-----|----------|
| 代码质量强制执行 | 工具调用后钩子 (Prettier, tsc) | 工具调用后钩子 (20+ Linter + 子进程修复) |
| 安全扫描 | AgentShield, security-reviewer 智能体 | Bandit (Python), Semgrep (TypeScript) |
| 配置保护 | — | 工具调用前钩子阻止 + 停止钩子检测 |
| 包管理器 | 检测 + 设置 | 强制执行 (阻止旧版包管理器) |
| CI 集成 | — | 用于 git 的 Pre-commit 钩子 |
| 模型路由 | 手动 (`/model opus`) | 自动 (违规复杂性 → 相应层级) |

### 推荐组合

1. 安装 ECC 作为你的插件（智能体、技能、命令、规则）。
2. 添加 Plankton 钩子用于编写时质量强制执行。
3. 使用 AgentShield 进行安全审计。
4. 使用 ECC 的验证循环（verification-loop）作为 PR 前的最终门控。

### 避免钩子冲突

如果同时运行 ECC 和 Plankton 钩子：
- ECC 的 Prettier 钩子和 Plankton 的 biome 格式化程序可能会在 JS/TS 文件上发生冲突。
- 解决方法：在使用 Plankton 时禁用 ECC 的 Prettier 工具调用后钩子（Plankton 的 biome 更全面）。
- 两者可以在不同文件类型上共存（ECC 可以处理 Plankton 未涵盖的内容）。

## 配置参考

Plankton 的 `.claude/hooks/config.json` 控制所有行为：

```json
{
  "languages": {
    "python": true,
    "shell": true,
    "yaml": true,
    "json": true,
    "toml": true,
    "dockerfile": true,
    "markdown": true,
    "typescript": {
      "enabled": true,
      "js_runtime": "auto",
      "biome_nursery": "warn",
      "semgrep": true
    }
  },
  "phases": {
    "auto_format": true,
    "subprocess_delegation": true
  },
  "subprocess": {
    "tiers": {
      "haiku":  { "timeout": 120, "max_turns": 10 },
      "sonnet": { "timeout": 300, "max_turns": 10 },
      "opus":   { "timeout": 600, "max_turns": 15 }
    },
    "volume_threshold": 5
  }
}
```

**关键设置:**
- 禁用你不使用的语言以加快钩子运行速度。
- `volume_threshold` — 违规数超过此值将自动升级到更高级别的模型。
- `subprocess_delegation: false` — 完全跳过阶段 3（仅报告违规项）。

## 环境变量覆盖

| 变量 | 用途 |
|----------|---------|
| `HOOK_SKIP_SUBPROCESS=1` | 跳过阶段 3，直接报告违规项 |
| `HOOK_SUBPROCESS_TIMEOUT=N` | 覆盖模型层级的超时时间 |
| `HOOK_DEBUG_MODEL=1` | 记录模型选择决策 |
| `HOOK_SKIP_PM=1` | 绕过包管理器强制执行 |

## 参考资料

- Plankton (感谢 @alxfazio)
- Plankton REFERENCE.md — 完整架构文档 (感谢 @alxfazio)
- Plankton SETUP.md — 详细安装指南 (感谢 @alxfazio)
