# Extracts durable memories from conversations via LLM.

"""
================================================================================
memory_extractor.py - 记忆提取器
================================================================================

根据 MD 文件标题结构，从 conversation_log.json 当日对话中批量提取信息的子 Agent。

用法:
    extractor = MemoryExtractor(
        md_path="brain/USER.md",
        conversation_log_path="initspace/memorys/conversation_log.json",
    )
    result = await extractor.extract()

================================================================================
"""

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from buddyMe.initspace.utils import _PROJECT_ROOT, _extract_json, _load_md

logger = logging.getLogger(__name__)


class MemoryExtractor:
    """记忆提取器 — 根据 MD 文件标题结构，从 conversation_log.json 当日对话中批量提取信息。

    用法:
        extractor = MemoryExtractor(
            md_path="brain/USER.md",
            conversation_log_path="initspace/memorys/conversation_log.json"
        )
        result = await extractor.extract()
    """

    # 非 data 段落标题，解析时跳过
    _SKIP_SECTIONS = frozenset({"说明"})

    def __init__(self, model_name: str = "glm", md_path: str = "",
                 conversation_log_path: str = "",
                 client: Optional[Any] = None):
        """
        Args:
            model_name: LLM 模型名称，用于内部创建客户端（client 为 None 时生效）
            md_path: markdown 文件路径（自动提取 ##/### 标题作为提取字段）
            conversation_log_path: conversation_log.json 文件路径
            client: 外部注入的 LLM 客户端（可选，优先于 model_name 创建的客户端）
        """
        self.model_name: str = model_name
        self.md_path: str = md_path
        self.sections: List[str] = self._parse_sections(md_path)
        self.conversation_log_path: str = conversation_log_path

        if client is not None:
            self.client = client
        else:
            from buddyMe.llm_moudle import basic_llm
            self.client = basic_llm.create_client(model_name)

    def _parse_sections(self, md_path: str) -> List[str]:
        """从 md 文件提取 ## 和 ### 标题名，跳过非数据段落。"""
        raw = _load_md(md_path)
        if not raw:
            return []
        return [
            s for s in re.findall(r"^#{2,3}\s+(.+)$", raw, re.MULTILINE)
            if s.strip() not in self._SKIP_SECTIONS
        ]

    def _get_recent_conversations(self, days: int = 5) -> str:
        """从 conversation_log.json 中读取最近 N 日所有对话记录，拼接为文本。"""
        if not self.conversation_log_path:
            return ""

        abs_path = Path(self.conversation_log_path).resolve()
        if not abs_path.exists():
            abs_path = Path(_PROJECT_ROOT) / self.conversation_log_path
        if not abs_path.exists():
            return ""

        try:
            data = json.loads(abs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            # 半写入/损坏的日志不应导致整个记忆提取任务失败
            logger.warning(f"[MemoryExtractor] 读取对话日志失败，跳过: {e}")
            return ""
        if not isinstance(data, dict):
            logger.warning("[MemoryExtractor] 对话日志格式异常（非对象），跳过")
            return ""

        # 生成最近 N 日的日期键
        today = datetime.now()
        date_keys = [
            (today - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(days)
        ]

        parts = []
        for date_key in date_keys:
            conversations = data.get(date_key, [])
            if not conversations:
                continue
            for conv in conversations:
                query = conv.get("query", "")
                response = conv.get("response", "")
                parts.append(
                    "[" + date_key + "] 用户: " + query + "\n助手: " + response
                )

        return "\n\n".join(parts)

    async def extract(self, days: int = 5) -> Dict[str, Any]:
        """
        根据 MD 文件标题结构，从最近 N 日对话中批量提取信息。

        Args:
            days: 回溯天数，默认 5

        Returns:
            提取结果字典，失败或无新发现返回空字典
        """
        text = self._get_recent_conversations(days)
        if not text.strip() or not self.sections:
            return {}
        sections_str = ", ".join(self.sections)
        prompt = (
            "从以下近" + str(days) + "日对话记录中提取信息。只提取这些字段：" + sections_str + "\n"
            "规则：只提取明确提到的，不推测。没有新发现就输出空 JSON: {}\n"
            "输出纯 JSON：{\"字段名\": \"值或列表\", ...}"
        )
        try:
            response = await self.client.chat(messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ])
            raw = "".join(
                b.get("text", "") for b in response.get("content", [])
                if b.get("type") == "text"
            )
            return _extract_json(raw)
        except Exception as e:
            logger.warning(f"[MemoryExtractor] 提取失败: {e}")
            return {}
