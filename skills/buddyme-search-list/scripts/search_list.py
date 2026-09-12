#!/usr/bin/env python3
"""BuddyMe 普通搜索 API 客户端（纯标准库）/ List-search client, stdlib only.

用法 / Usage:
    export BUDDYME_API_KEY="bk-..."        # 推荐 / recommended
    python3 search_list.py --q "flask 教程"
    python3 search_list.py --q "LLM" --pageno 2 --json
"""
import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://www.buddyme.cn/api/search/list"
TIMEOUT = 20  # 秒 / seconds


def search(q: str, key: str, pageno: int = 1) -> dict:
    """调用普通搜索 API，返回解析后的 JSON。/ Call the list-search API, return parsed JSON."""
    params = urllib.parse.urlencode({"q": q, "pageno": pageno})
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(f"{API_URL}?{params}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        raise SystemExit(f"HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise SystemExit(f"网络错误 / network error: {e.reason}")


def main():
    ap = argparse.ArgumentParser(description="BuddyMe 普通搜索 / list search")
    ap.add_argument("--q", required=True, help="搜索关键词 / query keywords")
    ap.add_argument("--pageno", type=int, default=1, help="页码 1~10 / page number")
    ap.add_argument("--key", default=os.environ.get("BUDDYME_API_KEY", ""),
                    help="API Key（默认取环境变量 BUDDYME_API_KEY）/ API key")
    ap.add_argument("--json", action="store_true", help="输出原始 JSON / print raw JSON")
    args = ap.parse_args()

    data = search(args.q, args.key, args.pageno)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    results = data.get("results") or []
    if not results:
        print("无结果 / no results")
        return
    for i, it in enumerate(results, 1):
        title = (it.get("title") or "").strip()
        url = it.get("url") or ""
        snippet = (it.get("content") or "").replace("\n", " ")[:80]
        print(f"[{i}] {title} | {url} | {snippet}…")


if __name__ == "__main__":
    main()
