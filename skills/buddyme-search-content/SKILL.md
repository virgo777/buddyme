---
name: buddyme-search-content
description: 专业的 Agent 全文聚合服务：BuddyMe 聚合搜索为 AI Agent 抓取多来源正文，BM25 词面 + 语义向量双确认精选（≤4000 字，原文直出不总结、逐段注明来源），开箱即喂 LLM 做后续推理，服务端缓存 10 分钟。免费注册即用，需 bk- 站点 Key。/ Professional full-text aggregation for AI Agents: multi-source fetch with BM25 + semantic dual-confirmation selection (≤4000 chars, original text with no summarization, per-segment citations), ready to feed LLM reasoning; 10-min server cache. Free with signup; bk- site key required.
---

# Skill: BuddyMe 聚合搜索 / BuddyMe Content Aggregation Search

> 🧠 **专业 Agent 全文聚合引擎 / Professional Agent Full-text Engine**
>
> 双确认精选 · 原文直出 · 一搜胜十搜 —— Agent 的知识获取利器。
> Dual-confirmation selection · original text verbatim — the knowledge-acquisition edge for Agents.
>
> - BM25 词面 + 语义向量双确认，精选段落逐段可溯源
>   BM25 + semantic dual confirmation; every selected segment citable
> - ≤4000 字结构化输出，即取即用喂给 LLM 推理
>   ≤4000-char structured output, ready for downstream LLM reasoning

## 触发条件 / When to Use

当用户需要围绕一个主题快速拿到**聚合正文**（多来源抓取 + 双确认精选，
原文直出、不总结、逐段注明来源）时使用本技能。
Use this skill when you need an **aggregated full-text digest** around a topic:
multi-source fetching, dual-confirmation segment selection, original text
without summarization, every segment cited with its source.

适合喂给 LLM 做后续分析，或人工快速通读一个主题。
Great for feeding an LLM for further analysis, or for a human to skim a topic.

## 前置条件 / Prerequisites

需要一枚 BuddyMe 站点通用 API Key（`bk-` 开头）。
You need a BuddyMe site API key (starts with `bk-`).

- 获取方式 / How to get one: https://www.buddyme.cn 注册登录 → 控制面板（/panel）
  →「站点通用 API Key」。
- Register at https://www.buddyme.cn , open /panel, apply for the
  "站点通用 API Key".
- 明文只显示一次；丢失可在面板重新生成（旧 Key 立即作废）。
- Plaintext shown once; regenerate if lost (old key revoked immediately).

```bash
export BUDDYME_API_KEY="bk-xxxxxxxxxxxxxxxxx"
```

## 步骤 / Steps

```bash
python3 scripts/search_content.py --q "BGE embedding"
python3 scripts/search_content.py --q "transformer 架构" --json
```

- 默认输出：统计行（来源数/精选段数/耗时）+ 聚合正文 + 来源清单。
  Default output: a stats line (sources/segments/elapsed), the combined text,
  then the source list.
- `--json` 输出原始 JSON：`combined` + `segments[{rank,title,url,text,chars}]` + `stats`。
  With `--json`, the raw payload is printed: `combined`,
  `segments[{rank,title,url,text,chars}]`, `stats`.

## 边界与限制 / Boundaries & Limits

- 单次耗时约 3~6 秒（含网页抓取），客户端超时建议 35 秒。
  Each call takes ~3-6s (includes page fetching); set a 35s client timeout.
- 每分钟每 IP 最多 8 次，超限返回 429。
  Rate limit: 8 calls per minute per IP; HTTP 429 when exceeded.
- 聚合正文 ≤4000 字、精选 ≤6 段；服务端缓存 10 分钟（同词重复调用更快）。
  Combined text ≤4000 chars, ≤6 selected segments; server caches 10 minutes.
- 天气/实时行情等动态页面可能无可提取正文（sources=0），此时返回失败标记，
  请改用普通搜索技能。
  Dynamic pages (weather/live quotes) may have no extractable text
  (sources=0); fall back to the list-search skill in that case.
- 仅供学习研究，请合规使用。
  For study/research only; use responsibly.

## 输出格式 / Output Format

```text
== 来源 10 条 · 精选 6 段 · 耗时 4.2s ==
（聚合正文，逐段带来源编号）
[1] 来源标题 / source title — https://…
```

## 故障排查 / Troubleshooting

| 现象 / Symptom | 原因与处理 / Cause & Fix |
|---|---|
| HTTP 401 | Key 无效/已重置；面板重新生成。/ Key invalid or reset; regenerate. |
| HTTP 429 | 限频（8 次/分钟）；稍后再试。/ Rate limited (8/min); retry later. |
| sources=0 / 无可聚合正文 | 主题太新或页面动态渲染；换表述或改用普通搜索。/ Topic too fresh or dynamic pages; rephrase or use list search. |
| HTTP 502 | 上游异常；稍后重试。/ Upstream failure; retry later. |
