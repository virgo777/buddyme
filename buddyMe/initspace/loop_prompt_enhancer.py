# Enhances loop prompts with skill-aware context.

"""
loop_prompt_enhancer.py — Loop 任务 Prompt 自动增强

架构:
    /loop 创建任务时，调用主模型将用户的一句话描述
    展开为结构化的执行指令（步骤 + 工具 + 路径），存入 heartbeat.json。
    心跳触发时，子智能体按预设指令逐步执行。

核心策略:
    将所有 Skill 的脚本路径和用途注入主模型的 system prompt，
    主模型生成直接使用 bash/read_file/write_file 的执行指令。
    子智能体拿到自包含的 prompt，无需调用 invoke_skill。

流程:
    1. 扫描所有 Skill，提取脚本路径和用途描述
    2. 调用主模型 LLM → 生成结构化执行指令
    3. 失败 → 返回原始描述（降级）
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _build_skill_resources_prompt(agent: Any, project_root: str) -> str:
    """扫描所有 Skill，提取可直接调用的脚本路径，供主模型生成 bash 命令。

    Returns:
        格式化的资源列表文本
    """
    if not hasattr(agent, "_skill_loader"):
        return ""

    loader = agent._skill_loader
    skills_dict = getattr(loader, "_skills", {}) or {}
    if not skills_dict:
        return ""

    lines = ["## 可用的 Skill 脚本资源", "以下是已注册 Skill 的脚本和资源路径，可以用 bash 直接调用：", ""]

    for skill_name, meta in skills_dict.items():
        skill_dir = getattr(meta, "skill_dir", "")
        if not skill_dir:
            continue
        skill_path = Path(skill_dir)
        if not skill_path.is_dir():
            continue

        abs_dir = str(skill_path).replace("\\", "/")
        desc = getattr(meta, "description", "")

        scripts_dir = skill_path / "scripts"
        script_paths: List[str] = []
        if scripts_dir.is_dir():
            for f in scripts_dir.iterdir():
                if f.name.endswith((".py", ".sh", ".js", ".bat")) and not f.name.startswith("__"):
                    script_paths.append(f.name)

        if script_paths:
            scripts_str = ", ".join(script_paths)
            lines.append(f"- **{skill_name}**: {desc}")
            lines.append(f"  目录: {abs_dir}")
            lines.append(f"  脚本: {scripts_str}")
            lines.append(f"  调用示例: python {abs_dir}/scripts/{script_paths[0]} [参数]")
            lines.append("")

    return "\n".join(lines)


_ENHANCER_SYSTEM_PROMPT = """你是一个定时任务规划师。你的工作是将用户的一句话任务描述，展开为结构化的执行指令，供子智能体逐步执行。

## 子智能体可用工具
- bash: 执行命令行命令（如运行 Python 脚本、curl 请求、系统命令）
- read_file: 读取文件内容
- write_file: 写入文件（覆盖写入，追加需先 read_file 再拼接）
- edit_file: 精确替换文件中的文本
- grep: 搜索文件内容
- glob: 按模式查找文件
- baidu_search: 搜索互联网信息

注意：子智能体不能调用 invoke_skill，必须用上面的基础工具完成任务。

## 项目根目录
{project_root}

{skill_resources}

## 输出要求
只输出执行指令，不要任何解释或前言。格式：

任务：[一句话总结]

步骤：
1. 用 [工具名] [做什么]（如：用 bash 执行 python {project_root}/skill_library/skills/weather-skill/scripts/weather.py beijing）
2. 用 [工具名] [做什么]
...

规则：
- [约束1]
- [约束2]

## 关键规则
- 文件路径必须用绝对路径
- 每步必须明确指定使用哪个工具，不能模糊带过
- 步骤尽量精简，不超过 5 步
- 涉及追加写入时：先 read_file 读已有内容 → 拼接新内容 → write_file 写回
- 需要查询天气等能力时，直接用 bash 调用上面给出的脚本路径，不要用 invoke_skill
- 需要搜索互联网时用 baidu_search
- 输出纯文本，不要用 markdown 代码块包裹"""


def enhance_loop_prompt(agent: Any, description: str) -> str:
    """主入口：调用主模型将用户描述展开为结构化执行指令。

    策略：
    1. 扫描 Skill 资源，将脚本路径注入 system prompt
    2. 主模型生成直接使用基础工具的执行指令
    3. 子智能体拿到自包含 prompt，不依赖 invoke_skill

    Args:
        agent: AgentMain 实例
        description: 用户任务描述

    Returns:
        增强后的 prompt，失败则返回原始描述
    """
    project_root = str(getattr(agent, "_DATA_DIR", Path.cwd())).replace("\\", "/")

    # 扫描 Skill 资源
    skill_resources = _build_skill_resources_prompt(agent, project_root)

    system = _ENHANCER_SYSTEM_PROMPT.format(
        project_root=project_root,
        skill_resources=skill_resources,
    )

    user_msg = f"请将以下定时任务描述展开为结构化的执行指令：\n\n{description}"

    result = agent.call_llm_sync(system, user_msg)

    if result and len(result) > 20:
        logger.info("[LoopEnhancer] LLM 增强成功，生成 %d 字符", len(result))
        return result

    logger.warning("[LoopEnhancer] LLM 增强失败，使用原始描述")
    return description
