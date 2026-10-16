"""Service area and coordinate normalization shared by checkout and the geocoder."""
import math
from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers


# Uzbekistan bounding box (inclusive). Coarse on purpose: it rejects obviously
# wrong points (0,0, swapped lat/lng, other countries) without a polygon test.
UZ_MIN_LATITUDE = 37.0
UZ_MAX_LATITUDE = 45.7
UZ_MIN_LONGITUDE = 55.9
UZ_MAX_LONGITUDE = 73.2
COORDINATE_STEP = Decimal('0.000001')


def inside_uzbekistan(latitude, longitude):
    return (
        UZ_MIN_LATITUDE <= float(latitude) <= UZ_MAX_LATITUDE
        and UZ_MIN_LONGITUDE <= float(longitude) <= UZ_MAX_LONGITUDE
    )


def quantize_coordinate(value):
    """Round a finite number to the stored precision (6 decimals, ~0.1 m)."""
    return Decimal(repr(float(value))).quantize(COORDINATE_STEP, rounding=ROUND_HALF_UP)


def parse_coordinate(value, limit):
    """Return a finite float within ``[-limit, limit]`` or raise ``ValueError``.

    Accepts numbers and numeric query-string text; booleans are rejected.
    """
    if isinstance(value, bool):
        raise ValueError('coordinate')
    parsed = float(value)
    if not math.isfinite(parsed) or not -limit <= parsed <= limit:
        raise ValueError('coordinate')
    return parsed


class CoordinateField(serializers.Field):
    """A JSON number coordinate, quantized to 6 decimals."""

    default_error_messages = {'invalid': 'A finite number between -{limit} and {limit} is required.'}

    def __init__(self, limit, **kwargs):
        self.limit = limit
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if not isinstance(data, (int, float)):
            self.fail('invalid', limit=self.limit)
        try:
            return quantize_coordinate(parse_coordinate(data, self.limit))
        except (TypeError, ValueError, OverflowError):
            self.fail('invalid', limit=self.limit)

    def to_representation(self, value):
        return None if value is None else float(value)
