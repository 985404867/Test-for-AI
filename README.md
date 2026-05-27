# LangChain Starter

这是一个适合在 PyCharm 里拆解学习的 Python LangChain 项目。项目把“配置链接、上下文、提示词、模型调用、RAG 检索、命令行入口”拆成了独立文件，方便你逐步修改。

## 目录结构

```text
langchain_starter/
├── .env.example                 # 环境变量示例：API Key、模型名、兼容接口地址等
├── requirements.txt             # Python 依赖
├── pyproject.toml               # 项目基础配置
├── main.py                      # 命令行入口，PyCharm 可直接运行
├── data/
│   └── knowledge.md             # 示例知识库，上下文/RAG 从这里读取
├── src/langchain_starter/
│   ├── config.py                # 所有可修改配置集中在这里读取
│   ├── llm.py                   # 创建大模型和 Embedding
│   ├── prompts.py               # 提示词模板集中管理
│   ├── context.py               # 上下文文档加载与切分
│   ├── rag.py                   # RAG 检索问答链
│   ├── web_search.py            # 联网搜索工具
│   ├── web_server.py            # React Web 对话界面服务
│   ├── static/                  # React 前端页面
│   └── chat.py                  # 普通聊天链
└── tests/
    └── test_config.py           # 一个很小的配置测试示例
```

## 在 PyCharm 中打开

1. 打开 PyCharm。
2. 选择 `Open`。
3. 打开这个文件夹：`/Users/zhangyuqi/Desktop/codex/lanchain/langchain_starter`
4. PyCharm 会把它识别为一个 Python 项目。

## 安装依赖

建议先创建虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置 API

复制环境变量文件：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```env
OPENAI_API_KEY=你的_api_key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=https://api.deepseek.com
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_MAX_TOKENS=8192
AUTO_CONTINUE_ENABLED=true
AUTO_CONTINUE_MAX_ROUNDS=4
WEB_SEARCH_ENABLED=true
WEB_SEARCH_PROVIDER=baidu
WEB_SEARCH_FETCH_PAGES=true
```

如果你使用的是 OpenAI 兼容接口，比如某些代理或自建网关，可以填写：

```env
OPENAI_BASE_URL=https://你的兼容接口/v1
```

## 运行

普通聊天：

```bash
python main.py chat "用三句话解释 LangChain 是什么"
```

基于本地知识库的 RAG 问答：

```bash
python main.py rag "这个项目的配置应该从哪里改？"
```

交互模式：

```bash
python main.py interactive
```

在交互模式里使用联网搜索：

```text
/search 今天 LangChain 有什么新版本变化？
```

桌面对话框：

```bash
python main.py gui
```

React Web 对话界面：

```bash
python main.py web
```

启动后访问终端里显示的本地地址，例如 `http://127.0.0.1:8000`。

在桌面对话框里，需要实时信息时勾选“联网搜索”。
普通对话和联网搜索回答会流式输出；如果回答仍然偏短，可以调大 `.env` 里的
`OPENAI_MAX_TOKENS`，例如 `8192` 或服务商允许的更大值。留空则不主动传输出长度限制。
如果模型仍然因为服务商单次上限被截断，`AUTO_CONTINUE_ENABLED=true` 会自动续写并拼接结果。
代理关闭后建议使用 `WEB_SEARCH_PROVIDER=baidu`；如果在可访问 DuckDuckGo 的网络里，
可以改为 `duckduckgo` 或 `auto`。

联网搜索默认会搜索网页，并尽量抓取前几个结果页的正文摘录。部分网站会阻止程序抓取，
这时回答会只能基于搜索摘要。

## 你最常改的地方

- 改模型或接口地址：`.env`
- 改 RAG 向量方式：`.env` 里的 `EMBEDDING_PROVIDER`
- 改大模型参数：`src/langchain_starter/config.py`
- 改提示词：`src/langchain_starter/prompts.py`
- 改知识库内容：`data/knowledge.md`
- 改 RAG 流程：`src/langchain_starter/rag.py`
- 改联网搜索逻辑：`src/langchain_starter/web_search.py`
- 改 React Web 界面：`src/langchain_starter/static/`
- 改入口逻辑：`main.py`
