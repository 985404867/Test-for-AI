"""RAG 检索问答链。

这个文件故意写得清楚一些，方便拆解学习：

1. 读取本地知识库。
2. 切分文档。
3. 创建向量库。
4. 检索相关上下文。
5. 把上下文和问题一起交给模型。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.runnables import RunnablePassthrough

from langchain_starter.config import Settings
from langchain_starter.context import load_knowledge_file, split_documents
from langchain_starter.llm import create_chat_model, create_embeddings
from langchain_starter.prompts import RAG_PROMPT
from langchain_starter.time_context import current_datetime_context

logger = logging.getLogger(__name__)
CACHE_DIR = Path("data/faiss_cache")
META_FILE = CACHE_DIR / "metadata.json"


def _format_context(documents: list[Document]) -> str:
    """把检索到的文档块合并成提示词里的 context 字符串。"""

    return "\n\n".join(
        f"[来源: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
        for doc in documents
    )


def _knowledge_signature(settings: Settings) -> dict[str, object]:
    knowledge_path = settings.knowledge_path
    stat = knowledge_path.stat()
    return {
        "knowledge_path": str(knowledge_path.resolve()),
        "mtime": stat.st_mtime,
        "size": stat.st_size,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
    }


def _load_cached_vector_store(settings: Settings, embeddings):
    if not META_FILE.exists():
        return None

    try:
        metadata = json.loads(META_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if metadata != _knowledge_signature(settings):
        return None

    try:
        logger.info("Loading FAISS index from %s", CACHE_DIR)
        return FAISS.load_local(
            str(CACHE_DIR),
            embeddings,
            allow_dangerous_deserialization=True,
        )
    except Exception as exc:  # noqa: BLE001 - cache should never break RAG.
        logger.warning("Failed to load FAISS cache: %s", exc)
        return None


def _save_vector_store(settings: Settings, vector_store: FAISS) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        vector_store.save_local(str(CACHE_DIR))
        META_FILE.write_text(
            json.dumps(_knowledge_signature(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Saved FAISS index cache to %s", CACHE_DIR)
    except Exception as exc:  # noqa: BLE001 - cache save failure is non-fatal.
        logger.warning("Failed to save FAISS cache: %s", exc)


def build_retriever(settings: Settings):
    """构建一个内存里的 FAISS 检索器。

    入门项目每次运行都会重新创建向量库，逻辑最直观。
    如果知识库很大，可以把 FAISS 保存到磁盘，避免每次重新向量化。
    """

    embeddings = create_embeddings(settings)
    vector_store = _load_cached_vector_store(settings, embeddings)
    if vector_store is None:
        logger.info("Building FAISS index from knowledge file")
        documents = load_knowledge_file(settings.knowledge_path)
        chunks = split_documents(documents)
        vector_store = FAISS.from_documents(chunks, embeddings)
        _save_vector_store(settings, vector_store)

    return vector_store.as_retriever(search_kwargs={"k": settings.retriever_k})


def retrieve_knowledge_context(question: str, settings: Settings) -> str:
    """检索本地知识库，返回可直接放进提示词或工具结果的上下文。"""

    retriever = build_retriever(settings)
    documents = retriever.invoke(question)
    return _format_context(documents)


def ask_with_rag(question: str, settings: Settings) -> str:
    """执行一次 RAG 问答。"""

    retriever = build_retriever(settings)
    model = create_chat_model(settings)

    chain = (
        {
            "context": retriever | _format_context,
            "question": RunnablePassthrough(),
            "current_datetime": lambda _question: current_datetime_context(),
        }
        | RAG_PROMPT
        | model
    )

    response = chain.invoke(question)
    return response.content
