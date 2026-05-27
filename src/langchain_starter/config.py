"""配置读取层。

这个文件的作用是把所有“可修改配置”集中起来：

- API Key
- 模型名称
- 兼容接口地址
- 温度
- 最大输出长度
- 自动续写配置
- RAG 检索数量
- 知识库文件路径
- 联网搜索配置

以后项目变大时，业务代码不要到处读取环境变量，而是统一使用 Settings。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """项目运行配置。

    frozen=True 表示创建后不再修改，避免运行中某个地方悄悄改配置。
    """

    openai_api_key: str
    openai_model: str
    openai_base_url: str | None
    openai_temperature: float
    openai_max_tokens: int | None
    auto_continue_enabled: bool
    auto_continue_max_rounds: int
    embedding_provider: str
    embedding_model: str
    retriever_k: int
    knowledge_path: Path
    web_search_enabled: bool
    web_search_max_results: int
    web_search_timeout: float
    web_search_fetch_pages: bool
    web_search_page_chars: int


def _optional_text(value: str | None) -> str | None:
    """把空字符串转成 None，方便传给 LangChain/OpenAI 客户端。"""

    if value is None or value.strip() == "":
        return None
    return value.strip()


def _optional_bool(value: str | None, default: bool = False) -> bool:
    """读取布尔环境变量，支持 true/false、1/0、yes/no。"""

    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _optional_int(value: str | None) -> int | None:
    """把空字符串转成 None，否则读取整数。"""

    if value is None or value.strip() == "":
        return None
    return int(value)


def load_settings() -> Settings:
    """从 .env 和系统环境变量中加载配置。

    python-dotenv 会先读取项目根目录的 .env；如果系统环境变量已经存在，
    系统环境变量优先级更高，适合部署时覆盖本地配置。
    """

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError(
            "请先复制 .env.example 为 .env，并填写 OPENAI_API_KEY。"
        )

    return Settings(
        openai_api_key=api_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        openai_base_url=_optional_text(os.getenv("OPENAI_BASE_URL")),
        openai_temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
        openai_max_tokens=_optional_int(os.getenv("OPENAI_MAX_TOKENS", "8192")),
        auto_continue_enabled=_optional_bool(os.getenv("AUTO_CONTINUE_ENABLED"), True),
        auto_continue_max_rounds=int(os.getenv("AUTO_CONTINUE_MAX_ROUNDS", "4")),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "local").strip().lower(),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small").strip(),
        retriever_k=int(os.getenv("RETRIEVER_K", "4")),
        knowledge_path=Path(os.getenv("KNOWLEDGE_PATH", "data/knowledge.md")),
        web_search_enabled=_optional_bool(os.getenv("WEB_SEARCH_ENABLED"), True),
        web_search_max_results=int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5")),
        web_search_timeout=float(os.getenv("WEB_SEARCH_TIMEOUT", "8")),
        web_search_fetch_pages=_optional_bool(os.getenv("WEB_SEARCH_FETCH_PAGES"), True),
        web_search_page_chars=int(os.getenv("WEB_SEARCH_PAGE_CHARS", "1600")),
    )
