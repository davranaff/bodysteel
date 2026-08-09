import re

from django.db import IntegrityError, transaction
from django.utils import timezone

from integration.models import IntegrationCart, IntegrationOrderAttribution


TOKEN = re.compile(r'^[A-Za-z0-9_-]{32,64}$')


def attach_order_attribution(order, token, product_ids):
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        return False
    cart = (
        IntegrationCart.objects.select_for_update()
        .filter(restore_token=token, expires_at__gt=timezone.now())
        .first()
    )
    if not cart or not _has_matching_product(cart, product_ids):
        return False
    existing = IntegrationOrderAttribution.objects.filter(order=order).first()
    if existing:
        return existing.cart_id == cart.pk
    try:
        with transaction.atomic():
            IntegrationOrderAttribution.objects.create(
                order=order,
                cart=cart,
                ai_session_id=cart.ai_session_id,
                channel=cart.channel,
            )
    except IntegrityError:
        return False
    return True


def _has_matching_product(cart, product_ids):
    ordered = {str(product_id) for product_id in product_ids}
    attributed = {item.get('productId') for item in cart.items if isinstance(item, dict)}
    return bool(ordered & attributed)
