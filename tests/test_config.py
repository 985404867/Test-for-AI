from pathlib import Path

import pytest

from langchain_starter.config import Settings, load_settings


def test_settings_can_be_constructed() -> None:
    """验证 Settings 可以在测试环境中正常构造。"""
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
        web_search_provider="baidu",
        web_search_max_results=5,
        web_search_timeout=8,
        web_search_fetch_pages=True,
        web_search_page_chars=1600,
    )

    assert settings.openai_model == "gpt-4.1-mini"
    assert settings.retriever_k == 4


def test_load_settings_reports_invalid_integer_env(monkeypatch) -> None:
    """整数配置写错时应该提示具体环境变量名。"""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("RETRIEVER_K", "many")

    with pytest.raises(RuntimeError, match="RETRIEVER_K 必须是整数"):
        load_settings()


def test_load_settings_reports_invalid_boolean_env(monkeypatch) -> None:
    """布尔配置写错时应该提示具体环境变量名和可用格式。"""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "maybe")

    with pytest.raises(RuntimeError, match="WEB_SEARCH_ENABLED 必须是布尔值"):
        load_settings()
