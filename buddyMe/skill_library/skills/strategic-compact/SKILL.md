---
name: strategic-compact
description: Suggests manual context compaction at logical intervals to preserve context through task phases rather than arbitrary auto-compaction.
origin: ECC
---

# 策略性压缩技能 (Strategic Compact Skill)

建议在工作流的战略点手动执行 `/compact`，而不是依赖随机的自动压缩。

## 何时激活 (When to Activate)

- 运行接近上下文限制（200K+ token）的长会话时
- 处理多阶段任务（研究 → 规划 → 实现 → 测试）时
- 在同一个会话中切换不相关的任务时
- 完成重大里程碑并开始新工作后
- 当响应变慢或连贯性下降（上下文压力）时

## 为什么需要策略性压缩？ (Why Strategic Compaction?)

自动压缩会在任意点触发：
- 通常在任务中途触发，导致丢失重要的上下文
- 无法识别逻辑任务边界
- 可能会中断复杂的多步操作

在逻辑边界进行策略性压缩：
- **研究之后，执行之前** — 压缩研究上下文，保留实现计划
- **完成里程碑之后** — 为下一阶段提供清新起点
- **重大上下文切换之前** — 在进入不同任务前清理探索性上下文

## 工作原理 (How It Works)

`suggest-compact.js` 脚本在工具预调用（PreToolUse，包括 Edit/Write）时运行，并执行：

1. **跟踪工具调用** — 统计会话中的工具调用次数
2. **阈值检测** — 在达到可配置阈值时提供建议（默认：50 次调用）
3. **定期提醒** — 超过阈值后，每 25 次调用提醒一次

## 钩子设置 (Hook Setup)

将以下内容添加到你的 `~/.claude/settings.json`：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit",
        "hooks": [{ "type": "command", "command": "node ~/.claude/skills/strategic-compact/suggest-compact.js" }]
      },
      {
        "matcher": "Write",
        "hooks": [{ "type": "command", "command": "node ~/.claude/skills/strategic-compact/suggest-compact.js" }]
      }
    ]
  }
}
```

## 配置 (Configuration)

环境变量：
- `COMPACT_THRESHOLD` — 首次建议前的工具调用次数（默认：50）

## 压缩决策指南 (Compaction Decision Guide)

参考下表决定何时进行压缩：

| 阶段转换 | 是否压缩？ | 原因 |
|-----------------|----------|-----|
| 研究 → 规划 | 是 | 研究上下文很臃肿；计划是精炼后的输出 |
| 规划 → 实现 | 是 | 计划已记录在 `TodoWrite` 或文件中；为代码腾出上下文空间 |
| 实现 → 测试 | 视情况而定 | 如果测试引用了最近的代码则保留；如果切换关注点则压缩 |
| 调试 → 下一个特性 | 是 | 调试追踪信息会污染不相关工作的上下文 |
| 实现过程中 | 否 | 丢失变量名、文件路径和部分状态的代价很高 |
| 尝试方案失败后 | 是 | 在尝试新方案前清理掉死胡同的推理过程 |

## 哪些内容在压缩后存留 (What Survives Compaction)

了解哪些内容会持久化，可以让你放心地进行压缩：

| 存留项 | 丢失项 |
|----------|------|
| `CLAUDE.md` 指令 | 中间推理与分析过程 |
| `TodoWrite` 任务列表 | 之前读取的文件内容 |
| 记忆文件 (`~/.claude/memory/`) | 多轮对话上下文 |
| Git 状态（提交、分支） | 工具调用历史与计数 |
| 磁盘上的文件 | 口头陈述的细微用户偏好 |

## 最佳实践 (Best Practices)

1. **规划后压缩** — 一旦在 `TodoWrite` 中确定了计划，进行压缩以重新开始
2. **调试后压缩** — 在继续之前清理错误解决的上下文
3. **不要在实现中途压缩** — 为相关更改保留上下文
4. **阅读建议** — 钩子告诉你*何时*可以压缩，由你决定*是否*执行
5. **压缩前写入** — 在压缩前将重要的上下文保存到文件或记忆中
6. **使用带摘要的 `/compact`** — 添加自定义消息：`/compact Focus on implementing auth middleware next`

## 相关资源 (Related)

- [长篇指南 (The Longform Guide)](https://x.com/affaanmustafa/status/2014040193557471352) — Token 优化章节
- 记忆持久化钩子 — 用于在压缩后存留的状态
- `continuous-learning` 技能 — 在会话结束前提取模式
