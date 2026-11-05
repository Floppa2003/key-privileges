"""Decode source HTML once, preserving inline text and explicit block boundaries."""
from __future__ import annotations

import re
from bs4 import BeautifulSoup, NavigableString, Tag
from bs4.element import Comment, Declaration, Doctype, ProcessingInstruction


BLOCKS = frozenset(('address', 'article', 'aside', 'blockquote', 'div', 'dl', 'dt', 'dd',
                   'fieldset', 'figcaption', 'figure', 'footer', 'h1', 'h2', 'h3', 'h4',
                   'h5', 'h6', 'header', 'hr', 'li', 'main', 'nav', 'ol', 'p', 'pre',
                   'section', 'table', 'thead', 'tbody', 'tfoot', 'tr', 'ul'))


def html_text(value: str | Tag | None) -> str:
    """Read HTML or a parsed DOM node without mutating it.

    The result is plain source text: inline tags add no whitespace, block tags
    and BR add newlines, PRE retains line breaks, and table cells add spaces.
    Entity references are decoded by the HTML parser exactly once; callers must
    not parse the result as HTML again. This follows HTML structure, not CSS
    visibility or layout.
    """
    if value is None:
        return ''
    node = BeautifulSoup(value, 'html.parser') if isinstance(value, str) and not isinstance(value, NavigableString) else value
    pieces = []
    stack = [(node, False, '')]
    while stack:
        item, preformatted, closing_boundary = stack.pop()
        if closing_boundary:
            pieces.append(closing_boundary)
            continue
        if isinstance(item, (Comment, Declaration, Doctype, ProcessingInstruction)):
            continue
        if isinstance(item, NavigableString):
            value = str(item).replace('\r\n', '\n').replace('\r', '\n')
            pieces.append(value if preformatted else re.sub(r'\s+', ' ', value))
        elif isinstance(item, Tag):
            if item.name in ('script', 'style', 'template'):
                continue
            boundary = '\n' if item.name in BLOCKS or item.name == 'br' else ' ' if item.name in ('td', 'th') else ''
            if boundary:
                pieces.append(boundary)
                stack.append((None, False, boundary))
            stack.extend((child, preformatted or item.name == 'pre', '')
                         for child in reversed(item.contents))
    result = re.sub(r'[^\S\n]+', ' ', ''.join(pieces))
    return re.sub(r' *\n[ \n]*', '\n', result).strip()
