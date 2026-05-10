"""
================================================================================
InvokeSkillTool — Skill 激活工具
================================================================================

继承 BaseTool，作为 LLM 与 SkillLoader 之间的桥梁。

LLM 在 system prompt 中看到 Level 1 元数据后，如果判断用户需求匹配某个 Skill，
就会调用 invoke_skill 工具，触发 Level 2 指令加载。

返回的指令内容包含完整的执行流程和资源绝对路径，LLM 据此自行调用
bash / read_file 等已有工具完成实际操作。

================================================================================
"""

import logging
from typing import Optional

from buddyMe.anthropic_standard.basic_anthropic_tool import BaseTool
from buddyMe.initspace.skill_loader import SkillLoader

logger = logging.getLogger(__name__)


class InvokeSkillTool(BaseTool):
    """Skill 激活工具 — 加载指定技能的完整执行指令"""

    def __init__(self, skill_loader: SkillLoader):
        super().__init__(
            name="invoke_skill",
            description="""激活并加载指定技能的完整执行指令。

【适用场景】
- 当用户需求匹配到 system prompt 中列出的某个技能时调用
- 由 LLM 根据技能描述（name + description）自动判断是否匹配
- 不要对不存在的技能名称调用此工具

【输入参数】
- skill_name (必需): 要激活的技能名称（必须是可用技能列表中存在的名称）
- user_query (必需): 用户原始问题（帮助技能理解上下文）

【输出】
- 返回该技能的完整执行指令，包含执行流程和资源绝对路径
- LLM 收到指令后，应按流程自行调用 bash / read_file 等工具完成操作""",
            parameters={
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "要激活的技能名称（如 weather-skill）"
                    },
                    "user_query": {
                        "type": "string",
                        "description": "用户原始问题，帮助技能理解上下文"
                    }
                },
                "required": ["skill_name", "user_query"]
            }
        )
        self._loader = skill_loader

    async def execute(self, skill_name: str, user_query: str) -> str:
        """加载 Skill 指令并返回给 LLM

        Args:
            skill_name: 技能名称
            user_query: 用户原始问题

        Returns:
            Skill 的完整执行指令，包含资源绝对路径
        """
        logger.info("=" * 60)
        logger.info("[Skill] >>> 激活技能: %s", skill_name)
        logger.info("[Skill] >>> 用户问题: %s", user_query)

        instructions = self._loader.load_instructions(skill_name)

        # 首次未命中：重新扫描 skill 目录，可能运行中新增了技能
        if not instructions:
            logger.info("[Skill] >>> 未命中，重新扫描 skill 目录...")
            added = self._loader.reload()
            instructions = self._loader.load_instructions(skill_name)

        if not instructions:
            available = list(self._loader.skills.keys())
            logger.warning("[Skill] >>> 技能 '%s' 不存在，可用: %s", skill_name, available)
            return (
                f"错误：未找到技能 '{skill_name}'。\n"
                f"当前可用技能: {available}"
            )

        # 将用户原始问题附加到指令中，方便 LLM 理解上下文
        result = (
            f"已激活技能: {skill_name}\n"
            f"用户问题: {user_query}\n\n"
            f"请按照以下指令完成任务:\n\n"
            f"{instructions}"
        )

        logger.info("[Skill] >>> 指令已加载（%d 字符）", len(result))
        logger.info("=" * 60)
        return result
