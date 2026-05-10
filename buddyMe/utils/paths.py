"""统一路径解析 — pathlib 实现，替代分散的 os.path 调用"""

import os
from pathlib import Path
from typing import Optional


def get_package_dir() -> Path:
    """buddyMe 源码包根目录（只读模板）"""
    return Path(__file__).resolve().parent.parent


def get_user_data_dir() -> Path:
    """用户数据目录。BUDDYME_HOME 环境变量可覆盖，默认 ~/.buddyme/"""
    env = os.environ.get("BUDDYME_HOME")
    if env:
        return Path(env).resolve()
    return Path.home() / ".buddyme"


def get_workspace_dir() -> Path:
    """Agent 工作空间（文件输出目录）。默认当前工作目录。"""
    env = os.environ.get("BUDDYME_WORKSPACE")
    if env:
        return Path(env).resolve()
    return Path.cwd()


def resolve_data_dir(data_dir_override: Optional[str] = None) -> Path:
    """解析运行时数据目录。
    - data_dir_override 非空：直接使用（dev 模式）
    - 否则：~/.buddyme/（CLI 模式）
    """
    if data_dir_override:
        return Path(data_dir_override).resolve()
    return get_user_data_dir()
