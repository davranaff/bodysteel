from django.db import models

from customer_telegram.models import CustomerTelegramChat


class CustomerTelegramWidget(models.Model):
    """A widget message the bot sent; widget queries are checked against it."""

    STOREFRONT = 'storefront'
    ORDER = 'order'
    CARD = 'card'
    KIND_CHOICES = ((STOREFRONT, 'Витрина'), (ORDER, 'Заказ'), (CARD, 'Карточка'))

    chat = models.ForeignKey(
        CustomerTelegramChat, on_delete=models.CASCADE, related_name='widgets', verbose_name='Чат',
    )
    message_id = models.BigIntegerField(verbose_name='ID сообщения')
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, verbose_name='Тип')
    search_query = models.CharField(max_length=100, blank=True, default='', verbose_name='Поисковый запрос')
    screen = models.CharField(max_length=32, blank=True, default='h', verbose_name='Текущий экран')
    last_list = models.CharField(max_length=32, blank=True, default='h', verbose_name='Последний список')
    order = models.ForeignKey(
        'store.Order', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='customer_telegram_widgets', verbose_name='Заказ',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Виджет клиентского бота'
        verbose_name_plural = 'Виджеты клиентского бота'
        constraints = [models.UniqueConstraint(fields=('chat', 'message_id'), name='customer_tg_widget_message')]


class CustomerTelegramCart(models.Model):
    chat = models.OneToOneField(
        CustomerTelegramChat, on_delete=models.CASCADE, related_name='cart', verbose_name='Чат',
    )
    items = models.JSONField(default=dict, blank=True, verbose_name='Товары')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Корзина в боте'
        verbose_name_plural = 'Корзины в боте'


class CustomerTelegramCheckout(models.Model):
    """The order a chat is placing; contact details stay for the next order."""

    CONTACT = 'contact'
    ADDRESS = 'address'
    CONFIRM = 'confirm'
    PLACED = 'placed'
    STEP_CHOICES = (
        (CONTACT, 'Ждём телефон'), (ADDRESS, 'Ждём адрес'), (CONFIRM, 'Подтверждение'), (PLACED, 'Оформлен'),
    )

    chat = models.OneToOneField(
        CustomerTelegramChat, on_delete=models.CASCADE, related_name='checkout', verbose_name='Чат',
    )
    step = models.CharField(max_length=16, choices=STEP_CHOICES, default=CONTACT, verbose_name='Шаг')
    attempt = models.PositiveIntegerField(default=0, verbose_name='Номер оформления')
    delivery_type = models.CharField(max_length=16, blank=True, default='', verbose_name='Способ получения')
    full_name = models.CharField(max_length=255, blank=True, default='', verbose_name='Имя')
    phone = models.CharField(max_length=13, blank=True, default='', verbose_name='Телефон')
    address = models.CharField(max_length=255, blank=True, default='', verbose_name='Адрес')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='Широта')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='Долгота')
    order = models.ForeignKey(
        'store.Order', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='customer_telegram_checkouts', verbose_name='Заказ',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Оформление в боте'
        verbose_name_plural = 'Оформления в боте'
