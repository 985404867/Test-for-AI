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


SUPPORTED_KNOWLEDGE_SUFFIXES = {".md", ".txt", ".sql"}


def iter_knowledge_files(path: Path) -> list[Path]:
    """列出知识库路径下可读取的文本资料文件。

    支持两种形态：
    - 单文件：兼容旧的 data/knowledge.md 配置。
    - 目录：递归读取 .md/.txt/.sql，适合数据开发资料、SQL 脚本和项目文档。
    """

    if not path.exists():
        raise FileNotFoundError(f"找不到知识库路径：{path}")

    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_KNOWLEDGE_SUFFIXES:
            raise ValueError(
                f"知识库文件类型不支持：{path}。"
                f"支持类型：{', '.join(sorted(SUPPORTED_KNOWLEDGE_SUFFIXES))}"
            )
        return [path]

    if not path.is_dir():
        raise ValueError(f"知识库路径既不是文件也不是目录：{path}")

    files = sorted(
        item
        for item in path.rglob("*")
        if item.is_file() and item.suffix.lower() in SUPPORTED_KNOWLEDGE_SUFFIXES
    )
    if not files:
        raise FileNotFoundError(
            f"知识库目录没有可读取文件：{path}。"
            f"请放入 {', '.join(sorted(SUPPORTED_KNOWLEDGE_SUFFIXES))} 文件。"
        )
    return files


def load_knowledge_file(path: Path) -> list[Document]:
    """读取知识库文件或目录，并包装成 LangChain Document。

    场景：RAG 构建向量索引前，先把本地文档转成标准文档对象。
    """

    documents = []
    for file_path in iter_knowledge_files(path):
        text = file_path.read_text(encoding="utf-8")
        if not text.strip():
            continue
        documents.append(Document(page_content=text, metadata={"source": str(file_path)}))

    if not documents:
        raise ValueError(f"知识库路径没有非空文本内容：{path}")
    return documents


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
