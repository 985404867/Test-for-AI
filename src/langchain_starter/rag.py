"""RAG 检索问答链。

这个文件故意写得清楚一些，方便拆解学习：

1. 读取本地知识库。
2. 切分文档。
3. 创建向量库。
4. 检索相关上下文。
5. 把上下文和问题一起交给模型。
"""

from __future__ import annotations

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.runnables import RunnablePassthrough

from langchain_starter.config import Settings
from langchain_starter.context import load_knowledge_file, split_documents
from langchain_starter.llm import create_chat_model, create_embeddings
from langchain_starter.prompts import RAG_PROMPT


def _format_context(documents: list[Document]) -> str:
    """把检索到的文档块合并成提示词里的 context 字符串。"""

    return "\n\n".join(
        f"[来源: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
        for doc in documents
    )


def build_retriever(settings: Settings):
    """构建一个内存里的 FAISS 检索器。

    入门项目每次运行都会重新创建向量库，逻辑最直观。
    如果知识库很大，可以把 FAISS 保存到磁盘，避免每次重新向量化。
    """

    documents = load_knowledge_file(settings.knowledge_path)
    chunks = split_documents(documents)
    embeddings = create_embeddings(settings)
    vector_store = FAISS.from_documents(chunks, embeddings)
    return vector_store.as_retriever(search_kwargs={"k": settings.retriever_k})


def ask_with_rag(question: str, settings: Settings) -> str:
    """执行一次 RAG 问答。"""

    retriever = build_retriever(settings)
    model = create_chat_model(settings)

    chain = (
        {
            "context": retriever | _format_context,
            "question": RunnablePassthrough(),
        }
        | RAG_PROMPT
        | model
    )

    response = chain.invoke(question)
    return response.content

