"""
basic_llm.py — 统一大模型调用模块

只需传入模型名称即可调用任意模型，自动适配 OpenAI / Anthropic 协议。
兼容项目现有的 BaseTool / ToolExecutor 工具系统和 Skill 技能系统。

使用:
    from buddyMe.llm_moudle.basic_llm import create_client

    client = create_client("glm")
    response = await client.chat([{"role": "user", "content": "你好"}])
    client.close()
"""

from typing import Optional

from buddyMe.anthropic_standard.unified_client import UnifiedLLMClient
from buddyMe.llm_moudle import model_config

# 模型特殊参数（非 max_tokens 的行为控制项）
_MODEL_DEFAULTS = {
    "deepseek": {
        "thinking_disabled": True,
    },
    "ernie": {
        "tool_choice": "auto",
    },
}


def create_client(model_name: str, max_tokens: int = None):
    """创建 LLM 客户端，自动适配协议。max_tokens 从 model_config 读取。"""
    if not model_config.ModelConfig.is_valid(model_name):
        raise ValueError(
            f"不支持的模型: {model_name}，可用: {model_config.ModelConfig.list_models()}"
        )

    cfg = model_config.ModelConfig.get(model_name)
    overrides = _MODEL_DEFAULTS.get(model_name, {})
    # max_tokens 优先级: 用户显式传入 > model_config 配置
    effective_mt = max_tokens or cfg.get("max_tokens")
    return UnifiedLLMClient(
        model_name=model_name,
        max_tokens=effective_mt,
        model_overrides=overrides,
    )


def list_models() -> list:
    """列出所有可用模型"""
    return model_config.ModelConfig.list_models()


# ———————————————————— 测试 ————————————————————
if __name__ == "__main__":
    import asyncio

    async def _test():
        print("=" * 60)
        print("basic_llm 测试 — 全部模型")
        print(f"可用模型: {list_models()}")
        print("=" * 60)

        for name in list_models():
            print(f"\n--- {name} ---")
            client = None
            try:
                client = create_client(name)
                print(f"  协议={client.protocol}, max_tokens={client.max_tokens}")

                resp = await client.chat([
                    {"role": "user", "content": "用一句话介绍自己"}
                ])
                texts = [b["text"] for b in resp["content"] if b["type"] == "text"]
                reply = "".join(texts)[:120].encode("gbk", errors="replace").decode("gbk")
                print(f"  回复: {reply}")
            except Exception as e:
                print(f"  错误: {e}")
            finally:
                if client:
                    client.close()

    asyncio.run(_test())
