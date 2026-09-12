#!/usr/bin/env python3
"""普通搜索 Skill 自检 / List-search skill self-test.

用法 / Usage:
    export BUDDYME_API_KEY="bk-..."
    python3 tests/test_search_list.py
退出码 0 = 全部通过 / exit 0 = all passed
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from search_list import API_URL, TIMEOUT  # noqa: E402

KEY = os.environ.get("BUDDYME_API_KEY", "")
PASSED, FAILED = 0, 0


def call(params: dict, key: str):
    req = urllib.request.Request(
        f"{API_URL}?{urllib.parse.urlencode(params)}",
        headers={"Authorization": f"Bearer {key}"} if key else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def check(name: str, cond: bool, detail: str = ""):
    global PASSED, FAILED
    print(f"  {'✓' if cond else '✗'} {name} {detail}")
    PASSED, FAILED = PASSED + (1 if cond else 0), FAILED + (0 if cond else 1)


print("== 1. 带 Key 正常搜索 / authenticated search")
code, data = call({"q": "flask tutorial"}, KEY)
check("HTTP 200", code == 200, f"got {code}")
check("results 非空 / results non-empty", bool(data.get("results")), f"{len(data.get('results') or [])} 条")
check("字段契约 / field contract",
      all(k in (data["results"][0] if data.get("results") else {})
          for k in ("title", "url", "content")) if data.get("results") else False)

print("== 2. 无 Key 也可匿名调用 / anonymous call works")
code2, _ = call({"q": "anonymous test"}, "")
check("HTTP 200", code2 == 200, f"got {code2}")

print("== 3. 无效 Key 应 401 / invalid key rejected")
code3, _ = call({"q": "x"}, "bk-invalidkey000000000")
check("HTTP 401", code3 == 401, f"got {code3}")

print(f"\n结果 / result: {PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
