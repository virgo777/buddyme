# Command base classes for the CLI command library.

"""
cmd_library/base.py — 命令系统的类型定义和基类
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


# ============================================================
# 命令上下文
# ============================================================

@dataclass
class CommandContext:
    """
    传递给每个命令处理函数的上下文对象。
    命令函数通过此对象访问 Agent 内部状态，避免直接耦合。
    """
    # Agent 引用
    agent: Any

    # 当前使用的模型名
    model_name: str

    # 原始用户输入（完整字符串，含命令前缀）
    raw_input: str

    # 命令名（去掉前缀后的规范名）
    command_name: str

    # 命令参数（命令名之后的部分，原始字符串）
    args_text: str

    # 解析后的参数列表（按空格分割，引号内视为一个参数）
    args_list: List[str] = field(default_factory=list)


# ============================================================
# 命令处理函数签名（Protocol）
# ============================================================

class CommandHandler(Protocol):
    """命令处理函数的标准签名: (ctx: CommandContext) -> CommandResult"""
    def __call__(self, ctx: CommandContext) -> "CommandResult": ...


# ============================================================
# 命令执行结果
# ============================================================

@dataclass
class CommandResult:
    """
    命令执行结果。

    Attributes:
        success: 是否成功执行
        message: 返回给用户的消息
        data: 可选的附加数据
        should_exit: 是否应退出 Agent 主循环
    """
    success: bool = True
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    should_exit: bool = False

    def __str__(self) -> str:
        return self.message


# ============================================================
# 命令元数据
# ============================================================

@dataclass
class CommandMeta:
    """命令注册时的元数据"""
    name: str
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    usage: str = ""
    category: str = "general"
    hidden: bool = False
