"""
================================================================================
utils.py - 公共工具函数
================================================================================

供 contextbuild、memorybuild、memory_extractor、use_memory 共用的基础函数。

导出:
    _load_md(md_path)   — 读取 .md 文件（支持绝对/相对/项目根路径）
    _extract_json(text)  — 从 LLM 回复中提取第一个 JSON 对象
    _PROJECT_ROOT        — 项目根目录绝对路径

================================================================================
"""

import json
import re
from pathlib import Path

from buddyMe.utils.paths import get_user_data_dir

_PROJECT_ROOT = str(get_user_data_dir())


def _load_md(md_path: str) -> str:
    """读取指定的 .md 文件内容。

    路径解析策略：
        1. 先按原始路径解析（支持绝对路径和 cwd 相对路径）
        2. 若找不到，再按项目根目录解析（兼容从任意目录运行）

    Args:
        md_path: 文件路径（绝对路径、相对路径均可）

    Returns:
        文件内容字符串；文件不存在时返回空字符串。
    """
    abs_path = Path(md_path).resolve()
    if not abs_path.exists():
        abs_path = Path(_PROJECT_ROOT) / md_path
    if not abs_path.exists():
        return ""
    return abs_path.read_text(encoding="utf-8").strip()


def _extract_json(text: str) -> dict:
    """从 LLM 回复中提取第一个 JSON 对象（使用花括号计数匹配最短完整 JSON）。"""
    start = text.find("{")
    if start == -1:
        return {}

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

    return {}
