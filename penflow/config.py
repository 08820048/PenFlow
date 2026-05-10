"""
配置管理
Key 保存在 ~/.penflow/config.json，只需配置一次
"""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()
CONFIG_DIR = Path.home() / ".penflow"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def init_config(force: bool = False):
    """引导用户初始化配置"""
    existing = load_config()

    console.print(Panel.fit(
        "[bold #A78BFA]🔧 初始化配置[/]\n"
        "[dim]Key 将保存到 ~/.penflow/config.json[/]",
        border_style="#3730a3"
    ))

    if existing and not force:
        console.print("\n[dim]检测到已有配置，回车跳过保留原值[/]\n")

    deepseek_key = Prompt.ask(
        "[#A78BFA]DeepSeek API Key[/]",
        default=existing.get("deepseek_key", "") if not force else "",
        password=True
    )

    tavily_key = Prompt.ask(
        "[#A78BFA]Tavily API Key[/]",
        default=existing.get("tavily_key", "") if not force else "",
        password=True
    )

    if not deepseek_key or not tavily_key:
        console.print("[red]❌ Key 不能为空[/]")
        raise typer.Exit(1)

    save_config({
        "deepseek_key": deepseek_key,
        "tavily_key": tavily_key,
    })

    console.print(f"\n[green]✅ 配置已保存到 {CONFIG_FILE}[/]\n")


def get_config() -> dict:
    """获取配置，未初始化则引导用户配置"""
    config = load_config()
    if not config.get("deepseek_key") or not config.get("tavily_key"):
        console.print("[yellow]⚠️  未找到配置，请先初始化[/]\n")
        init_config()
        config = load_config()
    return config