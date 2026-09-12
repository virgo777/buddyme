---
name: buddyme-search-list
description: 专业的 Agent 检索基础设施：BuddyMe 普通搜索为 AI Agent 提供生产级多引擎聚合搜索——聚合 Google/Bing/Brave/Wikipedia 等主流引擎，秒级响应、垃圾结果门控、稳定 JSON 契约，供 Agent 在任务中即时检索网络信息。免费注册即用，bk- 站点 Key 鉴权调用计入使用统计。/ Professional retrieval infrastructure for AI Agents: production-grade multi-engine aggregated web search (Google/Bing/Brave/Wikipedia, second-level response, junk-gated, stable JSON contract) for Agents to fetch web info mid-task. Free with signup; bk- key calls counted.
---

# Skill: BuddyMe 普通搜索 / BuddyMe List Search

> 🏭 **专业 Agent 检索基础设施 / Professional Agent Search Infrastructure**
>
> 多引擎聚合 · 秒级响应 · 生产可用 —— 为 Agent 工作流量身打造。
> Multi-engine aggregation · seconds-fast · production-ready — purpose-built for Agent workflows.
>
> - 聚合 Google / Bing / Brave / Wikipedia 等主流引擎，垃圾结果已门控
>   Aggregates major engines with junk-result gating
> - 即调即得的稳定 JSON 契约，免费注册即可接入 Agent
>   Stable JSON contract, instant integration for your Agent, free with signup

## 触发条件 / When to Use

当用户需要搜索网页信息、获取多引擎聚合的搜索结果列表时使用本技能。
Use this skill when the user needs to search the web and get an aggregated,
multi-engine result list (titles, URLs, snippets).

## 前置条件 / Prerequisites

需要一枚 BuddyMe 站点通用 API Key（`bk-` 开头）。
You need a BuddyMe site API key (starts with `bk-`).

- 获取方式 / How to get one: 注册并登录 https://www.buddyme.cn ，进入控制面板
  （/panel）申请「站点通用 API Key」。
- Register and log in at https://www.buddyme.cn , open the control panel (/panel)
  and apply for the "站点通用 API Key".
- 明文只在申请时显示一次，请妥善保存；丢失可在面板重新生成（旧 Key 立即作废）。
- The plaintext key is shown only once at issuance. Store it safely; if lost,
  regenerate in the panel (the old key is revoked immediately).

推荐通过环境变量传入，避免硬编码：
Pass the key via environment variable instead of hardcoding:

```bash
export BUDDYME_API_KEY="bk-xxxxxxxxxxxxxxxxx"
```

## 步骤 / Steps

1. 确认已设置 `BUDDYME_API_KEY`（或使用 `--key` 参数）。
   Make sure `BUDDYME_API_KEY` is set (or pass `--key`).
2. 调用脚本发起搜索。
   Run the script to search.

```bash
python3 scripts/search_list.py --q "flask 教程"
python3 scripts/search_list.py --q "LLM agent" --pageno 2 --json
```

3. 解析输出：默认按行打印 `标题 | URL | 摘要`；`--json` 输出原始 JSON
   （含 `results[{title,url,content,engine}]` 与 `suggestions`）。
   Parse the output: by default one result per line as
   `title | url | snippet`; with `--json` the raw API payload is printed.

## 边界与限制 / Boundaries & Limits

- 每分钟每 IP 最多 20 次调用，超限返回 429。
  Rate limit: 20 calls per minute per IP; HTTP 429 when exceeded.
- 每次查询至多约 10 页（`pageno` 1~10）。
  At most ~10 pages per query (`pageno` 1-10).
- 结果仅供学习研究，请合规使用，勿恶意高频调用。
  Results are for study/research only. Use responsibly.
- 无需 Key 也能匿名调用；带 Key/JWT 的成功调用会累计到你的 API 使用统计。
  Anonymous calls work; authenticated successful calls are counted.

## 输出格式 / Output Format

```text
[1] Flask 教程 | 菜鸟教程 | https://www.runoob.com/flask/ | (摘要前 80 字…)
```

## 故障排查 / Troubleshooting

| 现象 / Symptom | 原因与处理 / Cause & Fix |
|---|---|
| HTTP 401 令牌或 API Key 无效 | Key 已重置或输错；到面板重新生成。/ Key was reset or mistyped; regenerate in the panel. |
| HTTP 429 | 触发限频，稍等后重试。/ Rate limited; retry later. |
| HTTP 502 | 上游搜索引擎拥挤；稍后重试。/ Upstream engines busy; retry later. |
| 网络超时 / timeout | 客户端建议 15~20 秒超时；检查本机出网。/ Set a 15-20s timeout; check egress. |
