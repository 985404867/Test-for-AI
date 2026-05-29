"""LangChain tools used by the agent."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from langchain_core.tools import StructuredTool

from langchain_starter.config import Settings
from langchain_starter.rag import retrieve_knowledge_context
from langchain_starter.web_search import format_search_context, search_web

ToolEventCallback = Callable[[dict], None]
logger = logging.getLogger(__name__)


def _preview_text(value: str, limit: int = 700) -> str:
    """截断工具结果，方便在日志和界面里预览。"""
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def create_agent_tools(
    settings: Settings,
    on_tool_event: ToolEventCallback | None = None,
) -> list[StructuredTool]:
    """创建当前运行配置下可供 Agent 调用的工具集合。"""

    def emit(payload: dict) -> None:
        """把工具状态变化回调给前端或日志层。"""
        if on_tool_event is not None:
            on_tool_event(payload)

    def web_search(query: str) -> str:
        """联网搜索当前信息、外部资料或网页内容。"""

        started_at = time.perf_counter()
        logger.info("Tool web_search start query=%r", query)
        emit({"phase": "start", "tool": "web_search", "input": query})
        try:
            results = search_web(query, settings)
            content = format_search_context(results)
        except Exception as exc:
            elapsed = time.perf_counter() - started_at
            logger.exception("Tool web_search failed elapsed=%.2fs query=%r", elapsed, query)
            emit(
                {
                    "phase": "error",
                    "tool": "web_search",
                    "input": query,
                    "error": str(exc),
                }
            )
            raise

        elapsed = time.perf_counter() - started_at
        logger.info(
            "Tool web_search end elapsed=%.2fs results=%d query=%r",
            elapsed,
            len(results),
            query,
        )
        emit(
            {
                "phase": "end",
                "tool": "web_search",
                "input": query,
                "preview": _preview_text(content),
            }
        )
        return content

    def local_knowledge_search(query: str) -> str:
        """检索项目本地知识库，用于回答仓库内部问题。"""

        started_at = time.perf_counter()
        logger.info("Tool local_knowledge_search start query=%r", query)
        emit({"phase": "start", "tool": "local_knowledge_search", "input": query})
        try:
            context = retrieve_knowledge_context(query, settings)
            content = context if context.strip() else "本地知识库没有检索到相关内容。"
        except Exception as exc:
            elapsed = time.perf_counter() - started_at
            logger.exception(
                "Tool local_knowledge_search failed elapsed=%.2fs query=%r",
                elapsed,
                query,
            )
            emit(
                {
                    "phase": "error",
                    "tool": "local_knowledge_search",
                    "input": query,
                    "error": str(exc),
                }
            )
            raise

        elapsed = time.perf_counter() - started_at
        logger.info(
            "Tool local_knowledge_search end elapsed=%.2fs chars=%d query=%r",
            elapsed,
            len(content),
            query,
        )
        emit(
            {
                "phase": "end",
                "tool": "local_knowledge_search",
                "input": query,
                "preview": _preview_text(content),
            }
        )
        return content

    return [
        StructuredTool.from_function(
            func=web_search,
            name="web_search",
            description=(
                "Search the web for current events, recent facts, external websites, "
                "or anything not guaranteed to be in the local knowledge base. "
                "Input should be a concise search query."
            ),
        ),
        StructuredTool.from_function(
            func=local_knowledge_search,
            name="local_knowledge_search",
            description=(
                "Search the local project knowledge base. Use this for questions about "
                "this starter project, local documentation, configuration, RAG content, "
                "or facts likely stored in data/knowledge/. Input should be the user's question."
            ),
        ),
    ]
