import telebot
from django.conf import settings
from django.db.models import F, Count
from django.http import HttpResponse
from datetime import timedelta

from django.utils import timezone

from store.models import Basket
from teleg.models import SecretPhrase, Chat as ChatModel

bot = telebot.TeleBot(settings.BOT_TOKEN)


def index(request):
    if request.method == "POST":
        update = telebot.types.Update.de_json(request.body.decode('utf-8'))
        bot.process_new_updates([update])

    return HttpResponse('<h1>Ты подключился!</h1>')


@bot.message_handler(commands=['start'])
def start(message: telebot.types.Message):
    bot.send_message(message.chat.id, f'Добро Пожаловать!')


@bot.message_handler(commands=['statistics_month'])
async def statisticsMonth(message: telebot.types.Message):
    try:
        chat = ChatModel.objects.get(chat_id=message.chat.id)

        baskets = await Basket.objects.all()
        print(baskets)

        bot.send_message(chat.chat_id, f'Добро Пожаловать!')
    except ChatModel.DoesNotExist:
        ...


@bot.message_handler(func=lambda message: True)
def echo_message(message: telebot.types.Message):
    if message.text.split(':')[0] == 'key':

        if SecretPhrase.objects.filter(phrase=message.text.split(':')[1]).exists():
            data = ChatModel.objects.create(
                chat_id=message.chat.id,
                first_name=message.chat.first_name,
                last_name=message.chat.last_name,
                username=message.chat.username,
            )

            bot.send_message(message.chat.id, f'✅: {data.first_name}')
