import datetime
import hmac
import json
from html import escape

import telebot
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone

from teleg.invites import invited_greeting, owner_invite, register_invited
from teleg.models import SecretPhrase, Chat as ChatModel
from teleg.replies import reply, send_report
from teleg.stats import period_state, report_state
from teleg.widget_queries import handle_staff_widget_query

bot = telebot.TeleBot(settings.BOT_TOKEN)

VERIFY_PROMPT = (
    '🔐 <b>Нужна верификация</b>\n'
    'Отправьте ключ от администратора в формате <code>key:фраза</code> '
    'или попросите владельца бота пригласить вас.'
)
HELP_TEXT = (
    '📊 <b>Продажи</b>\n'
    '/day — за последний день\n/week — за неделю\n/month — за месяц\n/year — за год\n'
    '/filter — за выбранные даты\n\n'
    '🔔 Новые заказы, оплаты и отзывы приходят сюда сами.'
)
GREETING = '👋 <b>BodySteel · бот сотрудников</b>\n'
PERIOD_COMMANDS = {'day': 'd', 'week': 'w', 'month': 'm', 'year': 'y'}


def check_chat_registered(func):
    def wrapper(message: telebot.types.Message):
        if not ChatModel.objects.filter(chat_id=message.chat.id).exists():
            reply(bot, message.chat.id, VERIFY_PROMPT)
            return
        return func(message)

    return wrapper


def index(request):
    if request.method == "POST":
        if not _secret_ok(request):
            return HttpResponse(status=403)
        body = request.body.decode('utf-8')
        payload = _json(body)
        if isinstance(payload, dict) and 'widget_query' in payload:
            handle_staff_widget_query(payload['widget_query'])
            return HttpResponse(status=200)
        invited = owner_invite(payload.get('message')) if isinstance(payload, dict) else None
        if invited:
            if register_invited(invited):
                reply(bot, invited['id'], invited_greeting(invited, HELP_TEXT))
            return HttpResponse(status=200)
        update = telebot.types.Update.de_json(body)
        bot.process_new_updates([update])

    return HttpResponse('<h1>Ты подключился!</h1>')


@bot.message_handler(commands=['filter'])
@check_chat_registered
def filter_by_dates(message: telebot.types.Message):
    msg = bot.send_message(
        message.chat.id,
        '📅 <b>Отчёт за период</b>\nОтправьте две даты через пробел: <code>2026-11-01 2026-11-21</code>',
        parse_mode='HTML',
    )
    bot.register_next_step_handler(msg, process_date_filter)


def process_date_filter(message: telebot.types.Message):
    if not ChatModel.objects.filter(chat_id=message.chat.id).exists():
        reply(bot, message.chat.id, VERIFY_PROMPT)
        return
    try:
        start_date_str, end_date_str = (message.text or '').split()
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d') + datetime.timedelta(
            days=1) - datetime.timedelta(seconds=1)
    except ValueError:
        reply(bot, message.chat.id, 'Не понял даты. Отправьте их так: <code>2026-11-01 2026-11-21</code>, или /filter заново.')
        return
    if start_date > end_date:
        reply(bot, message.chat.id, 'Первая дата должна быть не позже второй. Отправьте /filter заново.')
        return
    start, end = timezone.make_aware(start_date), timezone.make_aware(end_date)
    title = 'с {} по {}'.format(start_date.date(), end_date.date())
    send_report(bot, message.chat.id, report_state(start, end, title))


@bot.message_handler(commands=['start'])
def start(message: telebot.types.Message):
    if ChatModel.objects.filter(chat_id=message.chat.id).exists():
        text = GREETING + '\n' + HELP_TEXT
    else:
        text = GREETING + '\n' + VERIFY_PROMPT
    reply(bot, message.chat.id, text, links=[['Открыть веб-приложение', 'https://t.me/test_teleg_app_bot/bodysteel']])


@bot.message_handler(commands=list(PERIOD_COMMANDS))
@check_chat_registered
def period_report(message: telebot.types.Message):
    command = (message.text or '').split()[0].lstrip('/').split('@')[0]
    send_report(bot, message.chat.id, period_state(PERIOD_COMMANDS.get(command, 'd')))


@bot.message_handler(commands=['help'])
def help_command(message: telebot.types.Message):
    registered = ChatModel.objects.filter(chat_id=message.chat.id).exists()
    reply(bot, message.chat.id, HELP_TEXT if registered else VERIFY_PROMPT)


@bot.message_handler(func=lambda message: True)
def echo_message(message: telebot.types.Message):
    text = message.text or ''
    if text.startswith('key:'):
        phrase = text.split(':', 1)[1].strip()
        if not SecretPhrase.objects.filter(phrase=phrase, expired_date__gte=timezone.now()).exists():
            reply(bot, message.chat.id, '❌ Ключ неверный или его срок истёк. Запросите новый у администратора.')
            return
        if ChatModel.objects.filter(chat_id=message.chat.id).exists():
            reply(bot, message.chat.id, '✅ Вы уже верифицированы.\n\n' + HELP_TEXT)
            return
        ChatModel.objects.create(
            chat_id=message.chat.id,
            first_name=message.chat.first_name or '',
            last_name=message.chat.last_name,
            username=message.chat.username,
        )
        name = escape(message.chat.first_name or '')
        reply(bot, message.chat.id, '✅ <b>Готово{}!</b> Теперь заказы и отчёты приходят сюда.\n\n{}'.format(
            ', ' + name if name else '', HELP_TEXT))
    elif not ChatModel.objects.filter(chat_id=message.chat.id).exists():
        reply(bot, message.chat.id, VERIFY_PROMPT)


def _secret_ok(request):
    """With STAFF_TELEGRAM_WEBHOOK_SECRET set, only Telegram's signed calls are accepted."""
    expected = getattr(settings, 'STAFF_TELEGRAM_WEBHOOK_SECRET', '')
    if not expected:
        return True
    supplied = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    return isinstance(supplied, str) and hmac.compare_digest(supplied, expected)


def _json(body):
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None

