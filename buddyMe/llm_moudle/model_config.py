import os


class ModelConfig:
    """大模型配置管理工具类（支持智谱GLM、deepseek、百度千帆ERNIE、MiniMax 等）"""

    _CONFIG = {
        "sub_agent_code_plan": {
            "api_key": os.environ.get("GLM_API_KEY", ""),
            "base_url": "https://open.bigmodel.cn/api/anthropic",
            "api_model": "glm-4.7",
            "max_tokens": 390000
        },
        "glm": {
            "api_key": os.environ.get("GLM_API_KEY", ""),
            "base_url": "https://open.bigmodel.cn/api/coding/paas/v4/chat/completions",
            "api_model": "glm-5.1",
            "max_tokens": 131072
        },
        "glm_code_plan": {
            "api_key": os.environ.get("GLM_API_KEY", ""),
            "base_url": "https://open.bigmodel.cn/api/anthropic",
            "api_model": "glm-5.1",
            "max_tokens": 390000
        },
        "deepseek": {
            "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
            "base_url": "https://api.deepseek.com/chat/completions",
            "api_model": "deepseek-v4-pro",
            "max_tokens": 393216
        },
        "deepseek_code_plan": {
            "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
            "base_url": "https://api.deepseek.com/anthropic",
            "api_model": "deepseek-v4-pro",
            "max_tokens": 960000
        },
        "ernie": {
            "api_key": os.environ.get("ERNIE_API_KEY", ""),
            "base_url": "https://qianfan.baidubce.com/v2/chat/completions",
            "api_model": "ernie-5.1",
            "max_tokens": 65536
        },
        "xiaomi": {
            "api_key": os.environ.get("XIAOMI_API_KEY", ""),
            "base_url": "https://api.xiaomimimo.com/v1/chat/completions",
            "api_model": "mimo-v2-pro",
            "max_tokens": 131072
        },
        "qwen": {
            "api_key": os.environ.get("QWEN_API_KEY", ""),
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            "api_model": "qwen3.6-plus",
            "max_tokens": 65536
        },
        "minimax": {
            "api_key": os.environ.get("MINIMAX_API_KEY", ""),
            "base_url": "https://api.minimax.io/v1/chat/completions",
            "api_model": "MiniMax-M2.7",
            "max_tokens": 192000
        },
        "minimax_highspeed": {
            "api_key": os.environ.get("MINIMAX_API_KEY", ""),
            "base_url": "https://api.minimax.io/v1/chat/completions",
            "api_model": "MiniMax-M2.7-highspeed",
            "max_tokens": 192000
        },
        "minimax_code_plan": {
            "api_key": os.environ.get("MINIMAX_API_KEY", ""),
            "base_url": "https://api.minimax.io/anthropic",
            "api_model": "MiniMax-M2.7",
            "max_tokens": 192000
        }
    }

    @classmethod
    def get(cls, model_name: str):
        """获取模型完整配置（安全获取，不存在返回空dict）"""
        return cls._CONFIG.get(model_name, {})

    @classmethod
    def get_api_key(cls, model_name: str) -> str:
        """获取模型API Key（带异常保护）"""
        config = cls.get(model_name)
        return config.get("api_key", "")

    @classmethod
    def get_base_url(cls, model_name: str) -> str:
        """获取模型Base URL（带异常保护）"""
        config = cls.get(model_name)
        return config.get("base_url", "")

    @classmethod
    def get_api_model(cls, model_name: str) -> str:
        """获取 API 端真实模型名（带异常保护）"""
        config = cls.get(model_name)
        return config.get("api_model", model_name)

    @classmethod
    def list_models(cls) -> list:
        """列出所有支持的模型名"""
        return list(cls._CONFIG.keys())

    @classmethod
    def is_valid(cls, model_name: str) -> bool:
        """判断模型是否在配置中"""
        return model_name in cls._CONFIG

    @classmethod
    def set_api_key(cls, model_name: str, api_key: str) -> None:
        """运行时更新指定模型的 API Key"""
        if model_name in cls._CONFIG:
            cls._CONFIG[model_name]["api_key"] = api_key

    @classmethod
    def get_args(cls) -> dict:
        args_dict = {

        "MAX_SUBTASK_RESULT_LEN" : 8192,# 子任务结果最大存储长度（增大以保留更多信息供 end_task 和合并使用）：单个子任务的最终结果写入 JSON 的上限

        "MAX_TOOLS_COMPRESS_LEN" : 5120,# 子任务多个工具调用后，压缩后摘要最大长度：多条工具调用结果拼接后压缩的上限，塞回 LLM 上下文

        "MAX_SEARCH_CALLS" : 5 # 每个子任务最多调用搜索工具次数（仅限 baidu_search）
        }

        return args_dict

# —————————————— 测试调用 ——————————————
if __name__ == '__main__':
    model_name = "glm"

    # 安全获取配置
    print(ModelConfig.get(model_name))
    print(ModelConfig.get_api_key(model_name))
    print(ModelConfig.get_base_url(model_name))

    # 工具方法
    print("支持模型:", ModelConfig.list_models())
    print("是否有效:", ModelConfig.is_valid(model_name))
