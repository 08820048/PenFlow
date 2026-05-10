"""
选题 Agent
搜索当前热点，结合账号定位推荐 3 个选题
"""

import re
from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_tavily import TavilySearch
from rich.console import Console

console = Console()


def run_tool_loop(llm_with_tools, tools_by_name, messages, max_steps=6):
    """子 Agent 内部工具循环，只返回最终文本回复"""
    local_messages = list(messages)
    for _ in range(max_steps):
        response = llm_with_tools.invoke(local_messages)
        if not (hasattr(response, "tool_calls") and response.tool_calls):
            return response
        local_messages.append(response)
        for tool_call in response.tool_calls:
            result = tools_by_name[tool_call["name"]].invoke(tool_call["args"])
            local_messages.append(ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
            ))
    return response


def build_topic_agent(llm, tavily_key: str):
    """构建选题 Agent，返回可调用的节点函数"""
    search_tool = TavilySearch(max_results=5, tavily_api_key=tavily_key)
    tools_by_name = {"tavily_search": search_tool}
    llm_with_tools = llm.bind_tools([search_tool])

    def topic_node(state: dict) -> dict:
        account_position = state["account_position"]
        content_direction = state["content_direction"]

        console.print("\n[#A78BFA]🔍 选题Agent 正在搜索热点...[/]")

        system_prompt = f"""你是一个专业的公众号选题策划师。
今天的日期是 {date.today()}。

账号定位：{account_position}
创作方向：{content_direction}

任务：搜索当前相关热点，结合账号定位推荐3个有传播潜力的选题。

严格按以下格式输出，不要有其他内容：

选题1：[标题]
角度：[一句话核心角度]
收益：[读者能获得什么]

选题2：[标题]
角度：[一句话核心角度]
收益：[读者能获得什么]

选题3：[标题]
角度：[一句话核心角度]
收益：[读者能获得什么]"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"请围绕「{content_direction}」搜索热点，推荐3个选题。")
        ]

        response = run_tool_loop(llm_with_tools, tools_by_name, messages)
        content = response.content

        # 解析选题
        topics = []
        for i in range(1, 4):
            end_pattern = rf"选题{i+1}" if i < 3 else r"$"
            match = re.search(
                rf"选题{i}[：:]\s*(.+?)(?={end_pattern})",
                content,
                re.DOTALL
            )
            if match:
                # 清洗 Markdown 符号
                cleaned = re.sub(r'\*+', '', match.group(1)).strip()
                topics.append(cleaned)
            else:
                topics.append(f"选题{i}（解析失败）\n原文：{content[:200]}")

        console.print("[green]✅ 选题生成完成[/]")
        return {
            "messages": state.get("messages", []) + [response],
            "topics": topics,
            "next": "human_select"
        }

    return topic_node