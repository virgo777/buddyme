# Builtin system-level CLI commands.

"""
cmd_library/builtin/system_cmds.py — 系统命令

注册: /help, /model, /api_key, /reset, /exit
"""

from __future__ import annotations

import sys

from ..base import CommandContext, CommandResult, CommandMeta
from ..registry import CommandRegistry


def register_system_commands(registry: CommandRegistry) -> None:
    """注册所有系统命令"""
    registry.register_handler("help", cmd_help, meta=CommandMeta(
        name="help", aliases=["h"],
        description="显示帮助信息",
        usage="/help [命令名]",
        category="system",
    ))
    registry.register_handler("model", cmd_model, meta=CommandMeta(
        name="model", aliases=["m"],
        description="模型管理（查看/切换）",
        usage="/model --list 或 /model --switch glm",
        category="system",
    ))
    registry.register_handler("api_key", cmd_api_key, meta=CommandMeta(
        name="api_key",
        description="查看或设置 API Key",
        usage="/api_key deepseek sk-xxx 或 /api_key --list",
        category="system",
    ))
    registry.register_handler("reset", cmd_reset, meta=CommandMeta(
        name="reset",
        description="重置对话历史",
        usage="/reset",
        category="system",
    ))
    registry.register_handler("exit", cmd_exit, meta=CommandMeta(
        name="exit", aliases=["quit", "q"],
        description="退出 Agent",
        usage="/exit",
        category="system",
    ))


# ============================================================
# /help [命令名]
# ============================================================

def cmd_help(ctx: CommandContext) -> CommandResult:
    if ctx.args_text.strip():
        detail = ctx.agent.cmd_registry.get_help_text(ctx.args_text.strip())
        return CommandResult(message=detail)
    return CommandResult(message=ctx.agent.cmd_registry.get_help_text())


# ============================================================
# /model [--list | --switch <名称>]
# ============================================================

def cmd_model(ctx: CommandContext) -> CommandResult:
    args = ctx.args_text.strip().lstrip("-")

    # 无参数 或 list：列出模型
    if not args or args in ("list", "l"):
        return _model_list(ctx)

    # switch：切换模型
    if args.startswith("switch") or args.startswith("s"):
        parts = args.split(None, 1)
        model_name = parts[1].strip() if len(parts) > 1 else ""
        return _model_switch(ctx, model_name)

    return CommandResult(
        success=False,
        message="用法: /model [--list | --switch <名称>]",
    )


def _model_list(ctx: CommandContext) -> CommandResult:
    agent = ctx.agent
    supported = agent.supported_models()
    lines = []
    for m in supported:
        marker = " → " if m == agent.model_name else "   "
        lines.append(f"{marker}{m}")
    return CommandResult(
        message=f"可用模型（→ 为当前）:\n" + "\n".join(lines)
    )


def _model_switch(ctx: CommandContext, model_name: str) -> CommandResult:
    if not model_name:
        return CommandResult(
            success=False,
            message="请指定模型名: /model --switch <名称>",
        )

    agent = ctx.agent

    # 校验1：模型是否存在
    if model_name not in agent._CLIENT_MAP:
        supported = ", ".join(agent.supported_models())
        return CommandResult(
            success=False,
            message=f"不支持 '{model_name}'，可用: {supported}",
        )

    # 校验2：API Key 是否已配置
    from buddyMe.llm_moudle.model_config import ModelConfig
    api_key = ModelConfig.get_api_key(model_name)
    if not api_key:
        return CommandResult(
            success=False,
            message=f"模型 '{model_name}' 未配置 API Key，请先用 /api_key {model_name} <key> 设置",
        )

    old = agent.model_name
    agent.switch_model(model_name)
    return CommandResult(message=f"模型已切换: {old} → {model_name}")


# ============================================================
# /api_key <模型名> <key>  或  /api_key --list
# ============================================================

def cmd_api_key(ctx: CommandContext) -> CommandResult:
    args = ctx.args_text.strip().lstrip("-")

    # list：展示所有 key（脱敏）
    if not args or args in ("list", "l"):
        return _api_key_list()

    parts = args.split(None, 1)
    if len(parts) < 2:
        return CommandResult(
            success=False,
            message="用法: /api_key <模型名> <key>",
        )
    return _api_key_set(parts[0], parts[1])


def _api_key_list() -> CommandResult:
    from buddyMe.llm_moudle.model_config import ModelConfig
    lines = []
    for name in ModelConfig.list_models():
        key = ModelConfig.get_api_key(name)
        masked = (key[:8] + "..." + key[-4:]) if len(key) > 12 else "(未设置)"
        lines.append(f"  {name:<10} {masked}")
    return CommandResult(message="API Keys:\n" + "\n".join(lines))


def _api_key_set(model_name: str, key: str) -> CommandResult:
    from buddyMe.llm_moudle.model_config import ModelConfig
    if not ModelConfig.is_valid(model_name):
        return CommandResult(
            success=False,
            message=f"未知模型 '{model_name}'，可用: {', '.join(ModelConfig.list_models())}",
        )
    ModelConfig.set_api_key(model_name, key)
    return CommandResult(message=f"已更新 {model_name} 的 API Key")


# ============================================================
# /reset
# ============================================================

def cmd_reset(ctx: CommandContext) -> CommandResult:
    ctx.agent.reset()
    return CommandResult(message="对话历史已重置")


# ============================================================
# /exit
# ============================================================

def cmd_exit(ctx: CommandContext) -> CommandResult:
    ctx.agent.stop_heartbeat()
    ctx.agent.close()
    return CommandResult(message="再见！", should_exit=True)
