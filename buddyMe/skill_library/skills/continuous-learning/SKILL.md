---
name: continuous-learning
description: Automatically extract reusable patterns from Claude Code sessions and save them as learned skills for future use.
origin: ECC
---

# 持续学习技能（Continuous Learning Skill）

在会话结束时自动评估 Claude Code 会话，提取可保存为已学习技能（Learned Skills）的可复用模式。

## 何时激活

- 设置从 Claude Code 会话中自动提取模式
- 为会话评估配置 `Stop` 钩子（Hook）
- 查看或整理 `~/.claude/skills/learned/` 中的已学习技能
- 调整提取阈值或模式类别
- 比较 v1（当前）与 v2（基于直觉/Instinct）的方法

## 工作原理

此技能在每个会话结束时作为 **Stop 钩子（Hook）** 运行：

1. **会话评估**：检查会话是否有足够的消息（默认：10 条以上）
2. **模式检测**：从会话中识别可提取的模式
3. **技能提取**：将有用的模式保存到 `~/.claude/skills/learned/`

## 配置

编辑 `config.json` 进行自定义：

```json
{
  "min_session_length": 10,
  "extraction_threshold": "medium",
  "auto_approve": false,
  "learned_skills_path": "~/.claude/skills/learned/",
  "patterns_to_detect": [
    "error_resolution",
    "user_corrections",
    "workarounds",
    "debugging_techniques",
    "project_specific"
  ],
  "ignore_patterns": [
    "simple_typos",
    "one_time_fixes",
    "external_api_issues"
  ]
}
```

## 模式类型

| 模式 | 描述 |
|---------|-------------|
| `error_resolution` | 特定错误的解决方法 |
| `user_corrections` | 来自用户纠偏的模式 |
| `workarounds` | 针对框架/库缺陷的解决方案 |
| `debugging_techniques` | 有效的调试方法 |
| `project_specific` | 项目特定的约定 |

## 钩子设置（Hook Setup）

添加到您的 `~/.claude/settings.json`：

```json
{
  "hooks": {
    "Stop": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "~/.claude/skills/continuous-learning/evaluate-session.sh"
      }]
    }]
  }
}
```

## 为什么使用 Stop 钩子？

- **轻量化**：仅在会话结束时运行一次
- **非阻塞**：不会给每条消息增加延迟
- **完整上下文**：可以访问完整的会话记录

## 相关内容

- [长篇指南（The Longform Guide）](https://x.com/affaanmustafa/status/2014040193557471352) - 关于持续学习的章节
- `/learn` 命令 - 会话中途手动提取模式

---

## 比较笔记（调研：2025年1月）

### 与 Homunculus 对比

Homunculus v2 采用了更复杂的方法：

| 特性 | 我们的方法 | Homunculus v2 |
|---------|--------------|---------------|
| 观察机制（Observation） | `Stop` 钩子（会话结束） | `PreToolUse`/`PostToolUse` 钩子（100% 可靠） |
| 分析方式（Analysis） | 主上下文（Main context） | 后台智能体（Haiku agent） |
| 粒度（Granularity） | 完整技能（Full skills） | 原子化“直觉”（Atomic "instincts"） |
| 置信度（Confidence） | 无 | 0.3-0.9 权重 |
| 演进路径（Evolution） | 直接生成技能 | 直觉 → 聚类 → 技能/命令/智能体 |
| 共享方式（Sharing） | 无 | 导出/导入直觉 |

**来自 Homunculus 的关键见解：**
> “v1 依赖技能（Skills）进行观察。技能是概率性的——它们的触发频率约为 50-80%。v2 使用钩子（Hooks）进行观察（100% 可靠），并将‘直觉（Instincts）’作为学习行为的原子单位。”

### 潜在的 v2 增强功能

1. **基于直觉的学习** - 带有置信度评分的更小、原子化的行为
2. **后台观察者** - 并行分析的 Haiku 智能体
3. **置信度衰减** - 如果发生冲突，直觉的置信度会降低
4. **领域标签** - 代码风格、测试、Git、调试等
5. **演进路径** - 将相关的直觉聚类为技能/命令

参见：`/Users/affoon/Documents/tasks/12-continuous-learning-v2.md` 获取完整规范。
