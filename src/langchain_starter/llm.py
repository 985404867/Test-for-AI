"""模型创建层。

这里专门负责创建 Chat Model 和 Embedding Model。
如果以后你想从 OpenAI 换到兼容服务，优先改 config.py 和这里。
"""

from __future__ import annotations

import hashlib
import math

from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from langchain_starter.config import Settings


class LocalHashEmbeddings(Embeddings):
    """本地哈希向量模型。

    场景：当兼容接口没有 embeddings 能力时，仍然可以让 RAG 跑起来。
    """

    def __init__(self, dimensions: int = 384) -> None:
        """初始化向量维度，便于在本地生成固定长度的可检索表示。"""
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        """把单段文本编码成归一化向量，供本地 FAISS 检索使用。"""
        vector = [0.0] * self.dimensions
        tokens = [token for token in text.lower().split() if token.strip()]
        if not tokens:
            tokens = [text.lower()]

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量编码文档文本，供知识库建索引时调用。"""
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """编码查询文本，供检索时与文档向量做相似度匹配。"""
        return self._embed(text)


def create_chat_model(settings: Settings) -> ChatOpenAI:
    """创建聊天模型。

    场景：CLI、GUI、Web、Agent 和 RAG 都通过这里拿到统一的对话模型实例。
    """

    return ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        max_tokens=settings.openai_max_tokens,
    )


def create_embeddings(settings: Settings) -> Embeddings:
    """创建向量模型，供 RAG 构建索引和查询召回使用。

    场景：知识库向量化、缓存重建、检索问题上下文。
    """

    if settings.embedding_provider == "local":
        return LocalHashEmbeddings()

    return OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.embedding_model,
    )
