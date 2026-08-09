import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


PHONE_PATTERN = re.compile(r'^\+998\d{9}$')


def validate_phone(phone):
    if not isinstance(phone, str) or not PHONE_PATTERN.fullmatch(phone):
        raise ValidationError(_('Invalid phone number'), params={'phone': phone})
