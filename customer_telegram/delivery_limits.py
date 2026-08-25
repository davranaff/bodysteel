from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction

from customer_telegram.models import CustomerTelegramChat


@dataclass(frozen=True)
class MarketingSlot:
    status: str
    retry_at: object = None


def reserve_marketing_slot(chat_id, now):
    with transaction.atomic():
        chat = CustomerTelegramChat.objects.select_for_update().get(pk=chat_id)
        if not chat.is_active or not chat.marketing_opt_in or chat.blocked_at is not None:
            return MarketingSlot('inactive')
        if chat.marketing_next_send_at and chat.marketing_next_send_at > now:
            return MarketingSlot('wait', chat.marketing_next_send_at)
        chat.marketing_next_send_at = now + timedelta(seconds=1)
        chat.save(update_fields=('marketing_next_send_at', 'updated_at'))
        return MarketingSlot('ready')
