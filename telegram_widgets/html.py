"""Render Telegram widget HTML from the bundled templates within the Bot API limits.

A widget is fixed code plus state: the template supplies the code, the labels and the
first screen are baked in as JSON, and later screens arrive as chat state or answers.
See https://core.telegram.org/bots/widgets.md for the limits enforced here.
"""
import json
import re
import zlib
from functools import lru_cache
from pathlib import Path


MAXIMUM_HTML_BYTES = 32768
MAXIMUM_COMPRESSED_BYTES = 4096
TEMPLATES = Path(__file__).resolve().parent / 'templates'
TEMPLATE_NAMES = ('card', 'order', 'storefront')
_INDENT = re.compile(r'\n\s*')


class WidgetTooLarge(ValueError):
    pass


def safe_json(value):
    """JSON that cannot close the surrounding <script> element."""
    text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return text.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


@lru_cache(maxsize=None)
def template(name):
    if name not in TEMPLATE_NAMES:
        raise ValueError('unknown widget template')
    source = (TEMPLATES / '{}.html'.format(name)).read_text(encoding='utf-8')
    return _INDENT.sub('\n', source.strip())


def compressed_size(html):
    return len(zlib.compress(html.encode('utf-8'), 9))


def render(name, labels, data):
    html = template(name).replace('__L__', safe_json(labels)).replace('__D__', safe_json(data))
    check_size(html)
    return html


def check_size(html):
    if '\x00' in html:
        raise WidgetTooLarge('widget HTML must not contain NUL')
    if len(html.encode('utf-8')) > MAXIMUM_HTML_BYTES or compressed_size(html) > MAXIMUM_COMPRESSED_BYTES:
        raise WidgetTooLarge('widget HTML exceeds the Bot API limits')
