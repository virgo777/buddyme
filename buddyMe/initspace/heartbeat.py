"""
================================================================================
heartbeat.py - 心跳配置与日志管理器（纯数据辅助层）
================================================================================

职责：
    - 管理 heartbeat.json 的读写
    - 管理执行日志的读写
    - 提供时间判断工具（活跃时段、任务是否该执行）
    - 提供任务增删改查操作

注意：
    本模块不包含任何执行逻辑，定时任务的调度和执行由 Agent.tick() 负责。

用法：
    from initspace.heartbeat import HeartbeatManager

    hb = HeartbeatManager(config_path="initspace/memorys/heartbeat.json")
    hb._load_config()                  # 读取配置
    hb._is_in_active_hours()           # 判断活跃时段
    hb._should_run(task)               # 判断任务是否该执行
    hb.add_task(task)                  # 添加任务
    hb.get_status()                    # 获取状态

================================================================================
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from buddyMe.utils.atomic import atomic_write

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class HeartbeatManager:
    """心跳配置与日志管理器 — 纯数据辅助层，不含执行逻辑。"""

    def __init__(
        self,
        config_path: str = "initspace/memorys/heartbeat.json"
    ):
        """
        初始化心跳管理器。

        参数:
            config_path: 心跳配置文件 heartbeat.json 的路径
            agent: 保留参数（向后兼容），当前版本不使用
        """
        self.config_path = Path(config_path).resolve()
        if not self.config_path.exists():
            self.config_path = Path(_PROJECT_ROOT) / config_path

        # 存储从配置文件加载的全局配置
        self._config: Dict[str, Any] = {}
        # 存储从配置文件加载的任务列表
        self._tasks: List[Dict[str, Any]] = []

        # 存储从配置文件加载的日志（内存中，不持久化到文件）
        self._logs: Dict[str, List[Dict[str, Any]]] = {}

        # 文件读写锁（可重入，因为 add_task 内部调用 _save_config）
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # 配置读写
    # ------------------------------------------------------------------

    def _load_config(self) -> Dict[str, Any]:
        """
        加载心跳配置文件。

        返回:
            包含 config 和 tasks 的配置字典，文件不存在或为空时返回默认配置
        """
        if not self.config_path.exists():
            return {"config": {"interval_minutes": 30}, "tasks": []}
        content = self.config_path.read_text(encoding="utf-8").strip()
        if not content:
            return {"config": {"interval_minutes": 30}, "tasks": []}
        return json.loads(content)

    def _save_config(self, data: Dict[str, Any]) -> None:
        """原子保存配置到文件。

        注意: 调用方应持有 self._lock，此方法不再内部加锁。
        """
        content = json.dumps(data, ensure_ascii=False, indent=2)
        atomic_write(str(self.config_path), content)

    # ------------------------------------------------------------------
    # 时间判断工具
    # ------------------------------------------------------------------

    def _is_in_active_hours(self) -> bool:
        """
        检查当前时间是否在活跃时段内。

        返回:
            True 表示在活跃时段内
        """
        active = self._config.get("active_hours")
        if not active:
            return True
        now_minutes = datetime.now().hour * 60 + datetime.now().minute
        start_parts = active.get("start", "00:00").split(":")
        end_parts = active.get("end", "23:59").split(":")
        start_min = int(start_parts[0]) * 60 + int(start_parts[1])
        end_min = int(end_parts[0]) * 60 + int(end_parts[1])
        return start_min <= now_minutes <= end_min

    def _should_run(self, task: Dict[str, Any]) -> bool:
        """
        判断单个任务是否满足执行条件。

        参数:
            task: 任务配置字典

        返回:
            True 表示该任务当前应该执行
        """
        if not task.get("enabled", True):
            return False

        # 首次执行正在进行中，跳过（防止心跳和首次执行同时运行）
        if task.get("first_exec_pending"):
            return False

        last_run = task.get("last_run")

        # schedule 模式（定时触发）
        schedule = task.get("schedule")
        if schedule:
            now = datetime.now()
            parts = schedule.split(":")
            target_minutes = int(parts[0]) * 60 + int(parts[1])
            now_minutes = now.hour * 60 + now.minute
            if abs(now_minutes - target_minutes) > 5:
                return False
            if last_run:
                try:
                    last_dt = datetime.fromisoformat(last_run)
                    if last_dt.date() == now.date():
                        return False
                except (ValueError, TypeError):
                    pass
            return True

        # interval 模式（间隔触发）
        interval = task.get("interval_minutes", 0)
        if interval <= 0:
            return False
        if not last_run:
            return True
        try:
            last_dt = datetime.fromisoformat(last_run)
            elapsed = (datetime.now() - last_dt).total_seconds() / 60
            return elapsed >= interval
        except (ValueError, TypeError):
            return True

    def _get_timeout(self, task: Dict[str, Any]) -> int:
        """获取任务超时时间（秒），任务未配置则用全局默认值。"""
        task_timeout = task.get("timeout_seconds", 0)
        if task_timeout > 0:
            return task_timeout
        return self._config.get("default_timeout_seconds", 300)

    # ------------------------------------------------------------------
    # 任务管理
    # ------------------------------------------------------------------

    def add_task(self, task: Dict[str, Any]) -> bool:
        """
        添加新任务。

        参数:
            task: 任务配置字典，需包含 id、name、prompt 等字段

        返回:
            True 表示添加成功，False 表示任务 ID 已存在
        """
        with self._lock:
            data = self._load_config()
            tasks = data.get("tasks", [])
            task_id = task.get("id", "")
            if any(t.get("id") == task_id for t in tasks):
                logger.warning("[Heartbeat] 任务 ID 已存在: %s", task_id)
                return False
            task.setdefault("enabled", True)
            task.setdefault("last_run", None)
            tasks.append(task)
            data["tasks"] = tasks
            self._save_config(data)
            logger.info("[Heartbeat] 添加任务: %s", task_id)
        return True

    def remove_task(self, task_id: str) -> bool:
        """
        删除任务。

        参数:
            task_id: 要删除的任务 ID

        返回:
            True 表示删除成功，False 表示任务 ID 不存在
        """
        with self._lock:
            data = self._load_config()
            tasks = data.get("tasks", [])
            new_tasks = [t for t in tasks if t.get("id") != task_id]
            if len(new_tasks) == len(tasks):
                return False
            data["tasks"] = new_tasks
            self._save_config(data)
            logger.info("[Heartbeat] 删除任务: %s", task_id)
        return True

    def enable_task(self, task_id: str, enabled: bool = True) -> bool:
        """
        启用或禁用任务。

        参数:
            task_id: 任务 ID
            enabled: True 表示启用，False 表示禁用

        返回:
            True 表示操作成功，False 表示任务 ID 不存在
        """
        with self._lock:
            data = self._load_config()
            for task in data.get("tasks", []):
                if task.get("id") == task_id:
                    task["enabled"] = enabled
                    self._save_config(data)
                    action = "启用" if enabled else "禁用"
                    logger.info("[Heartbeat] %s 任务: %s", action, task_id)
                    return True
        return False

    def get_status(self) -> Dict[str, Any]:
        """
        返回所有任务状态。

        返回:
            包含全局配置和任务列表的字典
        """
        data = self._load_config()
        config = data.get("config", {})
        tasks = data.get("tasks", [])
        return {
            "config": config,
            "tasks": [
                {
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "enabled": t.get("enabled", True),
                    "last_run": t.get("last_run"),
                }
                for t in tasks
            ],
        }


# ==============================================================================
# 测试
# ==============================================================================

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("HeartbeatManager 测试（纯数据辅助层）")
    print("=" * 60)

    hb = HeartbeatManager(
        config_path=str(_PROJECT_ROOT / "initspace" / "memorys" / "heartbeat.json"),
    )

    # 测试 1：读取状态
    print("\n--- 测试 1: 获取状态 ---")
    status = hb.get_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))

    # 测试 2：添加任务
    print("\n--- 测试 2: 添加任务 ---")
    ok = hb.add_task({
        "id": "test_task",
        "name": "测试任务",
        "enabled": True,
        "interval_minutes": 5,
        "schedule": None,
        "last_run": None,
        "prompt": "这是一个测试心跳任务，请回复 HEARTBEAT_OK",
    })
    print(f"添加结果: {ok}")

    # 测试 3：获取状态（含新任务）
    print("\n--- 测试 3: 获取更新后状态 ---")
    status = hb.get_status()
    for t in status["tasks"]:
        print(f"  {t['id']}: {t['name']} (enabled={t['enabled']}, last_run={t['last_run']})")

    # 测试 4：活跃时段判断
    print("\n--- 测试 4: 活跃时段判断 ---")
    data = hb._load_config()
    hb._config = data.get("config", {})
    print(f"当前是否在活跃时段: {hb._is_in_active_hours()}")

    # 测试 5：任务执行判断
    print("\n--- 测试 5: 任务执行判断 ---")
    for task in data.get("tasks", []):
        should = hb._should_run(task)
        print(f"  {task.get('id')}: should_run={should}")

    # 测试 6：超时配置
    print("\n--- 测试 6: 超时配置 ---")
    for task in data.get("tasks", []):
        timeout = hb._get_timeout(task)
        print(f"  {task.get('id')}: timeout={timeout}s")

    # 清理测试任务
    print("\n--- 清理测试任务 ---")
    ok = hb.remove_task("test_task")
    print(f"删除结果: {ok}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
