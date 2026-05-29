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
from langchain_starter.time_context import current_datetime_context
from langchain_starter.web_search import format_search_context, search_web


TRUNCATED_FINISH_REASONS = {"length", "max_tokens", "max_completion_tokens"}
CONTINUE_QUESTION = (
    "请从上一条回答被截断的位置继续输出，不要重复已经写过的内容，"
    "不要重新开头，直接接着未完成的句子或段落继续。"
)


def _chunk_to_text(content: object) -> str:
    """把模型流式返回的 chunk 统一转换成纯文本。"""

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
    """从常见的 LangChain/OpenAI chunk 结构中提取结束原因。"""

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
    """调用普通聊天链并返回完整字符串答案。"""

    model = create_chat_model(settings)
    chain = BASIC_CHAT_PROMPT | model
    response = chain.invoke(
        {
            "question": question,
            "current_datetime": current_datetime_context(),
        }
    )
    return response.content


def ask_conversation(
    question: str, history: list[BaseMessage], settings: Settings
) -> tuple[str, list[BaseMessage]]:
    """调用带历史上下文的聊天链，并返回答案和更新后的会话历史。"""

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
    """先流式输出一次，如被截断则自动续写。

    场景：服务商单次输出上限不足时，尽量拼出完整回答。
    """

    current_history = list(history)
    current_question = question
    rounds = settings.auto_continue_max_rounds if settings.auto_continue_enabled else 0

    for round_index in range(rounds + 1):
        model = create_chat_model(settings)
        chain = prompt | model
        inputs = {
            "question": current_question,
            "history": current_history,
            "current_datetime": current_datetime_context(),
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
    """按 chunk 流式输出普通对话结果。"""

    yield from _stream_with_auto_continue(
        prompt=CONVERSATION_PROMPT,
        question=question,
        history=history,
        settings=settings,
    )


def ask_conversation_with_search(
    question: str, history: list[BaseMessage], settings: Settings
) -> tuple[str, list[BaseMessage], str]:
    """先联网搜索，再结合历史上下文生成回答。"""

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
    """执行联网搜索并整理成可注入提示词的上下文。"""

    search_results = search_web(question, settings)
    return format_search_context(search_results)


def stream_conversation_with_search_context(
    question: str,
    history: list[BaseMessage],
    web_search_context: str,
    settings: Settings,
) -> Iterator[str]:
    """基于已准备好的联网搜索上下文流式输出回答。"""

    yield from _stream_with_auto_continue(
        prompt=WEB_SEARCH_PROMPT,
        question=question,
        history=history,
        settings=settings,
        extra_inputs={"web_search_context": web_search_context},
    )
