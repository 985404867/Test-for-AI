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

    Document 的 metadata 可以放来源、标题、作者等信息。
    这里放 source，方便回答时知道内容来自哪个文件。
    """

    if not path.exists():
        raise FileNotFoundError(f"找不到知识库文件：{path}")

    text = path.read_text(encoding="utf-8")
    return [Document(page_content=text, metadata={"source": str(path)})]


def split_documents(documents: list[Document]) -> list[Document]:
    """把长文档切分成适合检索的小块。

    chunk_size 越大，上下文更完整，但检索不够精细；
    chunk_size 越小，检索更精细，但可能丢失上下文。
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=120,
        separators=["\n## ", "\n### ", "\n\n", "\n", "。", "，", " "],
    )
    return splitter.split_documents(documents)

