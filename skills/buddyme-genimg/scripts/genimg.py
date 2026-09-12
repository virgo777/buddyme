#!/usr/bin/env python3
"""BuddyMe 免费生图 API 客户端（纯标准库）/ Image-generation client, stdlib only.

用法 / Usage:
    export BUDDYME_API_KEY="bk-..."
    python3 genimg.py --prompt "一只橘猫，扁平插画" --quality 低
    python3 genimg.py --prompt "a green leaf icon" --quality 中 --out leaf.png
    python3 genimg.py --quota
"""
import argparse
import json
import mimetypes
import os
import sys
import uuid
import urllib.error
import urllib.request

BASE = "https://www.buddyme.cn/api/genimg"
GENERATE_URL = f"{BASE}/generate"
QUOTA_URL = f"{BASE}/quota"
TIMEOUT = 180  # 生成含排队，给足时间 / generation may queue


def _post_multipart(url: str, key: str, fields: dict, files: list) -> tuple[int, dict]:
    """标准库实现 multipart/form-data 上传。/ stdlib multipart/form-data POST."""
    boundary = f"----buddymeskill{uuid.uuid4().hex}"
    body = []
    for name, value in fields.items():
        body.append(f"--{boundary}\r\n"
                    f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8"))
    for name, path in files:
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        fname = os.path.basename(path)
        body.append(f"--{boundary}\r\n"
                    f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{fname}\"\r\n"
                    f"Content-Type: {ctype}\r\n\r\n".encode("utf-8"))
        with open(path, "rb") as f:
            body.append(f.read())
        body.append(b"\r\n")
    body.append(f"--{boundary}--\r\n".encode("utf-8"))
    data = b"".join(body)

    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    })
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


def _get(url: str, key: str) -> tuple[int, dict]:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            return e.code, {}
    except urllib.error.URLError as e:
        raise SystemExit(f"网络错误 / network error: {e.reason}")


def main():
    ap = argparse.ArgumentParser(description="BuddyMe 免费生图 / free image generation")
    ap.add_argument("--prompt", help="画面描述 / image prompt (≤2000 chars)")
    ap.add_argument("--quality", default="中", choices=["低", "中", "高"],
                    help="质量档位：低=1点 中=2点 高=3点 / quality tier (credits 1/2/3)")
    ap.add_argument("--ref", action="append", default=[],
                    help="参考图路径，可多次传，最多 4 张 / reference image path, repeatable, max 4")
    ap.add_argument("--out", help="保存到文件 / save image to file")
    ap.add_argument("--quota", action="store_true", help="仅查询额度 / only check credits")
    ap.add_argument("--key", default=os.environ.get("BUDDYME_API_KEY", ""),
                    help="API Key（默认环境变量 BUDDYME_API_KEY）/ API key")
    args = ap.parse_args()

    if not args.key:
        raise SystemExit("缺少 API Key / missing API key：设置 BUDDYME_API_KEY 或用 --key")

    if args.quota:
        code, data = _get(QUOTA_URL, args.key)
        print(json.dumps(data, ensure_ascii=False, indent=2) if code == 200
              else f"HTTP {code}: {json.dumps(data, ensure_ascii=False)}")
        return

    if not args.prompt:
        raise SystemExit("需要 --prompt / --prompt is required")

    if len(args.ref) > 4:
        raise SystemExit("参考图最多 4 张 / at most 4 reference images")
    files = [("images", p) for p in args.ref]

    print(f"生成中 / generating（{args.quality}档，约 20~60 秒）…", file=sys.stderr)
    code, data = _post_multipart(GENERATE_URL, args.key,
                                 {"prompt": args.prompt, "quality": args.quality}, files)
    if code != 200:
        raise SystemExit(f"HTTP {code}: {json.dumps(data, ensure_ascii=False)[:300]}")

    url = data.get("url") or ""
    print(url)
    print(f"剩余额度 / credits left: {data.get('remaining')}")

    if args.out and url:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as resp, open(args.out, "wb") as f:
            f.write(resp.read())
        print(f"已保存 / saved: {args.out}")


if __name__ == "__main__":
    main()
