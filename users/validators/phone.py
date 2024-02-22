from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re


def validate_phone(phone):
    if not re.search(r'^[+]998[39]\d\d{7}$', phone):
        raise ValidationError(_('Invalid phone number'), params={'phone': phone})
