from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from langchain_starter.context import iter_knowledge_files, load_knowledge_file


def test_load_knowledge_file_keeps_single_file_compatibility() -> None:
    """旧的单文件知识库配置仍然可以读取。"""
    with TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "knowledge.md"
        file_path.write_text("单文件知识库", encoding="utf-8")

        documents = load_knowledge_file(file_path)

    assert documents[0].page_content == "单文件知识库"
    assert documents[0].metadata["source"].endswith("knowledge.md")


def test_load_knowledge_file_reads_supported_files_from_directory() -> None:
    """知识库目录会递归读取 Markdown、文本和 SQL 文件。"""
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "project.md").write_text("项目说明", encoding="utf-8")
        (root / "notes.txt").write_text("开发备注", encoding="utf-8")
        nested = root / "sql"
        nested.mkdir()
        (nested / "table.sql").write_text("select * from users;", encoding="utf-8")
        (nested / "ignore.json").write_text("{}", encoding="utf-8")

        files = iter_knowledge_files(root)
        documents = load_knowledge_file(root)

    assert sorted(file.name for file in files) == ["notes.txt", "project.md", "table.sql"]
    assert {document.page_content for document in documents} == {
        "项目说明",
        "开发备注",
        "select * from users;",
    }


def test_iter_knowledge_files_rejects_unsupported_single_file() -> None:
    """单文件模式下只接受明确支持的文本资料格式。"""
    with TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "data.json"
        file_path.write_text("{}", encoding="utf-8")

        with pytest.raises(ValueError, match="知识库文件类型不支持"):
            iter_knowledge_files(file_path)
