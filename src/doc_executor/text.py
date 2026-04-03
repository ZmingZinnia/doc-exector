from typing import Iterable


def lines_to_text(lines: Iterable[str]) -> str:
    text = ""
    index = 0
    for line in lines:
        if index > 0:
            text += "\n"
        text += line
        index += 1
    if text:
        text += "\n"
    return text
