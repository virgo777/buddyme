# BuddyMe 聚合搜索 API 契约 / Content Aggregation API Contract

## 端点 / Endpoint

```text
GET https://www.buddyme.cn/api/search/content?q=<URL编码主题>
Authorization: Bearer bk-你的Key     # 可选；带 Key 的成功调用计入使用统计
```

## 参数 / Parameters

| 参数 / Param | 必填 / Required | 说明 / Description |
|---|---|---|
| `q` | 是 / yes | 主题词，URL 编码，≤200 字。/ Topic, URL-encoded, ≤200 chars. |

## 返回 / Response（HTTP 200, JSON）

```json
{
  "combined": "聚合正文（≤4000 字，原文直出不总结，逐段含来源标记）…",
  "segments": [
    {
      "rank": 1,
      "title": "来源标题 / source title",
      "url": "https://example.com/a",
      "text": "该段原文 / segment original text …",
      "chars": 620
    }
  ],
  "stats": {
    "sources": 10, "packed": 6,
    "ms_fetch": 2338, "ms_rank": 821, "ms_searx": 2205,
    "gate": "dual", "gate_passed": 19, "pages_ok": 10
  }
}
```

`stats.gate=dual` 表示 BM25 词面 + 语义向量双确认精选；
`stats.gate=fallback` 表示降级到词面模式。
`stats.gate=dual` means dual-confirmation (BM25 + semantic vector) selection;
`fallback` means lexical-only degraded mode.

## 错误 / Errors

| 状态 / Code | 含义 / Meaning |
|---|---|
| 400 | 参数错误。/ Bad parameters. |
| 429 | 限频：每 IP 每分钟 8 次。/ Rate limited: 8 req/min per IP. |
| 502 | 上游异常。/ Upstream failure. |

注意：`combined` 为空或 `stats.sources=0` 时表示该主题无可聚合正文
（HTTP 仍可能是 200），客户端应回退到普通搜索。
Note: empty `combined` or `stats.sources=0` means nothing aggregatable for the
topic (HTTP may still be 200); clients should fall back to list search.

## 配额与统计 / Quota & Statistics

- 带 Key/JWT 的成功调用累计到用户「聚合搜索 API」使用次数。
  Successful authenticated calls increment the user's content-search counter.
- 服务端缓存 10 分钟，同词重复调用更快、不重复计上游开销。
  Server-side cache: 10 minutes; repeated same-topic calls are faster.

## 客户端建议 / Client Recommendations

- 超时 35~40 秒；429 指数退避。
  Timeout 35-40s; exponential backoff on 429.
- curl 示例 / example:

```bash
curl -H "Authorization: Bearer bk-你的Key" \
  "https://www.buddyme.cn/api/search/content?q=BGE+embedding"
```
