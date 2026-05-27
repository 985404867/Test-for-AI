"""项目入口文件。

你可以在 PyCharm 里右键运行这个文件，也可以在终端里执行：

    python main.py chat "你好"
    python main.py rag "这个项目如何修改提示词？"
    python main.py interactive
    python main.py gui
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

# 让 `python main.py ...` 和 PyCharm 直接运行 main.py 都能找到 src 里的包。
# 更正式的做法是 `pip install -e .`，但入门项目保留这个小兼容会更省心。
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from langchain_starter.chat import (
    ask_chat,
    prepare_web_search_context,
    stream_conversation,
    stream_conversation_with_search_context,
)
from langchain_starter.config import load_settings
from langchain_starter.gui import run_chat_window
from langchain_starter.rag import ask_with_rag


def build_parser() -> argparse.ArgumentParser:
    """集中定义命令行参数，后面想加新命令时只改这里。"""

    parser = argparse.ArgumentParser(description="LangChain starter project")
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat_parser = subparsers.add_parser("chat", help="普通大模型问答，不读取知识库")
    chat_parser.add_argument("question", help="你要问模型的问题")

    rag_parser = subparsers.add_parser("rag", help="基于 data/knowledge.md 的 RAG 问答")
    rag_parser.add_argument("question", help="你要基于知识库提问的问题")

    subparsers.add_parser("interactive", help="终端交互模式，可连续提问")
    subparsers.add_parser("gui", help="打开桌面对话框，可连续对话")
    return parser


def run_interactive() -> None:
    """一个最小交互循环，方便你在 PyCharm 里边跑边改。"""

    settings = load_settings()
    history = []
    print(
        "进入交互模式。输入 /exit 退出，"
        "输入 /rag 问题 使用知识库检索，输入 /search 问题 使用联网搜索。"
    )

    while True:
        user_input = input("\n你：").strip()
        if user_input in {"/exit", "exit", "quit"}:
            print("已退出。")
            return

        if user_input.startswith("/rag "):
            question = user_input.removeprefix("/rag ").strip()
            answer = ask_with_rag(question, settings)
            print(f"\nAI：{answer}")
        elif user_input.startswith("/search "):
            question = user_input.removeprefix("/search ").strip()
            search_context = prepare_web_search_context(question, settings)
            print("\nAI：", end="", flush=True)
            chunks = []
            for chunk in stream_conversation_with_search_context(
                question, history, search_context, settings
            ):
                chunks.append(chunk)
                print(chunk, end="", flush=True)
            print()
            answer = "".join(chunks)
            history = [*history, HumanMessage(content=question), AIMessage(content=answer)]
        elif settings.web_search_enabled:
            search_context = prepare_web_search_context(user_input, settings)
            print("\nAI：", end="", flush=True)
            chunks = []
            for chunk in stream_conversation_with_search_context(
                user_input, history, search_context, settings
            ):
                chunks.append(chunk)
                print(chunk, end="", flush=True)
            print()
            answer = "".join(chunks)
            history = [*history, HumanMessage(content=user_input), AIMessage(content=answer)]
        else:
            print("\nAI：", end="", flush=True)
            chunks = []
            for chunk in stream_conversation(user_input, history, settings):
                chunks.append(chunk)
                print(chunk, end="", flush=True)
            print()
            answer = "".join(chunks)
            history = [*history, HumanMessage(content=user_input), AIMessage(content=answer)]


def main() -> None:
    """根据命令选择普通聊天、RAG 问答或交互模式。"""

    args = build_parser().parse_args()
    settings = load_settings()

    if args.command == "chat":
        print(ask_chat(args.question, settings))
    elif args.command == "rag":
        print(ask_with_rag(args.question, settings))
    elif args.command == "interactive":
        run_interactive()
    elif args.command == "gui":
        run_chat_window(settings)


if __name__ == "__main__":
    main()
