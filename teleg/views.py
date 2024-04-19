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


@bot.message_handler(commands=['month'])
def month(message: telebot.types.Message):
    today = timezone.now()
    prev_month = today - timedelta(days=30)

    orders = Basket.objects.filter(
        created_at__gte=prev_month,
        created_at__lte=today,
        order__isnull=False,
    )
    
    basket_count = orders.count()
    
    text = f'📊 Купленных товаров от {prev_month.date()} до {today.date()}: {basket_count}шт.\n'
    subtext = ''
    for item in orders:
        subtext += f'Товар: {item.product.name_ru}, Кол-во: {item.quantity}шт, '
    bot.send_message(message.chat.id, )


@bot.message_handler(commands=['year'])
def year(message: telebot.types.Message):
    today = timezone.now()
    prev_month = today - timedelta(days=365)

    orders = Basket.objects.filter(
        created_at__gte=prev_month,
        created_at__lte=today,
        order__isnull=False,
    )
    
    basket_count = orders.count()

    
    bot.send_message(message.chat.id, f'📊 Купленных товаров от {prev_month.date()} до {today.date()}: {basket_count}шт.')


@bot.message_handler(commands=['week'])
def year(message: telebot.types.Message):
    today = timezone.now()
    prev_month = today - timedelta(days=7)

    orders = Basket.objects.filter(
        created_at__gte=prev_month,
        created_at__lte=today,
        order__isnull=False,
    )
    
    basket_count = orders.count()
    
    bot.send_message(message.chat.id, f'📊 Купленных товаров от {prev_month.date()} до {today.date()}: {basket_count}шт.')


@bot.message_handler(commands=['day'])
def year(message: telebot.types.Message):
    today = timezone.now()
    prev_month = today - timedelta(days=1)

    orders = Basket.objects.filter(
        created_at__gte=prev_month,
        created_at__lte=today,
        order__isnull=False,
    )
    
    basket_count = orders.count()
    
    bot.send_message(message.chat.id, f'📊 Купленных товаров от {prev_month.date()} до {today.date()}: {basket_count}шт.')


@bot.message_handler(func=lambda message: True)
def echo_message(message: telebot.types.Message):
    if message.text.split(':')[0] == 'key':
        if SecretPhrase.objects.filter(phrase=message.text.split(':')[1]).exists():
            data = ChatModel.objects.filter(chat_id=message.chat.id).exists()
            if not data:
                ChatModel.objects.create(
                    chat_id=message.chat.id,
                    first_name=message.chat.first_name,
                    last_name=message.chat.last_name,
                    username=message.chat.username,
                )
            bot.send_message(message.chat.id, f'✅: {message.chat.first_name}')
