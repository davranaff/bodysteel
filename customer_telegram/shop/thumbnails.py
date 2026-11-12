"""Tiny product photos for widgets: a widget shows images only as ``data:`` URLs.

The whole screen must fit 1024 bytes, so the photo gets whatever the text leaves
and is dropped when even the smallest version does not fit.
"""
import base64
import hashlib
import io
import logging

from django.core.cache import cache
from PIL import Image, UnidentifiedImageError


logger = logging.getLogger(__name__)
PREFIX = 'data:image/webp;base64,'
ATTEMPTS = ((96, 45), (80, 35), (64, 30), (48, 25), (40, 22), (32, 20))
CACHE_SECONDS = 24 * 60 * 60


def product_thumbnail(product, budget_bytes):
    if budget_bytes <= len(PREFIX) + 200:
        return None
    photo = _first_photo(product)
    if not photo:
        return None
    for side, quality in ATTEMPTS:
        uri = _cached_uri(photo, side, quality)
        if uri is None:
            return None
        if len(uri) <= budget_bytes:
            return uri
    return None


def _first_photo(product):
    image = product.product_images.order_by('pk').first()
    return image.photo if image and image.photo else None


def _cached_uri(photo, side, quality):
    # File names carry spaces and Cyrillic, which some cache backends refuse in keys.
    name = hashlib.sha256(photo.name.encode('utf-8')).hexdigest()[:32]
    key = 'customer_tg:thumb:{}:{}:{}'.format(name, side, quality)
    uri = cache.get(key)
    if uri is None:
        uri = _encode(photo, side, quality) or ''
        cache.set(key, uri, CACHE_SECONDS)
    return uri or None


def _encode(photo, side, quality):
    try:
        photo.open('rb')
        try:
            with Image.open(photo) as source:
                image = source.convert('RGBA')
        finally:
            photo.close()
    except (OSError, ValueError, UnidentifiedImageError):
        logger.warning('Product thumbnail could not be read')
        return None
    image.thumbnail((side, side))
    canvas = Image.new('RGB', (side, side), (255, 255, 255))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2), image)
    output = io.BytesIO()
    canvas.save(output, 'WEBP', quality=quality, method=6)
    return PREFIX + base64.b64encode(output.getvalue()).decode('ascii')
