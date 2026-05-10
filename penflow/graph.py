"""
LangGraph 图定义
把三个 Agent 串联成完整的创作流程
"""

from typing import Annotated
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from penflow.agents.topic import build_topic_agent
from penflow.agents.writer import build_writer_agent
from penflow.agents.formatter import build_formatter_agent


class State(TypedDict):
    messages: Annotated[list, add_messages]
    account_position: str
    content_direction: str
    topics: list
    selected_topic: str
    article: str
    formatted_article: str
    next: str


def build_graph(deepseek_key: str, tavily_key: str):
    """构建完整的 LangGraph 流程图"""

    llm = ChatOpenAI(
        model="deepseek-v4-pro",
        api_key=deepseek_key,
        base_url="https://api.deepseek.com",
        temperature=0.7,
        extra_body={"thinking": {"type": "disabled"}},
    )

    # 构建各 Agent 节点
    topic_node = build_topic_agent(llm, tavily_key)
    writer_node = build_writer_agent(llm)
    formatter_node = build_formatter_agent(llm)

    def human_select_node(state: State):
        """Human-in-the-loop 节点，恢复后直接路由到写作"""
        return {"next": "write_agent"}

    def router(state: State):
        return state.get("next", END)

    # 构建图
    builder = StateGraph(State)
    builder.add_node("topic_agent", topic_node)
    builder.add_node("human_select", human_select_node)
    builder.add_node("write_agent", writer_node)
    builder.add_node("format_agent", formatter_node)

    builder.set_entry_point("topic_agent")
    builder.add_conditional_edges("topic_agent", router, {
        "human_select": "human_select", END: END
    })
    builder.add_conditional_edges("human_select", router, {
        "write_agent": "write_agent", END: END
    })
    builder.add_conditional_edges("write_agent", router, {
        "format_agent": "format_agent", END: END
    })
    builder.add_conditional_edges("format_agent", router, {
        "__end__": END, END: END
    })

    memory = MemorySaver()
    app = builder.compile(
        checkpointer=memory,
        interrupt_before=["human_select"]
    )

    return app