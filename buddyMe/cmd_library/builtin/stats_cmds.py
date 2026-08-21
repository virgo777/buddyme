# Builtin session stats and cron (daily schedule) CLI commands.

"""
cmd_library/builtin/stats_cmds.py — 会话统计 + 每日定时命令（0.2.0 新增）

注册:
    /stats   — 会话统计（invoke 次数 / token 用量 / 工具调用 / 技能 / 生成文件）
    /cron    — 每日定时任务（HH:MM 模式；复用心跳调度器的 schedule 字段）
"""

from __future__ import annotations

import re
from datetime import datetime

from ..base import CommandContext, CommandResult, CommandMeta
from ..registry import CommandRegistry


def register_stats_commands(registry: CommandRegistry) -> None:
    """注册 /stats 与 /cron 命令"""
    registry.register_handler("stats", cmd_stats, meta=CommandMeta(
        name="stats", aliases=["st"],
        description="会话统计（token/工具/技能）",
        usage="/stats",
        category="system",
    ))
    registry.register_handler("cron", cmd_cron, meta=CommandMeta(
        name="cron",
        description="每日定时任务（HH:MM 触发）",
        usage=(
            "/cron <HH:MM> <任务描述>   添加每日定时任务\n"
            "/cron --list              查看所有每日任务\n"
            "/cron --remove <id>       删除任务\n"
            "/cron --history <id>      查看运行历史"
        ),
        category="task",
    ))


# ============================================================
# /stats — 会话统计
# ============================================================

def cmd_stats(ctx: CommandContext) -> CommandResult:
    agent = ctx.agent
    tin = getattr(agent, "session_token_in", 0)
    tout = getattr(agent, "session_token_out", 0)
    total = tin + tout
    tool_calls = getattr(agent, "session_tool_calls", {}) or {}
    skills = getattr(agent, "session_skills", []) or []

    lines = [
        f"会话统计（自 {getattr(agent, 'session_started_at', '?')} 起）",
        "=" * 46,
        f"  任务次数:   {getattr(agent, 'session_invoke_count', 0)}",
        f"  Token 输入: {tin:,}",
        f"  Token 输出: {tout:,}",
        f"  Token 合计: {total:,}",
        f"  生成文件:   {getattr(agent, 'session_files_written', 0)}",
    ]

    if tool_calls:
        top = sorted(tool_calls.items(), key=lambda kv: kv[1], reverse=True)
        lines.append("")
        lines.append("  工具调用 Top:")
        for name, n in top[:8]:
            lines.append(f"    {name:<20} {n} 次")
    else:
        lines.append("  工具调用:   （暂无）")

    if skills:
        lines.append("")
        lines.append(f"  使用技能:   {', '.join(skills[:10])}")

    if total > 0:
        # 按 glm 系列参考价粗略估算无法准确，这里只展示占比结构
        lines.append("")
        lines.append(f"  输入/输出比: {tin} / {tout}")

    return CommandResult(message="\n".join(lines))


# ============================================================
# /cron — 每日定时任务（schedule: "HH:MM"）
# ============================================================

def _parse_hhmm(text: str):
    """解析 HH:MM（24 小时制）；失败返回 None。"""
    m = re.match(r"^([01]?\d|2[0-3])[:：]([0-5]\d)$", text.strip())
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"


def cmd_cron(ctx: CommandContext) -> CommandResult:
    args = ctx.args_text.strip()

    if not args:
        return _cron_usage()

    stripped = args.lstrip("-")

    if stripped in ("list", "l"):
        return _cron_list(ctx)
    if stripped.startswith("remove") or stripped.startswith("r "):
        parts = stripped.split(None, 1)
        if len(parts) < 2:
            return CommandResult(success=False, message="用法: /cron --remove <任务id>")
        return _cron_remove(ctx, parts[1].strip())
    if stripped.startswith("history"):
        parts = stripped.split(None, 1)
        if len(parts) < 2:
            return CommandResult(success=False, message="用法: /cron --history <任务id>")
        return _cron_history(ctx, parts[1].strip())

    # 默认：添加任务 → <HH:MM> <描述>
    parts = args.split(None, 1)
    if len(parts) < 2:
        return CommandResult(
            success=False,
            message="用法: /cron <HH:MM> <任务描述>\n示例: /cron 09:00 \"每天早上总结昨日对话\"",
        )

    hhmm = _parse_hhmm(parts[0])
    if hhmm is None:
        return CommandResult(
            success=False,
            message=f"无法解析时间 '{parts[0]}'，支持格式: HH:MM（00:00 ~ 23:59）",
        )

    description = parts[1].strip().strip('"').strip("'")
    if not description:
        return CommandResult(success=False, message="任务描述不能为空")

    task_id = _generate_cron_id(description)
    task = {
        "id": task_id,
        "name": description[:50],
        "description": description,
        "enabled": True,
        "interval_minutes": 0,          # interval 模式关闭
        "schedule": hhmm,               # ★ 每日 HH:MM 触发（心跳 _should_run 已支持）
        "last_run": None,
        "timeout_seconds": 300,
        "prompt": description,
        "first_exec_pending": False,    # 定时任务无首次执行（到点才跑）
        "history": [],
    }

    hb = ctx.agent.heartbeat
    if not hb.add_task(task):
        return CommandResult(success=False, message=f"任务 ID '{task_id}' 已存在，请重试")

    return CommandResult(
        message=(
            f"已添加每日定时任务:\n"
            f"  ID:    {task_id}\n"
            f"  任务:  {description[:50]}\n"
            f"  时间:  每天 {hhmm}\n"
            f"  状态:  已启用\n"
            f"  （首次执行将在下一个 {hhmm} 进行）"
        ),
    )


def _cron_usage() -> CommandResult:
    return CommandResult(
        message=(
            "用法:\n"
            "  /cron <HH:MM> <任务描述>   添加每日定时任务\n"
            "  /cron --list              查看所有每日任务\n"
            "  /cron --remove <id>       删除任务\n"
            "  /cron --history <id>      查看运行历史\n\n"
            "时间格式: HH:MM（24 小时制），到点触发（±5 分钟容差）"
        ),
    )


def _generate_cron_id(description: str) -> str:
    """可读 ID：cron_ + 中文前 2 字（或英文前 2 词）+ 4 位随机串。"""
    import random
    import string
    chinese = re.findall(r"[一-鿿]", description)
    if len(chinese) >= 2:
        prefix = "".join(chinese[:2])
    else:
        words = re.findall(r"[a-zA-Z]+", description)
        prefix = "_".join(words[:2]).lower() if words else "task"
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"cron_{prefix}_{suffix}"


def _cron_list(ctx: CommandContext) -> CommandResult:
    """列出每日定时任务（只显示 schedule 模式的任务）。"""
    hb = ctx.agent.heartbeat
    data = hb._load_config()
    tasks = [t for t in data.get("tasks", []) if t.get("schedule")]

    lines = [
        f"心跳状态: {'运行中' if ctx.agent._heartbeat_running else '已停止'}",
        "",
    ]
    if not tasks:
        lines.append("暂无每日定时任务")
        lines.append("使用 /cron <HH:MM> <任务描述> 添加")
    else:
        lines.append(f"每日定时任务（共 {len(tasks)} 个）:")
        lines.append("-" * 60)
        for t in tasks:
            icon = "+" if t.get("enabled", True) else "-"
            last = (t.get("last_run") or "从未运行")[:19]
            lines.append(
                f"  [{icon}] {t.get('id', '?'):<25} 每天 {t.get('schedule')}  "
                f"{(t.get('name') or '未命名')[:20]:<20} 上次: {last}"
            )
    return CommandResult(message="\n".join(lines))


def _cron_remove(ctx: CommandContext, task_id: str) -> CommandResult:
    hb = ctx.agent.heartbeat
    data = hb._load_config()
    target = next((t for t in data.get("tasks", []) if t.get("id") == task_id), None)
    if not target:
        return CommandResult(success=False, message=f"任务 '{task_id}' 不存在")
    ok = hb.remove_task(task_id)
    if ok:
        return CommandResult(message=f"已删除每日任务: {task_id}")
    return CommandResult(success=False, message=f"删除失败: {task_id}")


def _cron_history(ctx: CommandContext, task_id: str) -> CommandResult:
    """查看某任务的运行历史（最近 20 条：状态 + 耗时）。"""
    hb = ctx.agent.heartbeat
    data = hb._load_config()
    task = next((t for t in data.get("tasks", []) if t.get("id") == task_id), None)
    if not task:
        return CommandResult(success=False, message=f"任务 '{task_id}' 不存在")

    hist = task.get("history") or []
    lines = [f"运行历史（{task_id}，最近 {len(hist)} 条）:", "-" * 46]
    if not hist:
        lines.append("  （暂无记录——任务还没到点执行过）")
    else:
        status_icon = {"ok": "✓", "timeout": "⏱", "error": "✗"}
        for h in reversed(hist):   # 最新在前
            icon = status_icon.get(h.get("status"), "?")
            lines.append(
                f"  {icon} {h.get('time', '?')}  {h.get('status', '?'):<8} "
                f"{h.get('duration_s', 0)}s"
            )
    return CommandResult(message="\n".join(lines))
