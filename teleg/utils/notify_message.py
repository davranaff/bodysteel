from store.models import Order
from teleg.models import Chat as ChatModel
from teleg.views import bot


def notify_message(order, baskets):
    for chat in ChatModel.objects.all():
        baskets_text = ''
        count = 1
        for basket in baskets:
            baskets_text += (f'- - - - - - - - - -\n'
                             f'{count}) {basket.product.name_ru}\n'
                             f'- - - {basket.quantity} шт.\n'
                             f'- - - 💸{basket.price:,} UZS\n')
            count += 1
        bot.send_message(chat.chat_id,
                         text=f"Новый Заказ. (🕘{order.created_at.strftime('%d/%m/%Y %H:%M')}) \n"
                              f"Номер Заказа: #{order.order_code} \n"
                              f"Тип доставки - {[item[1] for item in Order.DELIVERY_CHOICES if item[0] == order.type][0]} \n"
                              f"Адрес доставки - 🚚{order.address} \n"
                              f"Имя заказчика - {order.full_name} \n"
                              f"Телефон номер заказчика - {order.phone} \n"
                              f"Общая сумма - 💸{order.total_price:,} UZS \n"
                              f"{baskets_text}")
