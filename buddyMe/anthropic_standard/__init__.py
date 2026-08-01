"""anthropic_standard — Anthropic 标准 API 抽象层包。

将不同厂商的 LLM 接口归一为 Anthropic 风格的统一调用与工具协议：
- unified_client / basic_anthropic_client：自动识别 OpenAI / Anthropic 协议的统一客户端
- basic_anthropic_tool：工具抽象基类（BaseTool）
- anthropic_code_plan_base：代码规划（code plan）执行基座
"""
