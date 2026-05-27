from pathlib import Path

from langchain_starter.config import Settings


def test_settings_can_be_constructed() -> None:
    settings = Settings(
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
        web_search_enabled=False,
        web_search_max_results=5,
        web_search_timeout=8,
        web_search_fetch_pages=True,
        web_search_page_chars=1600,
    )

    assert settings.openai_model == "gpt-4.1-mini"
    assert settings.retriever_k == 4
