---
name: buddyme-genimg
description: 专业的 Agent 制图服务：BuddyMe 生图基于 GPT-Image-2.5（1K/1:1/一次一张），低中高三档质量（各扣 1/2/3 点额度），支持 ≤4 张参考图（图一/图二指示），为 Agent 工作流提供按需出图能力；图片永久直链、失败不扣额度，每日 10 点免费额度（同 IP 合计 20 点）。需 bk- 站点 Key。/ Professional image generation for AI Agents: GPT-Image-2.5 (1K/1:1/one per call), low-medium-high tiers (1/2/3 credits), ≤4 reference images (图一/图二 addressing) for on-demand imagery in Agent workflows; permanent image URLs, failures cost nothing, 10 free credits/day (20/IP shared). bk- site key required.
---

# Skill: BuddyMe 免费生图 / BuddyMe Image Generation

> 🎨 **专业 Agent 制图服务 / Professional Agent Image Service**
>
> GPT-Image-2.5 · 三档质量 · 永久直链 —— Agent 的随叫随到美术组。
> GPT-Image-2.5 · three quality tiers · permanent URLs — the on-call art department for Agents.
>
> - 低/中/高三档质量自由匹配成本与效果，失败不扣额度
>   Low/medium/high tiers to match cost vs quality; failures are free
> - 图片落盘本站永久直链，Agent 可直接引用交付
>   Images hosted with permanent URLs, ready for Agents to reference and deliver

## 触发条件 / When to Use

当用户需要用文字描述生成一张图片时使用本技能（GPT-Image-2.5 模型）。
Use this skill to generate one image from a text prompt (GPT-Image-2.5 model).

## 前置条件 / Prerequisites

**必须**持有一枚 BuddyMe 站点通用 API Key（`bk-` 开头）——生图 API 不接受匿名调用。
A BuddyMe site API key (`bk-` …) is **required**; the generation API rejects
anonymous calls.

- 获取方式 / How to get one: https://www.buddyme.cn 注册登录 → 控制面板（/panel）
  →「站点通用 API Key」。
- 明文只显示一次；丢失可在面板重新生成（旧 Key 立即作废）。
  Plaintext shown once; regenerate if lost (old key revoked immediately).

```bash
export BUDDYME_API_KEY="bk-xxxxxxxxxxxxxxxxx"
```

## 额度规则 / Credit Rules（重要 / important）

- 每个账号每日 **10 点**；同一 IP 所有账号合计每日 **20 点**（含管理员一律如此）。
  Each account gets **10 credits/day**; all accounts on one IP share
  **20 credits/day** (admins included, no exemption).
- **API Key 与网页登录共用同一额度池，合并计算**：每个 API Key 每日最多消耗其
  所属账号的 10 点——用 Key 调接口、用网页登录生成，扣的是同一份额度。
  **API keys and web logins share one merged credit pool**: each key can
  consume at most its owner account's 10 daily credits — key calls and
  web generations deduct from the same pool.
- 质量档位扣点：**低 = 1 点 / 中 = 2 点 / 高 = 3 点**。
  Quality tiers cost: **low = 1, medium = 2, high = 3 credits**.
- **生成失败不扣点**；额度不足该档位时返回 429 并提示换低档。
  **Failed generations cost nothing**; insufficient credits returns 429.

## 步骤 / Steps

```bash
# 生成（默认中档质量）/ generate (medium quality by default)
python3 scripts/genimg.py --prompt "一只戴眼镜的橘猫坐在书桌前，扁平插画" --quality 低

# 生成并保存到文件 / generate and save to a file
python3 scripts/genimg.py --prompt "a green leaf icon, flat vector" --quality 中 --out cat.png

# 查询今日剩余额度 / check remaining credits
python3 scripts/genimg.py --quota
```

## 参数与规格 / Parameters & Specs（固定 / fixed）

| 项 / Item | 值 / Value |
|---|---|
| 模型 / model | GPT-Image-2.5（Flare），服务端固定 / fixed server-side |
| 清晰度 / resolution | 1K |
| 比例 / ratio | 1:1 |
| 数量 / count | 每次一张 / one image per call |
| `quality` | `低` / `中` / `高`（low / medium / high） |
| `prompt` | ≤2000 字；描述越具体效果越稳。/ ≤2000 chars. |
| 参考图 / ref images | 可选 ≤4 张（jpg/png/gif/webp，单张 ≤8MB）多图在 prompt 中用「图一/图二」指示。/ optional, ≤4. |

## 输出 / Output

- 成功：打印图片直链（永久有效）与剩余额度；指定 `--out` 时同时保存文件。
  On success: prints the permanent image URL and remaining credits; saves to
  a file when `--out` is given.

## 边界与限制 / Boundaries & Limits

- 单次生成约 20~60 秒，客户端超时建议 ≥120 秒。
  One generation takes ~20-60s; set a client timeout ≥120s.
- 上游偶发 502/504 或模型维护（「image2.5维护中」），属外部状态：稍后重试，**不扣点**。
  Upstream may return 502/504 or maintenance — retry later; **no credits deducted**.
- 请勿生成违法有害内容。/ Do not generate illegal or harmful content.

## 故障排查 / Troubleshooting

| 现象 / Symptom | 原因与处理 / Cause & Fix |
|---|---|
| HTTP 401 | 未带 Key / Key 已重置；面板重新生成。/ Missing or reset key. |
| HTTP 429 额度不足 | 换低档或明日再用。/ Lower the tier or wait. |
| HTTP 429 IP 限额 | 同 IP 合计 20 点已满。/ Shared IP cap exhausted. |
| 「image2.5维护中」 | 上游维护；稍后重试。/ Upstream maintenance; retry later. |
