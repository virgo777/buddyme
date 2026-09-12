# BuddyMe 生图 API 契约 / Image Generation API Contract

## 鉴权（必须）/ Auth (required)

```text
Authorization: Bearer bk-你的Key
```

- 仅接受站点通用 API Key 或登录 JWT，不接受匿名。
  Only the site API key or a login JWT is accepted; no anonymous access.
- Key 申请：https://www.buddyme.cn/panel →「站点通用 API Key」。
  Apply at https://www.buddyme.cn/panel → "站点通用 API Key".

## 生成 / Generate

```text
POST https://www.buddyme.cn/api/genimg/generate
Content-Type: multipart/form-data
```

| 字段 / Field | 必填 / Required | 说明 / Description |
|---|---|---|
| `prompt` | 是 / yes | 画面描述 ≤2000 字。/ Image prompt, ≤2000 chars. |
| `quality` | 否 / no | `低` / `中` / `高`，默认 `中`。/ low / medium / high, default medium. |
| `images` | 否 / no | 参考图文件，≤4 张，jpg/png/gif/webp，单张 ≤8MB；多图在 prompt 中以「图一/图二」指代。/ Reference images, ≤4, each ≤8MB; refer to them as 图一/图二 in the prompt. |

### 成功返回 / Success（HTTP 200, JSON）

```json
{
  "url": "https://www.buddyme.cn/uploads/genimg_1789...png",
  "remaining": 7
}
```

`url` 为本站托管的永久直链；`remaining` 为该账号当日剩余额度（点）。
`url` is a permanent link hosted on our site; `remaining` is the account's
leftover credits (points) today.

### 规格（服务端固定）/ Fixed server-side specs

GPT-Image-2.5（Flare）· 1K · 1:1 · 每次一张。
GPT-Image-2.5 (Flare) · 1K · 1:1 · one image per call.

## 额度查询 / Quota

```text
GET https://www.buddyme.cn/api/genimg/quota
Authorization: Bearer bk-你的Key
```

```json
{
  "used": 2, "limit": 10, "remaining": 8,
  "ip": "1.2.3.4", "ip_used": 2, "ip_limit": 20, "ip_remaining": 18
}
```

## 额度规则 / Credit Rules

- 账号每日 10 点；同 IP 所有账号合计每日 20 点（管理员无豁免）。
  10 credits/account/day; 20 shared credits/IP/day (no admin exemption).
- **API Key 与网页登录合并计算同一额度池**：每个 Key 每日上限即其所属账号的
  10 点，Key 调用与网页生成互相占用。
  **Keys and web logins share one merged pool**: a key's daily cap is its
  owner account's 10 credits; key calls and web generations draw together.
- 低=1 点 / 中=2 点 / 高=3 点；**成功才扣，失败不扣**。
  low=1, medium=2, high=3 credits; **charged only on success**.
- 额度不足以支付所选档位时返回 429（不会扣成负数）。
  If credits can't cover the chosen tier, 429 is returned (never negative).

## 错误 / Errors

| 状态 / Code | 含义 / Meaning |
|---|---|
| 400 | 参数错误（质量档、图格式/大小/数量）。/ Bad params (tier, image format/size/count). |
| 401 | Key 无效或未提供。/ Key invalid or missing. |
| 429 | 账号额度不足 / IP 合计限额 / 提示换低档。/ Insufficient credits / IP cap / try a lower tier. |
| 502 | 上游异常或「image2.5维护中」（不扣点，稍后重试）。/ Upstream failure or model maintenance (no deduction; retry later). |

## 客户端建议 / Client Recommendations

- 超时 ≥120 秒（上游生成 20~60 秒，偶发排队）。
  Timeout ≥120s (generation takes 20-60s, occasional queuing).
- 502/504 可安全重试（服务端有幂等保护，不会重复扣点）。
  502/504 can be retried safely (server-side idempotency; no double charge).

```bash
curl -H "Authorization: Bearer bk-你的Key" \
  -F "prompt=a green leaf icon" -F "quality=低" \
  https://www.buddyme.cn/api/genimg/generate
```
