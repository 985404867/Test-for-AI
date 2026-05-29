# LangChain Starter

这是一个可直接在 PyCharm 里运行和改造的 Python LangChain 项目，目标是把常见能力拆开：配置、模型、RAG、联网搜索、Agent、GUI 和 Web 前端都放在独立模块里，方便逐步学习和维护。

## 主要能力

- 普通聊天
- 本地知识库 RAG
- Tool Calling Agent
- 联网搜索
- 桌面 GUI 对话
- React Web 对话
- 会话持久化、重命名、删除、恢复
- 流式输出和工具调用展示

## 目录结构

```text
langchain_starter/
├── .env.example                 # 环境变量示例
├── main.py                      # 命令行入口
├── data/
│   └── knowledge/               # 示例知识库目录，可放 Markdown、文本和 SQL
│       └── project.md           # 项目说明示例知识
├── src/langchain_starter/
│   ├── config.py                # 配置读取
│   ├── llm.py                   # 大模型与 Embedding
│   ├── prompts.py               # 提示词模板
│   ├── context.py               # 上下文加载与切分
│   ├── rag.py                   # RAG 检索链
│   ├── web_search.py            # 联网搜索实现
│   ├── tools.py                 # Agent Tools
│   ├── agent.py                 # Tool Calling Agent
│   ├── chat.py                  # 普通聊天链
│   ├── storage.py               # SQLite 会话存储
│   ├── time_context.py          # 当前日期时间上下文
│   ├── logging_config.py        # 日志配置
│   ├── web_server.py            # Web API + 静态服务
│   └── static/                  # React 前端资源
└── tests/                       # 基础测试
```

## 安装

建议先创建虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

复制环境变量文件：

```bash
cp .env.example .env
```

然后按你的接口填好 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` 等配置。

## 运行

普通聊天：

```bash
python main.py chat "用三句话解释 LangChain 是什么"
```

RAG 问答：

```bash
python main.py rag "这个项目的配置应该从哪里改？"
```

终端交互模式：

```bash
python main.py interactive
```

Agent 模式：

```bash
python main.py agent "这个项目如何运行？"
python main.py agent-interactive
```

桌面 GUI：

```bash
python main.py gui
```

React Web 界面：

```bash
python main.py web
```

## Web 界面说明

Web 界面默认支持：

- Agent 模式
- 联网搜索
- 流式输出
- 工具调用卡片
- 历史会话切换
- 会话搜索、重命名、删除、恢复

会话和消息会保存在 SQLite：

```text
data/conversations.sqlite3
```

删除会话默认是软删除，回收站里可以恢复；如果要永久删除，可以在回收站中直接清理。

## 知识库目录

默认知识库路径是：

```text
data/knowledge/
```

RAG 会递归读取该目录下的 `.md`、`.txt`、`.sql` 文件。你可以把项目文档、数据开发说明、常用 SQL、表结构说明放进去。仍然可以把 `KNOWLEDGE_PATH` 配成单个文件，例如 `data/knowledge/project.md`，旧的单文件模式也兼容。

## 运行时数据

以下目录和文件属于运行时数据，已经加入 `.gitignore`：

- `data/conversations.sqlite3`
- `data/faiss_cache/`
- `data/logs/`

## 测试

```bash
pytest
```

## 常改位置

- 改模型和接口：`.env`
- 改提示词：`src/langchain_starter/prompts.py`
- 改联网搜索：`src/langchain_starter/web_search.py`
- 改 Agent 工具：`src/langchain_starter/tools.py`
- 改 Agent 流程：`src/langchain_starter/agent.py`
- 改会话存储：`src/langchain_starter/storage.py`
- 改 Web 前端：`src/langchain_starter/static/`
- 改入口命令：`main.py`
