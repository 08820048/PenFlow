# PenFlow

选题、写作、排版一键生成的终端 Agent。

## 安装

```bash
pip install penflow
```

或从源码安装（开发模式）：

```bash
git clone https://github.com/your-repo/penflow
cd penflow
pip install -e .
```

## 配置

首次使用需要配置 API Key：

```bash
penflow init
```

需要准备：
- [DeepSeek API Key](https://platform.deepseek.com/api_keys)
- [Tavily API Key](https://app.tavily.com)

## 使用

```bash
penflow run
```

按提示输入账号定位和创作方向，Agent 自动完成：
1. 搜索热点，推荐 3 个选题
2. 你选择其中一个（或自定义）
3. 自动写作 + 排版
4. 输出到 `output.md`

## 命令列表

| 命令 | 说明 |
|---|---|
| `penflow init` | 初始化/更新 API Key 配置 |
| `penflow run` | 启动创作流程 |
| `penflow --help` | 查看帮助 |
