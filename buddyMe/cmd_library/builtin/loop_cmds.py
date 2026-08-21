# Builtin CLI commands for loop task execution.

"""
cmd_library/builtin/loop_cmds.py — 定时任务管理命令

注册: /loop

功能:
    /loop <间隔> <任务描述>   添加定时任务
    /loop --list              查看所有任务
    /loop --remove <id>       删除任务
    /loop --enable <id>       启用任务
    /loop --disable <id>      禁用任务
    /loop start               启动心跳系统
    /loop stop                停止心跳系统
"""

from __future__ import annotations

import asyncio
import logging
import re
import random
import string
import threading
from datetime import datetime
from typing import Dict, Optional

from ..base import CommandContext, CommandResult, CommandMeta
from ..registry import CommandRegistry


def register_loop_commands(registry: CommandRegistry) -> None:
    """注册所有 /loop 命令"""
    registry.register_handler("loop", cmd_loop, meta=CommandMeta(
        name="loop", aliases=["lp"],
        description="定时任务管理（添加/查看/删除/启禁）",
        usage=(
            "/loop <间隔> <任务描述>   添加定时任务\n"
            "/loop --list              查看所有任务\n"
            "/loop --remove <id>       删除任务\n"
            "/loop --enable <id>       启用任务\n"
            "/loop --disable <id>      禁用任务\n"
            "/loop --history <id>      查看运行历史"
        ),
        category="task",
    ))


# ============================================================
# 间隔解析
# ============================================================

def parse_interval(text: str) -> Optional[int]:
    """将间隔字符串解析为分钟数。

    支持格式:
        30m / 30min / 30分钟  → 30
        1h / 1hour / 1小时    → 60
        1d / 1day / 1天       → 1440
        30                    → 30（纯数字默认分钟）

    Returns:
        分钟数，解析失败返回 None
    """
    text = text.strip().lower()

    # 纯数字 → 分钟
    if text.isdigit():
        val = int(text)
        return val if val > 0 else None

    match = re.match(r"^(\d+)\s*(m|min|minute|minutes|分钟)$", text)
    if match:
        return int(match.group(1))

    match = re.match(r"^(\d+)\s*(h|hour|hours|小时)$", text)
    if match:
        return int(match.group(1)) * 60

    match = re.match(r"^(\d+)\s*(d|day|days|天)$", text)
    if match:
        return int(match.group(1)) * 1440

    # 兼容无单位简写：30m, 1h, 2d
    match = re.match(r"^(\d+)\s*([mhd])", text)
    if match:
        val = int(match.group(1))
        unit = match.group(2)
        if unit == "m":
            return val
        if unit == "h":
            return val * 60
        if unit == "d":
            return val * 1440

    return None


# ============================================================
# ID 生成
# ============================================================

def _generate_task_id(description: str) -> str:
    """根据任务描述生成可读的任务 ID。

    规则: loop_ + 中文前2字(或英文前2词) + 4位随机字符
    """
    # 提取中文字符
    chinese_chars = re.findall(r"[一-鿿]", description)
    if len(chinese_chars) >= 2:
        prefix = "".join(chinese_chars[:2])
    else:
        # 英文：取前两个单词
        words = re.findall(r"[a-zA-Z]+", description)
        prefix = "_".join(words[:2]).lower() if words else "task"

    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"loop_{prefix}_{suffix}"


# ============================================================
# 主入口
# ============================================================

def cmd_loop(ctx: CommandContext) -> CommandResult:
    args = ctx.args_text.strip()

    if not args:
        return _loop_usage()

    stripped = args.lstrip("-")

    if stripped in ("list", "l"):
        return _loop_list(ctx)
    if stripped == "start":
        return _loop_start_stop(ctx, start=True)
    if stripped == "stop":
        return _loop_start_stop(ctx, start=False)
    if stripped.startswith("remove") or stripped.startswith("r "):
        parts = stripped.split(None, 1)
        if len(parts) < 2:
            return CommandResult(success=False, message="用法: /loop --remove <任务id>")
        return _loop_remove(ctx, parts[1].strip())
    if stripped.startswith("enable"):
        parts = stripped.split(None, 1)
        if len(parts) < 2:
            return CommandResult(success=False, message="用法: /loop --enable <任务id>")
        return _loop_toggle(ctx, parts[1].strip(), enabled=True)
    if stripped.startswith("disable"):
        parts = stripped.split(None, 1)
        if len(parts) < 2:
            return CommandResult(success=False, message="用法: /loop --disable <任务id>")
        return _loop_toggle(ctx, parts[1].strip(), enabled=False)
    if stripped.startswith("history"):
        parts = stripped.split(None, 1)
        if len(parts) < 2:
            return CommandResult(success=False, message="用法: /loop --history <任务id>")
        return _loop_history(ctx, parts[1].strip())

    # 默认：添加任务 → 解析 <间隔> <描述>
    return _loop_add(ctx, args)


# ============================================================
# 子命令实现
# ============================================================

def _loop_usage() -> CommandResult:
    """返回帮助信息"""
    return CommandResult(
        message=(
            "用法:\n"
            "  /loop <间隔> <任务描述>   添加定时任务\n"
            "  /loop --list              查看所有任务\n"
            "  /loop --remove <id>       删除任务\n"
            "  /loop --enable <id>       启用任务\n"
            "  /loop --disable <id>      禁用任务\n"
            "  /loop --history <id>      查看运行历史（0.2.0）\n"
            "  /loop start               启动心跳系统\n"
            "  /loop stop                停止心跳系统\n\n"
            "间隔格式: 30m(分钟) 1h(小时) 2d(天) 或纯数字(默认分钟)\n"
            "每日定点任务用 /cron <HH:MM> <任务描述>"
        ),
    )


def _loop_history(ctx: CommandContext, task_id: str) -> CommandResult:
    """查看某任务的运行历史（最近 20 条：状态 + 耗时；0.2.0 新增）。"""
    hb = ctx.agent.heartbeat
    data = hb._load_config()
    task = next((t for t in data.get("tasks", []) if t.get("id") == task_id), None)
    if not task:
        return CommandResult(success=False, message=f"任务 '{task_id}' 不存在")

    hist = task.get("history") or []
    lines = [f"运行历史（{task_id}，最近 {len(hist)} 条）:", "-" * 46]
    if not hist:
        lines.append("  （暂无记录——任务还没执行过）")
    else:
        status_icon = {"ok": "✓", "timeout": "⏱", "error": "✗"}
        for h in reversed(hist):   # 最新在前
            icon = status_icon.get(h.get("status"), "?")
            lines.append(
                f"  {icon} {h.get('time', '?')}  {h.get('status', '?'):<8} "
                f"{h.get('duration_s', 0)}s"
            )
    return CommandResult(message="\n".join(lines))


def _loop_add(ctx: CommandContext, args: str) -> CommandResult:
    """添加定时任务"""
    parts = args.split(None, 1)
    if len(parts) < 2:
        return CommandResult(
            success=False,
            message="用法: /loop <间隔> <任务描述>\n示例: /loop 30m \"每30分钟提醒我喝水\"",
        )

    interval_text = parts[0]
    description = parts[1].strip().strip('"').strip("'")

    interval_minutes = parse_interval(interval_text)
    if interval_minutes is None:
        return CommandResult(
            success=False,
            message=f"无法解析间隔 '{interval_text}'，支持格式: 30m, 1h, 2d 或纯数字(分钟)",
        )

    if not description:
        return CommandResult(success=False, message="任务描述不能为空")

    task_id = _generate_task_id(description)

    task = {
        "id": task_id,
        "name": description[:50],
        "description": description,
        "enabled": True,
        "interval_minutes": interval_minutes,
        "schedule": None,
        "last_run": datetime.now().isoformat(),
        "timeout_seconds": 300,
        "prompt": description,
        "first_exec_pending": True,
    }

    hb = ctx.agent.heartbeat
    success = hb.add_task(task)

    if not success:
        return CommandResult(
            success=False,
            message=f"任务 ID '{task_id}' 已存在，请重试",
        )

    # 格式化间隔显示
    interval_display = _format_interval(interval_minutes)

    # 首次执行：后台线程执行，不阻塞用户输入
    _logger = logging.getLogger(__name__)

    _FIRST_EXEC_TIMEOUT = 300  # 首次执行总超时（秒）

    def _run_first_exec_bg():
        """后台线程：首次执行 + Skill 生成"""
        try:
            _logger.info("[loop] 首次执行（后台线程）: %s", task_id)

            async def _timed_exec():
                return await asyncio.wait_for(
                    ctx.agent._run_first_execution(description),
                    timeout=_FIRST_EXEC_TIMEOUT,
                )

            result, tool_chain, success = asyncio.run(_timed_exec())

            # 更新 last_run，清除 first_exec_pending，允许心跳调度
            with hb._lock:
                data = hb._load_config()
                for t in data.get("tasks", []):
                    if t.get("id") == task_id:
                        t["last_run"] = datetime.now().isoformat()
                        t["first_exec_pending"] = False
                        break
                hb._save_config(data)

            if success and tool_chain:
                skill_ok = ctx.agent._loop_skill_mgr.generate_skill(
                    task_id, description, tool_chain,
                )
                if skill_ok:
                    _logger.info(
                        "[loop] Loop Skill 已生成: %s（%d 步）",
                        task_id, len(tool_chain),
                    )
                else:
                    _logger.warning("[loop] Loop Skill 生成失败: %s", task_id)
            else:
                _logger.warning("[loop] 无工具调用，未生成 Skill: %s", task_id)

            _logger.info("[loop] 首次执行完成: %s", task_id)
        except asyncio.TimeoutError:
            _logger.error("[loop] 首次执行超时（%ds）: %s", _FIRST_EXEC_TIMEOUT, task_id)
            # 超时也要清除 pending 标志，允许后续心跳用 LLM 降级执行
            with hb._lock:
                data = hb._load_config()
                for t in data.get("tasks", []):
                    if t.get("id") == task_id:
                        t["first_exec_pending"] = False
                        break
                hb._save_config(data)
        except Exception as e:
            _logger.error("[loop] 首次执行失败: %s - %s", task_id, e)
            with hb._lock:
                data = hb._load_config()
                for t in data.get("tasks", []):
                    if t.get("id") == task_id:
                        t["first_exec_pending"] = False
                        break
                hb._save_config(data)

    bg_thread = threading.Thread(target=_run_first_exec_bg, daemon=True)
    bg_thread.start()

    return CommandResult(
        message=(
            f"已添加定时任务:\n"
            f"  ID:     {task_id}\n"
            f"  任务:   {description[:50]}\n"
            f"  间隔:   {interval_display}\n"
            f"  状态:   已启用\n"
            f"  首次执行: 后台进行中..."
        ),
    )


def _loop_start_stop(ctx: CommandContext, start: bool) -> CommandResult:
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


def _loop_list(ctx: CommandContext) -> CommandResult:
    """列出所有定时任务"""
    hb = ctx.agent.heartbeat
    status = hb.get_status()
    config = status.get("config", {})
    tasks = status.get("tasks", [])

    lines = [
        f"心跳状态: {'运行中' if ctx.agent._heartbeat_running else '已停止'}",
        f"检查间隔: {config.get('interval_minutes', '?')} 分钟",
        "",
    ]

    if not tasks:
        lines.append("暂无定时任务")
        lines.append("使用 /loop <间隔> <任务描述> 添加新任务")
    else:
        lines.append(f"定时任务（共 {len(tasks)} 个）:")
        lines.append("-" * 60)
        for task in tasks:
            enabled = task.get("enabled", True)
            task_id = task.get("id", "?")
            name = task.get("name", "未命名")
            last_run = task.get("last_run", "从未运行")

            # 读取间隔
            data = hb._load_config()
            interval_min = None
            for t in data.get("tasks", []):
                if t.get("id") == task_id:
                    interval_min = t.get("interval_minutes")
                    break

            icon = "+" if enabled else "-"
            interval_display = _format_interval(interval_min) if interval_min else "?"

            if last_run and len(last_run) > 19:
                last_run = last_run[:19]

            lines.append(f"  [{icon}] {task_id:<25} {name[:20]:<20} 间隔: {interval_display:<8} 上次: {last_run}")

    return CommandResult(message="\n".join(lines))


def _loop_remove(ctx: CommandContext, task_id: str) -> CommandResult:
    """删除定时任务，同步删除对应的 Loop Skill"""
    hb = ctx.agent.heartbeat
    success = hb.remove_task(task_id)

    if success:
        # 同步删除 Loop Skill 目录
        skill_deleted = ""
        if hasattr(ctx.agent, "_loop_skill_mgr"):
            if ctx.agent._loop_skill_mgr.delete_skill(task_id):
                skill_deleted = "（含 Loop Skill）"
        return CommandResult(message=f"已删除任务: {task_id}{skill_deleted}")

    available = ", ".join(
        t.get("id", "") for t in hb.get_status().get("tasks", [])
    )
    return CommandResult(
        success=False,
        message=f"任务 '{task_id}' 不存在\n可用任务: {available or '(无)'}",
    )


def _loop_toggle(ctx: CommandContext, task_id: str, enabled: bool) -> CommandResult:
    """启用/禁用任务"""
    action = "启用" if enabled else "禁用"
    hb = ctx.agent.heartbeat
    success = hb.enable_task(task_id, enabled=enabled)

    if success:
        return CommandResult(message=f"已{action}任务: {task_id}")

    available = ", ".join(
        t.get("id", "") for t in hb.get_status().get("tasks", [])
    )
    return CommandResult(
        success=False,
        message=f"任务 '{task_id}' 不存在\n可用任务: {available or '(无)'}",
    )


# ============================================================
# 工具函数
# ============================================================

def _format_interval(minutes: Optional[int]) -> str:
    """将分钟数格式化为可读字符串"""
    if minutes is None:
        return "?"
    if minutes < 60:
        return f"{minutes}m"
    if minutes % 1440 == 0:
        return f"{minutes // 1440}d"
    if minutes % 60 == 0:
        return f"{minutes // 60}h"
    return f"{minutes}m"
