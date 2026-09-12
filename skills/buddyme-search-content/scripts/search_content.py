#!/usr/bin/env python3
"""BuddyMe 聚合搜索 API 客户端（纯标准库）/ Content-aggregation client, stdlib only.

用法 / Usage:
    export BUDDYME_API_KEY="bk-..."
    python3 search_content.py --q "BGE embedding"
    python3 search_content.py --q "transformer" --json
"""
import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://www.buddyme.cn/api/search/content"
TIMEOUT = 40  # 聚合含抓取，给足时间 / aggregation includes fetching


def fetch(q: str, key: str):
    params = urllib.parse.urlencode({"q": q})
    req = urllib.request.Request(
        f"{API_URL}?{params}",
        headers={"Authorization": f"Bearer {key}"} if key else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            return e.code, {}
    except urllib.error.URLError as e:
        raise SystemExit(f"网络错误 / network error: {e.reason}")


def main():
    ap = argparse.ArgumentParser(description="BuddyMe 聚合搜索 / content aggregation")
    ap.add_argument("--q", required=True, help="主题 / topic")
    ap.add_argument("--key", default=os.environ.get("BUDDYME_API_KEY", ""),
                    help="API Key（默认环境变量 BUDDYME_API_KEY）/ API key")
    ap.add_argument("--json", action="store_true", help="输出原始 JSON / raw JSON")
    args = ap.parse_args()

    code, data = fetch(args.q, args.key)
    if code != 200:
        raise SystemExit(f"HTTP {code}: {json.dumps(data, ensure_ascii=False)[:300]}")

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    st = data.get("stats") or {}
    ms = (st.get("ms_fetch") or 0) + (st.get("ms_rank") or 0) + (st.get("ms_searx") or 0)
    combined = data.get("combined") or ""
    if not combined or not (st.get("sources") or 0):
        print("无可聚合正文 / nothing to aggregate（sources=0，建议改用普通搜索 / try list search）")
        return

    print(f"== 来源 {st.get('sources')} 条 · 精选 {st.get('packed')} 段 · 耗时 {(ms / 1000):.1f}s ==")
    print()
    print(combined)
    print()
    print("== 来源 / sources ==")
    for s in data.get("segments") or []:
        print(f"[{s.get('rank')}] {s.get('title')} — {s.get('url')}")


if __name__ == "__main__":
    main()
