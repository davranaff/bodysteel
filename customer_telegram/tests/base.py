from customer_telegram.bot_api import DeliveryStatus, TelegramResult


TELEGRAM_SETTINGS = {
    'DEBUG': True,
    'SECRET_KEY': 'production-strength-secret-key-1234567890',
    'CUSTOMER_TELEGRAM_ENABLED': True,
    'CUSTOMER_TELEGRAM_CAMPAIGNS_ENABLED': True,
    'CUSTOMER_TELEGRAM_BOT_TOKEN': '100000:customer_telegram_token_1234567890',
    'CUSTOMER_TELEGRAM_BOT_USERNAME': 'BodySteelClientBot',
    'CUSTOMER_TELEGRAM_WEBHOOK_SECRET': 'customer_webhook_secret_1234567890',
    'CUSTOMER_TELEGRAM_LINK_HASH_KEY': 'customer-telegram-link-hash-key-0000000001',
    'CUSTOMER_TELEGRAM_PUBLIC_ORIGIN': 'https://api.bodysteel.uz',
    'CUSTOMER_TELEGRAM_WEBHOOK_URL': 'https://api.bodysteel.uz/telegram/customer/webhook/',
    'CUSTOMER_TELEGRAM_STORE_ORIGIN': 'https://bodysteel.uz',
    'CUSTOMER_TELEGRAM_LINK_TTL_SECONDS': '300',
    'CUSTOMER_TELEGRAM_CONTACT_MAX_ATTEMPTS': '3',
    'BOT_TOKEN': '200000:staff_telegram_token_1234567890123',
    'BODYSTEEL_STOREFRONT_PROXY_TOKEN': 'storefront-proxy-token-0000000000000001',
    'PHONE_VERIFICATION_HASH_KEY': 'phone-verification-key-0000000000000001',
    'AUTH_RATE_LIMIT_HASH_KEY': 'auth-rate-limit-key-0000000000000000001',
    'AUTH_CHALLENGE_HASH_KEY': 'auth-challenge-key-000000000000000001',
}


class FakeTelegramApi:
    def __init__(self, status=DeliveryStatus.SENT, retry_after=None, widget_status=DeliveryStatus.SENT):
        self.status = status
        self.retry_after = retry_after
        self.widget_status = widget_status
        self.messages = []
        self.callbacks = []
        self.widgets = []
        self.answers = []
        self.edits = []

    def send_message(self, chat_id, text, reply_markup=None, parse_mode='HTML'):
        self.messages.append((chat_id, text, reply_markup, parse_mode))
        return TelegramResult(
            self.status,
            message_id=len(self.messages) if self.status is DeliveryStatus.SENT else None,
            retry_after=self.retry_after,
        )

    def answer_callback_query(self, callback_query_id, text=None):
        self.callbacks.append((callback_query_id, text))
        return TelegramResult(DeliveryStatus.SENT)

    def send_widget(self, chat_id, html, caption, chat_data=None, reply_markup=None):
        """Recorded in ``messages`` too, as (chat, caption, markup, 'widget', html)."""
        if self.widget_status is not DeliveryStatus.SENT:
            return TelegramResult(self.widget_status)
        self.widgets.append({'chat_id': chat_id, 'html': html, 'caption': caption, 'reply_markup': reply_markup})
        self.messages.append((chat_id, caption, reply_markup, 'widget', html))
        return TelegramResult(DeliveryStatus.SENT, message_id=1000 + len(self.messages))

    def answer_widget_query(self, widget_query_id, data=None):
        self.answers.append((widget_query_id, data))
        return TelegramResult(DeliveryStatus.SENT)

    def edit_widget_data(self, chat_id, message_id, chat_data):
        self.edits.append(('data', chat_id, message_id, chat_data))
        return TelegramResult(DeliveryStatus.SENT)

    def edit_reply_markup(self, chat_id, message_id, reply_markup):
        self.edits.append(('markup', chat_id, message_id, reply_markup))
        return TelegramResult(DeliveryStatus.SENT)

    def edit_caption(self, chat_id, message_id, caption):
        self.edits.append(('caption', chat_id, message_id, caption))
        return TelegramResult(DeliveryStatus.SENT)
