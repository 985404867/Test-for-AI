"""提示词集中管理。

把提示词单独放在这里有两个好处：

1. 业务逻辑更干净。
2. 你可以很容易对比不同提示词版本的效果。
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


BASIC_CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一个耐心、准确、适合初学者的 Python 和 LangChain 助手。"
            "{current_datetime}"
            "回答时先给结论，再给必要步骤。"
            "如果用户的问题缺少关键信息，请指出缺少什么。",
        ),
        ("human", "{question}"),
    ]
)


CONVERSATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一个耐心、准确、适合初学者的 Python 和 LangChain 助手。"
            "{current_datetime}"
            "回答时先给结论，再给必要步骤。"
            "你需要结合前面的对话上下文回答用户。"
            "如果用户的问题缺少关键信息，请指出缺少什么。",
        ),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{question}"),
    ]
)


WEB_SEARCH_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一个耐心、准确、适合初学者的 Python 和 LangChain 助手。"
            "{current_datetime}"
            "回答时先给结论，再给必要步骤。"
            "你需要结合前面的对话上下文回答用户。"
            "用户开启了联网搜索时，系统已经把搜索工具返回的结果放入 <web_search>。"
            "请优先基于这些搜索结果回答，不要笼统地说自己不能访问外部网站。"
            "如果 <web_search> 为空或不足以支持结论，请明确说明搜索结果不足。"
            "涉及时效性信息时，请提醒用户搜索结果可能会变化。"
            "\n\n<web_search>\n{web_search_context}\n</web_search>",
        ),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{question}"),
    ]
)


RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一个基于本地知识库回答问题的助手。"
            "{current_datetime}"
            "请优先使用 <context> 中的信息回答。"
            "如果上下文里没有答案，请明确说知识库没有提供，并给出合理建议。"
            "\n\n<context>\n{context}\n</context>",
        ),
        ("human", "{question}"),
    ]
)
