import re
from dataclasses import dataclass

from customer_telegram.models import CustomerTelegramLink


START_PARAMETER = re.compile(r'^[rpa]_[A-Za-z0-9_-]{43}$')


@dataclass(frozen=True)
class TelegramLinkReceipt:
    challenge_id: str | None
    expires_in: int
    resend_after: int | None
    telegram_url: str


@dataclass(frozen=True)
class StartedLink:
    link: CustomerTelegramLink | None
    requires_contact: bool = True
