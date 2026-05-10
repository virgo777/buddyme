"""
================================================================================
contextbuild.py - 动态 System Prompt 构建器
================================================================================

将 brain/ 目录下的分层人格文件（SOUL / IDENTITY / Agent）
与已注册工具的 Schema（能力说明）融合为一份完整的、上下文连贯的 system prompt。

分层设计:
    SOUL.md    (L0) — 人格内核：你怎么说话、什么性格、核心价值观
    IDENTITY.md(L1) — 角色身份：你是谁、服务什么、边界在哪
    AGENT.md   (能力) — 执行规范：怎么做事、怎么用工具、交互规则
    工具 Schema     — 动态能力：你能调用哪些工具、参数是什么

用法:
    from initspace.contextbuild import build_system_prompt

    prompt = build_system_prompt(
        tool_schemas=executor.get_all_schemas(),
        brain_dir="initspace/brain",
    )

================================================================================
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from buddyMe.initspace.utils import _load_md

logger = logging.getLogger(__name__)


# ==============================================================================
# 内部工具函数
# ==============================================================================


def _load_brain_files(brain_dir: str) -> List[str]:
    """按顺序加载 brain 目录下的 SOUL.md、IDENTITY.md、AGENT.md。

    加载顺序决定 system prompt 中的层级排列：
        1. SOUL.md     — 人格内核（L0，最稳定）
        2. IDENTITY.md — 角色身份（L1，切换角色时替换）
        3. AGENT.md    — 执行规范（能力边界）

    Args:
        brain_dir: brain 目录路径

    Returns:
        非空文件内容的列表（按上述顺序排列，跳过空文件）。
    """
    filenames = ["SOUL.md", "IDENTITY.md", "AGENT.md", "HEARTBEAT.md"]
    loaded: List[str] = []

    for name in filenames:
        path = str(Path(brain_dir) / name)
        content = _load_md(path)
        if content:
            loaded.append(content)

    return loaded

def _parse_tool_description(description: str) -> Dict[str, str]:
    """
    解析工具 description 中用 【】标记的结构化段落。

    例如:
        "使用百度搜索...\n【适用场景】\n- 查天气\n【输入参数】\n- query..."
    解析为:
        {"适用场景": "- 查天气", "输入参数": "- query...", ...}
    """
    sections: Dict[str, str] = {}
    current_key = ""
    current_lines: List[str] = []

    for line in description.split("\n"):
        match = re.match(r"^【(.+?)】", line.strip())
        if match:
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = match.group(1)
            current_lines = []
        elif current_key:
            current_lines.append(line)

    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections

def _format_params(properties: Dict, required: List[str]) -> str:
    """将参数 schema 格式化为简洁的单行描述列表"""
    parts = []
    for pname, pinfo in properties.items():
        ptype = pinfo.get("type", "any")
        pdesc = pinfo.get("description", "")
        req = "必需" if pname in required else "可选"
        default = pinfo.get("default")
        suffix = f"，默认{default}" if default is not None else ""
        parts.append(f"  - {pname} ({ptype}, {req}): {pdesc}{suffix}")
    return "\n".join(parts)

def _build_tool_section(tool_schemas: List[Dict]) -> str:
    """
    从工具 Schema 列表生成融合后的「工具能力与调用指南」段落。

    不是机械 dump 参数表，而是提取每个工具的 适用场景/输入参数/输出/安全限制
    等结构化信息，以与 SOUL.md 一致的 【】风格输出。
    """
    if not tool_schemas:
        return ""

    lines = [
        "【工具能力与调用指南】",
        "以下是你可以使用的工具。根据用户需求选择合适的工具，先获取数据再回答，禁止凭空编造。",
        "",
    ]

    for schema in tool_schemas:
        func = schema.get("function", schema)
        name = func.get("name", "unknown")
        description = func.get("description", "")
        parameters = func.get("parameters", {})
        properties = parameters.get("properties", {})
        required = parameters.get("required", [])

        # 解析 description 中的结构化段落
        desc_sections = _parse_tool_description(description)

        # 工具标题：从 description 第一行提取一句话摘要
        summary = description.strip().split("\n")[0].strip()
        lines.append(f"▶ {name} — {summary}")

        # 适用场景（从 description 解析）
        scenarios = desc_sections.get("适用场景", "")
        if scenarios:
            lines.append("  适用场景：")
            for s in scenarios.split("\n"):
                s = s.strip()
                if s:
                    lines.append(f"    {s}")

        # 调用参数（从 schema properties 生成）
        if properties:
            lines.append("  调用参数：")
            lines.append(_format_params(properties, required))

        # 输出说明（从 description 解析）
        output = desc_sections.get("输出", "")
        if output:
            lines.append(f"  输出：{output}")

        # 安全限制 / 注意事项（从 description 解析）
        for extra_key in ("安全限制", "注意", "限制"):
            extra = desc_sections.get(extra_key, "")
            if extra:
                lines.append(f"  {extra_key}：{extra}")

        lines.append("")

    return "\n".join(lines)

# ==============================================================================
# 公开接口
# ==============================================================================

def build_system_prompt(
    tool_schemas: List[Dict],
    brain_dir: Optional[str] = None,
    soul_path: Optional[str] = None,
    platform: Optional[str] = None,
    skill_metadata: Optional[str] = None,
) -> str:
    """
    动态构建完整的 system prompt。

    流程:
        1. 加载 brain 目录 → SOUL.md + IDENTITY.md + AGENT.md（按层级融合）
        2. 解析 tool_schemas → 每个工具的适用场景、参数、输出、限制
        3. 融合输出：人格文件 + 工具能力指南，风格统一

    Args:
        tool_schemas: 已注册工具的 schema 列表（来自 ToolExecutor.get_all_schemas()）
        brain_dir: brain 目录路径（包含 SOUL/IDENTITY/AGENT 三个 .md 文件）
        soul_path: SOUL.md 单文件路径（向后兼容，优先级低于 brain_dir）
        platform: 操作系统平台（如 'win32', 'linux'）
        skill_metadata: Skill Level 1 元数据摘要字符串（由 SkillLoader.get_metadata_prompt() 生成）

    Returns:
        融合后的完整 system prompt 字符串
    """
    sections: List[str] = []

    # --- 1. 环境信息 ---
    if platform:
        sections.append(f"【环境信息】\n系统平台: {platform}")


    # --- 2. 分层人格文件（SOUL → IDENTITY → Agent）---
    if brain_dir:
        brain_contents = _load_brain_files(brain_dir)
        sections.extend(brain_contents)
    elif soul_path:
        # 向后兼容：只传了 soul_path 的情况
        soul = _load_md(soul_path)
        if soul:
            sections.append(soul)

    # --- 3. Skill 元数据（在工具之前注入，优先引导 LLM 使用技能）---
    if skill_metadata:
        sections.append(skill_metadata)

    # --- 4. 工具能力与调用指南 ---
    tool_section = _build_tool_section(tool_schemas)
    if tool_section:
        sections.append(tool_section)

    return "\n\n".join(sections)
