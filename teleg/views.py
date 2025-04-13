import telebot
import datetime
from django.conf import settings
from django.db.models import F, Count, Sum
from django.http import HttpResponse
from datetime import timedelta

from django.utils import timezone
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from store.models import Basket
from teleg.models import SecretPhrase, Chat as ChatModel

bot = telebot.TeleBot(settings.BOT_TOKEN)


def check_chat_registered(func):
    def wrapper(message: telebot.types.Message):
        if not ChatModel.objects.filter(chat_id=message.chat.id).exists():
            bot.send_message(message.chat.id, "")
            return
        return func(message)

    return wrapper


def index(request):
    if request.method == "POST":
        update = telebot.types.Update.de_json(request.body.decode('utf-8'))
        bot.process_new_updates([update])

    return HttpResponse('<h1>Ты подключился!</h1>')


@bot.message_handler(commands=['filter'])
@check_chat_registered
def filter_by_dates(message: telebot.types.Message):
    msg = bot.send_message(message.chat.id, 'Введите даты в формате "YYYY-MM-DD YYYY-MM-DD" для фильтрации.')
    bot.register_next_step_handler(msg, process_date_filter)


def process_date_filter(message: telebot.types.Message):
    try:
        start_date_str, end_date_str = message.text.split()
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d') + datetime.timedelta(
            days=1) - datetime.timedelta(seconds=1)

        if start_date > end_date:
            bot.send_message(message.chat.id, 'Начальная дата должна быть меньше или равна конечной дате.')
            return

        orders = Basket.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date,
            order__isnull=False,
        ).values('product__name_ru').annotate(
            total_quantity=Sum('quantity'),
            total_sum=Sum('price'),
        ).order_by('-created_at')

        basket_count = orders.count()
        text = f'📊 Купленных товаров от {start_date.date()} до {end_date.date()}: {basket_count}шт.\n\n'
        for item in orders:
            text += (f'Товар: {item.get("product__name_ru")}, \n'
                     f'Кол-во: {item.get("total_quantity")}шт, \n'
                     f'Сумма {item.get("total_sum"):,}UZS \n\n')
        bot.send_message(message.chat.id, text)

        if not basket_count:
            bot.send_message(message.chat.id, "Никакой покупки нету!")

    except ValueError:
        bot.send_message(message.chat.id,
                         'Некорректный формат даты. Пожалуйста, используйте формат "YYYY-MM-DD YYYY-MM-DD".')
        return


@bot.message_handler(commands=['start'])
def start(message: telebot.types.Message):
    markup = InlineKeyboardMarkup()
    web_app_button = InlineKeyboardButton(
        text="Открыть веб-приложение",
        url="https://t.me/test_teleg_app_bot/bodysteel",
    )
    markup.add(web_app_button)
    bot.send_message(message.chat.id, f'Добро Пожаловать!', reply_markup=markup)


@bot.message_handler(commands=['month'])
@check_chat_registered
def month(message: telebot.types.Message):
    today = timezone.now()
    prev_month = today - timedelta(days=30)

    orders = Basket.objects.filter(
        created_at__gte=prev_month,
        created_at__lte=today,
        order__isnull=False,
    ).values('product__name_ru').annotate(
        total_quantity=Sum('quantity'),
        total_sum=Sum('price'),
    ).order_by('-created_at')

    basket_count = orders.count()

    text = f'📊 Купленных товаров от {prev_month.date()} до {today.date()}: {basket_count}шт.\n\n'
    for item in orders:
        text += f'Товар: {item.get("product__name_ru")}, Кол-во: {item.get("total_quantity")}шт, Сумма: {item.get("total_sum"):,}UZS \n\n'
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['year'])
@check_chat_registered
def year(message: telebot.types.Message):
    today = timezone.now()
    prev_month = today - timedelta(days=365)

    orders = Basket.objects.filter(
        created_at__gte=prev_month,
        created_at__lte=today,
        order__isnull=False,
    ).values('product__name_ru').annotate(
        total_quantity=Sum('quantity'),
        total_sum=Sum('price'),
    ).order_by('-created_at')

    basket_count = orders.count()

    text = f'📊 Купленных товаров от {prev_month.date()} до {today.date()}: {basket_count}шт.\n\n'
    for item in orders:
        text += f'Товар: {item.get("product__name_ru")}, Кол-во: {item.get("total_quantity")}шт, Сумма: {item.get("total_sum"):,}UZS \n\n'
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['week'])
@check_chat_registered
def week(message: telebot.types.Message):
    today = timezone.now()
    prev_month = today - timedelta(days=7)

    orders = Basket.objects.filter(
        created_at__gte=prev_month,
        created_at__lte=today,
        order__isnull=False,
    ).values('product__name_ru').annotate(
        total_quantity=Sum('quantity'),
        total_sum=Sum('price'),
    ).order_by('-created_at')

    basket_count = orders.count()

    text = f'📊 Купленных товаров от {prev_month.date()} до {today.date()}: {basket_count}шт.\n\n'
    for item in orders:
        text += f'Товар: {item.get("product__name_ru")}, Кол-во: {item.get("total_quantity")}шт, Сумма: {item.get("total_sum"):,}UZS \n\n'
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['day'])
@check_chat_registered
def day(message: telebot.types.Message):
    today = timezone.now()
    prev_month = today - timedelta(days=1)

    orders = Basket.objects.filter(
        created_at__gte=prev_month,
        created_at__lte=today,
        order__isnull=False,
    ).values('product__name_ru').annotate(
        total_quantity=Sum('quantity'),
        total_sum=Sum('price'),
    ).order_by('-created_at')

    basket_count = orders.count()

    text = f'📊 Купленных товаров от {prev_month.date()} до {today.date()}: {basket_count}шт.\n'
    for item in orders:
        text += f'\nТовар: {item.get("product__name_ru")}, Кол-во: {item.get("total_quantity")}шт, Сумма: {item.get("total_sum"):,}UZS \n\n'
    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda message: True)
def echo_message(message: telebot.types.Message):
    if message.text.startswith('key:'):
        phrase = message.text.split(':')[1]
        if SecretPhrase.objects.filter(phrase=phrase, expired_date__lte=datetime.datetime.now()).exists():
            chat_data = ChatModel.objects.filter(chat_id=message.chat.id).first()
            if not chat_data:
                ChatModel.objects.create(
                    chat_id=message.chat.id,
                    first_name=message.chat.first_name,
                    last_name=message.chat.last_name,
                    username=message.chat.username,
                )
            bot.send_message(message.chat.id, f'✅: {message.chat.first_name}')
