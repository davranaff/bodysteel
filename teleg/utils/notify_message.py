from store.models import Order
from teleg.models import Chat as ChatModel
from teleg.views import bot


def notify_message(order, baskets, coupon=None):
    for chat in ChatModel.objects.all():
        baskets_text = ''
        count = 1
        for basket in baskets:
            baskets_text += (f'- - - - - - - - - -\n'
                             f'{count}) {basket.product.name_ru}\n'
                             f'- - - {basket.quantity} шт.\n'
                             f'- - - 💸{basket.price:,} UZS\n')
            count += 1
        
        # Добавляем информацию о купоне, если он был использован
        coupon_text = ""
        if coupon:
            coupon_text = f"Использован купон: {coupon.code} (-{coupon.discount_percent}%)\n"
            
        bot.send_message(chat.chat_id,
                         text=f"Новый Заказ.\n"
                              f"Номер Заказа: #{order.order_code} \n"
                              f"Тип доставки - {[item[1] for item in Order.DELIVERY_CHOICES if item[0] == order.type][0]} \n"
                              f"Адрес доставки - 🚚{order.address} \n"
                              f"Имя заказчика - {order.full_name} \n"
                              f"Телефон номер заказчика - {order.phone} \n"
                              f"{coupon_text}"
                              f"Общая сумма - 💸{order.total_price:,} UZS \n"
                              f"{baskets_text}")
