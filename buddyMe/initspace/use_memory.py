"""
================================================================================
use_memory.py - 通用记忆管理器
================================================================================

支持：提取写入 → 去重 → 相似度评分 → 记忆衰减 → 记忆整合

用法:
    from initspace.use_memory import UseMemory

    mem = UseMemory(
        md_path="initspace/brain/USER.md",
        conversation_log_path="initspace/memorys/conversation_log.json",
    )
    changed = await mem.update()

================================================================================
"""

import json
import logging
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

from buddyMe.initspace.memory_extractor import MemoryExtractor
from buddyMe.initspace.utils import _load_md

logger = logging.getLogger(__name__)


class UseMemory:
    """通用记忆管理器 — 精细化记忆生命周期管理。

    支持：提取写入 → 去重 → 相似度评分 → 记忆衰减 → 记忆整合
    """

    # 记忆评分权重（参考 05_memory.md）
    RELEVANCE_WEIGHT = 0.4
    IMPORTANCE_WEIGHT = 0.3
    RECENCY_WEIGHT = 0.3

    # 衰减阈值
    ARCHIVE_THRESHOLD = 0.4   # < 0.4 归档
    CLEAN_THRESHOLD = 0.2     # < 0.2 清理

    # 去重阈值
    SIMILARITY_THRESHOLD = 0.8

    _SKIP_SECTIONS = frozenset({"说明"})

    def __init__(self, md_path: str, conversation_log_path: str = "",
                 model_name: str = "glm",
                 client: Optional[Any] = None):
        """
        Args:
            md_path: 记忆 MD 文件路径
            conversation_log_path: 对话记录 JSON 文件路径
            model_name: LLM 模型名称（client 为 None 时生效）
            client: 外部注入的 LLM 客户端（可选，传递给 MemoryExtractor 复用连接）
        """
        self.md_path: str = md_path
        self.conversation_log_path: str = conversation_log_path
        self.model_name: str = model_name
        self.data: Dict[str, Any] = {}
        self.sections: List[str] = []
        self.extractor = MemoryExtractor(
            model_name=model_name,
            md_path=md_path,
            conversation_log_path=conversation_log_path,
            client=client,
        )
        self.load()
        self._init_history()

    # ------------------------------------------------------------------
    # 基础：加载 / 保存 / 提示
    # ------------------------------------------------------------------

    def load(self) -> None:
        """解析 MD 文件：按 ## 切分段落，存入 self.data。"""
        raw = _load_md(self.md_path)
        if not raw:
            return
        sections = re.split(r"(?=^## )", raw, flags=re.MULTILINE)
        for sec in sections:
            lines = sec.strip().splitlines()
            if not lines:
                continue
            title_match = re.match(r"^## (.+)", lines[0])
            if not title_match:
                continue
            title = title_match.group(1).strip()
            content_lines = [
                l.strip() for l in lines[1:]
                if l.strip()
                and not l.strip().startswith("<!--")
                and l.strip() != "---"
                and "（暂无）" not in l
                and "（待识别）" not in l
            ]
            self.data[title] = "\n".join(content_lines)
        self.sections = list(self.data.keys())

    def save(self) -> None:
        """将 self.data 写回 MD 文件。"""
        lines = []
        for title in self.sections:
            lines.append("## " + title)
            lines.append("")
            value = self.data.get(title)
            if value:
                if isinstance(value, list):
                    for item in value:
                        lines.append("- " + str(item))
                else:
                    lines.append("- " + str(value))
            else:
                lines.append("- （暂无）")
            lines.append("")
        Path(self.md_path).write_text("\n".join(lines), encoding="utf-8")

    def to_prompt(self, max_sections: int = 5, max_chars: int = 800) -> str:
        history = self._load_history()
        last_active = history.get("last_active", {})

        # 按最近活跃时间排序，只取前 N 条
        sorted_sections = sorted(
            [(k, v) for k, v in self.data.items() if v],
            key=lambda x: last_active.get(x[0], ""),
            reverse=True
        )[:max_sections]

        parts = []
        for k, v in sorted_sections:
            truncated = v[:max_chars] + "..." if len(v) > max_chars else v
            parts.append(f"【{k}】\n{truncated}")

        if not parts:
            return ""
        md_name = Path(self.md_path).name
        return f"【{md_name} 记忆】\n以下是提取到的信息：\n\n" + "\n\n".join(parts)

    # ------------------------------------------------------------------
    # 核心：提取 + 去重
    # ------------------------------------------------------------------

    async def update(self, days: int = 5) -> Dict[str, Any]:
        """从对话中提取信息，去重后写入 MD。"""
        extracted = await self.extractor.extract(days)
        if not extracted:
            return {}

        now = datetime.now().isoformat()
        history = self._load_history()
        changed: Dict[str, Any] = {}

        for section, new_value in extracted.items():
            old_value = self.data.get(section)

            if not old_value:
                self.data[section] = new_value
                changed[section] = new_value
            else:
                score = self._similarity_score(old_value, new_value)
                if score >= self.SIMILARITY_THRESHOLD:
                    logger.info("[UseMemory] 重复跳过: %s (相似度=%.2f)", section, score)
                else:
                    # 冲突：归档旧值，写入新值
                    history.setdefault("archive", {}).setdefault(section, []).append({
                        "content": old_value,
                        "archived_at": now,
                        "similarity": round(score, 3),
                    })
                    self.data[section] = new_value
                    changed[section] = new_value

            history.setdefault("last_active", {})[section] = now

        self._save_history(history)
        if changed:
            self.save()
        return changed

    # ------------------------------------------------------------------
    # 记忆评分
    # ------------------------------------------------------------------

    def _calculate_memory_score(self, section: str, current_query: str = "") -> float:
        """计算单条记忆的有效得分 = 相关性×0.4 + 重要性×0.3 + 新鲜度×0.3"""
        history = self._load_history()

        # 1. 重要性
        importance = history.get("importance", {}).get(section, 0.5)

        # 2. 新鲜度
        last_active_str = history.get("last_active", {}).get(section)
        if not last_active_str:
            recency = 0.5
        else:
            last_active = datetime.fromisoformat(last_active_str)
            days_diff = (datetime.now() - last_active).days
            recency = max(0, 1 - (days_diff / 30))

        # 3. 相关性
        if not current_query:
            relevance = 0.5
        else:
            memory_content = str(self.data.get(section, ""))
            relevance = SequenceMatcher(None, current_query, memory_content).ratio()

        return round(
            relevance * self.RELEVANCE_WEIGHT
            + importance * self.IMPORTANCE_WEIGHT
            + recency * self.RECENCY_WEIGHT,
            2,
        )

    # ------------------------------------------------------------------
    # 记忆衰减
    # ------------------------------------------------------------------

    def run_memory_decay(self, current_query: str = ""):
        """执行记忆衰减：低分归档，极低分清理。"""
        history = self._load_history()
        archive = history.get("archive", {})
        active_sections = [s for s in list(self.data.keys()) if s not in self._SKIP_SECTIONS]
        to_archive = []

        for section in active_sections:
            score = self._calculate_memory_score(section, current_query)

            if score < self.CLEAN_THRESHOLD:
                # 极低分：直接删除
                del self.data[section]
                logger.info("[UseMemory] 清理: %s (得分=%.2f)", section, score)
                continue

            if score < self.ARCHIVE_THRESHOLD:
                # 低分：移入归档
                to_archive.append(section)

        for section in to_archive:
            archive.setdefault(section, []).append({
                "content": self.data[section],
                "archived_at": datetime.now().isoformat(),
            })
            del self.data[section]
            logger.info("[UseMemory] 归档: %s", section)

        history["archive"] = archive
        self._save_history(history)
        self.save()

    # ------------------------------------------------------------------
    # 记忆整合
    # ------------------------------------------------------------------

    def run_memory_consolidation(self):
        """合并碎片化/重复记忆。"""
        history = self._load_history()
        data = self.data

        # 语义合并规则，适配 USER.md 实际标题
        rules = [
            {
                "target": "历史摘要",
                "keywords": ["上次", "曾经", "之前", "历史"],
                "source_sections": ["任务进度"],
            },
            {
                "target": "偏好记录",
                "keywords": ["喜欢", "偏好", "口味", "风格"],
                "source_sections": [],
            },
        ]

        for rule in rules:
            target = rule["target"]
            if target not in data:
                continue

            merged_parts = []
            # 合并关键词匹配的段落
            for section in list(data.keys()):
                if section == target or section in self._SKIP_SECTIONS:
                    continue
                content = str(data.get(section, ""))
                if any(kw in content for kw in rule["keywords"]):
                    merged_parts.append(f"[{section}] {content}")
                    history.setdefault("archive", {}).setdefault(section, []).append({
                        "content": content,
                        "archived_at": datetime.now().isoformat(),
                        "reason": "consolidation",
                    })
                    del data[section]

            if merged_parts:
                existing = str(data.get(target, ""))
                new_content = existing + "\n" + "\n".join(merged_parts) if existing else "\n".join(merged_parts)
                data[target] = new_content
                history.setdefault("importance", {})[target] = 0.9

        self._save_history(history)
        self.save()

    # ------------------------------------------------------------------
    # 相似度工具
    # ------------------------------------------------------------------

    def _normalize(self, value: Any) -> str:
        if isinstance(value, list):
            return "\n".join(str(x).strip() for x in sorted(value))
        return str(value).strip()

    def _similarity_score(self, old: Any, new: Any) -> float:
        return SequenceMatcher(None, self._normalize(old), self._normalize(new)).ratio()

    # ------------------------------------------------------------------
    # 历史版本库
    # ------------------------------------------------------------------

    @property
    def history_path(self) -> str:
        md_path = Path(self.md_path).resolve()
        md_name = md_path.stem
        return str(md_path.parent.parent / "memorys" / (md_name + "_history.json"))

    def _init_history(self):
        if not Path(self.history_path).exists():
            self._save_history({"archive": {}, "last_active": {}, "importance": {}})

    def _load_history(self) -> Dict[str, Any]:
        hp = Path(self.history_path)
        if hp.exists():
            content = hp.read_text(encoding="utf-8").strip()
            if content:
                return json.loads(content)
        return {"archive": {}, "last_active": {}, "importance": {}}

    def _save_history(self, history_data: Dict[str, Any]):
        hp = Path(self.history_path)
        hp.parent.mkdir(parents=True, exist_ok=True)
        hp.write_text(json.dumps(history_data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == '__main__':
    import asyncio

    _PROJECT_ROOT = Path(__file__).resolve().parent.parent
    brain_dir = _PROJECT_ROOT / "initspace" / "brain"
    conv_log = str(_PROJECT_ROOT / "initspace" / "memorys" / "conversation_log.json")

    async def run():
        for md_file in ["USER.md"]:
            mem = UseMemory(str(brain_dir / md_file), conv_log)
            result = await mem.update()
            print(f"\n=== {md_file} ===")
            print(f"  标题: {mem.extractor.sections}")
            print(f"  提取: {result}")

    asyncio.run(run())
