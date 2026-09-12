#!/usr/bin/env python3
"""生图 Skill 自检 / Genimg skill self-test.

用法 / Usage:
    export BUDDYME_API_KEY="bk-..."
    python3 tests/test_genimg.py

说明：上游 GPT-Image-2.5 维护期间，生成返回 502「image2.5维护中」——
这属于文档化的外部状态（不扣点），本测试将其标记为 MAINTENANCE 而非失败。
Note: while upstream GPT-Image-2.5 is under maintenance, generation returns
502 "image2.5维护中" — a documented external state (no credits deducted);
this test marks it MAINTENANCE instead of failure.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from genimg import _get, _post_multipart  # noqa: E402

KEY = os.environ.get("BUDDYME_API_KEY", "")
PASSED, FAILED, SKIPPED = 0, 0, 0


def check(name, cond, detail="", skip=False):
    global PASSED, FAILED, SKIPPED
    mark = "○" if skip else ("✓" if cond else "✗")
    print(f"  {mark} {name} {detail}")
    if skip:
        SKIPPED += 1
    elif cond:
        PASSED += 1
    else:
        FAILED += 1


if not KEY:
    raise SystemExit("先设置 BUDDYME_API_KEY / set BUDDYME_API_KEY first")

print("== 1. 额度查询（鉴权验证）/ quota endpoint (auth check)")
code, data = _get("https://www.buddyme.cn/api/genimg/quota", KEY)
check("HTTP 200", code == 200, f"got {code}")
check("额度字段 / credit fields", all(k in data for k in ("used", "limit", "remaining")),
      f"剩余 {data.get('remaining')}/{data.get('limit')} 点")

print("== 2. 无效 Key 应 401 / invalid key rejected")
code2, _ = _get("https://www.buddyme.cn/api/genimg/quota", "bk-invalidkey000000000")
check("HTTP 401", code2 == 401, f"got {code2}")

print("== 3. 真实生成（低档 1 点）/ real generation (low tier, 1 credit)")
code3, data3 = _post_multipart(
    "https://www.buddyme.cn/api/genimg/generate",
    KEY, {"prompt": "a tiny gray dot on white background, flat, no text", "quality": "低"}, [])
if code3 == 200:
    check("生成成功 / generated", bool(data3.get("url")), data3.get("url", "")[:60])
    check("返回剩余额度 / remaining returned", isinstance(data3.get("remaining"), int))
elif code3 == 502 and "维护" in json.dumps(data3, ensure_ascii=False):
    check("上游维护中（外部状态，不扣点）/ upstream maintenance", True,
          json.dumps(data3, ensure_ascii=False)[:60], skip=True)
else:
    check("生成 / generation", False, f"HTTP {code3}: {json.dumps(data3, ensure_ascii=False)[:120]}")

print(f"\n结果 / result: {PASSED} passed, {FAILED} failed, {SKIPPED} maintenance-skip")
sys.exit(1 if FAILED else 0)
