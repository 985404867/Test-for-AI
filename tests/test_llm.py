import math

from langchain_starter.llm import LocalHashEmbeddings


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right)) / (
        math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    )


def test_local_hash_embeddings_tokenize_chinese_text() -> None:
    """中文文本没有空格时也应该产生字符和 n-gram 特征。"""
    embeddings = LocalHashEmbeddings()

    tokens = embeddings._tokenize("本地知识库检索")

    assert "本" in tokens
    assert "本地" in tokens
    assert "知识库" in tokens


def test_local_hash_embeddings_keep_related_chinese_texts_closer() -> None:
    """相关中文短句的相似度应该高于无关短句。"""
    embeddings = LocalHashEmbeddings(dimensions=1024)

    query = embeddings.embed_query("本地知识库怎么检索")
    related = embeddings.embed_query("知识库检索使用本地向量")
    unrelated = embeddings.embed_query("天气预报和股票价格")

    assert _cosine(query, related) > _cosine(query, unrelated)
