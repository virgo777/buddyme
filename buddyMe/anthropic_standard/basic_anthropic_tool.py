import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable, Union

logger = logging.getLogger(__name__)

class BaseTool(ABC):
    """
    工具抽象基类

    所有工具必须实现以下属性：
    - name: str - 工具名称（用于 tool_call 识别）
    - description: str - 工具描述（供大模型理解何时使用）
    - parameters: dict - JSON Schema 格式的参数定义

    所有工具必须实现 execute 方法
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any]
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self._model_name: str = "glm"  # 默认模型名称，可被 Agent 覆盖

    def set_model_name(self, model_name: str) -> "BaseTool":
        """
        设置工具使用的模型名称

        Args:
            model_name: 模型名称 (如 "glm", "ernie")

        Returns:
            self: 返回自身以支持链式调用
        """
        self._model_name = model_name
        return self

    @property
    def model_name(self) -> str:
        """获取当前模型名称"""
        return self._model_name

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """
        执行工具逻辑

        Args:
            **kwargs: 工具参数，由大模型根据 parameters schema 生成

        Returns:
            str: 执行结果文本，将作为 tool_result 返回给大模型
        """
        pass

    def get_schema(self) -> Dict[str, Any]:
        """
        获取工具的 JSON Schema 定义

        Returns:
            dict: 符合 OpenAI Tool Calling 协议的工具定义
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name})>"

class BaseToolExecutor(ABC):
    """工具执行器抽象基类"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    @abstractmethod
    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """执行工具并返回结果"""
        pass

    def register(self, tool: BaseTool):
        """注册工具

        Args:
            tool: BaseTool 实例
        """
        self._tools[tool.name] = tool

    def unregister(self, tool_name: str) -> bool:
        """注销工具"""
        if tool_name in self._tools:
            del self._tools[tool_name]
            return True
        return False

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """获取工具实例"""
        return self._tools.get(tool_name)

    def list_tools(self) -> List[str]:
        """列出已注册的工具名称"""
        return list(self._tools.keys())

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的 schema 列表"""
        return [tool.get_schema() for tool in self._tools.values()]

class ToolExecutor(BaseToolExecutor):
    """标准工具执行器实现"""

    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        if tool_name not in self._tools:
            return f"错误：未知工具 '{tool_name}'，可用: {list(self._tools.keys())}"

        try:
            tool = self._tools[tool_name]
            result = await tool.execute(**tool_input)
            return str(result) if result is not None else "执行完成"
        except TypeError as e:
            return f"参数错误: {e}"
        except Exception as e:
            return f"执行失败: {e}"

# 为了兼容旧代码，也导出 StandardToolExecutor
StandardToolExecutor = ToolExecutor
