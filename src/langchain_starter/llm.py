"""模型创建层。

这里专门负责创建 Chat Model 和 Embedding Model。
如果以后你想从 OpenAI 换到兼容服务，优先改 config.py 和这里。
"""

from __future__ import annotations

import hashlib
import math
import re

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

    def _tokenize(self, text: str) -> list[str]:
        """生成适合中英文混合文本的轻量 token。"""
        normalized = text.lower()
        # 英文和数字按连续单词保留，中文按单字切开。
        # 这样可以兼顾英文短语检索和中文没有空格分词的常见场景。
        tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", normalized)
        if not tokens:
            return [normalized] if normalized else [""]

        features = list(tokens)
        # 额外加入 2-gram 和 3-gram，保留“知识库”“本地知识”这类中文短语信号。
        # 纯单字容易召回太宽，n-gram 可以让相关中文句子更靠近。
        for size in (2, 3):
            features.extend(
                "".join(tokens[index : index + size])
                for index in range(len(tokens) - size + 1)
            )
        return features

    def _embed(self, text: str) -> list[float]:
        """把单段文本编码成归一化向量，供本地 FAISS 检索使用。"""
        vector = [0.0] * self.dimensions
        for token in self._tokenize(text):
            # 使用稳定哈希把 token 映射到固定维度；同一个 token 永远落在同一格。
            # digest 第 5 个字节决定正负号，减少不同 token 撞到同一维度时的单向累加偏差。
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        # 归一化后，向量相似度主要反映 token 方向相近，而不是文本长短。
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
