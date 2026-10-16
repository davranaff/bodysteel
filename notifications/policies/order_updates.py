"""Which order transitions notify the customer, and the frozen RU/UZ copy for each event.

Copy is transactional: it carries only the public order code. Never add prices, names, phones,
addresses, payment details or product lists here.
"""

ORDER_TARGET_URL = 'https://bodysteel.uz/app/orders'

PAYMENT_EVENTS = {
    'paid': 'payment_paid',
    'failed': 'payment_failed',
    'refunded': 'payment_refunded',
}
FULFILLMENT_EVENTS = {
    'confirmed': 'order_confirmed',
    'preparing': 'order_preparing',
    'ready': 'order_ready',
    'delivering': 'order_delivering',
    'delivered': 'order_delivered',
    'cancelled': 'order_cancelled',
}
# One save may change both statuses; the device shows one alert per order (stable collapse tag),
# so only the most important event of that save is queued.
EVENT_PRIORITY = (
    'payment_refunded', 'order_cancelled', 'payment_failed', 'order_delivered', 'order_delivering',
    'order_ready', 'payment_paid', 'order_preparing', 'order_confirmed',
)
PICKUP_TYPES = frozenset({'pickup', 'Самовывоз'})

COPY = {
    'payment_paid': {
        'ru': ('Оплата получена', 'Оплата заказа №{code} подтверждена. Спасибо за покупку!'),
        'uz': ('To‘lov qabul qilindi', '№{code} buyurtma uchun to‘lov tasdiqlandi. Xaridingiz uchun rahmat!'),
    },
    'payment_failed': {
        'ru': ('Оплата не прошла', 'Не удалось оплатить заказ №{code}. Подробности — в приложении.'),
        'uz': ('To‘lov o‘tmadi', '№{code} buyurtma uchun to‘lov amalga oshmadi. Batafsil — ilovada.'),
    },
    'payment_refunded': {
        'ru': ('Деньги возвращены', 'Возврат по заказу №{code} оформлен. Срок зачисления зависит от вашего банка.'),
        'uz': ('Pul qaytarildi', '№{code} buyurtma bo‘yicha pul qaytarildi. Mablag‘ tushish muddati bankingizga bog‘liq.'),
    },
    'order_confirmed': {
        'ru': ('Заказ подтверждён', 'Заказ №{code} подтверждён. Скоро начнём его собирать.'),
        'uz': ('Buyurtma tasdiqlandi', '№{code} buyurtmangiz tasdiqlandi. Tez orada uni yig‘ishni boshlaymiz.'),
    },
    'order_preparing': {
        'ru': ('Собираем заказ', 'Заказ №{code} уже собирается.'),
        'uz': ('Buyurtma yig‘ilmoqda', '№{code} buyurtmangiz yig‘ilmoqda.'),
    },
    'order_ready': {
        'ru': ('Заказ готов к выдаче', 'Заказ №{code} готов. Можно забирать!'),
        'uz': ('Buyurtma tayyor', '№{code} buyurtmangiz tayyor. Olib ketishingiz mumkin!'),
    },
    'order_delivering': {
        'ru': ('Заказ в пути', 'Заказ №{code} передан в доставку.'),
        'uz': ('Buyurtma yo‘lda', '№{code} buyurtmangiz yetkazib berishga topshirildi.'),
    },
    'order_delivered': {
        'ru': ('Заказ вручён', 'Заказ №{code} вручён. Спасибо, что выбрали BodySteel!'),
        'uz': ('Buyurtma topshirildi', '№{code} buyurtmangiz topshirildi. BodySteel’ni tanlaganingiz uchun rahmat!'),
    },
    'order_cancelled': {
        'ru': ('Заказ отменён', 'Заказ №{code} отменён. Если это ошибка, свяжитесь с нами.'),
        'uz': ('Buyurtma bekor qilindi', '№{code} buyurtmangiz bekor qilindi. Agar bu xato bo‘lsa, biz bilan bog‘laning.'),
    },
}
ORDER_EVENTS = frozenset(COPY)


def order_update_event(previous, order):
    """Return the single event to notify for a save, or None.

    ``previous`` is the ``(payment_status, fulfillment_status)`` pair read before the save, or
    None for a new order. Creation (``new``/``unpaid``) never notifies.
    """
    if previous is None:
        return None
    previous_payment, previous_fulfillment = previous
    events = set()
    if order.payment_status != previous_payment and order.payment_status in PAYMENT_EVENTS:
        events.add(PAYMENT_EVENTS[order.payment_status])
    if order.fulfillment_status != previous_fulfillment and order.fulfillment_status in FULFILLMENT_EVENTS:
        event = FULFILLMENT_EVENTS[order.fulfillment_status]
        # "Ready" means pickup-ready; delivery orders are announced when they leave.
        if event != 'order_ready' or order.type in PICKUP_TYPES:
            events.add(event)
    return next((event for event in EVENT_PRIORITY if event in events), None)


def order_update_copy(event, language, order_code):
    if event not in ORDER_EVENTS:
        raise ValueError('Unknown order update event')
    title, body = COPY[event]['uz' if language == 'uz' else 'ru']
    return title, body.format(code=order_code)
