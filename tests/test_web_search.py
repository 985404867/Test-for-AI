from pathlib import Path

from langchain_starter.config import Settings
from langchain_starter.web_search import (
    SearchResult,
    _extract_baidu_results,
    _extract_bing_results,
    _extract_duckduckgo_html_results,
    _extract_sogou_results,
    format_search_context,
    search_web,
)


def _settings() -> Settings:
    return Settings(
        openai_api_key="test-key",
        openai_model="gpt-4.1-mini",
        openai_base_url=None,
        openai_temperature=0.2,
        openai_max_tokens=8192,
        auto_continue_enabled=True,
        auto_continue_max_rounds=4,
        embedding_provider="local",
        embedding_model="text-embedding-3-small",
        retriever_k=4,
        knowledge_path=Path("data/knowledge.md"),
        web_search_enabled=True,
        web_search_provider="bing",
        web_search_max_results=2,
        web_search_timeout=8,
        web_search_fetch_pages=False,
        web_search_page_chars=1600,
    )


def test_extract_duckduckgo_html_results() -> None:
    html = """
    <div class="result">
      <h2><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdoc">示例文档</a></h2>
      <a class="result__snippet">这是摘要</a>
    </div></div>
    """

    results = _extract_duckduckgo_html_results(html)

    assert results == [
        SearchResult(title="示例文档", snippet="这是摘要", url="https://example.com/doc")
    ]


def test_extract_baidu_results() -> None:
    html = """
    <h3><a href="/link?url=abc">百度结果</a></h3>
    <div>结果摘要内容</div>
    """

    results = _extract_baidu_results(html)

    assert results[0].title == "百度结果"
    assert results[0].url == "https://www.baidu.com/link?url=abc"
    assert "结果摘要内容" in results[0].snippet


def test_extract_sogou_results() -> None:
    html = """
    <div class="vrwrap">
      <h3><a href="//example.com/sogou">搜狗结果</a></h3>
      <p>搜狗摘要</p>
    </div>
    """

    results = _extract_sogou_results(html)

    assert results[0].title == "搜狗结果"
    assert results[0].url == "https://example.com/sogou"
    assert "搜狗摘要" in results[0].snippet


def test_extract_bing_results() -> None:
    html = """
    <li class="b_algo">
      <h2><a href="https://example.com/bing">Bing 结果</a></h2>
      <p>Bing 摘要</p>
    </li>
    """

    results = _extract_bing_results(html)

    assert results == [
        SearchResult(title="Bing 结果", snippet="Bing 摘要", url="https://example.com/bing")
    ]


def test_search_web_deduplicates_and_limits_results(monkeypatch) -> None:
    settings = _settings()

    def fake_bing(query: str, settings: Settings) -> list[SearchResult]:
        return [
            SearchResult("A", "a", "https://example.com/a"),
            SearchResult("A again", "a2", "https://example.com/a"),
            SearchResult("B", "b", "https://example.com/b"),
            SearchResult("C", "c", "https://example.com/c"),
        ]

    monkeypatch.setattr("langchain_starter.web_search._search_bing_html", fake_bing)

    results = search_web("test", settings)

    assert [result.url for result in results] == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_format_search_context_includes_page_text() -> None:
    context = format_search_context(
        [SearchResult("标题", "摘要", "https://example.com", page_text="正文")]
    )

    assert "标题" in context
    assert "网页正文摘录：正文" in context
