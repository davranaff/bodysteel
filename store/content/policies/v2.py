import re

import nh3

from store.content.policies.v1 import (
    ALLOWED_ATTRIBUTES as V1_ALLOWED_ATTRIBUTES,
    ALLOWED_TAGS as V1_ALLOWED_TAGS,
    CLEAN_CONTENT_TAGS,
)


ALLOWED_TAGS = V1_ALLOWED_TAGS | {
    'address', 'article', 'aside', 'audio', 'area', 'bdi', 'bdo', 'data',
    'details', 'hgroup', 'kbd', 'main', 'map', 'mark', 'menu', 'nav',
    'picture', 'rp', 'rt', 'ruby', 'samp', 'section', 'source', 'summary',
    'track', 'var', 'video', 'wbr',
}

ALLOWED_ATTRIBUTES = {
    tag: set(attributes) for tag, attributes in V1_ALLOWED_ATTRIBUTES.items()
}
ALLOWED_ATTRIBUTES['*'] = {'class', 'style'}
ALLOWED_ATTRIBUTES['a'].update({'target'})
ALLOWED_ATTRIBUTES['area'] = {'alt', 'coords', 'href', 'shape', 'target'}
ALLOWED_ATTRIBUTES['audio'] = {'controls', 'loop', 'muted', 'preload'}
ALLOWED_ATTRIBUTES['img'].update({'height', 'loading', 'width'})
ALLOWED_ATTRIBUTES['map'] = {'name'}
ALLOWED_ATTRIBUTES['source'] = {'media', 'src', 'type'}
ALLOWED_ATTRIBUTES['track'] = {'default', 'kind', 'label', 'src', 'srclang'}
ALLOWED_ATTRIBUTES['video'] = {
    'controls', 'height', 'loop', 'muted', 'poster', 'preload', 'width',
}

FILTER_STYLE_PROPERTIES = {
    'background-color', 'border', 'border-radius', 'clear', 'color', 'display',
    'float', 'font-family', 'font-size', 'font-style', 'font-weight', 'height',
    'letter-spacing', 'line-height', 'list-style-type', 'margin', 'margin-bottom',
    'margin-left', 'margin-right', 'margin-top', 'max-height', 'max-width',
    'min-height', 'min-width', 'padding', 'padding-bottom', 'padding-left',
    'padding-right', 'padding-top', 'text-align', 'text-decoration',
    'text-transform', 'vertical-align', 'white-space', 'width',
}

UNSAFE_STYLE = re.compile(
    r'(?:@import|behavior\s*:|-moz-binding|expression\s*\(|javascript\s*:|url\s*\()',
    re.IGNORECASE,
)
URL_ATTRIBUTES = {'href', 'poster', 'src'}


def _filter_attribute(tag, attribute, value):
    if attribute == 'style' and UNSAFE_STYLE.search(value):
        return None
    if attribute in URL_ATTRIBUTES and value.lstrip().startswith('//'):
        return None
    return value


def sanitize_html_v2(value):
    if value is None:
        return None
    cleaned = nh3.clean(
        str(value),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        clean_content_tags=CLEAN_CONTENT_TAGS,
        strip_comments=True,
        link_rel='noopener noreferrer',
        url_schemes={'http', 'https', 'mailto', 'tel'},
        url_relative='pass_through',
        filter_style_properties=FILTER_STYLE_PROPERTIES,
        attribute_filter=_filter_attribute,
    )
    return re.sub(r'\sstyle=""', '', cleaned)
