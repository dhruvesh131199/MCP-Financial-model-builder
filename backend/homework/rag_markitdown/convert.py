"""MarkItDown wrapper for homework ingest."""

from __future__ import annotations

from pathlib import Path


def convert_file_to_markdown(path: Path) -> str:
    from markitdown import MarkItDown

    result = MarkItDown().convert(str(path))
    text = result.text_content or ""
    if not text.strip():
        raise ValueError(f"MarkItDown produced empty output for {path.name}")
    return text


def markdown_stats(text: str) -> tuple[int, int]:
    return len(text), text.count("\n") + (1 if text else 0)
