"""
写作 Agent
根据选定选题，生成完整的公众号文章
"""

from langchain_core.messages import HumanMessage, SystemMessage
from rich.console import Console

console = Console()


def build_writer_agent(llm):
    """构建写作 Agent"""

    def writer_node(state: dict) -> dict:
        selected_topic = state["selected_topic"]
        account_position = state["account_position"]

        with console.status("[#A78BFA]写作Agent 正在创作文章...[/]", spinner="dots"):
            system_prompt = f"""你是一个专业的微信公众号写作者。
账号定位：{account_position}

写作要求：
- 开头用真实故事或反常识数据作钩子，前3行决定读者去留
- 结构清晰，分3-5个小节，每节有小标题
- 语言口语化，像跟朋友聊天，多用「你」增加代入感
- 关键数据和结论单独成段加粗
- 避免说教，用故事和案例代替道理
- 结尾有互动引导（点赞/关注/留言）
- 字数：1500-2500字

请根据以下选题写一篇完整的公众号文章：
{selected_topic}"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"请根据选题写完整文章：{selected_topic}")
            ]

            response = llm.invoke(messages)

        console.print("[green]文章创作完成[/]")

        return {
            "messages": state.get("messages", []) + [response],
            "article": response.content,
            "next": "format_agent"
        }

    return writer_node