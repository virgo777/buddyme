# buddyMe local development entry point.

"""buddyMe 本地开发入口"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

try:
    from buddyMe.agent_moudle import agent
except ImportError:
    from agent_moudle import agent

_SRC_DIR = Path(__file__).resolve().parent

model_name = os.environ.get("BUDDYME_MODEL", "glm_code_plan")

print("=" * 60)
print("buddyMe — 本地开发模式")
print(f"源码目录: {_SRC_DIR}")
print(f"默认模型: {model_name}")
print("输入 /help 查看可用命令")
print("=" * 60)

ag = agent.AgentMain(model_name=model_name, data_dir=str(_SRC_DIR))

try:
    from buddyMe.tool_moudle.baidu_search_tool import BaiduSearchTool
except ImportError:
    from tool_moudle.baidu_search_tool import BaiduSearchTool
ag.register_tool(BaiduSearchTool())

while True:
    time.sleep(1)
    inp = input("query: ")
    reply = ag.invoke(inp)
    if reply:
        print(reply)
    if ag._last_cmd_should_exit:
        break
