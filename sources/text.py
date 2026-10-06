"""Turn ATS description HTML into plain text that keeps line structure.

Line breaks matter: the YoE extractor works sentence by sentence and looks for
"Requirements"-style headings, so block tags become newlines and list items
become "- " lines instead of being glued together.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_BLOCK = {"p", "div", "br", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article"}
_SKIP = {"script", "style"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self._skip_depth += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(markup: str | None) -> str:
    if not markup:
        return ""
    # Greenhouse double-encodes: the HTML itself arrives entity-escaped.
    if "&lt;" in markup and "<" not in markup:
        markup = html.unescape(markup)
    parser = _TextExtractor()
    parser.feed(markup)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    out: list[str] = []
    pending_bullet = False
    for line in lines:
        # <li><p>text</p></li> leaves the bullet on its own line; reattach it.
        if line == "-":
            pending_bullet = True
            continue
        out.append(f"- {line}" if pending_bullet and not line.startswith("- ") else line)
        pending_bullet = False
    return "\n".join(out)
