#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 客户端通用 SDK 核心模块
功能：提供抽象的大模型客户端接口 + OpenAI 兼容 API 实现
支持：消息格式转换、异步 HTTP 请求、响应标准化解析、工具调用、连接池管理
"""
import random
import time
# ===================== 导入依赖模块 =====================
# 抽象基类，用于定义接口规范
from abc import ABC, abstractmethod
# 类型注解，提升代码可读性和类型检查
from typing import List, Dict, Any, Optional, Union
# JSON 序列化/反序列化
import json
# 异步 HTTP 客户端（高性能，支持连接池）
import httpx
# 异步 I/O 框架
import asyncio
# 系统操作
import os
# 日志模块
import logging


# ===================== 日志初始化 =====================
# 获取当前模块的日志实例，统一日志管理
logger = logging.getLogger(__name__)

# ===================== 核心工具函数 =====================
def convert_to_sdk_format(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    将通用标准消息格式 转换为 SDK 内部兼容格式
    核心作用：统一消息结构，适配 OpenAI 系列模型的 API 要求

    处理逻辑：
    1. 收集所有 system 角色消息，统一放置在对话开头
    2. 标准化 assistant 消息的 tool_calls 结构
    3. 过滤无效空消息，保证格式合规

    Args:
        messages: 输入的标准消息列表，格式: [{"role": "xxx", "content": "xxx"}, ...]

    Returns:
        List[Dict[str, Any]]: 转换后的 SDK 兼容消息列表
    """
    # 存储最终转换结果
    result = []
    # 临时缓存所有 system 角色消息
    system_messages = []

    # 遍历每一条原始消息
    for msg in messages:
        # 获取消息角色，默认 user
        role = msg.get("role", "user")

        # 1. 收集 system 消息，暂不加入结果
        if role == "system":
            system_messages.append(msg)
            continue

        # 2. 遇到非 system 消息时，先将缓存的 system 消息加入结果
        if system_messages:
            result.extend(system_messages)
            system_messages = []

        # 3. 处理 assistant 角色消息（重点处理工具调用）
        if role == "assistant":
            tool_calls = msg.get("tool_calls", [])
            content = msg.get("content", "")

            if tool_calls:
                # 存在工具调用：保留 tool_calls，content 为空（OpenAI 规范）
                result.append({
                    "role": "assistant",
                    "content": content if content else None,
                    "tool_calls": tool_calls
                })
            elif content:
                # 纯文本消息：直接保留
                result.append(msg)
            else:
                # 空消息：直接保留
                result.append(msg)
        # 4. 其他角色（user/tool）：直接保留
        else:
            result.append(msg)

    # 最后将剩余的 system 消息加入结果（兜底处理）
    if system_messages:
        result.extend(system_messages)

    return result

# ===================== 抽象基类：LLM 客户端接口 =====================
class BaseLLMClient(ABC):
    """
    LLM 客户端 抽象基类（接口定义）
    所有大模型客户端（GLM/DeepSeek/Qwen 等）必须继承并实现此类
    作用：统一接口规范，屏蔽不同模型 API 的差异

    统一响应格式（行业标准）：
    {
        "content": [
            {"type": "text", "text": "回复文本"},
            {"type": "tool_use", "id": "工具ID", "name": "工具名", "input": 参数字典}
        ],
        "stop_reason": "stop/tool_use/max_tokens",  # 停止原因
        "usage": {"prompt_tokens": 输入token, "completion_tokens": 输出token, "total_tokens": 总token}
    }
    """

    def __init__(self, model_name: str):
        """
        初始化基类
        Args:
            model_name: 模型名称（如 glm-4、gpt-4o）
        """
        self.model_name = model_name

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 1.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        【抽象方法】异步发送聊天请求
        所有子类必须实现此方法，用于和大模型交互

        Args:
            messages: 对话消息列表（标准格式）
            tools: 工具定义列表（可选，用于函数调用）
            temperature: 采样温度（0=确定性，1=随机性）
            **kwargs: 扩展参数

        Returns:
            标准化的响应字典
        """
        pass

    @abstractmethod
    def close(self):
        """【抽象方法】关闭客户端，释放网络资源"""
        pass

    def build_tool_result_message(
        self,
        tool_call_id: str,
        tool_name: str,
        result: Union[str, Dict]
    ) -> Dict[str, Any]:
        """
        构建【工具执行结果】消息
        用于工具调用后，将结果回传给大模型的第二轮对话

        Args:
            tool_call_id: 模型返回的工具调用 ID
            tool_name: 工具名称
            result: 工具执行结果（字符串/字典）

        Returns:
            标准格式的工具结果消息
        """
        # 字典类型结果转为 JSON 字符串
        content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content
        }

# ===================== 实现类：OpenAI 兼容 API 客户端 =====================
from buddyMe.llm_moudle import model_config
class OpenAICompatibleClient(BaseLLMClient):
    """
    OpenAI 兼容 API 客户端（实现类）
    适配所有遵循 OpenAI API 规范的模型（GLM/DeepSeek/Qwen/Ollama 等）
    核心特性：
    1. 异步 HTTP 请求 + 连接池（高性能、高并发）
    2. 自动事件循环检测（避免异步上下文错误）
    3. 统一响应解析（将 OpenAI 格式转为标准格式）
    4. 完善的异常处理
    """

    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: int = 81920,
    ):
        """
        初始化 OpenAI 兼容客户端
        Args:
            model_name: 模型名称
            api_key: API 密钥
            base_url: API 基础地址
            max_tokens: 最大生成 token 数
        """
        # 调用父类构造方法
        super().__init__(model_name)
        # 模型配置参数
        self.max_tokens = max_tokens
        self.model = model_config.ModelConfig.get_api_model(model_name)
        self.api_key = model_config.ModelConfig.get_api_key(model_name) if api_key is None else api_key
        self.base_url = model_config.ModelConfig.get_base_url(model_name) if base_url is None else base_url

        # 异步 HTTP 客户端（懒加载，使用时创建）
        self._client: Optional[httpx.AsyncClient] = None
        # 记录客户端绑定的事件循环 ID（解决多事件循环冲突）
        self._client_loop_id: Optional[int] = None

    def _get_default_timeout(self) -> float:
        """
        私有方法：获取默认超时时间
        子类可重写此方法自定义超时
        """
        return 1080.0

    async def _get_client(self) -> httpx.AsyncClient:
        """
        私有方法：获取异步 HTTP 客户端（核心：连接池复用 + 事件循环检测）
        懒加载模式：第一次调用时创建客户端，后续复用
        """
        # 获取当前运行的异步事件循环
        current_loop = asyncio.get_running_loop()
        current_loop_id = id(current_loop)

        # 场景：事件循环发生变化（如多次调用 asyncio.run），重置旧客户端
        if self._client is not None and self._client_loop_id != current_loop_id:
            self._client = None
            self._client_loop_id = None

        # 客户端不存在：创建新的异步客户端（带连接池配置）
        if self._client is None:
            # 配置超时时间
            timeout = httpx.Timeout(
                connect=30.0,      # 连接超时
                read=self._get_default_timeout(),   # 读取超时
                write=30.0,        # 写入超时
                pool=self._get_default_timeout(),   # 连接池超时
            )
            # 配置连接池（限制并发，提升稳定性）
            limits = httpx.Limits(
                max_connections=3,             # 最大连接数
                max_keepalive_connections=2,   # 最大保活连接数
                keepalive_expiry=30.0          # 连接保活时间
            )
            # 创建异步客户端
            self._client = httpx.AsyncClient(timeout=timeout, limits=limits)
            self._client_loop_id = current_loop_id

        return self._client

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        实现父类抽象方法：发送异步聊天请求
        """
        # 获取复用的 HTTP 客户端
        client = await self._get_client()

        # 请求头（OpenAI 规范）
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 转换消息格式为 SDK 兼容格式
        formatted_messages = convert_to_sdk_format(messages)

        # 清除孤立的 UTF-16 代理字符（Windows 终端输入可能引入）
        for msg in formatted_messages:
            if isinstance(msg.get("content"), str):
                msg["content"] = msg["content"].encode(
                    "utf-8", errors="ignore",
                ).decode("utf-8")

        # 构造请求载荷
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens
        }

        # 追加工具参数
        if tools:
            payload["tools"] = tools
        # 子类可扩展的载荷预处理
        self._prepare_payload(payload, tools, kwargs)

        # 指数退避重试参数
        _BASE_RETRY_DELAY = 5   # 基础延迟(秒)
        _MAX_RETRY_DELAY = 120  # 延迟上限(秒)
        max_retries = 5
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await client.post(self.base_url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                return self._parse_response(result)

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                error_msg = f"[{self.model_name}] HTTP 错误 {status_code}"
                try:
                    error_detail = e.response.json()
                    error_msg += f": {json.dumps(error_detail, ensure_ascii=False)}"
                except Exception:
                    error_msg += f": {e.response.text}"

                if status_code in (429, 500, 502, 503, 529):
                    last_error = RuntimeError(error_msg)
                    delay = min(_BASE_RETRY_DELAY * (2 ** attempt), _MAX_RETRY_DELAY)
                    jitter = delay * random.uniform(0.75, 1.25)
                    logger.warning(f"{error_msg} (第{attempt + 1}/{max_retries}次，{jitter:.1f}s 后重试)")
                    await asyncio.sleep(jitter)
                    continue
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            except httpx.ReadTimeout:
                last_error = RuntimeError(f"[{self.model_name}] 请求超时")
                delay = min(_BASE_RETRY_DELAY * (2 ** attempt), _MAX_RETRY_DELAY)
                jitter = delay * random.uniform(0.75, 1.25)
                logger.warning(f"[{self.model_name}] 请求超时 (第{attempt + 1}/{max_retries}次，{jitter:.1f}s 后重试)")
                await asyncio.sleep(jitter)
                continue

            except httpx.ConnectError as e:
                last_error = RuntimeError(f"[{self.model_name}] 连接失败: {e}")
                delay = min(_BASE_RETRY_DELAY * (2 ** attempt), _MAX_RETRY_DELAY)
                jitter = delay * random.uniform(0.75, 1.25)
                logger.warning(f"[{self.model_name}] 连接失败 (第{attempt + 1}/{max_retries}次，{jitter:.1f}s 后重试): {e}")
                old_client = self._client
                self._client = None
                if old_client:
                    try:
                        await old_client.aclose()
                    except Exception:
                        pass
                client = await self._get_client()
                await asyncio.sleep(jitter)
                continue

            except Exception as e:
                logger.error(f"[{self.model_name}] 请求失败: {e}")
                old_client = self._client
                self._client = None
                if old_client:
                    try:
                        await old_client.aclose()
                    except Exception:
                        pass
                raise

        logger.error(f"[{self.model_name}] 已重试{max_retries}次，全部失败，无模型可回退")
        raise last_error
            
    def _prepare_payload(
        self,
        payload: Dict[str, Any],
        tools: Optional[List[Dict[str, Any]]],
        kwargs: Dict[str, Any]
    ):
        """
        私有方法：请求载荷预处理
        子类可重写此方法，添加自定义参数（如 tool_choice、stream 等）
        """
        if "tool_choice" in kwargs:
            payload["tool_choice"] = kwargs["tool_choice"]
        if kwargs.get("thinking_disabled"):
            payload["thinking"] = {"type": "disabled"}

    def _parse_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        私有方法：解析 OpenAI 格式响应 → 统一标准格式
        核心作用：屏蔽不同模型的响应差异，对外提供统一格式
        """
        # 初始化响应内容
        content = []
        stop_reason = "stop"

        # 解析响应主体
        if "choices" in result and result["choices"]:
            # 取第一条选择结果
            choice = result["choices"][0]
            message = choice.get("message", {})
            message_content = message.get("content")
            tool_calls = message.get("tool_calls") or []

            # 1. 解析文本内容
            if message_content:
                content.append({
                    "type": "text",
                    "text": message_content
                })

            # 2. 解析工具调用
            for tc in tool_calls:
                func = tc.get("function", {})
                arguments_str = func.get("arguments", "{}")
                tool_name = func.get("name", "")

                # 解析工具参数（JSON 字符串 → 字典）
                try:
                    if isinstance(arguments_str, str):
                        args = json.loads(arguments_str) if arguments_str.strip() else {}
                    else:
                        args = arguments_str if isinstance(arguments_str, dict) else {}
                except json.JSONDecodeError:
                    logger.warning(
                        f"[{self.model_name}] 工具 '{tool_name}' 参数解析失败, "
                        f"原始 arguments (前200字符): {repr(arguments_str)[:200]}"
                    )
                    # 尝试修复：截断到最后一个完整的 JSON 键值对
                    args = self._try_repair_arguments(arguments_str, tool_name)

                # 空参数告警
                if not args:
                    logger.warning(
                        f"[{self.model_name}] 工具 '{tool_name}' 参数为空, "
                        f"finish_reason={choice.get('finish_reason')}, "
                        f"message_content 前后: {repr(message_content)[:200] if message_content else 'None'}"
                    )

                content.append({
                    "type": "tool_use",
                    "id": tc.get("id", f"{self.model_name}_{id(tc)}"),
                    "name": tool_name,
                    "input": args
                })

            # 3. 解析停止原因
            finish_reason = choice.get("finish_reason", "stop")
            # 统一工具调用停止原因标识
            stop_reason = "tool_use" if finish_reason == "tool_calls" else finish_reason

        # 返回标准化响应
        return {
            "content": content,
            "stop_reason": stop_reason,
            "usage": result.get("usage", {})
        }

    def _try_repair_arguments(self, arguments_str: str, tool_name: str) -> dict:
        """
        尝试修复被截断或不完整的 JSON 参数。
        常见场景：模型因 max_tokens 截断导致 arguments JSON 不完整。
        """
        if not isinstance(arguments_str, str) or not arguments_str.strip():
            return {}

        s = arguments_str.strip()
        # 尝试补全 JSON：找最后一个完整的键值对
        for truncate_char in ['",', '}", ', '"}', '\\n']:
            last_pos = s.rfind(truncate_char)
            if last_pos > 0:
                truncated = s[:last_pos + len(truncate_char)]
                # 尝试补全闭合
                open_braces = truncated.count('{') - truncated.count('}')
                open_brackets = truncated.count('[') - truncated.count(']')
                repaired = truncated + ']' * max(0, open_brackets) + '}' * max(0, open_braces)
                try:
                    result = json.loads(repaired)
                    logger.info(f"[{self.model_name}] 工具 '{tool_name}' 参数修复成功")
                    return result
                except json.JSONDecodeError:
                    continue

        logger.warning(f"[{self.model_name}] 工具 '{tool_name}' 参数无法修复")
        return {}

    async def aclose(self):
        """异步安全关闭客户端（推荐使用）"""
        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                pass  # 忽略关闭错误
            self._client = None

    def close(self):
        """同步关闭客户端（兼容旧代码）"""
        client_to_close = self._client
        self._client = None
        if client_to_close:
            try:
                loop = asyncio.get_running_loop()
                asyncio.ensure_future(
                    self._do_aclose(client_to_close), loop=loop
                )
            except RuntimeError:
                try:
                    asyncio.run(self._do_aclose(client_to_close))
                except Exception:
                    pass

    async def _do_aclose(self, client):
        """关闭指定 client 连接"""
        try:
            await client.aclose()
        except Exception:
            pass

    async def _safe_aclose(self):
        """私有方法：安全关闭客户端，忽略所有异常"""
        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                pass