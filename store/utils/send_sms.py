from types import NoneType
from django.conf import settings
from requests import request

import json


def send_sms(mobile_phone: str, message: str, from_to: str = settings.ESKIZ_FROM_TO, callback_url: str = None) -> dict[
    str, any]:
    """
        Send SMS message to mobile_phone

        attrs:
            :mobile_phone type is <str>
            :message type is <str>
            :from_to type is <str> defaults to settings.ESKIZ_FROM_TO
            :callback type is <str> defaults to NoneType
    """

    return {}
