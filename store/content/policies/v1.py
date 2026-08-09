import nh3


ALLOWED_TAGS = {
    'a', 'abbr', 'b', 'blockquote', 'br', 'caption', 'code', 'col', 'colgroup',
    'dd', 'del', 'div', 'dl', 'dt', 'em', 'figure', 'figcaption', 'h1', 'h2',
    'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'ol', 'p', 'pre', 'q',
    's', 'small', 'span', 'strong', 'sub', 'sup', 'table', 'tbody', 'td',
    'tfoot', 'th', 'thead', 'time', 'tr', 'u', 'ul',
}

ALLOWED_ATTRIBUTES = {
    'a': {'href', 'title'},
    'abbr': {'title'},
    'blockquote': {'cite'},
    'col': {'span'},
    'del': {'cite', 'datetime'},
    'img': {'alt', 'src', 'title'},
    'li': {'value'},
    'ol': {'start'},
    'q': {'cite'},
    'td': {'colspan', 'rowspan'},
    'th': {'colspan', 'rowspan', 'scope'},
    'time': {'datetime'},
}

CLEAN_CONTENT_TAGS = {
    'embed', 'iframe', 'math', 'object', 'script', 'style', 'svg', 'template',
}

ALLOWED_URL_SCHEMES = {'http', 'https', 'mailto', 'tel'}


def sanitize_html_v1(value):
    if value is None:
        return None
    return nh3.clean(
        str(value),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        clean_content_tags=CLEAN_CONTENT_TAGS,
        strip_comments=True,
        link_rel='noopener noreferrer',
        url_schemes=ALLOWED_URL_SCHEMES,
        url_relative='deny',
    )
