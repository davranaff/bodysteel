from customer_telegram.models import CustomerTelegramLink


def consume_password_reset_link(challenge, now):
    CustomerTelegramLink.objects.filter(
        auth_challenge=challenge,
        state=CustomerTelegramLink.DELIVERED,
    ).update(
        state=CustomerTelegramLink.CONSUMED,
        consumed_at=now,
        updated_at=now,
    )
