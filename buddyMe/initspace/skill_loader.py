"""
================================================================================
skill_loader.py — Skill 动态发现、解析与加载引擎
================================================================================

遵循 Anthropic Skill 规范，实现三层渐进式加载：
  Level 1: 元数据（name + description） — Agent 启动时注入 system prompt
  Level 2: 指令体（SKILL.md body）      — 匹配到用户需求时加载
  Level 3: 资源（scripts/references/assets） — 执行流程需要时按需读取

兼容性：任何包含 SKILL.md（含 YAML frontmatter）的目录均自动识别。

用法:
    loader = SkillLoader(skill_dirs=["skill_library/skills"])
    prompt   = loader.get_metadata_prompt()                    # Level 1
    body     = loader.load_instructions("weather-skill")        # Level 2
    ref      = loader.resolve_reference("weather-skill", "city-codes.md")  # Level 3
    script   = loader.get_script_path("weather-skill", "weather.py")       # Level 3

================================================================================
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class SkillMeta:
    """Skill 元数据（从 SKILL.md YAML frontmatter 解析）"""
    name: str
    description: str
    skill_dir: str  # skill 根目录绝对路径


class SkillLoader:
    """Skill 动态发现、解析与加载引擎"""

    def __init__(self, skill_dirs: List[str]):
        """
        Args:
            skill_dirs: Skill 扫描目录列表（支持多个路径，兼容第三方 Skill）
        """
        self._skill_dirs = skill_dirs
        self._skills: Dict[str, SkillMeta] = {}
        self._discover()

    @property
    def skills(self) -> Dict[str, SkillMeta]:
        """返回已发现的所有 Skill 元数据（不可变副本）"""
        return dict(self._skills)

    def reload(self) -> int:
        """重新扫描所有 skill 目录，返回新增 skill 数量。"""
        old_count = len(self._skills)
        self._skills.clear()
        self._discover()
        new_count = len(self._skills)
        added = new_count - old_count
        if added > 0:
            logger.info("[SkillLoader] 热加载完成，新增 %d 个 Skill", added)
        return max(added, 0)

    # ------------------------------------------------------------------
    # Level 0：发现与解析
    # ------------------------------------------------------------------

    def _discover(self):
        """扫描所有 skill 目录，解析每个子目录中的 SKILL.md frontmatter"""
        for skill_dir in self._skill_dirs:
            abs_dir = Path(skill_dir).resolve()
            if not abs_dir.is_dir():
                logger.warning("[SkillLoader] 目录不存在: %s", abs_dir)
                continue

            for entry in abs_dir.iterdir():
                entry_path = entry
                if not entry_path.is_dir():
                    continue

                skill_md_path = entry_path / "SKILL.md"
                if not skill_md_path.is_file():
                    continue

                meta = self._parse_frontmatter(str(skill_md_path), str(entry_path))
                if meta:
                    self._skills[meta.name] = meta
                    logger.info("[SkillLoader] 发现 Skill: %s -> %s", meta.name, entry_path)

        logger.info("[SkillLoader] 共发现 %d 个 Skill", len(self._skills))

    @staticmethod
    def _parse_frontmatter(skill_md_path: str, skill_dir: str) -> Optional[SkillMeta]:
        """解析 SKILL.md 的 YAML frontmatter，提取 name 和 description。

        使用简易行级解析，不引入 PyYAML 等外部依赖。
        """
        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.warning("[SkillLoader] 读取失败: %s, %s", skill_md_path, e)
            return None

        match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not match:
            logger.warning("[SkillLoader] 无有效 frontmatter: %s", skill_md_path)
            return None

        frontmatter = match.group(1)
        name = ""
        description = ""
        for line in frontmatter.split("\n"):
            stripped = line.strip()
            if stripped.startswith("name:"):
                name = stripped[len("name:"):].strip()
            elif stripped.startswith("description:"):
                description = stripped[len("description:"):].strip()

        if not name:
            logger.warning("[SkillLoader] frontmatter 缺少 name: %s", skill_md_path)
            return None

        return SkillMeta(name=name, description=description, skill_dir=skill_dir)

    # ------------------------------------------------------------------
    # Level 1：元数据注入 system prompt
    # ------------------------------------------------------------------
    def get_metadata_prompt(self) -> str:
        """生成 Skill 元数据摘要，注入 system prompt（~100 tokens/skill）"""
        if not self._skills:
            return ""

        lines = [
            "【可用技能（Skills）】",
            "以下技能可根据用户需求自动触发，匹配时调用 invoke_skill 工具激活。",
            "",
            "【重要】优先使用技能：当用户需求与某个技能的描述匹配时，"
            "必须优先调用 invoke_skill 工具激活该技能，再按技能指令执行。"
            "不要跳过技能直接使用基础工具完成任务。",
            "",
        ]
        for meta in self._skills.values():
            lines.append(f"- {meta.name}: {meta.description}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Level 2：加载完整指令体
    # ------------------------------------------------------------------
    def load_instructions(self, skill_name: str) -> Optional[str]:
        """加载 SKILL.md 完整指令体（去掉 frontmatter），并追加资源绝对路径信息"""
        meta = self._skills.get(skill_name)
        if not meta:
            logger.warning("[SkillLoader] 未找到 Skill: %s", skill_name)
            return None

        skill_md_path = Path(meta.skill_dir) / "SKILL.md"
        try:
            with open(str(skill_md_path), "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error("[SkillLoader] 读取失败: %s, %s", str(skill_md_path), e)
            return None

        # 去掉 frontmatter，只保留 body
        body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL).strip()

        # 将反引号内的相对路径（references/xxx、scripts/xxx）替换为绝对路径
        body = self._resolve_inline_paths(body, meta.skill_dir)

        # 追加资源路径汇总
        abs_dir = meta.skill_dir.replace("\\", "/")
        paths_section = (
            f"\n\n---\n"
            f"【Skill 资源绝对路径】\n"
            f"- Skill 目录: {abs_dir}\n"
            f"- 参考文档目录: {abs_dir}/references/\n"
            f"- 可执行脚本目录: {abs_dir}/scripts/\n"
            f"- 素材资源目录: {abs_dir}/assets/\n"
            f"\n请使用 read_file 工具读取参考文档，使用 bash 工具执行脚本。"
        )

        return body + paths_section

    # ------------------------------------------------------------------
    # Level 3：按需加载资源
    # ------------------------------------------------------------------
    def resolve_reference(self, skill_name: str, ref_path: str) -> Optional[str]:
        """读取 references/ 目录下的文件内容"""
        meta = self._skills.get(skill_name)
        if not meta:
            return None

        abs_path = Path(meta.skill_dir) / "references" / ref_path
        if not abs_path.is_file():
            logger.warning("[SkillLoader] 参考文件不存在: %s", abs_path)
            return None

        try:
            with open(str(abs_path), "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error("[SkillLoader] 读取参考文件失败: %s, %s", abs_path, e)
            return None

    def get_script_path(self, skill_name: str, script_name: str) -> Optional[str]:
        """返回 scripts/ 目录下脚本的绝对路径（用于 bash 执行）"""
        meta = self._skills.get(skill_name)
        if not meta:
            return None

        abs_path = Path(meta.skill_dir) / "scripts" / script_name
        if not abs_path.is_file():
            logger.warning("[SkillLoader] 脚本不存在: %s", abs_path)
            return None

        return str(abs_path).replace("\\", "/")

    # ------------------------------------------------------------------
    # 关键词匹配：根据任务描述找到最匹配的 Skill
    # ------------------------------------------------------------------

    def match_skills(self, task_text: str, min_score: int = 1) -> List[SkillMeta]:
        """基于关键词重叠评分，返回按匹配度降序的 Skill 列表。

        Args:
            task_text: 子任务描述文本
            min_score: 最低匹配分数阈值（默认 1 分即可）

        Returns:
            匹配的 SkillMeta 列表（按分数降序），空列表表示无匹配
        """
        if not task_text or not self._skills:
            return []

        task_lower = task_text.lower()
        scored: List[tuple] = []

        for meta in self._skills.values():
            score = 0
            # 关键词来自 skill 名称（权重 3）和描述（权重 1）
            name_words = set(re.split(r"[-_\s]+", meta.name.lower()))
            desc_words = set(re.findall(r"[\w一-鿿]+", meta.description.lower()))

            for w in name_words:
                if len(w) >= 2 and w in task_lower:
                    score += 3
            for w in desc_words:
                if len(w) >= 2 and w in task_lower:
                    score += 1

            if score >= min_score:
                scored.append((score, meta))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [meta for _, meta in scored]

    def get_matched_instructions(self, task_text: str, max_skills: int = 2) -> Optional[str]:
        """预匹配 Skill 并返回完整指令文本，用于直接注入 subtask prompt。

        Args:
            task_text: 子任务描述
            max_skills: 最多注入几个匹配 skill

        Returns:
            匹配到的 skill 完整指令文本，无匹配返回 None
        """
        matched = self.match_skills(task_text)
        if not matched:
            return None

        parts = []
        for meta in matched[:max_skills]:
            body = self.load_instructions(meta.name)
            if body:
                parts.append(
                    f"## 已匹配技能: {meta.name}\n"
                    f"说明: {meta.description}\n\n"
                    f"{body}"
                )

        if not parts:
            return None

        return (
            "【技能优先 — 以下技能已匹配当前任务，请直接按指令执行，不要自行设计方案】\n\n"
            + "\n\n---\n\n".join(parts)
        )

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_inline_paths(body: str, skill_dir: str) -> str:
        """将 body 中反引号内的 references/scripts/assets 相对路径替换为绝对路径"""
        abs_dir = skill_dir.replace("\\", "/")

        def _replace_match(m):
            path = m.group(1)
            for prefix in ("references/", "scripts/", "assets/"):
                if path.startswith(prefix):
                    return f"`{abs_dir}/{path}`"
            return m.group(0)

        return re.sub(r"`([^`]+)`", _replace_match, body)


# ==============================================================================
# 模块自测
# ==============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    _PROJECT_ROOT = Path(__file__).resolve().parent.parent
    loader = SkillLoader(skill_dirs=[str(_PROJECT_ROOT / "skill_library" / "skills")])

    print("=" * 60)
    print("Level 1 — 元数据摘要:")
    print("=" * 60)
    print(loader.get_metadata_prompt())

    print("\n" + "=" * 60)
    print("Level 2 — weather-skill 指令体:")
    print("=" * 60)
    instructions = loader.load_instructions("weather-skill")
    print(instructions)

    print("\n" + "=" * 60)
    print("Level 3 — 脚本绝对路径:")
    print("=" * 60)
    print(loader.get_script_path("weather-skill", "weather.py"))

    print("\n" + "=" * 60)
    print("Level 3 — 参考文档内容（前 200 字符）:")
    print("=" * 60)
    ref = loader.resolve_reference("weather-skill", "city-codes.md")
    print(ref[:200] if ref else "(未找到)")
