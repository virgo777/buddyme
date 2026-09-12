# BuddyMe 普通搜索 API 契约 / List Search API Contract

## 端点 / Endpoint

```text
GET https://www.buddyme.cn/api/search/list?q=<URL编码关键词>&pageno=<1-10>
Authorization: Bearer bk-你的Key     # 可选；带 Key 的调用计入使用统计
                                    # optional; authenticated calls are counted
```

## 参数 / Parameters

| 参数 / Param | 必填 / Required | 说明 / Description |
|---|---|---|
| `q` | 是 / yes | 搜索关键词，URL 编码，≤200 字。/ Query keywords, URL-encoded, ≤200 chars. |
| `pageno` | 否 / no | 页码，1~10，默认 1。/ Page number, 1-10, default 1. |

## 返回 / Response（HTTP 200, JSON）

```json
{
  "results": [
    {
      "title": "结果标题 / result title",
      "url": "https://example.com/page",
      "content": "内容摘要 / snippet text …",
      "engine": "bing"
    }
  ],
  "suggestions": ["相关词 / related term", "..."]
}
```

## 错误 / Errors

| 状态 / Code | 含义 / Meaning |
|---|---|
| 400 | 参数错误（缺 q 或超长）。/ Bad parameters (missing q or too long). |
| 429 | 限频：每 IP 每分钟 20 次。/ Rate limited: 20 req/min per IP. |
| 502 | 上游搜索引擎异常。/ Upstream engine failure. |

## 配额与统计 / Quota & Statistics

- 匿名可调用；带 `bk-` Key 或登录 JWT 的成功调用会累计到该用户的
  「一般搜索 API」使用次数（管理员可见）。
  Anonymous calls work; successful authenticated calls (bk- key or JWT)
  increment the user's list-search API usage counter (visible to admins).
- Key 申请：https://www.buddyme.cn/panel →「站点通用 API Key」。
  Apply for a key at https://www.buddyme.cn/panel → "站点通用 API Key".

## 客户端建议 / Client Recommendations

- 超时设 15~20 秒。/ Set a 15-20s timeout.
- 收到 429 时指数退避重试。/ Back off exponentially on 429.
- curl 示例 / example:

```bash
curl -H "Authorization: Bearer bk-你的Key" \
  "https://www.buddyme.cn/api/search/list?q=flask%20%E6%95%99%E7%A8%8B"
```
