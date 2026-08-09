from enum import Enum
from typing import Protocol


class SmsDeliveryResult(Enum):
    SENT = 'sent'
    UNKNOWN = 'unknown'
    FAILED = 'failed'


class SmsGateway(Protocol):
    def send_otp(self, phone: str, code: str) -> SmsDeliveryResult:
        ...
