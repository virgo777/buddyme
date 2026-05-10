"""
cmd_library/builtin/skill_cmds.py — Skill 相关命令

注册: /reload_skills, /skill --list
"""

from __future__ import annotations

from ..base import CommandContext, CommandResult, CommandMeta
from ..registry import CommandRegistry


def register_skill_commands(registry: CommandRegistry) -> None:
    """注册所有 Skill 命令"""
    registry.register_handler("reload_skills", cmd_reload_skills, meta=CommandMeta(
        name="reload_skills",
        description="热加载 Skill 目录",
        usage="/reload_skills",
        category="skill",
    ))
    registry.register_handler("skill", cmd_skill, meta=CommandMeta(
        name="skill",
        description="Skill 管理",
        usage="/skill [--list]",
        category="skill",
    ))


def cmd_reload_skills(ctx: CommandContext) -> CommandResult:
    added = ctx.agent.reload_skills()
    total = len(ctx.agent._skill_loader.skills)
    return CommandResult(message=f"Skill 热加载完成，新增 {added} 个技能。当前共 {total} 个技能。")


def cmd_skill(ctx: CommandContext) -> CommandResult:
    args = ctx.args_text.strip().lstrip("-")

    if not args or args in ("list", "l"):
        return _skill_list(ctx)

    return CommandResult(
        success=False,
        message="用法: /skill [--list]",
    )


def _skill_list(ctx: CommandContext) -> CommandResult:
    skills = ctx.agent._skill_loader.skills
    if not skills:
        return CommandResult(message="当前无已加载的 Skill。")
    lines = []
    for name, skill in skills.items():
        desc = getattr(skill, "description", "") or ""
        lines.append(f"  {name:<30} {desc[:40]}")
    return CommandResult(message=f"已加载 Skill ({len(skills)}):\n" + "\n".join(lines))
