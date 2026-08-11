from __future__ import annotations

import re
from urllib.parse import quote, urlparse

# Characters that carry meaning anywhere in a line: the escape character
# itself, emphasis, code spans, link syntax, raw HTML, entities, tables and
# strikethrough. Escaping '[' and ']' is what makes '(' and ')' safe to leave
# alone — a link needs an unescaped ']' immediately before '('.
_INLINE = re.compile(r"([\\`*_\[\]<>&|~])")

# Markers that only matter at the start of a line: headings, blockquotes,
# bullet lists and ordered lists.
_BLOCK_START = re.compile(r"^(\s{0,3})(#{1,6}|[-+]|\d{1,9}(?=[.)]))", re.MULTILINE)

# C0/C1 control characters can be interpreted by terminals even when the
# surrounding text is correctly escaped for Markdown, HTML, or CSV. Preserve
# tabs and newlines, which are meaningful document content, but normalize
# carriage returns and remove the remaining terminal controls.
_UNSAFE_CONTROLS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")

# Percent-encoding safe set: everything with meaning in a URL stays literal.
# '%' is safe so an already-encoded URL is not double-encoded; parentheses and
# spaces are deliberately absent so they cannot terminate a link destination.
_URL_SAFE = "/:@?=&#%+,;$!*'~"


def sanitize_text(value: object) -> str:
    """Return text with terminal-interpreted control characters removed."""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return _UNSAFE_CONTROLS.sub("", text)


def _escape_block_start(match: re.Match[str]) -> str:
    indent, marker = match.group(1), match.group(2)
    if marker.isdigit():
        # The '.' or ')' is only looked ahead at, so the backslash lands on it.
        return f"{indent}{marker}\\"
    return f"{indent}\\{marker}"


def is_safe_url(url: str) -> bool:
    """True when the URL scheme is safe to use as a link target."""
    return urlparse(sanitize_text(url)).scheme in ("http", "https")


def escape_markdown(text: str) -> str:
    """Neutralize markdown syntax and raw HTML in untrusted multi-line text."""
    clean = sanitize_text(text)
    return _BLOCK_START.sub(_escape_block_start, _INLINE.sub(r"\\\1", clean))


def markdown_field(value: object) -> str:
    """Escape an untrusted single-line value for inline use in markdown.

    Newlines are collapsed so the value cannot break out of its line and forge
    a heading or a list item in the surrounding document."""
    return " ".join(_INLINE.sub(r"\\\1", sanitize_text(value)).split())


def markdown_url(url: str) -> str:
    """Render a URL as a markdown link destination, or '#' if the scheme is unsafe."""
    clean = sanitize_text(url)
    if not is_safe_url(clean):
        return "#"
    return quote(clean, safe=_URL_SAFE)
