"""
CLI 入口
penflow init   — 初始化配置
penflow run    — 启动创作流程
"""

from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich import box
from langchain_core.messages import AIMessage

from penflow.config import get_config, init_config
from penflow.graph import build_graph

app = typer.Typer(
    name="penflow",
    help="PenFlow — 选题、写作、排版一键生成",
    no_args_is_help=True,
)
console = Console()


def print_banner():
    console.print(Panel.fit(
        "[bold #A78BFA]PenFlow[/]\n"
        "[dim]选题 · 写作 · 排版 · 一键生成[/]",
        border_style="#3730a3",
        padding=(1, 4),
    ))


def print_topics(topics: list):
    """用 Rich 表格展示选题"""
    console.print("\n[bold #A78BFA]为你推荐 3 个选题[/]\n")
    for i, topic in enumerate(topics, 1):
        lines = topic.strip().split("\n")
        title = lines[0] if lines else f"选题{i}"
        rest = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

        console.print(Panel(
            f"[dim]选题 {i:02d}[/]\n"
            f"[bold white]{title}[/]\n"
            f"[dim]{rest}[/]" if rest else f"[bold white]{title}[/]",
            border_style="#3730a3" if i == 1 else "#2d2d2d",
            padding=(0, 2),
        ))


@app.command()
def init():
    """初始化配置（API Key 等）"""
    print_banner()
    init_config(force=True)


@app.command()
def run():
    """启动公众号内容创作流程"""
    print_banner()

    # 读取配置
    config = get_config()
    deepseek_key = config["deepseek_key"]
    tavily_key = config["tavily_key"]

    # 用户输入
    console.print()
    account_position = Prompt.ask("[#A78BFA]请输入你的账号定位[/] [dim](如：科技类、职场类)[/]")
    content_direction = Prompt.ask("[#A78BFA]请输入本次创作方向[/] [dim](如：AI、职场成长)[/]")

    if not account_position or not content_direction:
        console.print("[red]账号定位和创作方向不能为空[/]")
        raise typer.Exit(1)

    # 构建图
    agent_app = build_graph(deepseek_key, tavily_key)
    thread_id = f"session_{date.today()}"
    config_map = {"configurable": {"thread_id": thread_id}}

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

    # ── 第一阶段：生成选题 ──
    console.print("\n[dim]正在生成选题，请稍候...[/]")
    agent_app.invoke(initial_state, config=config_map)

    # 展示选题
    current_state = agent_app.get_state(config_map)
    topics = current_state.values.get("topics", [])
    print_topics(topics)

    # 用户选择
    console.print()
    while True:
        choice = Prompt.ask(
            "[#A78BFA]请选择选题编号[/] [dim](1/2/3，输入 0 自定义)[/]"
        )
        if choice in ["1", "2", "3"]:
            selected_topic = topics[int(choice) - 1]
            break
        elif choice == "0":
            selected_topic = Prompt.ask("[#A78BFA]请输入你的自定义选题[/]")
            break
        else:
            console.print("[yellow]请输入 1、2、3 或 0[/]")

    console.print(f"\n[green]已选择：[/]{selected_topic[:60]}{'...' if len(selected_topic) > 60 else ''}\n")

    # ── 第二阶段：写作 + 排版 ──
    agent_app.update_state(config_map, {"selected_topic": selected_topic})
    console.print("[dim]正在创作文章，请稍候...[/]\n")
    final_result = agent_app.invoke(None, config=config_map)

    # 获取最终文章
    formatted_article = final_result.get("formatted_article", "")
    if not formatted_article:
        console.print("[red]文章生成失败，请重试[/]")
        raise typer.Exit(1)

    # 保存文件
    output_path = Path("output.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# 公众号文章\n\n")
        f.write(f"- 账号定位：{account_position}\n")
        f.write(f"- 创作方向：{content_direction}\n")
        f.write(f"- 生成日期：{date.today()}\n\n")
        f.write("---\n\n")
        f.write(formatted_article)

    # 完成提示
    console.print(Panel.fit(
        f"[bold green]文章生成完成！[/]\n"
        f"[dim]已保存到：[/][bold]{output_path.absolute()}[/]",
        border_style="green",
        padding=(0, 2),
    ))

    # 预览前 300 字
    console.print("\n[dim]--- 文章预览 ---[/]\n")
    preview = formatted_article[:300] + "..." if len(formatted_article) > 300 else formatted_article
    console.print(preview)


if __name__ == "__main__":
    app()