"""
unified_client.py — 统一 LLM 客户端

自动检测协议（OpenAI / Anthropic），只需传入 model_name 即可调用。
兼容项目现有的 tool 调用（BaseTool/ToolExecutor）和 skill 系统。

使用:
    from buddyMe.anthropic_standard.unified_client import UnifiedLLMClient

    client = UnifiedLLMClient("glm")
    response = await client.chat([{"role": "user", "content": "你好"}])
    client.close()
"""

import logging
from typing import Any, Dict, List, Optional

from buddyMe.anthropic_standard.basic_anthropic_client import BaseLLMClient, OpenAICompatibleClient
from buddyMe.anthropic_standard.anthropic_code_plan_base import AnthropicCodePlanClient
from buddyMe.llm_moudle import model_config

logger = logging.getLogger(__name__)


def _is_anthropic_protocol(model_name: str) -> bool:
    cfg = model_config.ModelConfig.get(model_name)
    base_url = cfg.get("base_url", "")
    return model_name.endswith("_code_plan") or "anthropic" in base_url.lower()


class UnifiedLLMClient(BaseLLMClient):
    """统一 LLM 客户端 — 自动选择 OpenAI 或 Anthropic 协议

    支持 model_overrides 传入模型特殊参数:
        - thinking_disabled: bool  — DeepSeek 关闭思考模式
        - tool_choice: str        — ERNIE 开启自动工具选择
        - max_tokens: int         — 覆盖默认 token 上限
    """

    def __init__(
        self,
        model_name: str,
        max_tokens: Optional[int] = None,
        model_overrides: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(model_name)
        cfg = model_config.ModelConfig.get(model_name)
        if not cfg:
            raise ValueError(
                f"不支持的模型: {model_name}，可用: {model_config.ModelConfig.list_models()}"
            )

        self._protocol = "anthropic" if _is_anthropic_protocol(model_name) else "openai"
        self._overrides = model_overrides or {}

        # max_tokens: 优先用户显式传入 → overrides → delegate 默认
        effective_mt = max_tokens or self._overrides.get("max_tokens")
        if self._protocol == "anthropic":
            d_kwargs: Dict[str, Any] = dict(
                model_name=model_name,
                api_key=cfg.get("api_key", ""),
                base_url=cfg.get("base_url", ""),
                model=cfg.get("api_model", model_name),
            )
            if effective_mt is not None:
                d_kwargs["max_tokens"] = effective_mt
            self._max_tokens = d_kwargs.get("max_tokens", 131072)
            self._delegate: BaseLLMClient = AnthropicCodePlanClient(**d_kwargs)
        else:
            d_kwargs = dict(model_name=model_name)
            if effective_mt is not None:
                d_kwargs["max_tokens"] = effective_mt
            self._max_tokens = d_kwargs.get("max_tokens", 81920)
            self._delegate = OpenAICompatibleClient(**d_kwargs)

    @property
    def protocol(self) -> str:
        return self._protocol

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        **kwargs
    ) -> Dict[str, Any]:
        # 注入模型特殊参数
        if self._overrides.get("thinking_disabled"):
            kwargs.setdefault("thinking_disabled", True)
        if self._overrides.get("tool_choice") and tools:
            kwargs.setdefault("tool_choice", self._overrides["tool_choice"])
        return await self._delegate.chat(messages, tools, temperature, **kwargs)

    def close(self):
        self._delegate.close()

    def build_tool_result_message(
        self, tool_call_id: str, tool_name: str, result
    ) -> Dict[str, Any]:
        return self._delegate.build_tool_result_message(tool_call_id, tool_name, result)


# ———————————————————— 测试 ————————————————————
if __name__ == "__main__":
    import asyncio

    async def _test():
        print("=" * 60)
        print("UnifiedLLMClient 测试")
        print(f"可用模型: {model_config.ModelConfig.list_models()}")
        print("=" * 60)

        for name in ["glm", "deepseek", "minimax", "qwen"]:
            try:
                client = UnifiedLLMClient(name)
                print(f"\n[{name}] 协议: {client.protocol}, max_tokens: {client._max_tokens}")
                client.close()
            except Exception as e:
                print(f"[{name}] 错误: {e}")

        # 实际对话测试
        print("\n--- 对话测试 (glm) ---")
        client = UnifiedLLMClient("glm")
        try:
            resp = await client.chat([
                {"role": "user", "content": "用一句话介绍自己"}
            ])
            texts = [b["text"] for b in resp["content"] if b["type"] == "text"]
            print("回复:", "\n".join(texts))
        finally:
            client.close()

    asyncio.run(_test())
