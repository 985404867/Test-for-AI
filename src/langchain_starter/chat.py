"""普通聊天链。

这个模块不读取知识库，只演示最基础的：

Prompt -> Model -> Answer
"""

from __future__ import annotations

from collections.abc import Iterator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from langchain_starter.config import Settings
from langchain_starter.llm import create_chat_model
from langchain_starter.prompts import (
    BASIC_CHAT_PROMPT,
    CONVERSATION_PROMPT,
    WEB_SEARCH_PROMPT,
)
from langchain_starter.web_search import format_search_context, search_web


TRUNCATED_FINISH_REASONS = {"length", "max_tokens", "max_completion_tokens"}
CONTINUE_QUESTION = (
    "请从上一条回答被截断的位置继续输出，不要重复已经写过的内容，"
    "不要重新开头，直接接着未完成的句子或段落继续。"
)


def _chunk_to_text(content: object) -> str:
    """Normalize streamed model chunks to plain text."""

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


def _chunk_finish_reason(chunk: object) -> str | None:
    """Extract finish_reason from common LangChain/OpenAI chunk shapes."""

    response_metadata = getattr(chunk, "response_metadata", None) or {}
    finish_reason = response_metadata.get("finish_reason")
    if finish_reason:
        return str(finish_reason)

    generation_info = getattr(chunk, "generation_info", None) or {}
    finish_reason = generation_info.get("finish_reason")
    if finish_reason:
        return str(finish_reason)

    return None


def ask_chat(question: str, settings: Settings) -> str:
    """调用普通聊天链并返回字符串答案。"""

    model = create_chat_model(settings)
    chain = BASIC_CHAT_PROMPT | model
    response = chain.invoke({"question": question})
    return response.content


def ask_conversation(
    question: str, history: list[BaseMessage], settings: Settings
) -> tuple[str, list[BaseMessage]]:
    """调用带上下文的聊天链，并返回答案和更新后的历史。"""

    answer = "".join(stream_conversation(question, history, settings))
    updated_history = [*history, HumanMessage(content=question), AIMessage(content=answer)]
    return answer, updated_history


def _stream_with_auto_continue(
    *,
    prompt,
    question: str,
    history: list[BaseMessage],
    settings: Settings,
    extra_inputs: dict[str, str] | None = None,
) -> Iterator[str]:
    """Stream once, then continue automatically if the provider reports truncation."""

    current_history = list(history)
    current_question = question
    rounds = settings.auto_continue_max_rounds if settings.auto_continue_enabled else 0

    for round_index in range(rounds + 1):
        model = create_chat_model(settings)
        chain = prompt | model
        inputs = {
            "question": current_question,
            "history": current_history,
            **(extra_inputs or {}),
        }
        finish_reason = None
        chunks: list[str] = []

        for chunk in chain.stream(inputs):
            finish_reason = _chunk_finish_reason(chunk) or finish_reason
            text = _chunk_to_text(chunk.content)
            if text:
                chunks.append(text)
                yield text

        answer_part = "".join(chunks)
        if finish_reason not in TRUNCATED_FINISH_REASONS:
            break
        if round_index >= rounds:
            yield "\n\n[提示：模型服务达到单次输出上限，自动续写轮次已用完。]\n"
            break

        current_history = [
            *current_history,
            HumanMessage(content=current_question),
            AIMessage(content=answer_part),
        ]
        current_question = CONTINUE_QUESTION


def stream_conversation(
    question: str, history: list[BaseMessage], settings: Settings
) -> Iterator[str]:
    """Stream a conversation answer chunk by chunk."""

    yield from _stream_with_auto_continue(
        prompt=CONVERSATION_PROMPT,
        question=question,
        history=history,
        settings=settings,
    )


def ask_conversation_with_search(
    question: str, history: list[BaseMessage], settings: Settings
) -> tuple[str, list[BaseMessage], str]:
    """Search the web first, then answer with conversation history and sources."""

    search_results = search_web(question, settings)
    web_search_context = format_search_context(search_results)

    answer = "".join(
        stream_conversation_with_search_context(
            question,
            history,
            web_search_context,
            settings,
        )
    )
    updated_history = [*history, HumanMessage(content=question), AIMessage(content=answer)]
    return answer, updated_history, web_search_context


def prepare_web_search_context(question: str, settings: Settings) -> str:
    """Run web search and format its results for the prompt."""

    search_results = search_web(question, settings)
    return format_search_context(search_results)


def stream_conversation_with_search_context(
    question: str,
    history: list[BaseMessage],
    web_search_context: str,
    settings: Settings,
) -> Iterator[str]:
    """Stream an answer using previously prepared web search context."""

    yield from _stream_with_auto_continue(
        prompt=WEB_SEARCH_PROMPT,
        question=question,
        history=history,
        settings=settings,
        extra_inputs={"web_search_context": web_search_context},
    )
