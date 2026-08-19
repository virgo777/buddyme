# Baidu web search tool.

"""
================================================================================
BaiduSearchTool - 百度搜索工具
================================================================================

基于百度千帆 AI Search API 实现的网络搜索工具。

继承 BaseTool，提供通过百度搜索获取实时网络信息的能力。

使用示例:
    from tool_moudle.baidu_search_tool import BaiduSearchTool

    tool = BaiduSearchTool()
    result = await tool.execute(query="北京今天天气")
    print(result)

================================================================================
"""

import logging
import os
from typing import Any, Dict, Optional

import httpx

from buddyMe.anthropic_standard.basic_anthropic_tool import BaseTool

logger = logging.getLogger(__name__)

QIANFAN_SEARCH_URL = "https://qianfan.baidubce.com/v2/ai_search/web_search"


class BaiduSearchTool(BaseTool):
    """百度搜索工具 - 通过千帆 AI Search API 进行网络搜索"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            name="baidu_search",
            description="""使用百度搜索获取网络上的实时信息。

【适用场景】
- 查询实时信息：天气、新闻、股价、赛事结果等
- 搜索事实性问题：人物、事件、地点等
- 获取最新数据：需要互联网最新数据的场景

【输入参数】
- query (必需): 搜索关键词或问题

【输出】
- 返回搜索结果列表，包含标题、摘要和来源""",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或问题"
                    }
                },
                "required": ["query"]
            }
        )
        self._api_key = api_key or os.environ.get("BAIDU_SEARCH_API_KEY", "")

    async def execute(self, query: str) -> str:
        """执行百度搜索

        Args:
            query: 搜索关键词

        Returns:
            搜索结果字符串
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "messages": [{"role": "user", "content": query}],
            "search_source": "baidu_search_v2",
            "resource_type_filter": [{"type": "web", "top_k": 10}]
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    QIANFAN_SEARCH_URL,
                    headers=headers,
                    json=payload
                )
                resp.raise_for_status()
                result = resp.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"[baidu_search] HTTP 错误 {e.response.status_code}: {e.response.text}")
            return f"搜索失败：HTTP 错误 {e.response.status_code}"
        except httpx.RequestError as e:
            logger.error(f"[baidu_search] 连接失败: {e}")
            return f"搜索失败：网络连接错误"
        except Exception as e:
            logger.error(f"[baidu_search] 请求失败: {e}")
            return f"搜索失败：{str(e)}"

        references = result.get("references", [])
        if not references:
            return f"未找到「{query}」相关结果"

        lines = [f"搜索「{query}」结果："]
        for i, item in enumerate(references[:5], 1):
            title = item.get("title", "无标题")
            content = item.get("content", "")[:150]
            lines.append(f"\n{i}. {title}\n   摘要：{content}...")

        return "\n".join(lines)


# ==============================================================================
# 模块测试
# ==============================================================================

if __name__ == '__main__':
    import asyncio

    async def run_test():
        tool = BaiduSearchTool()
        print("工具名称:", tool.name)
        print("工具描述:", tool.description[:50] + "...")
        print()

        result = await tool.execute(query="北京2026年3月天气")
        print(result)

    asyncio.run(run_test())
