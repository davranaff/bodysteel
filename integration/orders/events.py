from integration.models import IntegrationOrderAttribution
from integration.webhooks.events import enqueue_order_event


def enqueue_completed_order(order, occurred_at=None):
    product_ids = sorted(
        {
            str(product_id)
            for product_id in order.baskets.values_list('product_id', flat=True)
            if product_id is not None
        },
        key=int,
    )
    data = {
        'orderId': str(order.pk),
        'amount': int(order.total_price),
        'currency': 'UZS',
        'productIds': product_ids,
    }
    attribution = (
        IntegrationOrderAttribution.objects.filter(order=order).first()
    )
    if attribution:
        data.update({
            'channel': attribution.channel,
            'aiSessionId': attribution.ai_session_id,
        })
    return enqueue_order_event(data, order.pk, occurred_at)
