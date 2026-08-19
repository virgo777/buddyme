# Command registry: name-to-handler resolution for the CLI.

"""
cmd_library/registry.py — 命令注册表

职责:
1. 维护命令名 → 处理函数的映射
2. 解析用户输入，匹配命令
3. 执行命令并返回结果
"""

from __future__ import annotations
import shlex
from typing import Any, Dict, List, Optional, Tuple

from .base import CommandContext, CommandHandler, CommandMeta, CommandResult


class CommandRegistry:
    """
    命令注册表。

    使用方式:
        registry = CommandRegistry(prefix="/")

        @registry.register(name="help", aliases=["h"], description="显示帮助")
        def cmd_help(ctx: CommandContext) -> CommandResult:
            return CommandResult(message="帮助信息...")

        result = registry.dispatch(user_input, agent_instance)
    """

    def __init__(self, prefix: str = "/"):
        self._prefix = prefix
        self._handlers: Dict[str, CommandHandler] = {}
        self._metas: Dict[str, CommandMeta] = {}
        self._aliases: Dict[str, str] = {}

    # --------------------------------------------------------
    # 注册 API
    # --------------------------------------------------------

    def register(
        self,
        name: str,
        aliases: Optional[List[str]] = None,
        description: str = "",
        usage: str = "",
        category: str = "general",
        hidden: bool = False,
    ):
        """装饰器方式注册命令。"""
        def decorator(handler: CommandHandler) -> CommandHandler:
            meta = CommandMeta(
                name=name,
                aliases=aliases or [],
                description=description,
                usage=usage or f"{self._prefix}{name}",
                category=category,
                hidden=hidden,
            )
            self._add_command(name, handler, meta)
            return handler
        return decorator

    def register_handler(
        self,
        name: str,
        handler: CommandHandler,
        meta: Optional[CommandMeta] = None,
    ):
        """直接注册命令处理函数（非装饰器方式）。"""
        if meta is None:
            meta = CommandMeta(name=name)
        self._add_command(name, handler, meta)

    def _add_command(self, name: str, handler: CommandHandler, meta: CommandMeta):
        if name in self._handlers:
            raise ValueError(f"命令 '{name}' 已注册")
        self._handlers[name] = handler
        self._metas[name] = meta
        for alias in meta.aliases:
            if alias in self._aliases:
                raise ValueError(
                    f"别名 '{alias}' 已被命令 '{self._aliases[alias]}' 使用"
                )
            self._aliases[alias] = name

    # --------------------------------------------------------
    # 分发 API
    # --------------------------------------------------------

    def is_command(self, user_input: str) -> bool:
        """判断用户输入是否为命令（以 prefix 开头）。"""
        return user_input.strip().startswith(self._prefix)

    def parse(self, user_input: str) -> Tuple[str, str]:
        """解析命令输入，返回 (命令名, 参数字符串)。"""
        text = user_input.strip()[len(self._prefix):]
        if not text:
            return ("", "")
        parts = text.split(maxsplit=1)
        cmd_name = parts[0].lower()
        args_text = parts[1] if len(parts) > 1 else ""
        return (cmd_name, args_text)

    def resolve(self, cmd_name: str) -> Optional[str]:
        """解析命令名到规范名（处理别名）。"""
        if cmd_name in self._handlers:
            return cmd_name
        if cmd_name in self._aliases:
            return self._aliases[cmd_name]
        return None

    def dispatch(self, user_input: str, agent: Any) -> Optional[CommandResult]:
        """
        解析并执行命令。

        Returns:
            CommandResult 如果成功匹配并执行
            None 如果输入不是命令
        """
        if not self.is_command(user_input):
            return None

        cmd_name, args_text = self.parse(user_input)
        canonical = self.resolve(cmd_name)

        if canonical is None:
            return CommandResult(
                success=False,
                message=(
                    f"未知命令: {self._prefix}{cmd_name}\n"
                    f"输入 {self._prefix}help 查看可用命令列表。"
                ),
            )

        # 解析参数列表（支持引号）
        try:
            args_list = shlex.split(args_text) if args_text.strip() else []
        except ValueError:
            args_list = args_text.split()

        ctx = CommandContext(
            agent=agent,
            model_name=getattr(agent, "model_name", "unknown"),
            raw_input=user_input,
            command_name=canonical,
            args_text=args_text,
            args_list=args_list,
        )

        handler = self._handlers[canonical]
        try:
            result = handler(ctx)
            if not isinstance(result, CommandResult):
                result = CommandResult(message=str(result))
            return result
        except Exception as e:
            return CommandResult(
                success=False,
                message=f"命令执行出错 [{canonical}]: {e}"
            )

    # --------------------------------------------------------
    # 查询 API
    # --------------------------------------------------------

    def get_meta(self, name: str) -> Optional[CommandMeta]:
        """获取命令元数据"""
        canonical = self.resolve(name)
        return self._metas.get(canonical) if canonical else None

    def list_commands(self, category: Optional[str] = None) -> List[CommandMeta]:
        """列出所有（或按分类过滤的）命令"""
        metas = list(self._metas.values())
        if category:
            metas = [m for m in metas if m.category == category]
        return sorted(metas, key=lambda m: m.name)

    def get_help_text(self, cmd_name: Optional[str] = None) -> str:
        """生成帮助文本"""
        if cmd_name:
            meta = self.get_meta(cmd_name)
            if meta is None:
                return f"未知命令: {cmd_name}"
            aliases_str = (
                f" (别名: {', '.join(meta.aliases)})" if meta.aliases else ""
            )
            return (
                f"{self._prefix}{meta.name}{aliases_str}\n"
                f"  {meta.description}\n"
                f"  用法: {meta.usage}"
            )

        lines = ["可用命令列表:", "=" * 40]
        for meta in self.list_commands():
            if meta.hidden:
                continue
            aliases_str = (
                f" ({', '.join(meta.aliases)})" if meta.aliases else ""
            )
            lines.append(
                f"  {self._prefix}{meta.name:<18} {meta.description}{aliases_str}"
            )
        lines.append(f"\n输入 {self._prefix}help <命令名> 查看详细用法。")
        return "\n".join(lines)

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def command_count(self) -> int:
        return len(self._handlers)
