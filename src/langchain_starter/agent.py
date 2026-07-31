"""Tool-calling agent powered by LangChain's agent graph."""

from __future__ import annotations

from collections.abc import Callable

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from langchain_starter.config import Settings
from langchain_starter.llm import create_chat_model
from langchain_starter.time_context import current_datetime_context
from langchain_starter.tools import create_agent_tools
from langchain_starter.chat import (
    prepare_web_search_context,
    stream_conversation_with_search_context,
)


AGENT_SYSTEM_PROMPT = (
    "你是一个严谨、实用的 LangChain Agent 助手。"
    "你可以根据问题自主选择工具："
    "需要实时、外部或最新信息时使用 web_search；"
    "需要查询本地项目知识库时使用 local_knowledge_search。"
    "当用户询问现在、当前、今天、最新或是否仍可用时，必须以当前日期对应年份的来源为准；"
    "若工具结果只包含旧年份或年份冲突，不得把它写成当前结论，应明确说明无法确认并建议查看官方来源。"
    "工具返回的信息要整合成自然回答，不要直接原样倾倒。"
    "如果工具结果不足以支持结论，请明确说明不确定。"
    "回答时先给结论，再给必要步骤。"
)


ToolEventCallback = Callable[[dict], None]


def _message_content_to_text(content: object) -> str:
    """把 Agent 返回的多种 content 结构统一成纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(content) if content else ""


def create_tool_calling_agent(
    settings: Settings,
    on_tool_event: ToolEventCallback | None = None,
):
    """创建 Tool Calling Agent 图，供 CLI、GUI 和 Web 复用。"""

    system_prompt = f"{current_datetime_context()}{AGENT_SYSTEM_PROMPT}"
    return create_agent(
        model=create_chat_model(settings),
        tools=create_agent_tools(settings, on_tool_event=on_tool_event),
        system_prompt=system_prompt,
    )


def ask_agent(
    question: str,
    history: list[BaseMessage],
    settings: Settings,
    on_tool_event: ToolEventCallback | None = None,
) -> tuple[str, list[BaseMessage]]:
    """运行 Agent 并返回答案与更新后的历史记录。"""

    try:
        agent = create_tool_calling_agent(settings, on_tool_event=on_tool_event)
        result = agent.invoke({"messages": [*history, HumanMessage(content=question)]})
        messages = result.get("messages", [])
        answer = ""
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                answer = _message_content_to_text(message.content)
                break
    except Exception as exc:
        if on_tool_event is not None:
            on_tool_event(
                {
                    "phase": "error",
                    "tool": "agent",
                    "input": question,
                    "error": f"Agent 工具调用失败，已切换为联网搜索兜底：{exc}",
                }
            )
        search_context = prepare_web_search_context(question, settings)
        answer = "".join(
            stream_conversation_with_search_context(
                question,
                history,
                search_context,
                settings,
            )
        )

    if not answer.strip():
        search_context = prepare_web_search_context(question, settings)
        answer = "".join(
            stream_conversation_with_search_context(
                question,
                history,
                search_context,
                settings,
            )
        )

    updated_history = [*history, HumanMessage(content=question), AIMessage(content=answer)]
    return answer, updated_history
