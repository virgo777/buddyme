"""
anthropic_code_plan_base.py — Anthropic 兼容客户端基类

被 glm_moudle_code_plan.py 和 minimax_moudle_code_plan.py 共用。
子类只需提供 api_key / base_url / model / timeout 等配置参数。
"""

import asyncio
import json
import logging
import random
from typing import Any, Dict, List, Optional

import httpx

from buddyMe.anthropic_standard.basic_anthropic_client import BaseLLMClient

logger = logging.getLogger(__name__)


class AnthropicCodePlanClient(BaseLLMClient):
    """
    Anthropic 兼容客户端基类。

    自动完成 OpenAI 格式 → Anthropic 格式的双向转换。

    核心转换:
        请求: OpenAI 工具 schema / 消息格式 → Anthropic 格式
        响应: Anthropic 响应 → 标准格式 (content / stop_reason / usage)
    """

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str,
        model: str,
        max_tokens: int = 131072,
        timeout_read: float = 1800.0,
        timeout_write: float = 360.0,
    ):
        super().__init__(model_name)
        self.model = model
        self.max_tokens = max_tokens
        self.api_key = api_key
        self.base_url = base_url
        self._timeout_read = timeout_read
        self._timeout_write = timeout_write
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop_id: Optional[int] = None

    # ------------------------------------------------------------------
    # HTTP 客户端管理
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        current_loop = asyncio.get_running_loop()
        current_loop_id = id(current_loop)

        if self._client is not None and self._client_loop_id != current_loop_id:
            self._client = None
            self._client_loop_id = None

        if self._client is None:
            timeout = httpx.Timeout(
                connect=90.0, read=self._timeout_read,
                write=self._timeout_write, pool=1800.0,
            )
            limits = httpx.Limits(
                max_connections=3, max_keepalive_connections=2, keepalive_expiry=30.0,
            )
            self._client = httpx.AsyncClient(timeout=timeout, limits=limits)
            self._client_loop_id = current_loop_id

        return self._client

    # ------------------------------------------------------------------
    # 消息格式转换: OpenAI → Anthropic
    # ------------------------------------------------------------------

    def _convert_messages(self, messages: List[Dict]) -> tuple:
        """
        将 OpenAI 格式消息转换为 Anthropic 格式。

        差异:
        - system 消息从数组中提取，放入 payload.system 字段
        - tool 角色消息 → user 角色中嵌入 tool_result 内容块
        - 连续多个 tool 消息合并为一个 user 消息（Anthropic 规范）
        - assistant 的 tool_calls → content 数组中的 tool_use 块
        """
        system_content = ""
        converted: List[Dict] = []

        for msg in messages:
            role = msg.get("role", "user")

            if role == "system":
                system_content = msg.get("content", "")
                continue

            if role == "assistant":
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    content: List[Dict] = []
                    text = msg.get("content")
                    if text:
                        content.append({"type": "text", "text": text})
                    for tc in tool_calls:
                        func = tc.get("function", {})
                        args_str = func.get("arguments", "{}")
                        try:
                            args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        except json.JSONDecodeError:
                            args = {}
                        content.append({
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": func.get("name", ""),
                            "input": args
                        })
                    converted.append({"role": "assistant", "content": content})
                else:
                    converted.append({"role": "assistant", "content": msg.get("content", "")})
                continue

            if role == "tool":
                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": msg.get("content", "")
                }
                if (converted
                        and converted[-1]["role"] == "user"
                        and isinstance(converted[-1].get("content"), list)
                        and converted[-1]["content"]
                        and converted[-1]["content"][0].get("type") == "tool_result"):
                    converted[-1]["content"].append(tool_result_block)
                else:
                    converted.append({
                        "role": "user",
                        "content": [tool_result_block]
                    })
                continue

            converted.append(msg)

        return system_content, converted

    # ------------------------------------------------------------------
    # 工具 Schema 转换: OpenAI → Anthropic
    # ------------------------------------------------------------------

    def _convert_tools(self, tools: Optional[List[Dict]]) -> Optional[List[Dict]]:
        if not tools:
            return None

        anthropic_tools = []
        for tool in tools:
            func = tool.get("function", tool)
            anthropic_tools.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}})
            })
        return anthropic_tools

    # ------------------------------------------------------------------
    # 核心: chat 方法
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        **kwargs
    ) -> Dict[str, Any]:
        client = await self._get_client()

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        system_content, converted_messages = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools)

        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": converted_messages,
            "temperature": temperature,
        }
        if system_content:
            payload["system"] = system_content
        if anthropic_tools:
            payload["tools"] = anthropic_tools

        _BASE_RETRY_DELAY = 5
        _MAX_RETRY_DELAY = 120
        max_retries = 5
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await client.post(
                    f"{self.base_url}/v1/messages",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                return self._parse_response(result)

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                error_msg = f"[{self.model_name}] HTTP 错误 {status_code}"
                try:
                    error_msg += f": {e.response.text}"
                except Exception:
                    pass

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
                self._client = None
                client = await self._get_client()
                await asyncio.sleep(jitter)
                continue

            except Exception as e:
                logger.error(f"[{self.model_name}] 请求失败: {e}")
                self._client = None
                raise

        logger.error(f"[{self.model_name}] 已重试{max_retries}次，全部失败，无模型可回退")
        raise last_error

    # ------------------------------------------------------------------
    # 响应解析: Anthropic → 标准格式
    # ------------------------------------------------------------------

    def _parse_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        stop_reason = result.get("stop_reason", "stop")
        if stop_reason == "end_turn":
            stop_reason = "stop"

        return {
            "content": result.get("content", []),
            "stop_reason": stop_reason,
            "usage": result.get("usage", {})
        }

    # ------------------------------------------------------------------
    # 关闭客户端
    # ------------------------------------------------------------------

    async def aclose(self):
        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None

    def close(self):
        if self._client:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.aclose())
            except RuntimeError:
                try:
                    asyncio.run(self.aclose())
                except Exception:
                    pass
            self._client = None
