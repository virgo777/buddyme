import os
import json
import re
import time
import shutil
import asyncio
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from buddyMe.llm_moudle import basic_llm

from buddyMe.initspace import todo_manager
from buddyMe.initspace.skill_loader import SkillLoader

from buddyMe.utils.paths import get_package_dir, get_user_data_dir, get_workspace_dir, resolve_data_dir
from buddyMe.llm_moudle import model_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AgentMain:
    """
    统一多模型 Agent

    功能:
        - 支持 GLM / Ernie / xiaomi / qwen / minimax / deepseek 多模型切换
        - 支持运行时热切换模型 (switch_model)
        - 支持工具调用 (bash, read_file, write_file 等)
        - 支持定时任务和循环任务

    使用:
        agent = AgentMain(model_name="glm")
        result = agent.invoke("帮我查询天气")
        agent.switch_model("deepseek")  # 运行中切换
        result = agent.invoke("写个方案")
    """

    @classmethod
    def supported_models(cls) -> list:
        """返回 model_config 中所有可用模型"""
        return basic_llm.list_models()

    @classmethod
    def _create_client(cls, model_name: str):
        """工厂方法：通过 basic_llm 创建客户端（支持 model_config 中任意模型）"""
        return basic_llm.create_client(model_name)

    def __init__(
        self,
        model_name: str = "glm",
        system_prompt: Optional[str] = None,
        data_dir: Optional[str] = None,
        workspace_dir: Optional[str] = None,
    ):
        """
        初始化 Agent

        Args:
            model_name: 模型名称 ("glm", "ernie", "xiaomi", "qwen", "minimax", "deepseek")
            system_prompt: 自定义系统提示 (可选)
            data_dir: 数据目录。None 时使用 ~/.buddyme/（CLI 模式），
                      传入路径时直接使用该目录（本地开发模式）。
            workspace_dir: 工作空间目录。Agent 的操作范围和文件输出目录。
                           None 时默认为当前工作目录。
        """
        self.model_name = model_name

        _args = model_config.ModelConfig.get_args()

        self.messages: List[Dict[str, Any]] = []
        self._used_tools: List[str] = []
        self._used_skills: List[str] = []
        self.max_steps = 11
        self._max_heartbeat_steps = 10
        self.max_messages_length = 20

        self._context_recent_turns = 3
        self._context_summary_max_chars = 6000

        # 创建主客户端
        self._client = self._create_client(model_name)

        #子任务使用的模型（固定 GLM，不受主模型切换影响）
        self._sub_client = basic_llm.create_client("sub_agent_code_plan" )
        #心跳任务使用的模型（固定 GLM，不受主模型切换影响）
        self._scheduled_sub_client = basic_llm.create_client("sub_agent_code_plan" )

        #todo 未来可扩展为：规划阶段用强模型（glm），执行阶段用快模型（minimax）。

        #获取对应模型的最大max token
        self._agent_max_token = self._client.max_tokens
        #根据模型最大的max token获取子任务最大max token
        self._sub_agent_max_token = self._agent_max_token//4

        # ------------------------------------------------------------------
        # 包目录（只读模板） + 用户数据目录（可写运行时数据）
        # ------------------------------------------------------------------
        self._PACKAGE_DIR = get_package_dir()
        self._USER_DATA_DIR = get_user_data_dir()

        if data_dir:
            self._DATA_DIR = resolve_data_dir(data_dir)
        else:
            self._init_user_workspace()
            self._DATA_DIR = self._USER_DATA_DIR

        self._PROJECT_ROOT = self._DATA_DIR  # 向后兼容别名

        self.SUBTASK_FILE = self._DATA_DIR / "initspace" / "memorys" / "subtask_results.json"

        # ------------------------------------------------------------------
        # 工作空间目录
        # ------------------------------------------------------------------
        if workspace_dir:
            self._WORKSPACE_DIR = Path(workspace_dir).resolve()
        else:
            self._WORKSPACE_DIR = get_workspace_dir()
        self._WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

        # 默认输出目录：跟随工作空间，未指定路径时所有生成文件保存到工作空间
        self._DEFAULT_OUTPUT_DIR = self._WORKSPACE_DIR
        self._written_files: List[str] = []  # 追踪本次任务写入的所有文件路径

        # Token 计数（每次 invoke 重置）
        self._token_in: int = 0
        self._token_out: int = 0

        self._MAX_SUBTASK_RESULT_LEN = self._sub_agent_max_token
        self._MAX_TOOLS_COMPRESS_LEN = _args["MAX_TOOLS_COMPRESS_LEN"]
        self._MAX_SEARCH_CALLS = _args["MAX_SEARCH_CALLS"]

        # 乱码检测正则：日文假名 + Latin-1 补充 + Unicode 替换字符
        self._GARBLED_CHAR_RE = re.compile('[\u3040-\u309f\u30a0-\u30ff\u00c0-\u00ff\ufffd]')


        from buddyMe.anthropic_standard import basic_anthropic_tool
        self._executor = basic_anthropic_tool.ToolExecutor()
        self._register_tools()

        # Skill 动态加载引擎：用户目录优先 + 包内置模板
        user_skills = self._DATA_DIR / "skill_library" / "skills"
        pkg_skills = self._PACKAGE_DIR / "skill_library" / "skills"
        self._skill_loader = SkillLoader(
            skill_dirs=[str(user_skills), str(pkg_skills)]
        )

        # 注册 Skill 激活工具
        from buddyMe.tool_moudle.invoke_skill_tool import InvokeSkillTool
        invoke_skill = InvokeSkillTool(self._skill_loader)
        invoke_skill.set_model_name(self.model_name)
        self._executor.register(invoke_skill)
        logger.info("[Agent] 已注册 invoke_skill 工具")

        # Loop Skill 管理器（首次执行成功后生成确定性 Skill，后续 tick 直接执行）
        from buddyMe.initspace.loop_skill_manager import LoopSkillManager
        self._loop_skill_mgr = LoopSkillManager(
            loop_skills_dir=os.path.join(self._PROJECT_ROOT, "skill_library", "loop_skills")
        )

        # 动态构建 system prompt（依赖 _executor 中的工具 schema + Skill 元数据）
        if system_prompt:
            self.system_prompt = system_prompt
        else:
            self._rebuild_system_prompt()
        logger.info(f"[Agent] system prompt 已构建，内容: {(self.system_prompt)} ")

        #建立和进行用户自进化-----------------------------------------
        from buddyMe.initspace.use_memory import UseMemory
        _brain_path = os.path.join(self._PROJECT_ROOT, "initspace", "brain", "USER.md")
        _conv_log_path = os.path.join(self._PROJECT_ROOT, "initspace", "memorys", "conversation_log.json")
        self.user_memory = UseMemory(_brain_path, conversation_log_path=_conv_log_path, client=self._sub_client)

        #将所有的交互记录进行持久化-----------------------------------------
        from buddyMe.initspace.memorybuild import ConversationLogger
        self.conv_logger = ConversationLogger(os.path.join(self._PROJECT_ROOT, "initspace", "memorys", "conversation_log.json"))

        # 心跳管理器（使用源码目录中的配置）
        from buddyMe.initspace.heartbeat import HeartbeatManager
        self.heartbeat = HeartbeatManager(
            config_path=str(self._PACKAGE_DIR / "initspace" / "memorys" / "heartbeat.json")
        )
        self._heartbeat_running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._last_cmd_should_exit = False

        #内部任务管理器
        self.todo_manager = todo_manager.TodoManager()

        # 命令系统（/help, /model, /api_key 等）
        from buddyMe.cmd_library import create_registry
        self.cmd_registry = create_registry()

    def _rebuild_system_prompt(self):
        """重建 system prompt（工具 schema + Skill 元数据）"""
        from buddyMe.initspace.contextbuild import build_system_prompt
        self.system_prompt = build_system_prompt(
            tool_schemas=self._executor.get_all_schemas(),
            brain_dir="initspace/brain",
            skill_metadata=self._skill_loader.get_metadata_prompt())

    def reload_skills(self):
        """运行时热加载：重新扫描 skill 目录，刷新 system prompt 中的技能列表。"""
        added = self._skill_loader.reload()
        if added > 0:
            self._rebuild_system_prompt()
            logger.info("[Agent] system prompt 已刷新，新增 %d 个 Skill", added)
        return added

    def _register_tools(self):
        """注册默认工具，并设置工具使用的模型名称"""
        try:
            from buddyMe.tool_moudle.bash_tool import (BashTool, ReadFileTool, WriteFileTool, EditFileTool, GrepTool, GlobTool )

            tools = [
                BashTool(), ReadFileTool(), WriteFileTool(), EditFileTool(),
                GrepTool(), GlobTool(),
            ]
            for tool in tools:
                # 为每个工具设置当前 Agent 的模型名称
                tool.set_model_name(self.model_name)
                self._executor.register(tool)
            logger.info(f"[Agent] 已注册 {len(tools)} 个工具，模型: {self.model_name}")
        except ImportError as e:
            logger.warning(f"[Agent] 无法导入工具模块: {e}")

    @staticmethod
    def _format_tool_calls(tool_calls: list) -> dict:
        """将 Anthropic 格式的 tool_use 块转换为 OpenAI 兼容的 assistant 消息"""
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc.get("input", {}), ensure_ascii=False)
                    }
                }
                for tc in tool_calls
            ]
        }

    def register_tool(self, tool: "BaseTool"):
        """
        后注册工具（初始化后手动添加新工具）

        Args:
            tool: BaseTool 实例

        Example:
            from tool_moudle.baidu_search_tool import BaiduSearchTool
            agent = AgentV0(model_name="glm")
            agent.register_tool(BaiduSearchTool())
        """
        tool.set_model_name(self.model_name)
        self._executor.register(tool)
        logger.info(f"[Agent] 后注册工具: {tool.name}")

    def unregister_tool(self, tool_name: str) -> bool:
        """
        注销工具

        Args:
            tool_name: 工具名称

        Returns:
            是否注销成功
        """
        success = self._executor.unregister(tool_name)
        if success:
            logger.info(f"[Agent] 已注销工具: {tool_name}")
        return success

    def call_llm_sync(self, system_prompt: str, user_message: str) -> str:
        """同步调用主模型（用于 loop prompt 增强等一次性场景）。

        Args:
            system_prompt: 系统提示
            user_message: 用户消息

        Returns:
            模型的文本回复
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        try:
            response = asyncio.run(self._client.chat(messages=messages))
            texts = [
                b.get("text", "")
                for b in response.get("content", [])
                if b.get("type") == "text"
            ]
            return "\n".join(texts).strip()
        except Exception as e:
            logger.error(f"[Agent] call_llm_sync 失败: {e}")
            return ""

    def _get_tool_schemas(self) -> List[Dict]:
        """获取已注册工具的 schema 列表（复用已注册的工具实例）"""
        return self._executor.get_all_schemas()

    def _load_sub_agent_prompt(self) -> str:
        """读取 SUB_AGENT.md 并填入动态参数（max_steps, max_output）。"""
        sub_agent_path = os.path.join(self._PROJECT_ROOT, "initspace", "brain", "SUB_AGENT.md")
        content = ""
        if os.path.exists(sub_agent_path):
            with open(sub_agent_path, "r", encoding="utf-8") as f:
                content = f.read()
        return content.format(
            max_steps=self.max_steps,
            max_output=self._sub_agent_max_token,
        )

    def _init_user_workspace(self):
        """首次运行时，将所有数据文件从包目录部署到 ~/.buddyme/"""
        dst = self._USER_DATA_DIR
        src = self._PACKAGE_DIR

        skill_dst = os.path.join(dst, "skill_library", "skills")

        # 快速检查：skill_library 已存在则跳过全量复制
        if os.path.exists(skill_dst) and os.listdir(skill_dst):
            return

        logger.info("[初始化] 首次运行，部署用户数据到 %s", dst)

        # 递归复制 initspace/ 和 skill_library/（不覆盖已有文件）
        for rel in ["initspace", "skill_library"]:
            src_dir = os.path.join(src, rel)
            dst_dir = os.path.join(dst, rel)
            if not os.path.exists(src_dir):
                continue
            self._copy_tree(src_dir, dst_dir)

        logger.info("[初始化] 部署完成")

    @staticmethod
    def _copy_tree(src_dir: str, dst_dir: str):
        """递归复制目录，不覆盖已有文件"""
        os.makedirs(dst_dir, exist_ok=True)
        for item in os.listdir(src_dir):
            s = os.path.join(src_dir, item)
            d = os.path.join(dst_dir, item)
            if os.path.isdir(s):
                AgentMain._copy_tree(s, d)
            elif os.path.isfile(s) and not os.path.exists(d):
                shutil.copy2(s, d)

    def add_message(self, role: str, content: str):
        """添加消息到历史"""
        if len(self.messages) >= self.max_messages_length:
            # 保留 system prompt (index 0) + 最新 N-1 条
            self.messages = [self.messages[0]] + self.messages[-(self.max_messages_length - 1):]

        self.messages.append({"role": role, "content": content})

    def reset(self):
        """重置对话历史"""
        self.messages = []

    def _build_conversation_context(self) -> str:
        """
        构建跨轮对话上下文（两层记忆）：
          1. 摘要记忆：从 memory_summary.md 提取历史摘要（有硬上限）
          2. 工作记忆：self.messages 中最近 N 轮的原文（滑动窗口）

        去重策略：当工作记忆有内容时，摘要只注入当天之前的记录，
        避免当天对话在两层中重复出现。

        Returns:
            拼接好的上下文字符串；无历史时返回空字符串。
        """
        parts: List[str] = []

        # --- 先判断工作记忆是否有内容（决定摘要注入范围）---
        conversation_msgs = [m for m in self.messages if m.get("role") in ("user", "assistant")]
        has_working_memory = len(conversation_msgs) > 0

        # --- 层1：摘要记忆 ---
        summary_path = os.path.join(
            self._PROJECT_ROOT, "initspace", "memorys", "memory_summary.md"
        )
        if os.path.exists(summary_path):
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
                sections = re.split(r"^## ", raw, flags=re.MULTILINE)
                if len(sections) >= 2:
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    summary_parts: List[str] = []
                    total_chars = 0
                    # sections[0] 是标题部分，sections[1:] 是各天摘要
                    for sec in sections[1:]:
                        sec_text = sec.strip()
                        if not sec_text:
                            continue
                        # 去重：有工作记忆时，跳过当天摘要（工作记忆已包含）
                        if has_working_memory and sec_text.startswith(today_str):
                            continue
                        if total_chars + len(sec_text) > self._context_summary_max_chars:
                            break
                        summary_parts.append(f"## {sec_text}")
                        total_chars += len(sec_text)

                    if summary_parts:
                        parts.append("[近期摘要]\n" + "\n".join(summary_parts))
            except Exception as e:
                logger.warning("[上下文] 读取 memory_summary.md 失败: %s", e)

        # --- 层2：工作记忆（最近 N 轮对话原文） ---
        if conversation_msgs:
            recent = conversation_msgs[-(self._context_recent_turns * 2):]
            working_lines: List[str] = []
            for m in recent:
                role_label = "用户" if m["role"] == "user" else "助手"
                content = m.get("content", "")
                if len(content) > 1000:
                    head = content[:600]
                    tail = content[-400:]
                    content = head + "\n...(中间内容已省略)...\n" + tail
                working_lines.append(f"{role_label}: {content}")
            if working_lines:
                parts.append("[最近对话]\n" + "\n".join(working_lines))

        return "\n\n".join(parts) if parts else ""

    def close(self):
        """关闭所有 LLM 客户端，释放连接池"""
        for client_attr in ("_client", "_sub_client", "_scheduled_sub_client"):
            client = getattr(self, client_attr, None)
            if client and hasattr(client, "close"):
                try:
                    client.close()
                except Exception:
                    pass

    def switch_model(self, new_model: str):
        """
        运行时热切换主模型，无需重启 Agent。

        Args:
            new_model: 目标模型名，如 "glm", "deepseek", "qwen" 等

        注意:
            - 仅切换主客户端 (self._client)
            - 子任务/心跳客户端保持不变（固定 GLM）
            - 对话历史 (self.messages) 保持不变
        """
        if new_model == self.model_name:
            logger.info(f"[Agent] 模型未变，跳过切换: {new_model}")
            return

        # 关闭旧客户端
        if self._client and hasattr(self._client, "close"):
            try:
                self._client.close()
            except Exception:
                pass

        # 创建新客户端
        self._client = self._create_client(new_model)
        old_model = self.model_name
        self.model_name = new_model

        # 更新 token 相关配置
        self._agent_max_token = self._client.max_tokens
        self._sub_agent_max_token = self._agent_max_token // 4

        # 通知所有已注册工具更新模型名
        if hasattr(self, "_executor"):
            for tool in self._executor._tools.values():
                if hasattr(tool, "set_model_name"):
                    tool.set_model_name(new_model)

        logger.info(f"[Agent] 模型已切换: {old_model} → {new_model}")

    def invoke(self, user_input: str) -> str:
        """同步运行 Agent，完成后自动关闭连接池"""
        # 命令拦截：以 / 开头的输入不走 LLM
        cmd_result = self.cmd_registry.dispatch(user_input, self)
        if cmd_result is not None:
            self._last_cmd_should_exit = getattr(cmd_result, 'should_exit', False)
            return cmd_result.message

        self._used_tools = []
        self._used_skills = []
        self._written_files = []  # 重置文件追踪列表
        self._token_in = 0
        self._token_out = 0
        start_time = time.time()

        result = asyncio.run(self.run(user_input))

        cost = round(time.time() - start_time, 2)

        # 收集本次任务写入的所有文件路径
        for tool_record in self._used_tools:
            if tool_record.get("tool_name") in ("write_file", "edit_file"):
                file_path = tool_record.get("args", {}).get("path", "")
                if file_path:
                    abs_path = os.path.abspath(file_path)
                    if abs_path not in self._written_files:
                        self._written_files.append(abs_path)

        # 向用户报告生成的文件地址
        if self._written_files:
            file_list = "\n".join(f"  - {p}" for p in self._written_files)
            result += f"\n\n{'=' * 40}\n项目已生成到:\n{file_list}"

        # 汇总 Skill 使用情况
        if self._used_skills:
            skill_summary = ", ".join(self._used_skills)
            logger.info("=" * 60)
            logger.info("[Skill] 本次任务共使用 %d 个技能: %s", len(self._used_skills), skill_summary)
            logger.info("=" * 60)

        self.conv_logger.log(
            query=user_input,
            response=result,
            model=self.model_name,
            tool_calls=self._used_tools,
            extra={
                "execute_cost_time": cost,
                "tool_call_count": len(self._used_tools),
                "used_skills": self._used_skills,
                "subtask_count": len(self._last_episode) if hasattr(self, "_last_episode") else 0,
                "episode": self._last_episode if hasattr(self, "_last_episode") else [],
            }
        )
        # 只关闭本次调用使用的客户端，不影响心跳线程的 _scheduled_sub_client
        for attr in ("_client", "_sub_client"):
            c = getattr(self, attr, None)
            if c and hasattr(c, "close"):
                try:
                    c.close()
                except Exception:
                    pass
        return result

    def _track_usage(self, response: dict):
        """从 LLM 响应中提取 usage 并累加到计数器。

        兼容两种格式：
          OpenAI:    {"prompt_tokens": N, "completion_tokens": N}
          Anthropic: {"input_tokens": N, "output_tokens": N}
        """
        usage = response.get("usage", {})
        self._token_in += usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
        self._token_out += usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)

    def _sanitize_result(self, text: str, max_length: int = 0) -> str:
        """
        清理子任务结果：逐行检测乱码并移除，可选截断。

        Args:
            text: 原始结果文本
            max_length: 最大允许长度，0 表示仅清理乱码不截断
        """
        if not text:
            return text

        # 1. 逐行检测并移除乱码行
        lines = text.split('\n')
        clean_lines = [line for line in lines if not self._is_garbled_line(line)]
        result = '\n'.join(clean_lines)

        # 2. 截断至最大长度（max_length > 0 时生效）
        if max_length > 0 and len(result) > max_length:
            result = result[:max_length] + "\n...(结果过长已截断)"

        return result

    def _is_garbled_line(self, line: str) -> bool:
        """
        检测单行文本是否为乱码。

        判定规则：
        - 包含 Unicode 替换字符 (U+FFFD) → 乱码
        - 乱码指示字符（日文假名、Latin-1 补充等）占比超过 20% → 乱码
        """
        stripped = line.strip()
        if not stripped:
            return False

        # Unicode 替换字符 → 一定是乱码
        if '\ufffd' in stripped:
            return True

        # 统计乱码指示字符数量
        garbled_count = len(self._GARBLED_CHAR_RE.findall(stripped))
        total = len(stripped)

        # 超过 20% 的字符为乱码指示字符 → 判定为乱码行
        return total > 5 and garbled_count / total > 0.2

    def _init_subtask_file(self):
        """每次任务开始前：确保文件不存在（清空旧数据）"""
        if os.path.exists(self.SUBTASK_FILE):
            os.remove(self.SUBTASK_FILE)
            logger.info("[子任务文件] 已清除旧文件")

    def _create_subtask_file(self, plans: list):
        """所有子任务开始前：创建 JSON 文件，初始化状态"""
        total = len(plans)
        data = {}
        for idx, text in enumerate(plans):
            is_first = (idx == 0)
            is_last = (idx == total - 1)
            tags = []
            if is_first:
                tags.append("start_task")
            if is_last or total == 1:
                tags.append("end_task")
            data[text] = {
                "status": "pending",
                "tags": tags,
                "result": ""
            }
        with open(self.SUBTASK_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"[子任务文件] 已创建: {self.SUBTASK_FILE}")

    def _update_subtask_file(self, task_text: str, result: str, is_end_task: bool = False):
        """子任务完成时：截断结果并更新对应任务的状态"""
        # end_task 使用智能体完整 max_tokens，普通子任务使用截断上限
        max_len = self._agent_max_token if is_end_task else self._MAX_SUBTASK_RESULT_LEN
        if len(result) > max_len:
            result = result[:max_len] + "\n...(结果过长已截断)"

        with open(self.SUBTASK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if task_text in data:
            data[task_text]["status"] = "completed"
            data[task_text]["result"] = result
        with open(self.SUBTASK_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _read_completed_results(self) -> str:
        """直接读取已完成子任务的结果（代码读文件，不靠 LLM 调工具）"""
        try:
            with open(self.SUBTASK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            parts = []
            for task, info in data.items():
                if info.get("status") == "completed":
                    parts.append(f"【{task}】\n{info.get('result', '无结果')}")
            return "\n\n".join(parts) if parts else "暂无已完成的结果"
        except Exception:
            return "暂无已完成的结果"

    def _delete_subtask_file(self):
        """所有子任务结束后：删除 JSON 文件"""
        try:
            if os.path.exists(self.SUBTASK_FILE):
                os.remove(self.SUBTASK_FILE)
                logger.info("[子任务文件] 已删除")
        except Exception as e:
            logger.warning(f"[子任务文件] 删除失败: {e}")

    def _is_simple_task(self, user_input: str) -> bool:
        """纯规则判断是否为简单任务，零 LLM 调用"""
        text = user_input.strip()

        COMPLEX_KEYWORDS = [
            "生成", "创建", "写", "制作", "开发", "设计", "实现", "构建",
            "html", "css", "js", "javascript", "python", "vue", "react",
            "页面", "脚本", "程序", "项目", "系统", "前端", "后端",
            "重构", "方案", "架构", "并", "且", "然后",
        ]

        # 明确包含生成/创建关键词 → 复杂
        if any(kw in text.lower() for kw in COMPLEX_KEYWORDS):
            return False

        # 短文本且无复杂关键词 → 简单
        if len(text) < 40:
            return True

        # 中等长度，含组合特征 → 复杂
        if len(text) > 100:
            return False

        # 默认中等长度判断为简单（保守策略，宁可多走完整流程）
        return True

    def _classify_subtask(self, task_text: str) -> str:
        """规则判断子任务类型：research / build / verify"""
        text_lower = task_text.lower()

        VERIFY_KEYWORDS = ["验证", "检查", "测试", "修复", "确认", "[VERIFY]"]
        BUILD_KEYWORDS = [
            "生成", "编写", "创建", "写", "制作", "实现", "开发", "构建",
            "html", "css", "js", "javascript", "python",
            "页面", "脚本", "程序", "文件", "代码", "样式", "交互",
            "添加", "注入", "补充", "填充", "整合",
            "[CREATE]", "[EDIT]",
        ]

        if any(kw in text_lower for kw in VERIFY_KEYWORDS):
            return "verify"
        if any(kw in text_lower for kw in BUILD_KEYWORDS):
            return "build"
        return "research"

    def _refresh_written_files(self):
        """从 _used_tools 中提取已写入的文件路径，实时更新 _written_files"""
        for tool_record in self._used_tools:
            if tool_record.get("tool_name") in ("write_file", "edit_file"):
                file_path = tool_record.get("args", {}).get("path", "")
                if file_path:
                    abs_path = os.path.abspath(file_path)
                    if abs_path not in self._written_files:
                        self._written_files.append(abs_path)

    async def _run_simple(self, user_input: str, conversation_context: str) -> str:
        """简单任务快速通道：单轮 LLM + 工具调用，跳过规划-拆解-合并"""
        logger.info("[短路] 检测到简单任务，跳过规划阶段")

        user_memory_context = self.user_memory.to_prompt()
        full_system = self.system_prompt + "\n\n" + user_memory_context

        # 注入工作空间路径 + 默认输出目录，让工具调用定位准确
        path_hint = (
            f"\n\n【环境信息】\n"
            f"项目工作空间: {self._WORKSPACE_DIR}\n"
            f"默认输出目录: {self._DEFAULT_OUTPUT_DIR}\n"
            f"当前工作目录应基于项目工作空间。\n\n"
            f"【文件输出规则】\n"
            f"当用户没有明确指定文件保存路径时，所有生成的文件必须保存到默认输出目录: {self._DEFAULT_OUTPUT_DIR}\n"
            f"write_file 的 path 参数必须以该目录为基础路径。"
        )

        enriched_input = user_input
        if conversation_context:
            enriched_input = f"{conversation_context}\n\n{'=' * 40}\n\n当前用户需求:\n{user_input}"

        messages = [
            {"role": "system", "content": full_system + path_hint},
            {"role": "user", "content": enriched_input},
        ]

        tools = self._get_tool_schemas()
        full_text = ""
        max_steps = 5  # 简单任务最多5步

        for step in range(1, max_steps + 1):
            try:
                response = await self._client.chat(messages=messages, tools=tools)
                self._track_usage(response)
            except Exception as e:
                logger.error(f"[短路 Step {step}] LLM 调用失败: {e}")
                return full_text or f"[执行失败: {e}]"

            content_blocks = response.get("content", [])
            texts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            tool_calls = [b for b in content_blocks if b.get("type") == "tool_use"]

            assistant_text = "\n".join(texts)
            if assistant_text:
                full_text = assistant_text

            # 无工具调用 → 直接返回
            if not tool_calls:
                logger.info(f"[短路] 完成，共 {step} 步")
                self.add_message("user", user_input)
                self.add_message("assistant", full_text)
                return full_text or "[任务完成]"

            # 有工具调用 → 执行（OpenAI/DeepSeek 兼容格式）
            logger.info(f"[短路 Step {step}] 执行 {len(tool_calls)} 个工具")
            messages.append(self._format_tool_calls(tool_calls))

            for tc in tool_calls:
                tool_name = tc.get("name", "")
                tool_input = tc.get("input", {})
                tool_id = tc.get("id", "")

                logger.info(f"[短路 Step {step}] 工具: {tool_name}, 输入: {str(tool_input)[:200]}")
                self._used_tools.append({"tool_name": tool_name, "args": tool_input})

                result_text = await self._executor.execute(tool_name, tool_input)
                if not result_text:
                    result_text = "[工具无输出]"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": result_text
                })

                # 合并工具结果到最终文本（基于模型 token 预算动态截断）
                _max_simple_result = min(self._agent_max_token // 4, 8000)
                if len(result_text) <= _max_simple_result:
                    full_text = result_text
                else:
                    head = result_text[:_max_simple_result * 2 // 3]
                    tail = result_text[-(_max_simple_result // 3):]
                    full_text = head + "\n...(中间已省略)...\n" + tail

        # 超过最大步数
        logger.info(f"[短路] 达到最大步数 {max_steps}")
        self.add_message("user", user_input)
        self.add_message("assistant", full_text)
        return full_text or "[任务完成]"

    async def run(self, user_input: str) -> str:
        """
        Agent 核心循环（三阶段架构，含简单任务短路）

        阶段0: 简单任务检测 → 走短路（单轮 LLM + 工具调用）
        阶段1: 任务规划（最小 prompt）
        阶段2: 逐个执行子任务（独立 messages，不累积）
        阶段3: 最终合并（完整 system prompt）
        """

        # 每次对话前自动扫描 skill 目录，检测新增技能并刷新 system prompt
        added = self._skill_loader.reload()
        if added > 0:
            self._rebuild_system_prompt()
            logger.info("[Agent] 检测到 %d 个新 Skill，system prompt 已自动刷新", added)

        # ===== 阶段0：构建跨轮对话上下文 =====
        conversation_context = self._build_conversation_context()
        if conversation_context:
            logger.info("[上下文] 已注入对话上下文 (%d 字符)", len(conversation_context))

        # ===== 简单任务短路 =====
        if self._is_simple_task(user_input):
            return await self._run_simple(user_input, conversation_context)

        # ===== 阶段1：任务规划（最小 prompt） =====
        # 规划时也注入对话上下文，让任务分解能感知前文
        enriched_input = user_input
        if conversation_context:
            enriched_input = f"{conversation_context}\n\n{'=' * 40}\n\n当前用户需求:\n{user_input}"
        plans = await todo_manager.plan_task(enriched_input, client=self._client)
        render = self.todo_manager.create_from_plan(plans)
        num_subagent = len(self.todo_manager.items)
        logger.info(f"任务分解为:\n{render}")

        safe_num = max(num_subagent, 1)
        self._MAX_SUBTASK_RESULT_LEN = self._agent_max_token // safe_num
        self._MAX_TOOLS_COMPRESS_LEN = int(self._MAX_SUBTASK_RESULT_LEN * 0.67)

        # ===== 阶段2：逐个执行子任务（独立 messages） =====
        sub_results = []
        self._last_episode = []  # 本次任务的子任务摘要
        total_tasks = len(self.todo_manager.items)
        # 创建子任务 JSON 文件（记录状态和结果）
        if total_tasks > 0:
            self._init_subtask_file()
            self._create_subtask_file(plans)

        if not self.todo_manager.is_empty():
            for i, item in enumerate(self.todo_manager.items):
                    logger.info(self.todo_manager.render())
                    logger.info(f"[子任务 {item['id']}/{total_tasks}] {item['text']}")

                    is_last = (i == total_tasks - 1)
                    is_end_task = is_last or total_tasks == 1

                    # 所有子任务共用的环境信息
                    readonly_warning = (
                        f"\n\n【环境信息】\n"
                        f"项目工作空间: {self._WORKSPACE_DIR}\n"
                        f"默认输出目录: {self._DEFAULT_OUTPUT_DIR}\n"
                        f"使用 grep/glob/read_file 等工具时，path 参数应基于项目工作空间。\n\n"
                        f"【文件输出规则】\n"
                        f"当用户没有明确指定文件保存路径时，所有生成的文件必须保存到默认输出目录: {self._DEFAULT_OUTPUT_DIR}\n"
                        f"write_file 的 path 参数必须以该目录为基础路径。\n\n"
                        "【禁止事项】\n"
                        "严禁使用 write_file 或 edit_file 修改 initspace/memorys/subtask_results.json，"
                        "该文件由系统自动管理，你只能通过 read_file 读取它。违反此规则会导致任务失败。"
                    )

                    # 读取 SUB_AGENT.md 安全规则模板
                    sub_agent_rules = self._load_sub_agent_prompt()

                    # Skill 预匹配：根据任务描述匹配最相关的 Skill，直接注入完整指令
                    matched_instructions = self._skill_loader.get_matched_instructions(
                        item["text"], max_skills=1
                    )
                    skill_metadata = self._skill_loader.get_metadata_prompt()

                    if matched_instructions:
                        skill_prefix = (
                            matched_instructions
                            + "\n\n---\n"
                            + "【技能已预加载】上方已提供完整的技能执行指令，"
                            + "请严格按照指令执行，不要自行设计方案或重新搜索。\n"
                        )
                        logger.info(f"[子任务 {item['id']}] Skill 已预匹配并注入指令")
                    elif skill_metadata:
                        skill_prefix = (
                            "【技能优先规则 — 开始任务前必须执行】\n"
                            "1. 先检查下方技能列表，看是否有匹配当前任务的技能\n"
                            "2. 如有匹配技能，立即调用 invoke_skill 激活，不要自己设计方案\n"
                            "3. 技能提供了最佳实践和专业流程，直接跟进即可\n"
                            "4. 只有在确认无匹配技能时，才自行完成\n\n"
                            + skill_metadata
                            + "\n\n---\n"
                        )
                    else:
                        skill_prefix = ""

                    # 子任务类型分类
                    task_type = self._classify_subtask(item["text"])
                    logger.info(f"[子任务 {item['id']}] 类型: {task_type}")

                    if is_end_task and i > 0:
                        # end_task：验证+修复模式
                        written_files_list = "\n".join(f"  - {f}" for f in self._written_files) or "  (暂无)"
                        system_content = (
                            f"当前子任务: 最终验证与修复\n\n"
                            f"【已生成的文件】\n{written_files_list}\n\n"
                            f"【验证任务】\n"
                            f"1. 用 read_file 读取已生成的文件\n"
                            f"2. 检查结构完整性（标签闭合、语法正确、路径有效）\n"
                            f"3. 发现问题用 edit_file 修复\n"
                            f"4. 无问题则输出文件路径和功能说明\n"
                            f"5. 禁止重新搜索，只基于已生成的内容工作\n"
                            + readonly_warning
                            + "\n\n" + sub_agent_rules
                        )
                    elif total_tasks == 1:
                        # 单任务：同时是 start_task 和 end_task
                        system_content = (
                            f"当前子任务: {item['text']}\n\n"
                            f"【文件构建策略】\n"
                            f"1. 先用 write_file 创建文件骨架（只写基础结构）\n"
                            f"2. 再用 edit_file 逐步填充具体内容\n"
                            f"3. 每次写入控制在合理长度内，避免参数被截断\n"
                            f"4. 写入后不要读回验证（系统已确认写入成功）\n"
                            + readonly_warning
                            + "\n\n" + sub_agent_rules
                        )
                    elif task_type == "build":
                        # build 子任务：允许写文件，增量构建
                        _prev = self._read_completed_results() if i > 0 else ""
                        written_files_list = "\n".join(f"  - {f}" for f in self._written_files) or "  (暂无)"
                        prev_context = ""
                        if _prev and _prev != "暂无已完成的结果":
                            prev_context = f"\n\n【前置子任务结果】\n{_prev[:self._MAX_TOOLS_COMPRESS_LEN]}"
                        system_content = (
                            f"当前子任务: {item['text']}\n\n"
                            f"【文件构建策略】\n"
                            f"1. 先用 write_file 创建文件骨架（只写基础结构，不要一次写完所有内容）\n"
                            f"2. 再用 edit_file 逐步填充具体内容\n"
                            f"3. 每次写入控制在合理长度内，避免参数被截断\n"
                            f"4. 写入后不要读回验证（系统已确认写入成功）\n"
                            f"5. 优先使用前置子任务的已有结果，不重复搜索\n\n"
                            f"【已生成的文件】\n{written_files_list}"
                            + prev_context
                            + readonly_warning
                            + "\n\n" + sub_agent_rules
                        )
                    else:
                        # research 子任务：搜索/读取信息，不写文件
                        _prev = self._read_completed_results() if i > 0 else ""
                        if _prev and _prev != "暂无已完成的结果":
                            system_content = (
                                f"当前子任务: {item['text']}\n\n"
                                f"【严格规则】\n"
                                f"1. 下方已提供前置子任务的结果，优先使用已有信息\n"
                                f"2. 禁止重新搜索前置子任务已经获取过的信息\n"
                                f"3. 只有在需要全新信息时才使用搜索工具\n"
                                f"4. 只输出搜索/整理结果，不要创建文件\n"
                                + readonly_warning
                                + "\n\n" + sub_agent_rules
                            )
                        else:
                            system_content = (
                                f"当前子任务: {item['text']}\n"
                                f"只完成这一个子任务，不要做其他工作。只输出搜索/整理结果，不要创建文件。"
                                + readonly_warning
                                + "\n\n" + sub_agent_rules
                            )

                    # Skill 优先提示前置（已匹配则注入完整指令，未匹配则注入规则+列表）
                    if skill_prefix:
                        system_content = skill_prefix + "\n\n" + system_content

                    # 构建 task_messages
                    # 注入跨轮对话上下文（工作记忆 + 摘要记忆）
                    context_prefix = ""
                    if conversation_context:
                        context_prefix = f"{conversation_context}\n\n{'=' * 40}\n\n"

                    if is_end_task and i > 0:
                        written_files_list = "\n".join(f"  - {f}" for f in self._written_files) or "  (暂无)"
                        user_content = (
                            f"{context_prefix}"
                            f"请验证并修复以下已生成的文件:\n{written_files_list}\n\n"
                            f"原始需求: {user_input}"
                        )
                    elif task_type == "build" and i > 0:
                        _prev = self._read_completed_results()
                        prev_section = ""
                        if _prev and _prev != "暂无已完成的结果":
                            prev_section = (
                                f"\n\n{'=' * 40}\n"
                                f"前置子任务已完成的结果:\n\n{_prev[:self._MAX_TOOLS_COMPRESS_LEN]}\n\n"
                                f"{'=' * 40}\n"
                                f"请基于以上已有信息完成任务。"
                            )
                        user_content = (
                            f"{context_prefix}"
                            f"请完成以下任务: {item['text']}\n\n"
                            f"背景信息: {user_input}"
                            f"{prev_section}"
                        )
                    elif not is_end_task and i > 0:
                        # research 中间子任务
                        _prev = self._read_completed_results()
                        if _prev and _prev != "暂无已完成的结果":
                            user_content = (
                                f"{context_prefix}"
                                f"请完成以下任务: {item['text']}\n\n"
                                f"背景信息: {user_input}\n\n"
                                f"{'=' * 40}\n"
                                f"前置子任务已完成的结果:\n\n{_prev}\n\n"
                                f"{'=' * 40}\n"
                                f"请基于以上已有信息完成任务。只有前置结果中确实缺失且当前任务必需的信息，才允许搜索。"
                            )
                        else:
                            user_content = f"{context_prefix}请完成以下任务: {item['text']}\n\n背景信息: {user_input}"
                    else:
                        user_content = f"{context_prefix}请完成以下任务: {item['text']}\n\n背景信息: {user_input}"

                    task_messages = [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content}
                    ]

                    # 根据子任务类型选择工具集
                    if is_end_task and i > 0:
                        # end_task：验证+修复，允许读取和编辑
                        _allowed = {"read_file", "edit_file", "write_file", "invoke_skill"}
                        file_schemas = [
                            s for s in self._get_tool_schemas()
                            if s.get("function", {}).get("name") in _allowed
                        ]
                        result = await self._run_sub_task(
                            task_messages, item["id"], item["text"],
                            tool_schemas=file_schemas
                        )
                    elif task_type == "build":
                        # build 任务：允许文件操作 + 搜索（可能需要查资料）
                        _allowed = {"read_file", "write_file", "edit_file", "grep",
                                    "glob", "baidu_search", "invoke_skill"}
                        build_schemas = [
                            s for s in self._get_tool_schemas()
                            if s.get("function", {}).get("name") in _allowed
                        ]
                        result = await self._run_sub_task(
                            task_messages, item["id"], item["text"],
                            tool_schemas=build_schemas
                        )
                    else:
                        result = await self._run_sub_task(
                            task_messages, item["id"], item["text"]
                        )
                    # end_task 结果不截断（保留完整信息供合并使用）
                    result = self._sanitize_result(result)
                    sub_results.append({"task": item["text"], "result": result})
                    # end_task 不写入 subtask_results.json（结果可能很长，且已通过 sub_results 传递）
                    if not (is_end_task and i > 0):
                        self._update_subtask_file(item["text"], result, is_end_task=is_end_task)
                    # 实时更新已写入文件列表（供后续子任务和 end_task 使用）
                    self._refresh_written_files()
                    self.todo_manager.mark_current_done()
                    # 记录子任务摘要
                    self._last_episode.append({
                        "task": item["text"],
                        "success": not result.startswith("[子任务执行失败]"),
                        "result_preview": result[:200],
                    })

        # ===== 阶段3：最终合并 =====
        self.add_message("user", user_input)

        # end_task 已产出最终结果，直接拼接返回，跳过合并 LLM 调用
        if total_tasks >= 1 and sub_results:
            last_result = sub_results[-1]["result"]
            if last_result and len(last_result) > 50:
                summary_parts = []
                for r in sub_results[:-1]:
                    summary_parts.append(f"- {r['task']}: 已完成")
                summary = "\n".join(summary_parts)
                final_text = last_result
                if summary:
                    final_text += f"\n\n---\n已完成所有子任务：\n{summary}"
                self.add_message("assistant", final_text)
                logger.info("[合并] 直接使用 end_task 结果（跳过合并 LLM 调用）")
                return final_text

        # 兜底：end_task 无有效结果时，拼接所有子任务结果
        fallback = "\n\n".join([f"**{r['task']}**\n{r['result']}" for r in sub_results])
        self.add_message("assistant", fallback)
        return fallback

    def _compress_tool_results(self, task_messages: list, max_chars: int) -> str:
        """将 task_messages 中的工具结果智能压缩为摘要字符串。

        策略:
            1. 按工具名标注每条结果
            2. 对单条过长结果保留首尾、省略中间（2/3 + 1/3）
            3. 总长度超限时优先保留最近的结果（从头部丢弃早期结果）

        Args:
            task_messages: 子任务消息列表
            max_chars: 压缩后摘要的最大字符数

        Returns:
            压缩后的摘要字符串
        """
        tool_items = [
            (m.get("name", "unknown"), m.get("content", ""))
            for m in task_messages
            if m.get("role") == "tool"
        ]

        if not tool_items:
            return "暂无"

        if max_chars < 100:
            return "暂无(压缩空间不足)"

        n = len(tool_items)
        item_budget = max_chars // max(n, 1)
        formatted_items: List[str] = []

        for tool_name, content in tool_items:
            label = f"[{tool_name}] "
            available = item_budget - len(label)
            if available < 50:
                formatted_items.append(label + "(结果已省略)")
            elif len(content) <= available:
                formatted_items.append(label + content)
            else:
                head = content[:available * 2 // 3]
                tail = content[-(available // 3):]
                formatted_items.append(
                    label + head + "\n...(中间已省略)...\n" + tail
                )

        combined = "\n\n".join(formatted_items)
        if len(combined) <= max_chars:
            return combined

        # 总长超限：从尾部开始保留，丢弃最早的
        selected: List[str] = []
        remaining = max_chars
        for item in reversed(formatted_items):
            needed = len(item) + (2 if selected else 0)
            if needed <= remaining:
                selected.insert(0, item)
                remaining -= needed
            else:
                break

        # 保底：至少保留最后一条结果（强行截断）
        if not selected and formatted_items:
            last = formatted_items[-1]
            if len(last) > max_chars:
                last = last[:max_chars - 3] + "..."
            selected.append(last)
            skipped = n - 1
        else:
            skipped = n - len(selected)

        if skipped > 0:
            selected.insert(0, f"...(已省略前 {skipped} 条早期工具结果)...")

        return "\n\n".join(selected) if selected else "暂无"

    async def _run_sub_task(self, task_messages: list, task_id: int, task_text: str,
                            tool_schemas: list = None) -> str:
        """执行单个子任务，独立消息上下文，不碰 self.messages

        Args:
            task_messages: 子任务的消息列表
            task_id: 子任务编号
            task_text: 子任务描述
            tool_schemas: 可用工具列表，None 则使用全部已注册工具。
                          end_task 时传入过滤掉搜索工具的列表，强制基于已有结果工作。
        """
        _tools = tool_schemas if tool_schemas is not None else self._get_tool_schemas()
        full_text = ""
        collected_tool_results = []  # 累积所有工具执行结果
        search_call_count = 0  # 当前子任务已调用 baidu_search 次数
        _has_search = any(s.get("function", {}).get("name") == "baidu_search" for s in _tools)

        for step in range(1, self.max_steps + 1):
            logger.info(f"[子任务{task_id} Step {step}] 调用模型 ({self.model_name})，搜索工具: {_has_search}")

            try:
                response = await self._client.chat(
                    messages=task_messages,
                    tools=_tools
                )
                self._track_usage(response)
            except Exception as e:
                logger.error(f"[子任务{task_id} Step {step}] LLM 调用失败: {e}")
                # 截断后重试一次
                if len(task_messages) > 3:
                    summary = self._compress_tool_results(task_messages, self._MAX_TOOLS_COMPRESS_LEN)
                    task_messages = [
                        task_messages[0],
                        {"role": "user", "content": f"以下是已获取的信息:\n\n{summary}\n\n请直接基于以上信息完成任务，不要重复任务。"}
                    ]
                    try:
                        response = await self._sub_client.chat(
                            messages=task_messages,
                            tools=_tools
                        )
                        self._track_usage(response)
                    except Exception as e2:
                        logger.error(f"[子任务{task_id} Step {step}] 重试也失败: {e2}")
                        return full_text or "[子任务执行失败]"
                else:
                    return full_text or "[子任务执行失败]"

            stop_reason = response.get("stop_reason", "stop")
            content_blocks = response.get("content", [])

            # 提取内容
            tool_calls = [b for b in content_blocks if b.get("type") == "tool_use"]
            self._used_tools.extend([{"tool_name": tc["name"], "args": tc.get("input", {})} for tc in tool_calls])
            texts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            step_text = "\n".join(texts)
            if step_text:
                full_text += step_text + "\n"  # 累积文本，而非覆盖
                # 限制累积文本长度，避免后续步骤消息过长
    
            # 处理截断：引导 LLM 用 edit_file 分段写入（而非追加上下文续写）
            if stop_reason in ["max_tokens", "length"]:
                # 检查本轮是否已有 write_file 调用
                has_written_file = any(
                    tc.get("name") in ("write_file", "edit_file")
                    for tc in tool_calls
                ) if tool_calls else False

                if has_written_file:
                    # 已写入文件：引导用 edit_file 补充剩余内容
                    logger.warning(f"[子任务{task_id} Step {step}] 输出被截断，引导用 edit_file 继续")
                    task_messages.append({
                        "role": "user",
                        "content": (
                            "你的输出被截断了，文件可能不完整。\n"
                            "请使用 edit_file 将缺失的部分补充到已写入的文件中，而不是重新输出完整内容。\n"
                            "edit_file 的 old_string 填写文件中最后一个完整段落的内容，"
                            "new_string 填写该段落 + 后续要补充的内容。"
                        )
                    })
                else:
                    # 未写过文件：允许一次续写（仅追加文本，不增加工具调用）
                    logger.warning(f"[子任务{task_id} Step {step}] 输出被截断，续写一次")
                    task_messages.append({"role": "assistant", "content": step_text})
                    task_messages.append({
                        "role": "user",
                        "content": "请从上次中断的地方继续输出，不要重复已输出的内容。如果需要写文件，请用 write_file 创建。"
                    })

            # 记录文本回复
            if full_text:
                logger.info(f"[子任务{task_id} Step {step}] 助手: {full_text[:100]}...")

            # 无工具调用则子任务完成
            if not tool_calls:
                logger.info(f"[子任务{task_id}] 完成")
                return full_text or "[子任务完成]"

            # 执行工具
            # 检查搜索工具调用次数上限（仅限 baidu_search）
            search_tools = [tc for tc in tool_calls if tc["name"] == "baidu_search"]
            other_tools = [tc for tc in tool_calls if tc["name"] != "baidu_search"]

            if search_call_count + len(search_tools) > self._MAX_SEARCH_CALLS:
                # 搜索次数超限，只保留还能执行的搜索次数
                remaining = self._MAX_SEARCH_CALLS - search_call_count
                if remaining <= 0:
                    # 搜索次数已满，只执行非搜索工具
                    if other_tools:
                        tool_calls = other_tools
                        logger.info(f"[子任务{task_id}] 搜索次数已满({self._MAX_SEARCH_CALLS}次)，仅执行非搜索工具")
                    else:
                        logger.info(f"[子任务{task_id}] 搜索次数已满({self._MAX_SEARCH_CALLS}次)，强制总结")
                        return full_text.strip() or "[子任务完成]"
                else:
                    # 截断搜索工具，保留非搜索工具
                    tool_calls = search_tools[:remaining] + other_tools
                    logger.warning(f"[子任务{task_id} Step {step}] 搜索调用截断至 {remaining} 个（已达上限）")

            search_count_this_step = sum(1 for tc in tool_calls if tc["name"] == "baidu_search")
            logger.info(f"[子任务{task_id} Step {step}] 执行 {len(tool_calls)} 个工具 (搜索 {search_count_this_step}/{self._MAX_SEARCH_CALLS})")

            task_messages.append(self._format_tool_calls(tool_calls))

            for tc in tool_calls:
                tool_name = tc["name"]
                tool_input = tc.get("input", {})
                tool_id = tc["id"]

                logger.info(f"[子任务{task_id} Step {step}] 工具: {tool_name}, 输入: {tool_input}")

                # 空参数检测：参数被截断导致 JSON 解析失败时给出定向引导
                if not tool_input:
                    if tool_name == "write_file":
                        result_content = (
                            "错误：write_file 的参数因内容过长被截断，JSON 解析失败。\n"
                            "请缩短 content（精简 CSS、去掉注释），确保一次能完整输出 path 和 content。\n"
                            "或者分步写入：先 write_file 写基础结构，再 edit_file 逐步补充内容。"
                        )
                    else:
                        tool_schema = next(
                            (s for s in _tools if s.get("function", {}).get("name") == tool_name), None
                        )
                        params_desc = json.dumps(
                            tool_schema.get("function", {}).get("parameters", {}),
                            ensure_ascii=False
                        ) if tool_schema else "未知"
                        result_content = (
                            f"错误：工具 '{tool_name}' 的参数为空，JSON 可能被截断。"
                            f"\n工具参数格式: {params_desc}"
                        )
                    logger.warning(f"[子任务{task_id} Step {step}] 工具 '{tool_name}' 参数为空，已反馈修复建议")
                else:
                    try:
                        result = await self._executor.execute(tool_name, tool_input)
                        result_content = result or '(无输出)'
                    except Exception as e:
                        result_content = f"执行失败: {type(e).__name__}"

                # write_file 成功后追加提示，防止 LLM 进入"读回验证"死循环
                if tool_name == "write_file" and "成功" in result_content:
                    result_content += "\n\n[系统] 文件已成功写入，当前子任务已完成。请直接输出结果摘要，不要再读取或验证该文件。"
                    logger.info(f"[子任务{task_id}] write_file 成功，已注入完成提示")

                # invoke_skill 调用追踪：显式记录使用了哪个 Skill
                if tool_name == "invoke_skill":
                    invoked_skill = tool_input.get("skill_name", "未知")
                    self._used_skills.append(invoked_skill)
                    logger.info("=" * 60)
                    logger.info("[子任务%d] >>> Skill 已激活: %s", task_id, invoked_skill)
                    logger.info("[子任务%d] >>> Skill 用户问题: %s", task_id, tool_input.get("user_query", ""))
                    logger.info("=" * 60)

                collected_tool_results.append(f"[{tool_name}] {result_content}")
                task_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": result_content
                })
                # 仅计数搜索工具
                if tool_name == "baidu_search":
                    search_call_count += 1

            # 主动截断：把所有工具结果合并进 user 消息，避免丢失信息导致重复搜索
            if len(task_messages) > self.max_messages_length:
                summary = self._compress_tool_results(task_messages, self._MAX_TOOLS_COMPRESS_LEN)
                task_messages = [
                    task_messages[0],
                    {"role": "user", "content": (
                        f"【当前子任务目标】{task_text}\n\n"
                        f"以下是已获取的信息:\n\n{summary}\n\n"
                        f"请直接基于以上信息完成当前子任务「{task_text}」，不要重复搜索已有信息。"
                    )}
                ]
                logger.warning(f"[子任务{task_id} Step {step}] 子任务消息过长，已合并工具结果")

            # 搜索次数达上限：压缩消息，下次 LLM 调用不带 tools，强制直接输出结果
            if search_call_count >= self._MAX_SEARCH_CALLS:
                summary = self._compress_tool_results(task_messages, self._MAX_TOOLS_COMPRESS_LEN)
                task_messages = [
                    {"role": "system", "content": f"你是助手，当前子任务: {task_text}"},
                    {"role": "user", "content": (
                        f"【当前子任务目标】{task_text}\n\n"
                        f"以下是已获取的信息:\n\n{summary}\n\n"
                        f"请直接基于以上信息给出最终结果，禁止再调用搜索工具。"
                    )}
                ]
                logger.info(f"[子任务{task_id}] 搜索次数已达上限({self._MAX_SEARCH_CALLS}次)，强制总结")
                try:
                    response = await self._client.chat(messages=task_messages)
                    self._track_usage(response)
                    texts = [b.get("text", "") for b in response.get("content", []) if b.get("type") == "text"]
                    final = "\n".join(texts)
                    return (full_text + "\n" + final).strip() if full_text else final.strip()
                except Exception as e:
                    logger.error(f"[子任务{task_id}] 强制总结失败: {e}")
                    return full_text.strip() or "[子任务完成]"

        # 达到最大步数：返回累积文本 + 工具结果
        if full_text.strip():
            return full_text.strip()
        if collected_tool_results:
            return "[已收集的信息]\n" + "\n\n".join(collected_tool_results)
        return "[达到最大步数限制]"

    def _build_heartbeat_system_prompt(self, *, no_skill: bool = False) -> str:
        """构建心跳任务专用的精简 system prompt（不含旅游顾问人格）。

        将 HEARTBEAT.md 中的相对路径动态替换为绝对路径（基于 _PROJECT_ROOT），
        解决 PyCharm 运行时 CWD 为 agent_moudle/ 导致路径找不到的问题。

        Args:
            no_skill: True 时不包含 invoke_skill 工具和技能元数据（loop 任务专用）
        """
        # 读取 HEARTBEAT.md
        heartbeat_md_path = os.path.join(self._PROJECT_ROOT, "initspace", "brain", "HEARTBEAT.md")
        heartbeat_content = ""
        if os.path.exists(heartbeat_md_path):
            with open(heartbeat_md_path, "r", encoding="utf-8") as f:
                heartbeat_content = f.read()

        # 将相对路径替换为绝对路径（只替换 HEARTBEAT.md 中的路径行）
        replacements = {
            "initspace/memorys/conversation_log.json": os.path.join(self._PROJECT_ROOT, "initspace", "memorys", "conversation_log.json"),
            "initspace/brain/USER.md": os.path.join(self._PROJECT_ROOT, "initspace", "brain", "USER.md"),
            "initspace/memorys/heartbeat.json": os.path.join(self._PROJECT_ROOT, "initspace", "memorys", "heartbeat.json"),
            "initspace/memorys/memory_summary.md": os.path.join(self._PROJECT_ROOT, "initspace", "memorys", "memory_summary.md"),
        }
        for rel, abs_path in replacements.items():
            heartbeat_content = heartbeat_content.replace(rel, abs_path.replace("\\", "/"))

        # loop 任务不包含 invoke_skill，避免与 prompt 中的直接工具调用冲突
        if no_skill:
            _HEARTBEAT_ALLOWED_TOOLS = {
                "bash", "read_file", "write_file", "edit_file", "grep", "glob", "baidu_search",
            }
        else:
            _HEARTBEAT_ALLOWED_TOOLS = {
                "bash", "read_file", "write_file", "edit_file", "grep", "glob", "invoke_skill", "baidu_search",
            }
        tool_schemas = self._get_tool_schemas()
        tool_desc_parts = []
        for schema in tool_schemas:
            func = schema.get("function", {})
            name = func.get("name", "")
            if name not in _HEARTBEAT_ALLOWED_TOOLS:
                continue
            desc = func.get("description", "")
            params = func.get("parameters", {}).get("properties", {})
            param_str = ", ".join(
                f"{k}: {v.get('description', v.get('type', ''))}"
                for k, v in params.items()
            )
            tool_desc_parts.append(f"- {name}: {desc} 参数: {param_str}")

        tool_desc = "\n".join(tool_desc_parts)

        if no_skill:
            # loop 任务：不注入技能元数据，prompt 已包含完整的脚本路径
            return (
                f"你是一个任务执行助手，严格按照指令中的步骤执行操作。\n\n"
                f"{heartbeat_content}\n\n"
                f"可用工具:\n{tool_desc}\n\n"
                f"规则：\n"
                f"- 按步骤顺序执行，直接使用指令中给出的工具和路径\n"
                f"- 写文件必须使用 write_file 工具，禁止用 bash 重定向（echo >> file、cat > file）\n"
                f"- 追加写入：先用 read_file 读取已有内容，拼接新内容后用 write_file 写回\n"
                f"- 获取动态数据（天气、时间等）用 bash 执行脚本，结果用后续步骤引用"
            )

        # 内置心跳任务（记忆更新、每日摘要）：包含技能元数据和 invoke_skill
        skill_metadata = self._skill_loader.get_metadata_prompt()

        return (
            f"你是一个任务执行助手，按指令完成操作。你可以使用 bash 执行命令、读写文件、搜索内容、调用技能。\n\n"
            f"{heartbeat_content}\n\n"
            f"可用工具:\n{tool_desc}\n\n"
            f"{skill_metadata}\n\n"
            f"规则：直接使用上面给出的绝对路径操作文件。需要执行外部命令时使用 bash。需要特定能力时调用 invoke_skill 激活对应技能。"
        )


    async def run_scheduled_task(self, prompt: str, *, no_skill: bool = False) -> str:
        """
        执行定时任务（使用局部 messages，不污染主对话）。

        流程与 run() 一致：LLM → 工具调用循环 → 返回结果。
        线程安全：使用局部 messages，不影响 self.messages。

        Args:
            prompt: 任务描述（来自 heartbeat.json 的 prompt 字段）
            no_skill: True 时不包含 invoke_skill 和技能元数据（用于 loop 任务，
                      因为 loop 的 prompt 已包含完整的脚本路径，不需要 invoke_skill）

        Returns:
            任务执行结果字符串
        """
        # 局部 messages，不碰 self.messages
        # 心跳任务使用精简 system prompt（仅 HEARTBEAT.md + 工具说明），不加载旅游顾问人格
        heartbeat_prompt = self._build_heartbeat_system_prompt(no_skill=no_skill)

        messages = [
            {"role": "system", "content": heartbeat_prompt},
            {"role": "user", "content": prompt},
        ]

        # loop 任务不包含 invoke_skill，避免与 prompt 中的直接工具调用冲突
        if no_skill:
            _HEARTBEAT_ALLOWED_TOOLS = {
                "bash", "read_file", "write_file", "edit_file", "grep", "glob", "baidu_search",
            }
        else:
            _HEARTBEAT_ALLOWED_TOOLS = {
                "bash", "read_file", "write_file", "edit_file", "grep", "glob", "invoke_skill", "baidu_search",
            }
        heartbeat_tools = [
            s for s in self._get_tool_schemas()
            if s.get("function", {}).get("name") in _HEARTBEAT_ALLOWED_TOOLS
        ]

        for step in range(1, self._max_heartbeat_steps + 1):
            logger.info(f"[ScheduledTask Step {step}] 调用模型 (glm)...")

            response = await self._scheduled_sub_client.chat(
                messages=messages,
                tools=heartbeat_tools
            )
            self._track_usage(response)

            stop_reason = response.get("stop_reason", "stop")
            content_blocks = response.get("content", [])

            tool_calls = [b for b in content_blocks if b.get("type") == "tool_use"]
            texts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            full_text = "\n".join(texts)

            if stop_reason in ("max_tokens", "length"):
                _MAX_CONTINUATION = 3
                for cont_i in range(1, _MAX_CONTINUATION + 1):
                    logger.warning(f"[ScheduledTask Step {step}] 输出被截断，续写第{cont_i}次")
                    messages.append({"role": "assistant", "content": full_text})
                    messages.append({
                        "role": "user",
                        "content": "请从上次中断的地方继续输出，不要重复已输出的内容。"
                    })
                    try:
                        cont_response = await self._scheduled_sub_client.chat(
                            messages=messages,
                            tools=heartbeat_tools
                        )
                        self._track_usage(cont_response)
                    except Exception as e:
                        logger.error(f"[ScheduledTask Step {step}] 续写调用失败: {e}")
                        break
                    cont_stop = cont_response.get("stop_reason", "stop")
                    cont_blocks = cont_response.get("content", [])
                    cont_texts = [b.get("text", "") for b in cont_blocks if b.get("type") == "text"]
                    cont_text = "\n".join(cont_texts)
                    if cont_text:
                        full_text += "\n" + cont_text
                    if cont_stop not in ("max_tokens", "length"):
                        logger.info(f"[ScheduledTask Step {step}] 续写完成")
                        break
                else:
                    logger.warning(f"[ScheduledTask Step {step}] 续写{_MAX_CONTINUATION}次后仍截断")

            if full_text:
                logger.info(f"[ScheduledTask Step {step}] 结果: {full_text[:100]}...")

            # 无工具调用则结束
            if not tool_calls:
                logger.info(f"[ScheduledTask Step {step}] 完成")
                return full_text or "[任务完成]"

            # 工具调用循环
            logger.info(f"[ScheduledTask Step {step}] 执行 {len(tool_calls)} 个工具")

            messages.append(self._format_tool_calls(tool_calls))

            for tc in tool_calls:
                tool_name = tc["name"]
                tool_input = tc.get("input", {})
                tool_id = tc["id"]

                logger.info(f"[ScheduledTask Step {step}] 工具: {tool_name}, 输入: {tool_input}")

                try:
                    result = await self._executor.execute(tool_name, tool_input)
                    result_content = result or "(无输出)"
                except Exception as e:
                    result_content = f"执行失败: {e}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": result_content
                })

        return "[达到最大步数限制]"

    # ------------------------------------------------------------------
    # Loop Skill：首次执行（主 agent + 录制） & 确定性回放
    # ------------------------------------------------------------------

    async def _run_first_execution(
        self, prompt: str
    ) -> tuple:
        """首次执行 loop 任务，使用主智能体并录制工具调用链。

        Returns:
            (result_text, tool_chain, success)
            tool_chain: [{"step": N, "tool": name, "args": dict, "result": str}, ...]
        """
        heartbeat_prompt = self._build_heartbeat_system_prompt(no_skill=True)
        loop_hint = (
            "\n\n[Loop Skill 提示] 这是一个定时循环任务，请严格遵循以下规则：\n"
            "1. 追加写入文件时，必须先用 read_file 读取当前内容，再用 write_file 写入完整内容（旧内容 + 新追加内容）\n"
            "2. 如果是覆盖写入（如生成HTML网页），直接 write_file 即可，不需要先 read_file\n"
            "3. 绝对不要使用 edit_file，只能用 write_file\n"
            "4. 必须先用 bash 获取当前时间: date \"+%Y-%m-%d %H:%M:%S\"\n"
            "5. 写入文件时，时间必须包含时分秒，格式为 YYYY-MM-DD HH:MM:SS\n"
            "6. 如果需要使用技能(skill)，可以调用 invoke_skill 工具\n"
            "7. 不要使用 glob 工具"
        )
        messages = [
            {"role": "system", "content": heartbeat_prompt + loop_hint},
            {"role": "user", "content": prompt},
        ]

        _ALLOWED_TOOLS = {
            "bash", "read_file", "write_file", "grep", "baidu_search",
            "invoke_skill",
        }
        tools = [
            s for s in self._get_tool_schemas()
            if s.get("function", {}).get("name") in _ALLOWED_TOOLS
        ]

        tool_chain = []

        for step in range(1, self._max_heartbeat_steps + 1):
            logger.info("[FirstExec Step %d] 调用主模型...", step)

            try:
                response = await self._client.chat(messages=messages, tools=tools)
                self._track_usage(response)
            except Exception as e:
                logger.error("[FirstExec] 模型调用失败: %s", e)
                return ("", tool_chain, False)

            stop_reason = response.get("stop_reason", "stop")
            content_blocks = response.get("content", [])
            tool_calls = [b for b in content_blocks if b.get("type") == "tool_use"]
            texts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            full_text = "\n".join(texts)

            if full_text:
                logger.info("[FirstExec Step %d] 文本: %s", step, full_text[:100])

            if not tool_calls:
                logger.info("[FirstExec Step %d] 无工具调用，完成", step)
                return (full_text or "[任务完成]", tool_chain, bool(tool_chain))

            logger.info("[FirstExec Step %d] 执行 %d 个工具", step, len(tool_calls))
            messages.append(self._format_tool_calls(tool_calls))

            for tc in tool_calls:
                tool_name = tc["name"]
                tool_input = tc.get("input", {})
                tool_id = tc["id"]

                logger.info("[FirstExec Step %d] 工具: %s", step, tool_name)

                try:
                    result = await self._executor.execute(tool_name, tool_input)
                    result_content = result or "(无输出)"
                except Exception as e:
                    result_content = f"执行失败: {e}"

                # 录制到工具链（保存完整结果，用于后续自动检测模板变量）
                tool_chain.append({
                    "step": step,
                    "tool": tool_name,
                    "args": dict(tool_input),
                    "result": result_content,
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": result_content,
                })

        return ("[达到最大步数限制]", tool_chain, bool(tool_chain))

    async def _execute_loop_skill(self, task_id: str) -> str:
        """确定性执行 Loop Skill，不经过 LLM。"""
        return await self._loop_skill_mgr.execute_skill(self._executor, task_id)

    # ------------------------------------------------------------------
    # 心跳调度（Agent-centric 定时任务）
    # ------------------------------------------------------------------

    @staticmethod
    def _read_file_tail(file_path: str, max_chars: int = 40960) -> str:
        """读取文件最后 max_chars 个字符（用于预注入 prompt，避免 LLM 浪费步骤读大文件）。"""
        try:
            file_size = os.path.getsize(file_path)
            with open(file_path, "r", encoding="utf-8") as f:
                if file_size > max_chars:
                    f.seek(file_size - max_chars)
                    f.readline()  # 跳过可能截断的第一行
                    return f.read()
                return f.read()
        except Exception:
            return ""

    @staticmethod
    def _extract_recent_conversations(log_path: str, max_chars: int = 8192) -> str:
        """
        解析 conversation_log.json，按日期从新到旧提取对话记录。
        优先注入最新日期的对话，而非文件尾部字节，避免漏掉中间日期。

        Args:
            log_path: conversation_log.json 的绝对路径
            max_chars: 最大注入字符数

        Returns:
            按日期排列的对话文本（最新在前）
        """
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return ""

            # 日期从新到旧排列
            dates = sorted(data.keys(), reverse=True)

            parts = []
            total_len = 0
            for date in dates:
                entries = data[date]
                date_block = f"## {date}\n"
                for entry in entries:
                    # 每条记录取关键字段，控制体积
                    query = entry.get("query", "")
                    response = entry.get("response", "")
                    facts = entry.get("facts", {})
                    model = entry.get("model", "")
                    time_str = entry.get("time", "")
                    # 优先使用结构化 facts，其次使用 response_summary，兜底 response
                    if facts:
                        resp_short = json.dumps(facts, ensure_ascii=False)[:300]
                    else:
                        resp_summary = entry.get("response_summary", response)
                        resp_short = resp_summary[:300] + "..." if len(resp_summary) > 300 else resp_summary
                    line = f"- [{time_str}] ({model}) Q: {query}\n  A: {resp_short}\n"
                    # 单条超出剩余预算则跳过该日期后续条目
                    if total_len + len(date_block) + len(line) > max_chars and parts:
                        break
                    date_block += line

                if total_len + len(date_block) > max_chars and parts:
                    break
                parts.append(date_block)
                total_len += len(date_block)

            return "\n".join(parts)
        except Exception:
            return ""

    def _extract_missing_dates_conversations(self, log_path: str, summary_path: str, max_chars: int = 30000) -> str:
        """为 daily_summary 提取缺失日期的对话记录。

        读取已有 memory_summary.md 中的日期，只提取 conversation_log.json 中
        尚未有摘要的日期的对话，避免重复处理已有摘要的日期。

        Args:
            log_path: conversation_log.json 路径
            summary_path: memory_summary.md 路径
            max_chars: 最大注入字符数

        Returns:
            缺失日期的对话文本（从新到旧排列）
        """
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return ""

            # 解析已有摘要中的日期（匹配 "## YYYY-MM-DD" 格式）
            existing_dates = set()
            try:
                with open(summary_path, "r", encoding="utf-8") as sf:
                    for line in sf:
                        m = re.match(r"^## (\d{4}-\d{2}-\d{2})", line)
                        if m:
                            existing_dates.add(m.group(1))
            except FileNotFoundError:
                pass

            # 只提取缺失日期（从新到旧），且限制在近 5 天内
            from datetime import timedelta
            cutoff = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
            all_dates = sorted(data.keys(), reverse=True)
            missing_dates = [d for d in all_dates if d not in existing_dates and d >= cutoff]

            parts = []
            total_len = 0
            max_entries_per_date = 15
            for date in missing_dates:
                entries = data[date][:max_entries_per_date]
                date_block = f"## {date}\n"
                for entry in entries:
                    query = entry.get("query", "")
                    response = entry.get("response", "")
                    facts = entry.get("facts", {})
                    model = entry.get("model", "")
                    time_str = entry.get("time", "")
                    if facts:
                        resp_short = json.dumps(facts, ensure_ascii=False)[:300]
                    else:
                        resp_summary = entry.get("response_summary", response)
                        resp_short = resp_summary[:300] + "..." if len(resp_summary) > 300 else resp_summary
                    date_block += f"- [{time_str}] ({model}) Q: {query}\n  A: {resp_short}\n"

                if total_len + len(date_block) > max_chars:
                    break
                parts.append(date_block)
                total_len += len(date_block)

            return "\n".join(parts)
        except Exception:
            return ""

    def tick(self):
        """
        心跳入口：读配置 → 判断时段 → 遍历任务 → 执行 → 更新状态 → 记录日志。

        由 start_heartbeat() 的后台线程周期性调用。
        """
        data = self.heartbeat._load_config()
        config = data.get("config", {})
        tasks = data.get("tasks", [])
        self.heartbeat._config = config

        # 不在活跃时段，跳过
        if not self.heartbeat._is_in_active_hours():
            return

        for task in tasks:
            if not self.heartbeat._should_run(task):
                continue

            task_id = task.get("id", "unknown")
            task_name = task.get("name", "未命名")
            prompt = task.get("prompt", "")

            # loop 任务（ID 以 loop_ 开头）的 prompt 已由主模型增强为结构化指令，
            # 直接使用，不注入对话记录等无关内容，避免干扰子智能体执行。
            is_loop_task = task_id.startswith("loop_")

            if not is_loop_task:
                # 预读 conversation_log.json，按日期从新到旧提取对话，注入 prompt
                log_path = os.path.join(self._PROJECT_ROOT, "initspace", "memorys", "conversation_log.json")
                if task_id == "daily_summary":
                    summary_path = os.path.join(self._PROJECT_ROOT, "initspace", "memorys", "memory_summary.md")
                    recent_convs = self._extract_missing_dates_conversations(log_path, summary_path, max_chars=30000)
                else:
                    recent_convs = self._extract_recent_conversations(log_path, max_chars=8192)

                prompt_parts = [prompt]

                # 根据任务类型注入对应的文件内容
                if task_id == "memory_update":
                    user_md_path = os.path.join(self._PROJECT_ROOT, "initspace", "brain", "USER.md")
                    user_md_content = self._read_file_tail(user_md_path, max_chars=8192)
                    if user_md_content:
                        prompt_parts.append(
                            f"以下是当前 USER.md 原有内容（保留标签结构，在此基础上更新）:\n"
                            f"---\n{user_md_content}\n---"
                        )
                elif task_id == "daily_summary":
                    summary_path = os.path.join(self._PROJECT_ROOT, "initspace", "memorys", "memory_summary.md")
                    summary_content = self._read_file_tail(summary_path, max_chars=8192)
                    if summary_content:
                        prompt_parts.append(
                            f"以下是当前 memory_summary.md 原有内容（已有日期的摘要保持不变，只补充缺失日期）:\n"
                            f"---\n{summary_content}\n---"
                        )

                if recent_convs:
                    prompt_parts.append(
                        f"以下是对话记录（按日期从新到旧排列，优先更新最新内容）:\n"
                        f"---\n{recent_convs}\n---"
                    )
                prompt = "\n\n".join(prompt_parts)

            logger.info(f"[Heartbeat] 开始执行任务: {task_name} ({task_id})")
            start_time = time.time()
            task_timeout = self.heartbeat._get_timeout(task)

            try:
                async def _run_with_timeout():
                    if is_loop_task and self._loop_skill_mgr.has_skill(task_id):
                        return await self._execute_loop_skill(task_id)
                    elif is_loop_task:
                        return await self.run_scheduled_task(prompt, no_skill=True)
                    else:
                        return await self.run_scheduled_task(prompt, no_skill=False)

                result = asyncio.run(
                    asyncio.wait_for(_run_with_timeout(), timeout=task_timeout)
                )
                duration = round(time.time() - start_time, 2)
                logger.info(f"[Heartbeat] 任务完成: {task_name}, 耗时 {duration}s")
            except asyncio.TimeoutError:
                duration = round(time.time() - start_time, 2)
                logger.error(
                    f"[Heartbeat] 任务超时: {task_name}, {duration}s > {task_timeout}s"
                )
                result = None
            except Exception as e:
                duration = round(time.time() - start_time, 2)
                logger.error(f"[Heartbeat] 任务失败: {task_name}, 错误: {e}")
                result = None

            # 更新 last_run（重新加载最新数据，避免覆盖其他线程新增的任务）
            now_iso = datetime.now().isoformat()
            with self.heartbeat._lock:
                fresh_data = self.heartbeat._load_config()
                for t in fresh_data.get("tasks", []):
                    if t.get("id") == task_id:
                        t["last_run"] = now_iso
                        break
                self.heartbeat._save_config(fresh_data)

    def start_heartbeat(self):
        """
        启动心跳后台线程。

        按 config.interval_minutes 间隔周期性调用 tick()。
        与主线程交互输入并行运行。
        """
        if self._heartbeat_running:
            logger.warning("[Heartbeat] 心跳已在运行")
            return

        self._heartbeat_running = True

        def _heartbeat_loop():
            logger.info("[Heartbeat] 心跳线程已启动")
            while self._heartbeat_running:
                try:
                    self.tick()
                except Exception as e:
                    logger.error(f"[Heartbeat] tick 异常: {e}")

                # 固定 60 秒轮询，tick() 内部按各任务的 interval_minutes 判断是否执行
                for _ in range(60):
                    if not self._heartbeat_running:
                        break
                    time.sleep(1)

            logger.info("[Heartbeat] 心跳线程已停止")

        self._heartbeat_thread = threading.Thread(
            target=_heartbeat_loop,
            daemon=True,
            name="heartbeat-thread"
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self):
        """停止心跳后台线程。"""
        self._heartbeat_running = False
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=5)
            logger.info("[Heartbeat] 心跳线程已关闭")



# ==============================================================================
# 主程序
# ==============================================================================

if __name__ == '__main__':

    print("=" * 60)
    print("Agent — 多模型智能体 + Skill")
    print("输入 /help 查看可用命令")
    print("=" * 60)

    model_name = "glm"

    agent = AgentMain(model_name=model_name)
    from buddyMe.tool_moudle.baidu_search_tool import BaiduSearchTool
    agent.register_tool(BaiduSearchTool())
    agent.start_heartbeat()

    while True:
        inp = input("query: ")
        reply = agent.invoke(inp)
        if reply:
            print(reply)
