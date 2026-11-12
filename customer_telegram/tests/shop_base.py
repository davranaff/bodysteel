import json

from customer_telegram.handlers import handle_update
from customer_telegram.models import CustomerTelegramChat, CustomerTelegramWidget
from customer_telegram.tests.base import FakeTelegramApi
from store.models import Category, Product


CHAT_ID = 7001


class ShopFixtures:
    """A chat, a category with products and helpers that drive the bot like Telegram does."""

    def setUp(self):
        self.api = FakeTelegramApi()
        self.chat = CustomerTelegramChat.objects.create(telegram_user_id=CHAT_ID, chat_id=CHAT_ID, language='ru')
        self.category = Category.objects.create(name_ru='Протеин', name_uz='Protein', sort=1, slug='protein', description='')
        self.whey = self.product('Сывороточный протеин 2 кг', 'whey', price=450_000, discount=50_000, quantity=3)
        self.creatine = self.product('Креатин моногидрат', 'creatine', price=150_000, quantity=10)
        self.hidden = self.product('Черновик', 'draft-item', price=1, quantity=5, status='draft')
        self.updates = 0
        self.queries = 0

    def product(self, name, slug, price, discount=0, quantity=5, status='manual'):
        product = Product.objects.create(
            name_ru=name, name_uz='{} uz'.format(name), price=price, discounted_price=discount, quantity=quantity,
            slug=slug, country_ru='США', country_uz='AQSH', regos_catalog_status=status,
        )
        product.category.add(self.category)
        return product

    def send(self, text=None, **extra):
        self.updates += 1
        message = {'message_id': self.updates, 'from': {'id': CHAT_ID, 'is_bot': False, 'first_name': 'Ali'},
                   'chat': {'id': CHAT_ID, 'type': 'private'}, **extra}
        if text is not None:
            message['text'] = text
        return handle_update({'update_id': self.updates, 'message': message}, self.api)

    def tap(self, widget, data, sender=CHAT_ID):
        self.queries += 1
        query = {
            'id': 'query-{}'.format(self.queries), 'from': {'id': sender, 'is_bot': False, 'first_name': 'Ali'},
            'chat': {'id': CHAT_ID, 'type': 'private'}, 'message_id': widget.message_id,
            'chat_instance': '1', 'type': {'type': 'data'}, 'data': data,
        }
        outcome = handle_update({'update_id': 10_000 + self.queries, 'widget_query': query}, self.api)
        answer = self.api.answers[-1]
        self.assertEqual(answer[0], query['id'])
        return outcome, (json.loads(answer[1]) if answer[1] else None)

    def storefront(self):
        return CustomerTelegramWidget.objects.filter(chat=self.chat, kind='storefront').latest('pk')

    def order_widget(self):
        return CustomerTelegramWidget.objects.filter(chat=self.chat, kind='order').latest('pk')

    def assert_fits(self, state):
        self.assertLessEqual(len(json.dumps(state, ensure_ascii=False, separators=(',', ':')).encode()), 1024)
