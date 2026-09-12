#!/usr/bin/env python3
"""聚合搜索 Skill 自检 / Content-search skill self-test.

用法 / Usage:
    export BUDDYME_API_KEY="bk-..."
    python3 tests/test_search_content.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from search_content import fetch  # noqa: E402

KEY = os.environ.get("BUDDYME_API_KEY", "")
PASSED, FAILED = 0, 0


def check(name, cond, detail=""):
    global PASSED, FAILED
    print(f"  {'✓' if cond else '✗'} {name} {detail}")
    PASSED, FAILED = PASSED + (1 if cond else 0), FAILED + (0 if cond else 1)


print("== 1. 带 Key 聚合（真实主题） / authenticated aggregation")
code, data = fetch("BGE embedding", KEY)
check("HTTP 200", code == 200, f"got {code}")
if code == 200:
    st = data.get("stats") or {}
    check("有聚合正文 / combined non-empty", bool(data.get("combined")))
    check("segments 契约 / segments contract",
          isinstance(data.get("segments"), list) and (not data["segments"] or
          all(k in data["segments"][0] for k in ("rank", "title", "url"))))
    check("stats 诊断字段 / stats fields", "sources" in st and "packed" in st,
          f"sources={st.get('sources')} packed={st.get('packed')}")

print("== 2. 10 分钟缓存验证 / server cache (same query twice)")
t0 = time.time()
code2, _ = fetch("BGE embedding", KEY)
elapsed = time.time() - t0
check("第二次成功 / second call ok", code2 == 200, f"took {elapsed:.1f}s")

print("== 3. 无效 Key 应 401 / invalid key rejected")
code3, _ = fetch("x", "bk-invalidkey000000000")
check("HTTP 401", code3 == 401, f"got {code3}")

print(f"\n结果 / result: {PASSED} passed, {FAILED} failed")
sys.exit(1 if FAILED else 0)
