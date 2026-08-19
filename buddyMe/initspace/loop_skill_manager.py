# Manages skill loading for loop executions.

"""
loop_skill_manager.py — Loop Skill 生命周期管理（JSON 格式）

核心策略:
    Loop 任务首次执行时，主 agent 执行并记录完整工具调用链。
    成功后直接从 tool chain 生成 skill.json（纯 JSON，不经过 LLM）。
    后续 tick 直接按 Skill 中的步骤调用工具，不经过 LLM。

生命周期:
    generate_skill()   — 首次成功后，从 tool chain 自动生成 skill.json
    has_skill()        — tick 时检查是否存在 Skill
    load_skill_steps() — 读取 skill.json 提取确定性步骤
    execute_skill()    — 顺序执行步骤，支持模板变量替换
    delete_skill()     — /loop --remove 时同步删除
"""

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from buddyMe.utils.atomic import atomic_write

logger = logging.getLogger(__name__)


class LoopSkillManager:
    """Loop Skill 生命周期管理器（JSON 格式）"""

    def __init__(self, loop_skills_dir: str):
        self._loop_skills_dir = Path(loop_skills_dir).resolve()
        self._loop_skills_dir.mkdir(parents=True, exist_ok=True)

    def _skill_dir(self, task_id: str) -> Path:
        return self._loop_skills_dir / task_id

    def _skill_path(self, task_id: str) -> Path:
        return self._skill_dir(task_id) / "skill.json"

    # ------------------------------------------------------------------
    # 检测
    # ------------------------------------------------------------------

    def has_skill(self, task_id: str) -> bool:
        return self._skill_path(task_id).is_file()

    # ------------------------------------------------------------------
    # 生成（纯字符串匹配，不使用 LLM）
    # ------------------------------------------------------------------

    def generate_skill(
        self,
        task_id: str,
        description: str,
        tool_chain: List[Dict],
    ) -> bool:
        """从工具调用记录生成 skill.json。

        Args:
            task_id: 任务 ID
            description: 用户原始任务描述
            tool_chain: 工具调用记录列表，每项含 step/tool/args/result

        Returns:
            True 表示生成成功
        """
        if not tool_chain:
            logger.warning("[LoopSkill] 工具链为空，不生成 Skill")
            return False

        # 检查不可重放的工具
        for entry in tool_chain:
            if entry.get("tool") == "edit_file":
                logger.warning("[LoopSkill] 工具链含 edit_file，不可确定性重放")
                return False

        # 检查错误
        error_patterns = ["执行失败", "查询失败", "API 返回错误",
                          "Error:", "Exception", "Traceback"]
        for entry in tool_chain:
            result = entry.get("result", "")
            tool_name = entry.get("tool", "")
            if tool_name == "read_file" and "不存在" in result:
                continue
            if any(p in result for p in error_patterns):
                logger.warning("[LoopSkill] 工具链含错误: %s", result[:100])
                return False

        steps = self._build_steps(tool_chain)
        if not steps:
            logger.warning("[LoopSkill] 构建步骤为空")
            return False

        if not any(s.get("tool") == "write_file" for s in steps):
            logger.warning(
                "[LoopSkill] 工具链无 write_file 步骤，不生成 Skill（%d 步: %s）",
                len(steps),
                [s.get("tool") for s in steps],
            )
            return False

        skill_data = {
            "name": task_id,
            "description": description[:100],
            "task_id": task_id,
            "created": datetime.now().isoformat(),
            "steps": steps,
        }

        skill_dir = self._skill_dir(task_id)
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = self._skill_path(task_id)

        json_str = json.dumps(skill_data, ensure_ascii=False, indent=2)
        atomic_write(str(skill_file), json_str)

        logger.info("[LoopSkill] 已生成: %s (%d 步骤)", task_id, len(steps))
        return True

    def _build_steps(self, tool_chain: List[Dict]) -> List[Dict]:
        """从 tool chain 构建步骤列表。

        策略:
        1. 对 write_file 的 content，按长度降序匹配前序 step result，替换为 {{step_N_result}}
        2. read_file → write_file 同路径时，自动前置 {{prev_content}}
        3. bash Get-Date 输出替换为 {{current_time}}，并删除该 bash 步骤
        4. 步骤索引基于过滤后的输出位置（确保与 execute_skill 中的 step_results 对齐）
        """
        steps: List[Dict] = []
        cleaned_results: List[str] = []
        prev_contents: List[str] = []
        last_read_path: Optional[str] = None
        get_date_step_indices: set = set()

        # 第一遍：收集信息
        for i, entry in enumerate(tool_chain):
            tool_name = entry["tool"]
            args = dict(entry["args"])
            raw_result = entry.get("result", "")
            cleaned = raw_result.replace("\r\n", "\n").replace("\r", "\n")
            cleaned_results.append(cleaned)

            if tool_name == "read_file":
                file_path = args.get("path", "")
                last_read_path = file_path
                match = re.search(r"内容:\n(.*)", cleaned, re.DOTALL)
                file_content = match.group(1).rstrip() if match else cleaned.rstrip()
                if file_content:
                    prev_contents.append(file_content)

            if tool_name == "bash" and self._is_date_command(args.get("command", "")):
                get_date_step_indices.add(i)

        # 构建 原始索引 → 过滤后索引 的映射
        # 这样 {{step_N_result}} 使用过滤后的索引，与 execute_skill 中的 step_results 对齐
        original_to_filtered: Dict[int, int] = {}
        filtered_idx = 0
        for i in range(len(tool_chain)):
            if i not in get_date_step_indices:
                original_to_filtered[i] = filtered_idx
                filtered_idx += 1

        # 第二遍：构建步骤
        for i, entry in enumerate(tool_chain):
            tool_name = entry["tool"]
            args = dict(entry["args"])

            if tool_name == "write_file" and "content" in args:
                content = args["content"]
                write_path = args.get("path", "")

                # 按长度降序匹配前序 result → {{step_N_result}}（使用过滤后索引）
                replacements = []
                for idx in range(i):
                    if idx in get_date_step_indices:
                        continue
                    result = cleaned_results[idx]
                    if result and len(result) > 3:
                        mapped = original_to_filtered.get(idx, idx)
                        replacements.append(
                            (len(result), result, f"{{{{step_{mapped + 1}_result}}}}")
                        )
                for pc in prev_contents:
                    if pc and len(pc) > 3:
                        replacements.append((len(pc), pc, "{{prev_content}}"))

                replacements.sort(key=lambda x: -x[0])
                for _, old, new in replacements:
                    if old in content:
                        content = content.replace(old, new, 1)

                # read_file → write_file 同路径，自动前置 {{prev_content}}
                if (last_read_path and write_path == last_read_path
                        and "{{prev_content}}" not in content):
                    content = "{{prev_content}}\n\n" + content

                # Date step result → {{current_time}}
                for idx in get_date_step_indices:
                    mapped = original_to_filtered.get(idx, idx)
                    placeholder = f"{{{{step_{mapped + 1}_result}}}}"
                    if placeholder in content:
                        content = content.replace(placeholder, "{{current_time}}")
                    else:
                        content = self._replace_datetime_pattern(content)

                args["content"] = content

            # 跳过 Get-Date bash 步骤（已替换为 {{current_time}}）
            if i in get_date_step_indices:
                continue

            steps.append({"tool": tool_name, "args": args})

        return steps

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------

    def load_skill_steps(self, task_id: str) -> Optional[List[Dict]]:
        """读取 skill.json 提取步骤列表。"""
        skill_file = self._skill_path(task_id)
        if not skill_file.is_file():
            return None

        try:
            data = json.loads(skill_file.read_text(encoding="utf-8"))
            return data.get("steps")
        except Exception as e:
            logger.error("[LoopSkill] 加载失败: %s, %s", skill_file, e)
            return None

    # ------------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------------

    async def execute_skill(
        self, executor: Any, task_id: str,
    ) -> str:
        """确定性执行 Loop Skill 中的步骤。"""
        steps = self.load_skill_steps(task_id)
        if not steps:
            return "[Loop Skill 加载失败，无可用步骤]"

        step_results: List[str] = []
        prev_content = ""

        for i, step in enumerate(steps):
            tool_name = step["tool"]
            tool_args = dict(step["args"])

            tool_args = self._resolve_templates(
                tool_args, step_results, prev_content,
            )

            logger.info(
                "[LoopSkill Step %d] tool=%s, args=%s",
                i + 1, tool_name,
                {k: v[:80] if isinstance(v, str) else v
                 for k, v in tool_args.items()},
            )

            try:
                result = await executor.execute(tool_name, tool_args)
                result = result or ""
            except Exception as e:
                logger.error("[LoopSkill Step %d] 执行失败: %s", i + 1, e)
                return f"[Loop Skill 步骤 {i + 1} 执行失败: {e}]"

            step_results.append(result)

            if tool_name == "read_file":
                if "不存在" in result or "错误" in result:
                    prev_content = ""
                else:
                    content_match = re.search(r"内容:\n(.*)", result, re.DOTALL)
                    prev_content = (
                        content_match.group(1).rstrip()
                        if content_match else result.rstrip()
                    )

        return step_results[-1] if step_results else "[Loop Skill 执行完成]"

    def _resolve_templates(
        self,
        args: Dict,
        step_results: List[str],
        prev_content: str,
    ) -> Dict:
        """替换模板变量为实际值。"""
        now = datetime.now()
        resolved = {}
        for k, v in args.items():
            if not isinstance(v, str):
                resolved[k] = v
                continue
            v = v.replace("{{current_time}}", now.strftime("%Y-%m-%d %H:%M:%S"))
            v = v.replace("{{current_date}}", now.strftime("%Y-%m-%d"))
            if prev_content:
                v = v.replace("{{prev_content}}", prev_content)
            else:
                v = v.replace("{{prev_content}}", "")
                v = v.lstrip("\n")
            for idx, result in enumerate(step_results):
                short = result.replace("\r\n", "\n").replace("\r", "\n").strip()
                v = v.replace(f"{{{{step_{idx + 1}_result}}}}", short)
            resolved[k] = v
        return resolved

    # ------------------------------------------------------------------
    # 删除
    # ------------------------------------------------------------------

    def delete_skill(self, task_id: str) -> bool:
        """删除 Loop Skill 目录。"""
        skill_dir = self._skill_dir(task_id)
        if skill_dir.is_dir():
            shutil.rmtree(str(skill_dir))
            logger.info("[LoopSkill] 已删除: %s", task_id)
            return True
        return False

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _is_date_command(command: str) -> bool:
        """检测 bash 命令是否为获取当前时间。"""
        cmd = command.strip()
        if "Get-Date" in cmd:
            return True
        if re.match(r'^date\b', cmd):
            return True
        return False

    @staticmethod
    def _replace_datetime_pattern(content: str) -> str:
        """在 write_file content 中替换第一个时间戳为 {{current_time}}。

        匹配顺序: ISO带秒 > ISO不带秒 > 日期（YYYY-MM-DD）
        优先匹配更精确的时间格式。
        """
        # 1) ISO 带秒: 2026-05-06 14:30:15
        m = re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', content)
        if m:
            return content[:m.start()] + '{{current_time}}' + content[m.end():]
        # 2) ISO 不带秒: 2026-05-06 14:30
        m = re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?!\d)', content)
        if m:
            return content[:m.start()] + '{{current_time}}' + content[m.end():]
        # 3) 纯日期: 2026-05-06（不含后续数字，避免误匹配日期列表中的数据）
        m = re.search(r'\d{4}-\d{2}-\d{2}(?!\s*\d)', content)
        if m:
            return content[:m.start()] + '{{current_time}}' + content[m.end():]
        return content
