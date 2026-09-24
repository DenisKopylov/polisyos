"""Internal, source-preserving syntax helpers for Markdown table consumers."""

from __future__ import annotations

import re


def split_markdown_table_row(text: str) -> list[str]:
    """Split a row at unescaped pipes outside matched inline-code spans.

    Backtick spans use equal-length maximal runs; unmatched runs are literal.
    Backslashes escape the next character outside code and are literal inside
    code. Optional outer delimiter pipes and padding outside those delimiters
    are omitted. Empty cells and every character inside a cell are preserved,
    including whitespace, escapes and backticks. This does not render Markdown
    or validate column roles, row shape, provenance or authority.

    Args:
        text: One Markdown table row, with or without outer delimiter pipes.

    Returns:
        Source slices for the cells, without unescaping or trimming their text.
    """
    runs = list(re.finditer(r"`+", text))
    next_end_by_width: dict[int, int] = {}
    code_runs: dict[int, tuple[int, int | None]] = {}
    for run in reversed(runs):
        width = run.end() - run.start()
        code_runs[run.start()] = (run.end(), next_end_by_width.get(width))
        next_end_by_width[width] = run.end()

    cells: list[str] = []
    start = 0
    index = 0
    while index < len(text):
        character = text[index]
        if character == "\\":
            index += 2
            continue
        if index in code_runs:
            run_end, closing_end = code_runs[index]
            index = closing_end if closing_end is not None else run_end
            continue
        if character == "|":
            cells.append(text[start:index])
            start = index + 1
        index += 1
    cells.append(text[start:])

    if len(cells) > 1 and not cells[0].strip():
        cells.pop(0)
    if len(cells) > 1 and not cells[-1].strip():
        cells.pop()
    return cells
