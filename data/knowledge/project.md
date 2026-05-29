# LangChain Starter 知识库

## 项目目标

这个项目是一个可拆解的 LangChain Python 示例。它适合用 PyCharm 打开，并通过普通聊天和 RAG 问答理解 LangChain 的基本结构。

## 配置在哪里修改

主要配置放在 `.env` 文件里。你可以修改：

- `OPENAI_API_KEY`：你的 API Key。
- `OPENAI_MODEL`：聊天模型名称。
- `OPENAI_BASE_URL`：OpenAI 兼容接口地址，留空表示使用官方接口。
- `OPENAI_TEMPERATURE`：模型回答的发散程度。
- `RETRIEVER_K`：RAG 检索返回的上下文数量。
- `KNOWLEDGE_PATH`：知识库路径，可以是单个文件，也可以是目录。

Python 代码会通过 `src/langchain_starter/config.py` 读取这些配置。

## 提示词在哪里修改

提示词集中放在 `src/langchain_starter/prompts.py`。

普通聊天使用 `BASIC_CHAT_PROMPT`。
RAG 问答使用 `RAG_PROMPT`。

如果你想让模型更像老师、客服、程序员、翻译助手，可以优先修改这里的 system prompt。

## 上下文在哪里修改

示例知识库目录是 `data/knowledge/`。

RAG 会递归读取目录下的 `.md`、`.txt`、`.sql` 文件，再把它们切分成多个小文本块，然后用向量检索找出和用户问题最相关的内容。

## 模型调用在哪里修改

模型创建逻辑在 `src/langchain_starter/llm.py`。

如果你要改聊天模型，通常只需要改 `.env` 的 `OPENAI_MODEL`。
如果你要改 embedding 模型，可以修改 `create_embeddings` 函数。

## RAG 流程在哪里修改

RAG 主流程在 `src/langchain_starter/rag.py`。

核心步骤是：

1. `load_knowledge_file` 读取知识库。
2. `split_documents` 切分文档。
3. `FAISS.from_documents` 创建向量库。
4. `as_retriever` 创建检索器。
5. `RAG_PROMPT | model` 生成答案。

## 常见扩展方向

- 在 `data/knowledge/` 中增加更多 Markdown、文本、SQL、PDF 或网页资料。
- 把 FAISS 向量库保存到磁盘。
- 增加聊天历史，实现多轮对话。
- 增加 FastAPI，做成网页接口。
- 增加 Streamlit，做成可视化小应用。
