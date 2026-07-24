<div align="center">

<img src="https://raw.githubusercontent.com/KevRojo/Dulus/main/docs/dulus-bird.png" alt="Dulus — 棕榈鸦" width="280">

<h1>DULUS</h1>

<h3>你的 AI 伙伴。不是聊天机器人。一个飞在你身边的朋友。</h3>

<p>
  <strong>无需 API 密钥即可使用前沿 AI。$0。无需信用卡。无需订阅。</strong>
</p>

<p>
  <a href="https://pypi.org/project/dulus/"><img src="https://img.shields.io/pypi/v/dulus.svg?style=flat-square&color=ff6b1f&labelColor=07070a&label=pypi" alt="PyPI"/></a>
  <a href="https://pypi.org/project/dulus/"><img src="https://static.pepy.tech/badge/dulus?style=flat-square" alt="下载量"/></a>
  <img src="https://img.shields.io/badge/python-3.11+-ff6b1f?style=flat-square&labelColor=07070a" alt="Python"/>
  <img src="https://img.shields.io/badge/许可证-GPLv3-ff6b1f?style=flat-square&labelColor=07070a" alt="许可证"/>
  <img src="https://img.shields.io/badge/提供商-100%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="提供商"/>
  <img src="https://img.shields.io/badge/工具-30%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="工具"/>
  <img src="https://img.shields.io/badge/测试-263%2B-ff6b1f?style=flat-square&labelColor=07070a" alt="测试"/>
  <a href="https://x.com/KevRojo"><img src="https://img.shields.io/badge/x-%40KevRojo-ff6b1f?style=flat-square&labelColor=07070a&logo=x" alt="X"/></a>
</p>

<p>
  <a href="#快速开始"><b>快速开始</b></a> ·
  <a href="#功能"><b>功能</b></a> ·
  <a href="#提供商"><b>提供商</b></a> ·
  <a href="#架构"><b>架构</b></a> ·
</p>

</div>

---

> 以**棕榈鸦**（*Dulus dominicus*）命名，多米尼加共和国国鸟 —— 自由、韧性和共同飞翔的象征。Dulus 不是聊天机器人。它是你的伙伴、你的朋友、飞在你身边的 AI 搭档。

---

## 为什么选择 Dulus？

| | 封闭生态系统 | 复杂框架 | **Dulus** |
|---|---|---|---|
| **设置时间** | 数小时 + 审批 | 数天配置 | **30 秒** |
| **起步成本** | $$$ + API 密钥 | $$$ + 基础设施 | **$0** |
| **模型锁定** | 单一提供商 | 单一提供商 | **100+ 提供商** |
| **代码库** | 黑盒 | 100K+ 行 | **~56K 行第一方 Python 代码** |
| **语音** | 仅云端 | 未包含 | **离线 Whisper** |
| **记忆** | 仅上下文 | 手动 | **MemPalace 语义记忆** |

**问题：** 如今的 AI 智能体要么锁定在单一提供商，要么需要 ML 工程博士学位才能配置。而且它们都想让你在试用前绑定信用卡。

**解决方案：** Dulus。一个 Python 自主智能体，可连接任何模型 —— 从免费的浏览器会话（Gemini guest、Claude.ai、Kimi、Qwen、DeepSeek）到通过 LiteLLM 的 100+ 付费提供商，再到您自己硬件上的本地模型。~56K 行第一方 Python 代码。无需构建步骤。没有门槛。只有利爪。

---

## 快速开始

### 30 秒安装

```bash
pip install dulus && dulus
```

仅此而已。首次运行时，Dulus 会打开浏览器，捕获一个 **Gemini 访客会话**（无需登录、无需 API 密钥、无需信用卡），你在 30 秒内就能与前沿 AI 对话。

### 一键安装（推荐）

```bash
curl -fsSL https://raw.githubusercontent.com/KevRojo/Dulus/main/install.sh | bash
```

### Docker（无需本地设置）

```bash
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/.env.example
mv .env.example .env
docker compose up -d
```

---

## 功能

| 功能 | 描述 |
|---|---|
| 多提供商 | 11 个原生 + 100+ 通过 LiteLLM |
| 零 API 密钥 | 捕获免费的浏览器会话 |
| 30+ 内置工具 | 文件、shell、网页、OCR、语音等 |
| 自动适配器 | 将任何 Python 仓库安装为插件 |
| MemPalace | 基于 ChromaDB 的语义记忆 |
| 语音 I/O | 通过 Whisper 的离线 STT。多引擎 TTS |
| 子智能体 | 在隔离的 git worktree 中的类型化智能体 |
| 圆桌会议 | 多模型辩论 |
| 沙盒操作系统 | 基于浏览器的迷你操作系统，58 个应用 |
| Telegram 桥接 | 从手机运行 Dulus |
| MCP 支持 | 模型上下文协议 |
| 头脑风暴 | AI 专家委员会 |
| SSJ 模式 | 10 个工作流快捷方式链式执行 |
| 检查点 | 快照和回退任何对话回合 |
| 上下文压缩 | 自动压缩长会话 |
| 本地 OCR | 无需视觉模型令牌即可提取图像文本 |
| 多语言 | `/lang` 命令 — 34 个 ISO 代码 |
| Composio | 1,000+ SaaS 集成 |
| WebBridge | 通过 Playwright 的浏览器自动化 |

---

## 提供商

### 免费（无需 API 密钥）

| 提供商 | 模型 | 设置 |
|---|---|---|
| **Gemini Guest** | gemini-2.0-flash | 打开浏览器 → 输入"你好" → 完成 |
| **Claude.ai** | claude-sonnet-4-6 | 您现有的 claude.ai 会话 |
| **Kimi.com** | kimi-k2.5 | 您现有的 kimi.com 会话 |
| **Qwen** | qwen-max, qwen-plus | 您现有的 qwen.ai 会话 |
| **DeepSeek** | deepseek-chat | 您现有的 deepseek 会话 |
| **NVIDIA NIM** | 14 个模型，每个 40 RPM | 在 build.nvidia.com 免费注册 |
| **Ollama** | 任何本地模型 | `ollama pull qwen2.5-coder` |

### 云 API（需要 API 密钥）

| 提供商 | 模型 | 环境变量 |
|---|---|---|
| Anthropic | claude-opus-4-6, claude-sonnet-4-6 | `ANTHROPIC_API_KEY` |
| OpenAI | gpt-4o, gpt-4o-mini, o3-mini | `OPENAI_API_KEY` |
| Google | gemini-2.5-pro, gemini-2.0-flash | `GEMINI_API_KEY` |
| DeepSeek | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |
| Qwen | qwen-max, qwen-plus, qwq-32b | `DASHSCOPE_API_KEY` |
| Kimi | moonshot-v1-8k/32k/128k, kimi-k2.5 | `MOONSHOT_API_KEY` |
| LiteLLM | 通过单一网关的 100+ 后端 | 后端特定密钥 |

---

## 架构

```
用户输入
    |
    v
dulus.py —— REPL、斜杠命令、语音、Telegram、GUI
    |
    ├── agent.py —— 多轮循环、权限门控、治理
    |       |
    |       ├── providers.py —— 多提供商流式传输
    |       ├── tool_registry.py —— 插件系统
    |       ├── tools.py —— 30+ 内置工具
    |       ├── compaction.py —— 上下文窗口管理
    |       ├── governance.py —— 预算/权限治理
    |       └── multi_agent/ —— 子智能体（群）
    |
    ├── context.py —— 系统提示构建器
    |       └── memory/ —— MemPalace 语义记忆
    |
    ├── skill/ —— 技能系统
    ├── checkpoint/ —— 快照 + 回退
    ├── plugin/ —— 自动适配器插件系统
    ├── voice/ —— STT（Whisper）+ TTS（多引擎）
    ├── task/ —— 任务管理
    ├── webbridge/ —— Playwright 浏览器自动化
    └── dulus_mcp/ —— MCP 客户端
```

---

## 群（子智能体）

Dulus 可以生成在**隔离的 git worktree**中工作的类型化智能体。

```
/agents
Agent(type="coder",    task="refactor auth")
Agent(type="reviewer", task="review #042")
Agent(type="tester",   task="run e2e on auth")
```

---

## 权限

| 模式 | 行为 |
|---|---|
| `auto` *(默认)* | 读取始终允许。写入/shell 前询问。 |
| `accept-all` | 无提示。全部自动批准。**YOLO。** |
| `manual` | 每个操作都询问。 |
| `plan` | 只读。仅计划文件可写。 |

---

## 斜杠命令

| 命令 | 描述 |
|---|---|
| `/model [名称]` | 显示或切换模型 |
| `/memory [查询]` | 持久语义记忆 |
| `/voice` | 语音输入（离线 Whisper） |
| `/brainstorm [主题]` | 幽灵委员会 |
| `/ssj` | 超级赛亚人模式（10 个快捷方式） |
| `/telegram [令牌] [ID]` | Telegram 桥接 |
| `/checkpoint [ID]` | 列出/回退检查点 |
| `/plan [描述]` | 进入/退出计划模式 |
| `/lang [代码]` | 切换语言（34 个代码） |
| `/cost` | 消耗的令牌和 USD |
| `/help` | 所有命令 |

---

## 许可证

GPLv3。分叉、修改、再分发 —— 但保持开放。

> *以鸟命名，而非火箭。我们继续飞翔。*

---

<div align="center">

<p><sub>用利爪构建：<a href="https://github.com/KevRojo">KevRojo</a> · 圣多明各，多米尼加共和国 · 2026</sub></p>

</div>
