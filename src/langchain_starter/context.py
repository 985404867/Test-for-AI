"""上下文和知识库加载层。

RAG 的核心思想是：

1. 先把本地文档切成小块。
2. 把每个小块转成向量。
3. 用户提问时，先检索最相关的小块。
4. 把检索到的上下文塞进提示词，再交给大模型回答。
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def load_knowledge_file(path: Path) -> list[Document]:
    """读取 Markdown 知识库文件，并包装成 LangChain Document。

    场景：RAG 构建向量索引前，先把本地文档转成标准文档对象。
    """

    if not path.exists():
        raise FileNotFoundError(f"找不到知识库文件：{path}")

    text = path.read_text(encoding="utf-8")
    return [Document(page_content=text, metadata={"source": str(path)})]


def split_documents(documents: list[Document]) -> list[Document]:
    """把长文档切分成适合检索的小块。

    场景：知识库索引、RAG 检索、长文档分段召回。
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=120,
        separators=["\n## ", "\n### ", "\n\n", "\n", "。", "，", " "],
    )
    return splitter.split_documents(documents)
