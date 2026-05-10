"""
memorybuild.py — 对话记录持久化

以 JSON 格式存储所有对话，日期为主 key。支持日志轮转和原子写入。
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from buddyMe.initspace.utils import _load_md


def _extract_facts(text: str) -> Dict[str, Any]:
    """从文本中提取结构化关键事实（纯正则，零LLM开销）。

    提取内容：
      - 文件路径（.html/.py/.md/.json/.txt/.css/.js/.csv/.xlsx/.pdf）
      - URL
      - 日期（YYYY-MM-DD / YYYY/MM/DD）
      - 模型名称
    """
    facts: Dict[str, Any] = {}

    file_paths = re.findall(
        r'[a-zA-Z0-9_/\-\\]+\.(?:html|py|md|json|txt|css|js|csv|xlsx|pdf)',
        text,
    )
    if file_paths:
        facts["files"] = list(set(file_paths))[:10]

    urls = re.findall(r'https?://[^\s<>"\']+', text)
    if urls:
        facts["urls"] = urls[:5]

    dates = re.findall(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', text)
    if dates:
        facts["dates"] = list(set(dates))

    model_names = re.findall(
        r'(?<![./\w])(?:glm|ernie|xiaomi|qwen|minimax|deepseek|claude|gpt)[\w.\-]*(?![/\w])',
        text, re.IGNORECASE,
    )
    if model_names:
        facts["models"] = list(set(m.lower() for m in model_names))[:3]

    return facts


class ConversationLogger:
    """对话记录器 — 追加式写入，按日期归档，支持日志轮转和原子写入。"""

    def __init__(self, log_path: str = "memorys/conversation_log.json",
                 max_mb: int = 100, rotate_count: int = 5):
        self.log_path = Path(log_path).resolve()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._max_mb = max_mb
        self._rotate_count = rotate_count
        self._init_log_file()

    def _init_log_file(self):
        if not self.log_path.exists():
            self.log_path.write_text("{}", encoding="utf-8")

    def log(self, query: str, response: str,
            tool_calls: List[Dict[str, Any]] = None,
            model: str = "", extra: Dict[str, Any] = None) -> None:
        """
        追加一条对话记录。

        Args:
            query: 用户输入
            response: 助手回复
            tool_calls: 工具调用列表
            model: 模型名称
            extra: 补充信息（支持 task_type, execute_status, quality_score 等情景记忆字段）
        """
        date_key = datetime.now().strftime("%Y-%m-%d")

        record = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "model": model,
            "query": query,
            "response": response,
            "response_summary": response[:500] if len(response) > 500 else response,
            "facts": _extract_facts(response),
            "tool_calls": tool_calls or [],
            **(extra or {}),
        }

        data = self._load()
        if date_key not in data:
            data[date_key] = []
        data[date_key].append(record)
        self._save(data)

    def _load(self) -> Dict:
        if self.log_path.exists():
            content = self.log_path.read_text(encoding="utf-8").strip()
            if not content:
                return {}
            return json.loads(content)
        return {}

    def _save(self, data: Dict) -> None:
        from buddyMe.utils.atomic import atomic_write

        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        atomic_write(self.log_path, json_str)

        if self.log_path.stat().st_size > self._max_mb * 1024 * 1024:
            self._rotate()

    def _rotate(self):
        """轮转日志：当前 → .1.json，.1.json → .2.json，最多 rotate_count 个归档。"""
        import shutil

        base = self.log_path
        for i in range(self._rotate_count - 1, 0, -1):
            src = base.with_name(f"{base.stem}.{i}{base.suffix}")
            dst = base.with_name(f"{base.stem}.{i + 1}{base.suffix}")
            if src.exists():
                shutil.move(str(src), str(dst))
        archive = base.with_name(f"{base.stem}.1{base.suffix}")
        shutil.move(str(base), str(archive))
        self._init_log_file()
