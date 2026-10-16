"""OpenStreetMap Nominatim adapter: the only module that talks to the geocoder."""
from dataclasses import dataclass

import httpx
from django.conf import settings

from store.geocoding.bounds import inside_uzbekistan


USER_AGENT = 'BODYSTEEL/1.0 (+https://bodysteel.uz)'
TIMEOUT = httpx.Timeout(6.0, connect=3.0)
MAXIMUM_RESPONSE_BYTES = 256 * 1024
SEARCH_LIMIT = 5
# Bias (not a restriction) towards Bukhara: lng_min,lat_max,lng_max,lat_min.
BUKHARA_VIEWBOX = '64.22,39.97,64.62,39.57'
LOCALITY_KEYS = ('city', 'town', 'village', 'hamlet', 'municipality', 'county', 'state')
STREET_KEYS = ('road', 'pedestrian', 'neighbourhood', 'quarter', 'suburb')


class GeocoderUnavailable(Exception):
    """The upstream geocoder failed, timed out or answered with an unusable body."""


@dataclass(frozen=True)
class Place:
    label: str
    address: str
    lat: float | None = None
    lng: float | None = None


def reverse(latitude, longitude, language):
    payload = _get('/reverse', {
        'format': 'jsonv2',
        'lat': latitude,
        'lon': longitude,
        'zoom': 18,
        'addressdetails': 1,
    }, language)
    if not isinstance(payload, dict):
        raise GeocoderUnavailable('reverse payload')
    if 'error' in payload:
        # Nominatim answers 200 {"error": "Unable to geocode"} for empty areas.
        return Place(label='', address='')
    return _place(payload)


def search(query, language):
    payload = _get('/search', {
        'format': 'jsonv2',
        'q': query,
        'countrycodes': 'uz',
        'viewbox': BUKHARA_VIEWBOX,
        'bounded': 0,
        'addressdetails': 1,
        'limit': SEARCH_LIMIT,
    }, language)
    if not isinstance(payload, list):
        raise GeocoderUnavailable('search payload')
    places = []
    for item in payload:
        place = _located_place(item)
        if place is not None:
            places.append(place)
        if len(places) == SEARCH_LIMIT:
            break
    return places


def http_client():
    return httpx.Client(timeout=TIMEOUT, follow_redirects=False, trust_env=False)


def _get(path, params, language):
    base_url = str(getattr(settings, 'GEOCODER_BASE_URL', '') or '').rstrip('/')
    if not base_url.startswith(('https://', 'http://')):
        raise GeocoderUnavailable('configuration')
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json', 'Accept-Language': language}
    try:
        with http_client() as client:
            response = client.get(
                f'{base_url}{path}',
                params={**params, 'accept-language': language},
                headers=headers,
            )
    except httpx.HTTPError as error:
        raise GeocoderUnavailable('transport') from error
    if response.status_code != 200 or len(response.content) > MAXIMUM_RESPONSE_BYTES:
        raise GeocoderUnavailable(f'status {response.status_code}')
    try:
        return response.json()
    except ValueError as error:
        raise GeocoderUnavailable('json') from error


def _located_place(item):
    if not isinstance(item, dict):
        return None
    try:
        latitude = float(item.get('lat'))
        longitude = float(item.get('lon'))
    except (TypeError, ValueError):
        return None
    if not inside_uzbekistan(latitude, longitude):
        return None
    place = _place(item)
    return Place(label=place.label, address=place.address, lat=latitude, lng=longitude)


def _place(item):
    details = item.get('address') if isinstance(item.get('address'), dict) else {}
    display_name = _text(item.get('display_name'))
    street = _first(details, STREET_KEYS)
    house = _text(details.get('house_number'))
    locality = _first(details, LOCALITY_KEYS)
    street_line = ', '.join(part for part in (street, house) if part)
    label = _text(item.get('name')) or street_line or display_name.split(',')[0].strip()
    address = ', '.join(part for part in (street, house, locality) if part) or display_name
    return Place(label=label[:255], address=address[:255])


def _first(details, keys):
    for key in keys:
        value = _text(details.get(key))
        if value:
            return value
    return ''


def _text(value):
    return value.strip() if isinstance(value, str) else ''
