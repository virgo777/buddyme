"""
cmd_library — buddyMe 命令系统模块

提供一种比工具调用更轻量的用户交互方式。
用户以 "/" 开头的输入在进入 LLM 推理之前被拦截处理，不消耗 token。

使用方式:
    from cmd_library import create_registry, dispatch_command

    registry = create_registry()
    result = dispatch_command(registry, user_input, agent)
"""

from .registry import CommandRegistry
from .base import CommandContext, CommandResult, CommandMeta

__all__ = [
    "CommandRegistry",
    "CommandContext",
    "CommandResult",
    "CommandMeta",
    "create_registry",
    "dispatch_command",
]


def create_registry(prefix: str = "/") -> CommandRegistry:
    """
    创建并初始化命令注册表，注册所有内置命令。

    Args:
        prefix: 命令前缀，默认 "/"

    Returns:
        已注册所有内置命令的 CommandRegistry 实例
    """
    registry = CommandRegistry(prefix=prefix)

    # 注册系统命令
    from .builtin.system_cmds import register_system_commands
    register_system_commands(registry)

    # 注册 Skill 命令
    from .builtin.skill_cmds import register_skill_commands
    register_skill_commands(registry)

    # 注册记忆管理命令
    from .builtin.memory_cmds import register_memory_commands
    register_memory_commands(registry)

    # 注册定时任务命令
    from .builtin.loop_cmds import register_loop_commands
    register_loop_commands(registry)

    return registry


def dispatch_command(registry: CommandRegistry, user_input: str, agent) -> "CommandResult | None":
    """
    便捷函数：解析并执行命令。

    Args:
        registry: 命令注册表
        user_input: 用户原始输入
        agent: AgentMain 实例

    Returns:
        CommandResult 如果匹配到命令，否则 None
    """
    return registry.dispatch(user_input, agent)
