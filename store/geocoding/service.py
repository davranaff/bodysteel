"""Cached, rate-limited geocoding used by the public storefront endpoints."""
import hashlib
import logging
from dataclasses import asdict

from django.core.cache import cache
from django.utils import timezone

from store.geocoding import nominatim
from users.auth.errors import AuthProblem
from users.auth.rate_limits import RateLimitPolicy, consume


logger = logging.getLogger(__name__)
CACHE_SECONDS = 7 * 24 * 60 * 60
CACHE_VERSION = 'v1'
GEOCODE_IP = RateLimitPolicy('geocode_ip', 60, 60)
# Nominatim's public policy allows about one request per second for the whole
# application; cache misses share this budget across all shoppers.
GEOCODE_UPSTREAM = RateLimitPolicy('geocode_upstream', 50, 60)


def throttle_client(ip_address):
    consume(GEOCODE_IP, ip_address, timezone.now())


def reverse_place(latitude, longitude, language):
    key = 'geocode:{}:reverse:{}:{:.5f}:{:.5f}'.format(CACHE_VERSION, language, latitude, longitude)
    return _cached(key, lambda: asdict(nominatim.reverse(
        '{:.5f}'.format(latitude), '{:.5f}'.format(longitude), language,
    )))


def search_places(query, language):
    digest = hashlib.sha256(query.encode('utf-8')).hexdigest()
    key = 'geocode:{}:search:{}:{}'.format(CACHE_VERSION, language, digest)
    return _cached(key, lambda: [asdict(place) for place in nominatim.search(query, language)])


def normalize_query(value):
    return ' '.join(value.split()).casefold()


def _cached(key, load):
    cached = cache.get(key)
    if cached is not None:
        return cached
    _consume_upstream_budget()
    try:
        value = load()
    except nominatim.GeocoderUnavailable as error:
        # Never log coordinates or search text: they describe a shopper's home.
        logger.warning('Geocoder unavailable: %s', error)
        raise AuthProblem(503, 'geocoder_unavailable', 'Geocoder is temporarily unavailable') from None
    cache.set(key, value, CACHE_SECONDS)
    return value


def _consume_upstream_budget():
    try:
        consume(GEOCODE_UPSTREAM, 'nominatim', timezone.now())
    except AuthProblem as problem:
        if problem.status != 429:
            raise
        raise AuthProblem(
            503, 'geocoder_unavailable', 'Geocoder is temporarily unavailable', problem.retry_after,
        ) from None
