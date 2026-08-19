# LLM-backed task planner: splits a goal into ordered steps.

"""LLM-backed task planner: splits a goal into ordered steps."""

from typing import Dict, List, Optional


async def plan_task(user_input: str, client, skill_metadata: str = "") -> list:
    """
    单独调用一次 LLM，仅用于生成任务计划。
    返回步骤文本列表，如 ["创建项目结构", "编写入口文件", ...]
    client: GLMClient 实例
    skill_metadata: 可用的技能元数据摘要（Level 1），用于引导任务分解参考已有技能
    """
    skill_section = ""
    if skill_metadata:
        skill_section = f"""
可用技能参考（分解任务时优先对齐已有技能，能匹配到技能的步骤用 [SKILL:技能名] 标注）：
{skill_metadata}
"""

    plan_prompt = f"""分析以下用户需求，按文件操作粒度分解为执行步骤。
{skill_section}
规则：
- 每个步骤必须对应一个具体的操作类型，用标签标注：
  [SEARCH] 搜索/查找外部信息
  [CREATE] 创建新文件（骨架/初始版本）
  [EDIT] 编辑已有文件（填充内容、添加样式、添加交互）
  [VERIFY] 读取文件并验证完整性、修复问题
  [SKILL:技能名] 该步骤可由指定技能完成（与其他标签可组合，如 [CREATE][SKILL:frontend-design]）
- 如果某个步骤能匹配到上方「可用技能参考」中的技能，必须用 [SKILL:技能名] 标注
- 代码生成类任务按"骨架→填充→验证"顺序拆分，每个步骤控制在合理输出长度内
- 最多 8 个步骤，简单任务返回原句不分解
- 步骤之间不要有内容重叠，每个步骤处理不同的子目标
- 只输出步骤列表，每行一个步骤，不要编号，不要额外解释

示例：

用户需求：帮我写一个 Python 脚本计算斐波那契数列
输出：
[CREATE] 创建斐波那契计算脚本文件，包含函数定义和基本结构
[EDIT] 向脚本中补充用户输入和输出逻辑
[VERIFY] 读取脚本文件，检查语法和逻辑正确性

用户需求：今天天气怎么样
输出：
今天天气怎么样

用户需求：设计一个响应式着陆页
输出：
[CREATE][SKILL:frontend-design] 使用前端设计技能创建响应式着陆页 HTML 骨架和样式
[EDIT][SKILL:frontend-design] 添加交互动效和响应式适配
[VERIFY] 读取最终文件，检查完整性和跨端兼容性

现在请分解以下用户需求：
{user_input}
"""
    try:
        messages = [
            {"role": "system", "content": "你是一个务实的任务分解助手。"},
            {"role": "user", "content": plan_prompt}
        ]

        response = await client.chat(messages=messages)
        # 提取所有 type 为 "text" 的内容块并拼接
        texts = [b["text"] for b in response["content"] if b["type"] == "text"]
        plan_text = "".join(texts).strip()
    except Exception:
        # 调用失败时降级为只包含原任务
        return [user_input]

    # 解析：按行分割，过滤空行，去除可能的编号前缀（如 "1. "、"- " 等）
    steps = []
    for line in plan_text.splitlines():
        line = line.strip()
        if not line:
            continue
        # 去除常见编号前缀
        if line[0].isdigit() and len(line) > 2 and line[1] in ".、) ":
            parts = line.split(maxsplit=1)
            if len(parts) > 1:
                line = parts[1]
        elif line[0] in "-*•▪▫":
            line = line[1:].strip()
        steps.append(line)

    return steps if steps else [user_input]


class TodoManager:
    """智能体内部任务管理器 —— 对大语言模型不可见，不对外暴露为工具"""

    def __init__(self):
        # 待办任务列表，每个任务以字典形式存储（包含id、text、status）
        self.items: List[Dict] = []
        # 内部计数器：追踪距离上次任务状态更新已过去多少轮对话
        self._rounds_since_update: int = 0

    def create_from_plan(self, plan: List[str]) -> str:
        """
        根据大模型生成的任务计划列表初始化待办清单

        参数:
            plan: 字符串列表，每个元素是一个具体的任务步骤描述

        返回:
            渲染后的任务清单文本，可直接注入到智能体上下文中
        """
        # 将计划列表转换为标准化的待办字典列表，初始状态全部设为 pending（待处理）
        self.items = [
            {"id": i + 1, "text": text, "status": "pending"}
            for i, text in enumerate(plan)
        ]
        # 如果待办列表不为空，自动将第一个任务状态设为 in_progress（进行中）
        if self.items:
            self.items[0]["status"] = "in_progress"

        # 重置“未更新轮数”计数器
        self._rounds_since_update = 0
        # 返回渲染好的任务清单
        return self.render()

    def mark_current_done(self) -> Optional[Dict]:
        """
        将当前进行中的任务标记为已完成，并自动激活下一个待办任务

        返回:
            新激活的下一个任务字典；如果没有剩余任务则返回 None
        """
        # 找到当前状态为 in_progress 的任务
        current = self._get_in_progress()
        if current:
            # 将其状态更新为 completed（已完成）
            current["status"] = "completed"
        # 遍历列表，找到第一个状态为 pending 的任务
        for item in self.items:
            if item["status"] == "pending":
                # 将其激活为新的 in_progress 任务
                item["status"] = "in_progress"
                # 重置“未更新轮数”计数器
                self._rounds_since_update = 0
                # 返回新激活的任务
                return item
        # 如果没有找到下一个任务，重置计数器并返回 None（表示全部完成）
        self._rounds_since_update = 0
        return None

    def is_empty(self) -> bool:
        """检查待办清单是否为空（尚未初始化任何任务）"""
        return len(self.items) == 0

    def render(self) -> str:
        """
        将当前待办清单渲染为可读的文本格式，用于注入到大模型上下文中

        返回:
            格式化的任务清单字符串
        """
        if not self.items:
            return ""

        # 定义状态到Emoji图标的映射
        status_map = {"pending": "⬜", "in_progress": "🔄", "completed": "✅"}
        # 初始化渲染行列表，以标题开头
        lines = ["\n## 当前任务计划"]
        # 遍历每个待办项，将其转换为带图标的文本行
        for item in self.items:
            icon = status_map.get(item["status"], "⬜")
            lines.append(f"  {icon} [{item['id']}] {item['text']} ({item['status']})")

        # 计算并添加总体进度条
        completed = sum(1 for i in self.items if i["status"] == "completed")
        lines.append(f"  进度: {completed}/{len(self.items)}")
        # 将所有行拼接为一个字符串返回
        return "\n".join(lines)

    def _get_in_progress(self) -> Optional[Dict]:
        """
        内部辅助方法：查找当前状态为 in_progress（进行中）的任务项

        返回:
            找到的任务字典；如果未找到则返回 None
        """
        for item in self.items:
            if item["status"] == "in_progress":
                return item
        return None
