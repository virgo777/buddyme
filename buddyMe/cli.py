"""buddyMe CLI 入口"""

import os
import queue
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from rich.console import Console

from buddyMe.agent_moudle import agent
from buddyMe.tool_moudle.baidu_search_tool import BaiduSearchTool

console = Console()

_SPINNERS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def _invoke_with_spinner(ag: agent.AgentMain, user_input: str) -> str:
    """在后台线程运行 invoke()，主线程显示 Rich 状态 spinner。"""
    result_queue: queue.Queue = queue.Queue(maxsize=1)

    def _worker():
        try:
            result_queue.put(("ok", ag.invoke(user_input)))
        except Exception as exc:
            result_queue.put(("err", exc))

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    idx = 0
    with console.status("") as status:
        while t.is_alive():
            s = _SPINNERS[idx % len(_SPINNERS)]
            status.update(
                f"[bold cyan]{s} 思考中... "
                f"[dim](in: {ag._token_in} · out: {ag._token_out})[/]"
            )
            idx += 1
            t.join(timeout=0.25)

    status_type, value = result_queue.get()
    if status_type == "err":
        raise value
    return value


def main():
    workspace_dir = Path.cwd()
    model_name = os.environ.get("BUDDYME_MODEL", "glm_code_plan")

    console.print("=" * 60, style="bold green")
    console.print("buddyMe — 多模型智能体 + Skill", style="bold green")
    console.print(f"项目空间: {workspace_dir}", style="cyan")
    console.print(f"默认模型: {model_name}", style="dim")
    console.print("输入 /help 查看可用命令", style="dim")
    console.print("=" * 60, style="bold green")

    ag = agent.AgentMain(model_name=model_name, workspace_dir=str(workspace_dir))
    ag.register_tool(BaiduSearchTool())
    ag.start_heartbeat()

    while True:
        try:
            inp = input("query: ")
            reply = _invoke_with_spinner(ag, inp)
            if reply:
                console.print(reply)
        except (KeyboardInterrupt, EOFError):
            console.print("\n再见!", style="bold yellow")
            ag.close()
            break


if __name__ == "__main__":
    main()
