"""
cmd_library/builtin/memory_cmds.py — 记忆管理命令

注册: /memory, /log, /heartbeat
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime

from ..base import CommandContext, CommandResult, CommandMeta
from ..registry import CommandRegistry


def register_memory_commands(registry: CommandRegistry) -> None:
    """注册所有记忆管理命令"""
    registry.register_handler("memory", cmd_memory, meta=CommandMeta(
        name="memory", aliases=["mem"],
        description="记忆管理（查看/更新/衰减/整合）",
        usage="/memory [--show | --summary | --update | --decay | --consolidate | --history | --clear]",
        category="memory",
    ))
    registry.register_handler("log", cmd_log, meta=CommandMeta(
        name="log", aliases=["history"],
        description="对话记录管理",
        usage="/log [--today | --date YYYY-MM-DD | --search 关键词 | --clear]",
        category="memory",
    ))
    registry.register_handler("heartbeat", cmd_heartbeat, meta=CommandMeta(
        name="heartbeat", aliases=["hb"],
        description="心跳任务管理",
        usage="/heartbeat [--status | --enable <id> | --disable <id>]",
        category="memory",
    ))


# ============================================================
# /memory
# ============================================================

def cmd_memory(ctx: CommandContext) -> CommandResult:
    args = ctx.args_text.strip().lstrip("-")

    if not args or args in ("show", "s"):
        return _memory_show(ctx)
    if args == "summary":
        return _memory_summary(ctx)
    if args in ("update", "u"):
        return _memory_update(ctx)
    if args in ("decay", "d"):
        return _memory_decay(ctx)
    if args in ("consolidate", "c"):
        return _memory_consolidate(ctx)
    if args == "history":
        return _memory_history(ctx)
    if args.startswith("clear"):
        return _memory_clear(ctx)

    return CommandResult(
        success=False,
        message=(
            "用法:\n"
            "  /memory              显示当前记忆\n"
            "  /memory --summary    显示对话摘要\n"
            "  /memory --update     手动更新记忆\n"
            "  /memory --decay      执行记忆衰减\n"
            "  /memory --consolidate 执行记忆整合\n"
            "  /memory --history    查看归档历史\n"
            "  /memory --clear      清除所有记忆"
        ),
    )


def _memory_show(ctx: CommandContext) -> CommandResult:
    """显示当前用户记忆"""
    mem = ctx.agent.user_memory
    if not mem.data:
        mem.load()
    if not mem.data:
        return CommandResult(message="记忆为空")

    lines = []
    for section, content in mem.data.items():
        if not content:
            continue
        lines.append(f"## {section}")
        if isinstance(content, list):
            for item in content:
                lines.append(f"  - {item}")
        else:
            for line in str(content).splitlines():
                lines.append(f"  {line}")
        lines.append("")

    return CommandResult(message="当前用户记忆:\n" + "\n".join(lines))


def _memory_summary(ctx: CommandContext) -> CommandResult:
    """显示近期对话摘要"""
    summary_path = os.path.join(
        ctx.agent._PROJECT_ROOT, "initspace", "memorys", "memory_summary.md"
    )
    if not os.path.exists(summary_path):
        return CommandResult(message="暂无对话摘要")

    with open(summary_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    if not content:
        return CommandResult(message="对话摘要为空")

    if len(content) > 2000:
        content = content[:2000] + "\n...(内容过长已截断)"

    return CommandResult(message="近期对话摘要:\n" + content)


def _memory_update(ctx: CommandContext) -> CommandResult:
    """手动触发记忆提取更新"""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(
                    asyncio.run, ctx.agent.user_memory.update()
                ).result()
        else:
            result = asyncio.run(ctx.agent.user_memory.update())

        if not result:
            return CommandResult(message="记忆更新完成（无新增内容）")

        lines = ["记忆更新完成，变更的章节:"]
        for section in result:
            lines.append(f"  - {section}")
        return CommandResult(message="\n".join(lines))
    except Exception as e:
        return CommandResult(success=False, message=f"记忆更新失败: {e}")


def _memory_decay(ctx: CommandContext) -> CommandResult:
    """执行记忆衰减"""
    try:
        mem = ctx.agent.user_memory
        before_count = len(mem.data)
        mem.run_memory_decay()
        after_count = len(mem.data)
        removed = before_count - after_count
        return CommandResult(
            message=f"记忆衰减完成: {before_count} -> {after_count} 章节（移除 {removed} 个低分记忆）"
        )
    except Exception as e:
        return CommandResult(success=False, message=f"记忆衰减失败: {e}")


def _memory_consolidate(ctx: CommandContext) -> CommandResult:
    """执行记忆整合"""
    try:
        mem = ctx.agent.user_memory
        before_count = len(mem.data)
        mem.run_memory_consolidation()
        after_count = len(mem.data)
        merged = before_count - after_count
        return CommandResult(
            message=f"记忆整合完成: {before_count} -> {after_count} 章节（合并 {merged} 个碎片）"
        )
    except Exception as e:
        return CommandResult(success=False, message=f"记忆整合失败: {e}")


def _memory_history(ctx: CommandContext) -> CommandResult:
    """查看记忆归档历史"""
    mem = ctx.agent.user_memory
    history = mem._load_history()

    archive = history.get("archive", {})
    last_active = history.get("last_active", {})
    importance = history.get("importance", {})

    if not archive and not last_active:
        return CommandResult(message="暂无记忆历史")

    lines = []

    if last_active:
        lines.append("=== 活跃记忆 ===")
        for section, timestamp in sorted(last_active.items(), key=lambda x: x[1], reverse=True):
            score = importance.get(section, "N/A")
            if isinstance(score, float):
                score = f"{score:.2f}"
            ts = timestamp[:19] if len(timestamp) > 19 else timestamp
            lines.append(f"  [{score}] {section} (最后活跃: {ts})")

    if archive:
        lines.append("\n=== 归档记忆 ===")
        for section, entries in archive.items():
            lines.append(f"  {section} ({len(entries)} 条归档)")

    return CommandResult(message="\n".join(lines))


def _memory_clear(ctx: CommandContext) -> CommandResult:
    """清除所有用户记忆"""
    args = ctx.args_text
    if "--force" not in args and "-f" not in args:
        return CommandResult(
            success=False,
            message="确认清除所有记忆？请使用: /memory --clear --force",
        )

    try:
        mem = ctx.agent.user_memory
        mem.data = {}
        mem.save()
        history_path = mem.history_path
        if os.path.exists(history_path):
            os.remove(history_path)
        return CommandResult(message="所有用户记忆已清除")
    except Exception as e:
        return CommandResult(success=False, message=f"清除记忆失败: {e}")


# ============================================================
# /log
# ============================================================

def cmd_log(ctx: CommandContext) -> CommandResult:
    args = ctx.args_text.strip().lstrip("-")

    if not args or args in ("recent", "r"):
        return _log_recent(ctx)
    if args in ("today", "t"):
        return _log_date(ctx, datetime.now().strftime("%Y-%m-%d"))
    if args.startswith("date"):
        parts = args.split(None, 1)
        if len(parts) < 2:
            return CommandResult(success=False, message="用法: /log --date YYYY-MM-DD")
        return _log_date(ctx, parts[1].strip())
    if args.startswith("search"):
        parts = args.split(None, 1)
        if len(parts) < 2:
            return CommandResult(success=False, message="用法: /log --search 关键词")
        return _log_search(ctx, parts[1].strip())
    if args.startswith("clear"):
        return _log_clear(ctx)

    return CommandResult(
        success=False,
        message=(
            "用法:\n"
            "  /log                   显示最近对话\n"
            "  /log --today           今天的对话\n"
            "  /log --date YYYY-MM-DD 指定日期对话\n"
            "  /log --search 关键词   搜索对话\n"
            "  /log --clear           清除对话记录"
        ),
    )


def _read_conversation_log(ctx: CommandContext) -> tuple:
    """读取对话日志文件，返回 (data_dict, error_result)"""
    log_path = ctx.agent.conv_logger.log_path
    if not os.path.exists(log_path):
        return None, CommandResult(message="暂无对话记录")
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data, None
    except (json.JSONDecodeError, OSError) as e:
        return None, CommandResult(success=False, message=f"对话记录读取失败: {e}")


def _log_recent(ctx: CommandContext, limit: int = 5) -> CommandResult:
    """显示最近对话记录"""
    data, err = _read_conversation_log(ctx)
    if err:
        return err

    all_dates = sorted(data.keys(), reverse=True)

    entries = []
    count = 0
    for date in all_dates:
        for record in reversed(data[date]):
            if count >= limit:
                break
            time_str = record.get("time", "?")
            query = record.get("query", "")
            model = record.get("model", "")
            entries.append(f"[{date} {time_str}] ({model}) {query}")
            count += 1
        if count >= limit:
            break

    if not entries:
        return CommandResult(message="暂无对话记录")

    total = sum(len(v) for v in data.values())
    return CommandResult(message=f"最近 {len(entries)} 条对话（共 {total} 条）:\n" + "\n".join(entries))


def _log_date(ctx: CommandContext, date_str: str) -> CommandResult:
    """查看指定日期的对话"""
    data, err = _read_conversation_log(ctx)
    if err:
        return err

    records = data.get(date_str, [])
    if not records:
        return CommandResult(message=f"{date_str} 无对话记录")

    lines = [f"=== {date_str} ({len(records)} 条对话) ==="]
    for record in records:
        time_str = record.get("time", "?")
        query = record.get("query", "")
        model = record.get("model", "")
        response = record.get("response_summary", record.get("response", ""))
        if len(response) > 100:
            response = response[:100] + "..."
        lines.append(f"[{time_str}] ({model}) Q: {query}")
        lines.append(f"  A: {response}")

    return CommandResult(message="\n".join(lines))


def _log_search(ctx: CommandContext, keyword: str) -> CommandResult:
    """搜索对话记录"""
    data, err = _read_conversation_log(ctx)
    if err:
        return err

    keyword_lower = keyword.lower()
    results = []

    for date in sorted(data.keys(), reverse=True):
        for record in data[date]:
            query = record.get("query", "")
            response = record.get("response_summary", record.get("response", ""))
            if keyword_lower in query.lower() or keyword_lower in response.lower():
                time_str = record.get("time", "?")
                model = record.get("model", "")
                results.append(f"[{date} {time_str}] ({model}) {query}")
                if len(results) >= 20:
                    break
        if len(results) >= 20:
            break

    if not results:
        return CommandResult(message=f"未找到包含 '{keyword}' 的对话")

    return CommandResult(
        message=f"搜索 '{keyword}' 找到 {len(results)} 条:\n" + "\n".join(results)
    )


def _log_clear(ctx: CommandContext) -> CommandResult:
    """清除对话记录"""
    args = ctx.args_text
    if "--force" not in args and "-f" not in args:
        return CommandResult(
            success=False,
            message="确认清除所有对话记录？请使用: /log --clear --force",
        )

    try:
        log_path = ctx.agent.conv_logger.log_path
        if os.path.exists(log_path):
            os.remove(log_path)
        return CommandResult(message="对话记录已清除")
    except Exception as e:
        return CommandResult(success=False, message=f"清除失败: {e}")


# ============================================================
# /heartbeat
# ============================================================

def cmd_heartbeat(ctx: CommandContext) -> CommandResult:
    args = ctx.args_text.strip().lstrip("-")

    if not args or args in ("status", "s"):
        return _heartbeat_status(ctx)
    if args == "start":
        return _heartbeat_start_stop(ctx, start=True)
    if args == "stop":
        return _heartbeat_start_stop(ctx, start=False)
    if args.startswith("enable"):
        parts = args.split(None, 1)
        if len(parts) < 2:
            return CommandResult(success=False, message="用法: /heartbeat --enable <任务id>")
        return _heartbeat_toggle(ctx, parts[1].strip(), enabled=True)
    if args.startswith("disable"):
        parts = args.split(None, 1)
        if len(parts) < 2:
            return CommandResult(success=False, message="用法: /heartbeat --disable <任务id>")
        return _heartbeat_toggle(ctx, parts[1].strip(), enabled=False)

    return CommandResult(
        success=False,
        message=(
            "用法:\n"
            "  /heartbeat                 显示心跳状态\n"
            "  /heartbeat start           启动心跳系统\n"
            "  /heartbeat stop            停止心跳系统\n"
            "  /heartbeat --enable <id>   启用任务\n"
            "  /heartbeat --disable <id>  禁用任务"
        ),
    )


def _heartbeat_status(ctx: CommandContext) -> CommandResult:
    """显示心跳任务状态"""
    status = ctx.agent.heartbeat.get_status()
    config = status.get("config", {})
    tasks = status.get("tasks", [])

    lines = [
        f"心跳状态: {'运行中' if ctx.agent._heartbeat_running else '已停止'}",
        f"间隔: {config.get('interval_minutes', '?')} 分钟",
        f"活跃时段: {config.get('active_hours', '00:00-23:59')}",
        "",
    ]

    if not tasks:
        lines.append("无定时任务")
    else:
        lines.append("定时任务:")
        for task in tasks:
            enabled = task.get("enabled", True)
            task_id = task.get("id", "?")
            name = task.get("name", "未命名")
            last_run = task.get("last_run", "从未运行")
            icon = "+" if enabled else "-"
            if len(last_run) > 19:
                last_run = last_run[:19]
            lines.append(f"  [{icon}] [{task_id}] {name} (上次运行: {last_run})")

    return CommandResult(message="\n".join(lines))


def _heartbeat_start_stop(ctx: CommandContext, start: bool) -> CommandResult:
    """启动/停止整个心跳系统"""
    if start:
        if ctx.agent._heartbeat_running:
            return CommandResult(message="心跳系统已在运行中")
        ctx.agent.start_heartbeat()
        return CommandResult(message="心跳系统已启动")
    else:
        if not ctx.agent._heartbeat_running:
            return CommandResult(message="心跳系统已处于停止状态")
        ctx.agent.stop_heartbeat()
        return CommandResult(message="心跳系统已停止")


def _heartbeat_toggle(ctx: CommandContext, task_id: str, enabled: bool) -> CommandResult:
    """启用/禁用心跳任务"""
    action = "启用" if enabled else "禁用"
    success = ctx.agent.heartbeat.enable_task(task_id, enabled=enabled)
    if success:
        return CommandResult(message=f"已{action}任务: {task_id}")

    available = ", ".join(
        t.get("id", "") for t in ctx.agent.heartbeat.get_status().get("tasks", [])
    )
    return CommandResult(
        success=False,
        message=f"任务 '{task_id}' 不存在，可用任务: {available}",
    )
