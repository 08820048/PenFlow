"""
排版 Agent
把文章转成微信公众号标准格式
"""

from langchain_core.messages import HumanMessage, SystemMessage
from rich.console import Console

console = Console()


def build_formatter_agent(llm):
    """构建排版 Agent"""

    def formatter_node(state: dict) -> dict:
        article = state["article"]

        with console.status("[#A78BFA]排版Agent 正在处理格式...[/]", spinner="dots"):
            system_prompt = """你是一个专业的公众号排版师。

排版规范：
- 文章标题：加粗，用【】包裹，如 **【标题】**
- 小节标题：前加编号，如「一、第一节标题」
- 重点内容：加粗或用「」引用
- 每段之间空一行
- 数据和结论单独成段加粗
- 结尾固定加：

---
你怎么看？欢迎在评论区留言
觉得有用就点个赞，让更多人看到
关注账号，不错过每期内容

只输出排版后的正文内容，不要加任何说明或前缀。"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=article)
            ]

            response = llm.invoke(messages)

        console.print("[green]排版完成[/]")

        return {
            "messages": state.get("messages", []) + [response],
            "formatted_article": response.content,
            "next": "__end__"
        }

    return formatter_node