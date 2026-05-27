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
    """Small deterministic embedding model for local RAG demos.

    It is not a semantic embedding model, but it keeps the starter project runnable
    when the selected chat provider does not expose an embeddings endpoint.
    """

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
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
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def create_chat_model(settings: Settings) -> ChatOpenAI:
    """创建聊天模型。

    base_url 是可选项：
    - None：使用官方 OpenAI API
    - 有值：使用 OpenAI 兼容接口，比如代理、自建网关或第三方兼容服务
    """

    return ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        max_tokens=settings.openai_max_tokens,
    )


def create_embeddings(settings: Settings) -> Embeddings:
    """创建向量模型，用于把文本转成向量，供 FAISS 检索。

    默认使用本地 hash embedding，保证 DeepSeek 等只提供聊天模型的兼容接口
    也能跑通 RAG 示例。需要真实语义检索时，把 EMBEDDING_PROVIDER 改成 openai。
    """

    if settings.embedding_provider == "local":
        return LocalHashEmbeddings()

    return OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.embedding_model,
    )
