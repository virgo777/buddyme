<div align="center">

# buddyMe

**BuddyMe — 构建更聪明的智能体**

支持 6 大 LLM 供应商运行时热切换。分层人格、三级技能加载、心跳记忆，为需要灵活性的开发者而生。

支持多模型热切换 · 工具调用 · 技能系统 · 持久记忆 · 定时任务

[Blog](http://49.235.53.176/) · [GitHub](https://github.com/virgo777/buddyme)

</div>

---

## 项目简介

buddyMe 是一个 Python 实现的多模型 AI 智能体框架。它能够将复杂任务自动拆解为子任务，逐一规划、执行、验证，并合并结果。内置 25+ 技能、8 个工具、完整的记忆系统和定时调度能力，可作为编程助手或通用任务代理使用。

<div style="background-color: #f8f9fa; padding: 18px 22px; border-radius: 8px; margin: 28px 0; border-left: 4px solid #e67e22;">
  <p style="margin: 0 0 14px 0; line-height: 1.6;">欢迎访问 <a href="http://49.235.53.176/" style="color: #2563eb; text-decoration: none;">BuddyMe Blog</a> 阅读最新文章与技术分享。</p>
  <p style="color: #e67e22; font-size: 1.1em; font-weight: bold; margin: 0 0 12px 0;">📚 更新推荐阅读</p>
  <ul style="margin: 0; padding-left: 22px; line-height: 1.9;">
    <li><a href="http://49.235.53.176/blog/heartbeat-and-loop-skill-engine-deep-dive" style="color: #2563eb; text-decoration: none;">buddyMe 心跳系统与 Loop 引擎：让 AI 自己干活，还不花钱</a></li>
    <li><a href="http://49.235.53.176/blog/buddyme" style="color: #2563eb; text-decoration: none;">技术深度：buddyMe 框架任务拆解的 "盲拆" 问题与技能感知优化方案</a></li>
    <li><a href="http://49.235.53.176/blog/react-plan-and-execute-reflection" style="color: #2563eb; text-decoration: none;">ReAct、Plan-and-Execute 与 Reflection 的本质差异与落地指南</a></li>
  </ul>
</div>

## 核心特性

- **多模型支持** — GLM、DeepSeek、ERNIE、Qwen、MiMo，运行时一键切换，零中断
- **三阶段任务执行** — 规划 → 子任务执行 → 结果合并，复杂任务自动拆解
- **工具系统** — 内置 bash、文件读写/编辑、搜索、glob 等 8 个工具，支持自定义扩展
- **技能系统** — 25+ 预置技能（API 设计、前端开发、Python 测试等），三级渐进加载，运行时热重载
- **持久记忆** — 用户画像、对话摘要、历史日志跨会话保持，支持记忆衰减与合并
- **定时任务** — `/loop` 命令创建循环/定时任务，心跳线程后台轮询
- **命令系统** — `/` 前缀命令直接处理，不消耗 LLM Token
- **双协议适配** — 自动识别 OpenAI 兼容 / Anthropic 兼容协议，统一调用接口

## 支持的模型

| 配置名 | 服务商 | 模型 | 最大 Token |
|--------|--------|------|-----------|
| `glm` | 智谱 AI | glm-5.1 | 131,072 |
| `glm_code_plan` | 智谱 AI | glm-5.1 | 390,000 |
| `deepseek` | DeepSeek | deepseek-v4-pro | 393,216 |
| `deepseek_code_plan` | DeepSeek | deepseek-v4-pro | 960,000 |
| `ernie` | 百度千帆 | ernie-5.1 | 65,536 |
| `xiaomi` | 小米 | mimo-v2-pro | 131,072 |
| `qwen` | 阿里通义 | qwen3.6-plus | 65,536 |

## 安装

### 环境要求

- Python >= 3.9
- pip

### 从源码安装

```bash
git clone https://github.com/virgo777/buddyme.git
cd buddyme
pip install -e .
```

## 配置

### 1. 创建环境变量文件

在项目根目录创建 `.env` 文件，填入你的 API Key：

```bash
cp .env.example .env
```

`.env` 内容示例：

```env
GLM_API_KEY=your_glm_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
ERNIE_API_KEY=your_ernie_api_key
XIAOMI_API_KEY=your_xiaomi_api_key
QWEN_API_KEY=your_qwen_api_key
```

只需配置你实际使用的模型对应的 Key，其余可留空。

### 2. 环境变量（可选）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `BUDDYME_MODEL` | 默认模型名称 | `glm_code_plan` |
| `BUDDYME_HOME` | 用户数据目录 | `~/.buddyme/` |
| `BUDDYME_WORKSPACE` | 工作区目录 | 当前目录 |

## 快速开始

### CLI 模式
先导入脚本地址到环境，即把Scripts目录加到PATH：
```bash
set PATH=%PATH%;C:\Users\yourname\AppData\Roaming\Python\Python313\Scripts
buddyme
```

### 开发模式

```bash
python -m buddyMe
```

启动后会进入交互式对话界面：

```
============================================================
buddyMe — 多模型智能体 + Skill
项目空间: /your/workspace
默认模型: glm_code_plan
输入 /help 查看可用命令
============================================================
query:
```

## 使用示例

### 基本对话

```
query: 帮我写一个 Python 的快速排序函数
```

### 复杂任务（自动拆解）

```
query: 在当前项目下创建一个 Flask REST API，包含用户增删改查接口，写好单元测试
```

Agent 会自动将任务拆解为：项目初始化 → 模型定义 → API 路由 → 单元测试 → 验证。

### 切换模型

```
query: /model --list        # 查看可用模型
query: /model --switch deepseek  # 切换到 DeepSeek
```

### 定时任务

```
query: /loop 30m 检查当前项目的测试是否全部通过
query: /loop --list         # 查看运行中的任务
query: /loop --remove abc12345  # 移除任务
```

### 记忆管理

```
query: /memory --show       # 查看当前记忆
query: /memory --summary    # 查看对话摘要
query: /memory --update     # 手动触发记忆提取
```

## 命令列表

所有 `/` 命令在本地直接处理，不消耗 Token。

| 命令 | 别名 | 说明 |
|------|------|------|
| `/help [cmd]` | `/h` | 显示帮助 |
| `/model --list` | `/m` | 列出可用模型 |
| `/model --switch <name>` | | 切换模型 |
| `/api_key <model> <key>` | | 设置 API Key |
| `/reset` | | 清空对话历史 |
| `/exit` | `/q` | 退出 |
| `/skill --list` | | 列出已加载技能 |
| `/reload_skills` | | 热重载技能目录 |
| `/memory --show` | `/mem` | 查看用户记忆 |
| `/memory --summary` | | 查看对话摘要 |
| `/memory --update` | | 手动提取记忆 |
| `/memory --clear --force` | | 清空所有记忆 |
| `/log --today` | `/history` | 今日对话日志 |
| `/log --search <关键词>` | | 搜索对话日志 |
| `/heartbeat` | `/hb` | 心跳任务管理 |
| `/loop <间隔> <任务>` | `/lp` | 创建定时任务 |

## 内置工具

| 工具 | 说明 |
|------|------|
| `bash` | 执行 Shell 命令（异步、超时控制、危险命令拦截） |
| `read_file` | 读取文件（大文件智能截断） |
| `write_file` | 写入文件（自动创建目录） |
| `edit_file` | 精确查找替换编辑 |
| `grep` | 正则内容搜索 |
| `glob` | 文件名模式匹配 |
| `baidu_search` | 百度搜索（千帆 AI Search API） |
| `invoke_skill` | 技能激活 |

## 内置技能

| 技能 | 领域 |
|------|------|
| `api-design` | API 设计模式 |
| `backend-patterns` | 后端开发模式 |
| `frontend-design` | 前端 UI 设计 |
| `frontend-patterns` | 前端开发模式 |
| `frontend-slides` | 前端幻灯片生成 |
| `python-patterns` | Python 设计模式 |
| `python-testing` | pytest 测试实践 |
| `coding-standards` | 编码规范 |
| `deployment-patterns` | 部署策略 |
| `article-writing` | 文档写作 |
| `market-research` | 市场调研 |
| `weather-skill` | 天气查询 |
| `qqmail-1.0.0` | QQ 邮件集成 |
| `continuous-learning` | 持续学习 |
| `eval-harness` | 评估框架 |
| `markitdown-skill` | Markdown 转换 |
| `autonomous-loops` | 自主循环执行 |
| `iterative-retrieval` | 迭代式信息检索 |
| `verification-loop` | 验证循环 |
| `strategic-compact` | 战略性摘要压缩 |
| `search-first` | 搜索优先策略 |
| `content-hash-cache-pattern` | 内容哈希缓存模式 |
| `plankton-code-quality` | 代码质量分析 |
| `project-guidelines-example` | 项目规范模板 |
| `configure-ecc` | ECC 配置 |

## 架构概览

```
用户输入
  │
  ├─ /command ──→ 命令系统（本地处理，零 Token）
  │
  └─ 普通输入
      │
      ├─ 简单任务 ──→ 单次 LLM 调用 + 工具循环
      │
      └─ 复杂任务
          │
          ├─ 阶段一：任务规划 ──→ 注入 Skill 元数据 → LLM 参考已有技能拆分子任务
          │                     匹配到的步骤标注 [SKILL:技能名]
          │
          ├─ 阶段二：子任务执行 ──→ 逐个执行，每个子任务独立 LLM+工具循环
          │                       预匹配 Skill 注入完整指令 · 结果传递 · 类型分类
          │
          └─ 阶段三：结果合并 ──→ 拼接子任务结果，返回最终输出
```

### 系统提示构建

系统提示由四层动态合并：

1. **SOUL.md** — 人格内核
2. **IDENTITY.md** — 角色定义（80% 编程助手 + 20% 生活助手）
3. **AGENT.md** — 行为契约（工具规则、记忆管理、安全约束）
4. **工具 Schema** — 已注册工具的动态描述

### 目录结构

```
buddyMe/
├── agent_moudle/          # Agent 核心逻辑
├── anthropic_standard/    # LLM 客户端（双协议适配）
├── cmd_library/           # 命令系统
│   └── builtin/           # 内置命令（system/skill/memory/loop）
├── initspace/             # 初始化与上下文构建
│   ├── brain/             # 人格与行为模板
│   └── memorys/           # 记忆存储
├── llm_moudle/            # 模型配置管理
├── skill_library/         # 技能库
│   └── skills/            # 25+ 预置技能
├── tool_moudle/           # 工具模块
└── utils/                 # 工具函数
```

## 项目依赖

```
httpx          # HTTP 客户端
rich           # 终端富文本渲染
python-dotenv  # 环境变量加载
```

## License

MIT
