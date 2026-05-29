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

    用来集中保存模型、RAG、联网搜索和持久化相关参数，避免业务代码直接读环境变量。
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
    web_search_provider: str
    web_search_max_results: int
    web_search_timeout: float
    web_search_fetch_pages: bool
    web_search_page_chars: int


def _optional_text(value: str | None) -> str | None:
    """把空字符串统一转成 None，便于传给兼容接口或可选参数。"""

    if value is None or value.strip() == "":
        return None
    return value.strip()


def _optional_bool(value: str | None, default: bool = False) -> bool:
    """解析布尔环境变量，支持 true/false、1/0、yes/no 等常见写法。"""

    # 环境变量未设置或只写空白时，保持调用方给出的默认值。
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    # 明确区分 true/false 两组写法，避免拼错时被静默当成 False。
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"布尔配置值无效：{value!r}")


def _optional_int(value: str | None) -> int | None:
    """把空字符串转成 None，否则转换为整数值。"""

    if value is None or value.strip() == "":
        return None
    return int(value)


def _env_int(name: str, default: str) -> int:
    """读取整数环境变量，并在格式错误时指出变量名。"""
    # 这里统一包装异常，是为了启动失败时能直接看到具体是哪项配置写错。
    value = os.getenv(name, default)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} 必须是整数，当前值为 {value!r}。") from exc


def _env_optional_int(name: str, default: str) -> int | None:
    """读取可选整数环境变量，并在格式错误时指出变量名。"""
    # 例如 OPENAI_MAX_TOKENS 支持留空，留空会传 None 给模型客户端。
    value = os.getenv(name, default)
    try:
        return _optional_int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} 必须是整数或留空，当前值为 {value!r}。") from exc


def _env_float(name: str, default: str) -> float:
    """读取浮点数环境变量，并在格式错误时指出变量名。"""
    # 温度、超时时间这类配置使用浮点数，错误值在这里提前拦截。
    value = os.getenv(name, default)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} 必须是数字，当前值为 {value!r}。") from exc


def _env_bool(name: str, default: bool) -> bool:
    """读取布尔环境变量，并在格式错误时指出变量名。"""
    # _optional_bool 负责具体解析；这里补充变量名，让错误信息对用户可操作。
    value = os.getenv(name)
    try:
        return _optional_bool(value, default)
    except ValueError as exc:
        raise RuntimeError(
            f"{name} 必须是布尔值，可用 true/false、1/0、yes/no，当前值为 {value!r}。"
        ) from exc


def load_settings() -> Settings:
    """从 `.env` 和系统环境变量中加载项目配置。

    场景：启动 CLI、GUI、Web 服务或测试时，都通过这个入口获取统一配置。
    """

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError(
            "请先复制 .env.example 为 .env，并填写 OPENAI_API_KEY。"
        )

    # 所有需要类型转换的环境变量都走专门 helper，避免配置写错时抛出难懂的原生异常。
    return Settings(
        openai_api_key=api_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        openai_base_url=_optional_text(os.getenv("OPENAI_BASE_URL")),
        openai_temperature=_env_float("OPENAI_TEMPERATURE", "0.2"),
        openai_max_tokens=_env_optional_int("OPENAI_MAX_TOKENS", "8192"),
        auto_continue_enabled=_env_bool("AUTO_CONTINUE_ENABLED", True),
        auto_continue_max_rounds=_env_int("AUTO_CONTINUE_MAX_ROUNDS", "4"),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "local").strip().lower(),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small").strip(),
        retriever_k=_env_int("RETRIEVER_K", "4"),
        knowledge_path=Path(os.getenv("KNOWLEDGE_PATH", "data/knowledge")),
        web_search_enabled=_env_bool("WEB_SEARCH_ENABLED", True),
        web_search_provider=os.getenv("WEB_SEARCH_PROVIDER", "auto").strip().lower(),
        web_search_max_results=_env_int("WEB_SEARCH_MAX_RESULTS", "5"),
        web_search_timeout=_env_float("WEB_SEARCH_TIMEOUT", "8"),
        web_search_fetch_pages=_env_bool("WEB_SEARCH_FETCH_PAGES", True),
        web_search_page_chars=_env_int("WEB_SEARCH_PAGE_CHARS", "1600"),
    )
