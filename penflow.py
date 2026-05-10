"""
微信公众号内容助手
架构：Supervisor + 选题Agent + 写作Agent + 排版Agent
特性：Human-in-the-loop（选题环节用户参与）

使用方式：
    python3 penflow.py

输出：
    output.md（可直接复制到公众号编辑器）
"""

import os
import re
from datetime import date
from typing import Annotated, Optional
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver


# ─────────────────────────────────────────
# 1. State
#    比多 Agent 版本多了业务字段
#    记录整个创作流程的中间产物
# ─────────────────────────────────────────
class State(TypedDict):
    messages: Annotated[list, add_messages]
    account_position: str    # 账号定位（用户输入）
    content_direction: str   # 创作方向（用户输入）
    topics: list             # 选题Agent生成的3个选题
    selected_topic: str      # 用户选定的选题
    article: str             # 写作Agent生成的文章
    formatted_article: str   # 排版Agent输出的最终文章
    next: str                # 路由目标


# ─────────────────────────────────────────
# 2. 工具
# ─────────────────────────────────────────
tavily_search = TavilySearch(
    max_results=5,
    tavily_api_key="your-tavily-key",   # 替换成你的 Key
)


# ─────────────────────────────────────────
# 3. LLM
# ─────────────────────────────────────────
def make_llm(bind_tools=None):
    llm = ChatOpenAI(
        model="deepseek-v4-pro",
        api_key="your-deepseek-key",    # 替换成你的 Key
        base_url="https://api.deepseek.com",
        temperature=0.7,                 # 创作类任务适当提高随机性
        extra_body={"thinking": {"type": "disabled"}},
    )
    if bind_tools:
        return llm.bind_tools(bind_tools)
    return llm


llm = make_llm()
search_llm = make_llm(bind_tools=[tavily_search])
search_tools_by_name = {"tavily_search": tavily_search}


# ─────────────────────────────────────────
# 4. 工具循环（复用之前的设计）
# ─────────────────────────────────────────
from langchain_core.messages import ToolMessage

def run_tool_loop(llm_with_tools, tools_by_name, messages, max_steps=5):
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


# ─────────────────────────────────────────
# 5. 各 Agent 节点
# ─────────────────────────────────────────

def topic_agent_node(state: State):
    """
    选题 Agent
    搜索当前热点，结合账号定位和创作方向，推荐3个选题
    """
    print("\n选题Agent 正在搜索热点...\n")

    account_position = state["account_position"]
    content_direction = state["content_direction"]

    system_prompt = f"""你是一个专业的公众号选题策划师。
今天的日期是 {date.today()}。

账号定位：{account_position}
创作方向：{content_direction}

你的任务：
1. 搜索当前相关热点话题
2. 结合账号定位，推荐3个有传播潜力的选题
3. 每个选题包含：标题、核心角度、预期读者收益

输出格式（严格遵守）：
选题1：[标题]
角度：[一句话说明核心角度]
收益：[读者能获得什么]

选题2：[标题]
角度：[一句话说明核心角度]
收益：[读者能获得什么]

选题3：[标题]
角度：[一句话说明核心角度]
收益：[读者能获得什么]"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"请围绕「{content_direction}」搜索热点，推荐3个选题。")
    ]

    response = run_tool_loop(search_llm, search_tools_by_name, messages)

    # 解析3个选题
    content = response.content
    topics = []
    for i in range(1, 4):
        match = re.search(rf"选题{i}[：:]\s*(.+?)(?=选题{i+1}|$)", content, re.DOTALL)
        if match:
            topics.append(match.group(1).strip())
        else:
            topics.append(f"选题{i}（解析失败，请查看原文）")

    if not topics:
        topics = [content]  # 解析失败时把全文作为选题展示

    print("\n[DEBUG 选题原文]\n", content)
    print("选题生成完成")
    return {
        "messages": [response],
        "topics": topics,
        "next": "human_select"
    }


def human_select_node(state: State):
    """
    Human-in-the-loop 节点
    暂停流程，让用户从3个选题中选择1个
    这个节点在 interrupt_before 模式下会在执行前暂停
    所以这里的逻辑实际是"恢复后"执行的：直接读取用户已经写入的 selected_topic
    """
    # 恢复后直接路由到写作 Agent
    return {"next": "write_agent"}


def write_agent_node(state: State):
    """
    写作 Agent
    根据选定选题，生成完整文章
    """
    selected_topic = state["selected_topic"]
    account_position = state["account_position"]

    system_prompt = f"""你是一个专业的微信公众号写作者。
账号定位：{account_position}

写作要求：
- 开头要有钩子，吸引读者继续读
- 结构清晰，分3-5个小节
- 语言生动，避免干燥说教
- 结尾有互动引导（引导点赞/关注/留言）
- 字数：1500-2500字

请根据以下选题，写一篇完整的公众号文章：
{selected_topic}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"请根据选题写完整文章：{selected_topic}")
    ]

    print("\n--- 文章创作中 ---\n")
    full_content = []
    for chunk in llm.stream(messages):
        if chunk.content:
            import sys
            sys.stdout.write(chunk.content)
            sys.stdout.flush()
            full_content.append(chunk.content)
    print()

    article = "".join(full_content)
    return {
        "messages": [AIMessage(content=article)],
        "article": article,
        "next": "format_agent"
    }


def format_agent_node(state: State):
    """
    排版 Agent
    把文章转成微信公众号标准格式
    """
    print("\n排版Agent 正在处理格式...\n")

    article = state["article"]

    system_prompt = """你是一个专业的公众号排版师。

排版规范：
- 标题：加粗，前后加【】，如 **【标题】**
- 正文小节标题：前加编号，如 第一节
- 重点内容：用「」引用，或加粗
- 段落间距：每段后空一行
- 结尾固定加：
  ---
  你怎么看？欢迎在评论区留言
  觉得有用就点个赞，让更多人看到
  关注账号，不错过每期内容

请对以下文章进行排版，只输出排版后的内容，不要加额外说明："""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=article)
    ]

    response = llm.invoke(messages)
    formatted_article = response.content

    print("排版完成")
    return {
        "messages": [response],
        "formatted_article": formatted_article,
        "next": END
    }


# ─────────────────────────────────────────
# 6. 路由函数
# ─────────────────────────────────────────
def router(state: State):
    next_step = state.get("next", END)
    return next_step


# ─────────────────────────────────────────
# 7. 构建图
#
# 流程：
# topic_agent → [暂停等用户选题] → human_select → write_agent → format_agent → END
# ─────────────────────────────────────────
builder = StateGraph(State)

builder.add_node("topic_agent", topic_agent_node)
builder.add_node("human_select", human_select_node)
builder.add_node("write_agent", write_agent_node)
builder.add_node("format_agent", format_agent_node)

builder.set_entry_point("topic_agent")

builder.add_conditional_edges("topic_agent", router, {
    "human_select": "human_select",
    END: END,
})
builder.add_conditional_edges("human_select", router, {
    "write_agent": "write_agent",
    END: END,
})
builder.add_conditional_edges("write_agent", router, {
    "format_agent": "format_agent",
    END: END,
})
builder.add_conditional_edges("format_agent", router, {
    END: END,
})

memory = MemorySaver()
# interrupt_before：在 human_select 节点执行前暂停，等待用户输入后再恢复
app = builder.compile(checkpointer=memory, interrupt_before=["human_select"])


# ─────────────────────────────────────────
# 8. 主程序：命令行交互
# ─────────────────────────────────────────
def main():
    print("=" * 55)
    print("   PenFlow")
    print("=" * 55)

    # 用户输入
    account_position = input("\n请输入你的账号定位（如：科技类、职场类、生活类）：\n> ").strip()
    content_direction = input("\n请输入本次创作方向（如：AI、职场成长、亲子教育）：\n> ").strip()

    if not account_position or not content_direction:
        print("账号定位和创作方向不能为空")
        return

    thread_id = f"session_{date.today()}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [],
        "account_position": account_position,
        "content_direction": content_direction,
        "topics": [],
        "selected_topic": "",
        "article": "",
        "formatted_article": "",
        "next": "",
    }

    # ── 第一阶段：生成选题（遇到 human_select 暂停）──
    print("\n正在生成选题，请稍候...\n")
    app.invoke(initial_state, config=config)

    # ── 读取选题，让用户选择 ──
    current_state = app.get_state(config)
    topics = current_state.values.get("topics", [])

    print("\n" + "=" * 55)
    print("以下是为你推荐的3个选题：")
    print("=" * 55)
    for i, topic in enumerate(topics, 1):
        print(f"\n【选题 {i}】\n{topic}")
        print("-" * 40)

    while True:
        choice = input("\n请输入选题编号（1/2/3），或输入 0 自定义选题：\n> ").strip()
        if choice in ["1", "2", "3"]:
            selected_topic = topics[int(choice) - 1]
            break
        elif choice == "0":
            selected_topic = input("请输入你的自定义选题：\n> ").strip()
            break
        else:
            print("请输入 1、2、3 或 0")

    print(f"\n已选择：{selected_topic[:50]}...")

    # ── 第二阶段：写入用户选择，恢复图继续执行 ──
    app.update_state(config, {"selected_topic": selected_topic})

    final_result = app.invoke(None, config=config)

    # ── 输出结果 ──
    formatted_article = final_result.get("formatted_article", "")

    if not formatted_article:
        print("文章生成失败，请重试")
        return

    # 保存到文件
    output_path = "output.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# 公众号文章\n")
        f.write(f"账号定位：{account_position}\n")
        f.write(f"创作方向：{content_direction}\n")
        f.write(f"选题：{selected_topic[:80]}\n")
        f.write(f"生成日期：{date.today()}\n\n")
        f.write("---\n\n")
        f.write(formatted_article)

    print("\n" + "=" * 55)
    print("文章生成完成！")
    print(f"已保存到：{output_path}")
    print("=" * 55)


if __name__ == "__main__":
    main()