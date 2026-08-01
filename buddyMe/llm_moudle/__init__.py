"""llm_moudle — 大模型统一调用模块包。

只需传入模型名称即可调用任意模型，底层自动适配 OpenAI / Anthropic 协议：
- basic_llm：统一调用入口（create_client）
- model_config：模型名称与端点、参数的映射配置
"""
