from store.models import Order
from teleg.models import Chat as ChatModel
from teleg.views import bot


def notify_review(message):
    for chat in ChatModel.objects.all():
        bot.send_message(chat.chat_id, 
            text=f"Новый Отзыв.\n"
            f"id этой комментарий: {message.get('id')} \n"
            f"Никнейм: #{message.get('username')} \n"
            f"Полное Имя: {message.get('first_name')} {message.get('last_name')} \n"
            f"Телефон номер: {message.get('phone')} \n"
            f"Комментарие: {message.get('comment')} \n"
            f"Продукт: {message.get('product').name_ru} \n"
        )
