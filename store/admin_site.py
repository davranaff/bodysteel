from datetime import timedelta

from django.contrib import admin
from django.db.models import Count, Q, Sum
from django.urls import NoReverseMatch, path, reverse
from django.utils import timezone

from store.admin_rich_html import rich_html_image_upload


def format_uzs(value):
    """Format dashboard values without making presentation logic a template filter."""
    return '{:,.0f}'.format(value or 0).replace(',', ' ') + ' сум'


def admin_url(model, action='changelist', object_id=None):
    name = 'admin:{}_{}_{}'.format(model._meta.app_label, model._meta.model_name, action)
    try:
        if object_id is None:
            return reverse(name)
        return reverse(name, args=[object_id])
    except NoReverseMatch:
        return ''


class BodySteelAdminSite(admin.AdminSite):
    site_header = 'BODY STEEL / ОПЕРАЦИОННЫЙ ЦЕНТР'
    site_title = 'BodySteel Admin'
    index_title = 'Командный центр'
    index_template = 'admin/index.html'

    menu_app_titles = {
        'courses': 'Обучение',
        'customer_telegram': 'Клиентский Telegram-бот',
        'nutrition': 'Правильное питание',
        'payments': 'Оплата',
        'store': 'Магазин',
        'teleg': 'Бот заказов',
        'users': 'Пользователи',
    }
    menu_model_titles = {
        'courses.course': 'Курсы',
        'courses.courseaccess': 'Доступы к курсам',
        'courses.coursemodule': 'Модули курсов',
        'courses.coursepurchase': 'Покупки курсов',
        'courses.lesson': 'Уроки',
        'courses.lessonmaterial': 'Материалы уроков',
        'courses.lessonprogress': 'Прогресс уроков',
        'customer_telegram.customertelegramcampaign': 'Рассылки',
        'customer_telegram.customertelegramcampaignrecipient': 'Получатели рассылок',
        'customer_telegram.customertelegramchat': 'Клиенты Telegram',
        'nutrition.allergen': 'Аллергены',
        'nutrition.deliverymethod': 'Способы доставки',
        'nutrition.deliveryslot': 'Интервалы доставки',
        'nutrition.deliveryzone': 'Зоны доставки',
        'nutrition.foodtag': 'Теги блюд',
        'nutrition.mealproduct': 'Блюда правильного питания',
        'nutrition.nutritionprofile': 'Профили питания',
        'payments.payment': 'Платежи',
        'payments.paymentevent': 'События платежей',
        'store.basket': 'Корзины',
        'store.blog': 'Блоги',
        'store.brand': 'Бренды',
        'store.category': 'Категории',
        'store.coupon': 'Купоны',
        'store.filial': 'Филиалы',
        'store.filialphoto': 'Фото филиалов',
        'store.menu': 'Меню сайта',
        'store.order': 'Заказы',
        'store.product': 'Товары',
        'store.product360image': '360° изображения товаров',
        'store.productimage': 'Изображения товаров',
        'store.review': 'Отзывы',
        'store.setofproduct': 'Комплекты товаров',
        'teleg.chat': 'Чаты сотрудников',
        'teleg.secretphrase': 'Секретные ключи',
        'users.user': 'Пользователи',
    }

    def get_urls(self):
        custom_urls = [
            path(
                'rich-html/upload/',
                self.admin_view(rich_html_image_upload),
                name='rich-html-upload',
            ),
        ]
        return custom_urls + super().get_urls()

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        for app in app_list:
            app['name'] = self.menu_app_titles[app['app_label']]
            for model in app['models']:
                model['name'] = self.menu_model_titles[model['model']._meta.label_lower]
            app['models'].sort(key=lambda model: model['name'].casefold())
        return sorted(app_list, key=lambda app: app['name'].casefold())

    def each_context(self, request):
        context = super().each_context(request)
        context.update({
            'brand_name': 'BODY STEEL',
            'brand_tagline': 'Питание для сильных результатов',
        })
        return context

    def index(self, request, extra_context=None):
        context = self.dashboard_context()
        if extra_context:
            context.update(extra_context)
        return super().index(request, extra_context=context)

    def dashboard_context(self):
        from integration.models import IntegrationWebhookEvent
        from store.models import Coupon, Order, Product
        from users.models import User

        now = timezone.now()
        month_start = now - timedelta(days=30)
        paid_orders = Order.objects.filter(status='purchased')
        revenue = paid_orders.filter(created_at__gte=month_start).aggregate(total=Sum('total_price'))['total']
        recent_orders = list(Order.objects.select_related('user').order_by('-created_at')[:7])
        for order in recent_orders:
            order.admin_url = admin_url(Order, 'change', order.pk)

        stock_alerts = list(
            Product.objects.filter(quantity__lte=5).select_related('brand').order_by('quantity', 'name_ru')[:7]
        )
        for product in stock_alerts:
            product.admin_url = admin_url(Product, 'change', product.pk)

        top_products = Product.objects.annotate(
            sold_count=Count('baskets', filter=Q(baskets__order__isnull=False)),
        ).order_by('-sold_count', 'name_ru')[:5]
        webhook_pending = IntegrationWebhookEvent.objects.filter(
            status__in=('pending', 'retry', 'failed'),
        ).count()

        return {
            'dashboard': {
                'metrics': [
                    {
                        'label': 'Выручка за 30 дней',
                        'value': format_uzs(revenue),
                        'hint': 'по завершённым заказам',
                        'tone': 'lime',
                        'icon': 'chart',
                    },
                    {
                        'label': 'Заказы сегодня',
                        'value': Order.objects.filter(created_at__date=now.date()).count(),
                        'hint': 'новые заявки и покупки',
                        'tone': 'blue',
                        'icon': 'orders',
                    },
                    {
                        'label': 'На модерации',
                        'value': Order.objects.filter(status='moderation').count(),
                        'hint': 'требуют внимания команды',
                        'tone': 'orange',
                        'icon': 'pulse',
                    },
                    {
                        'label': 'Клиенты',
                        'value': User.objects.filter(is_staff=False).count(),
                        'hint': 'зарегистрированных покупателей',
                        'tone': 'violet',
                        'icon': 'users',
                    },
                ],
                'catalog': {
                    'products': Product.objects.count(),
                    'in_stock': Product.objects.filter(quantity__gt=0).count(),
                    'out_of_stock': Product.objects.filter(quantity=0).count(),
                    'coupons': Coupon.objects.filter(is_active=True).count(),
                },
                'recent_orders': recent_orders,
                'stock_alerts': stock_alerts,
                'top_products': top_products,
                'webhook_pending': webhook_pending,
                'quick_actions': [
                    {
                        'label': 'Добавить товар',
                        'description': 'Создать новую карточку каталога',
                        'url': admin_url(Product, 'add'),
                        'tone': 'lime',
                    },
                    {
                        'label': 'Проверить заказы',
                        'description': 'Открыть очередь модерации',
                        'url': admin_url(Order),
                        'tone': 'blue',
                    },
                    {
                        'label': 'Обновить купон',
                        'description': 'Настроить активные предложения',
                        'url': admin_url(Coupon),
                        'tone': 'orange',
                    },
                ],
            },
        }


bodysteel_admin_site = BodySteelAdminSite(name='bodysteel_admin')
