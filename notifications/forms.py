from django import forms
from django.contrib.auth.models import Group
from django.contrib.admin.widgets import AutocompleteSelectMultiple
from django.utils.dateparse import parse_datetime

from courses.models import CourseAccess
from notifications.models import PushCampaign, PushDevice
from notifications.serializers.audience import AudienceSerializer
from store.admin_site import bodysteel_admin_site
from store.models import Basket, Product
from users.models import User

BASE_FIELDS = ('name', 'title_ru', 'body_ru', 'title_uz', 'body_uz', 'target_url', 'scheduled_at')


def _tri(label):
    return forms.TypedChoiceField(label=label, required=False, choices=(('', 'Не важно'),
        ('true', 'Да'), ('false', 'Нет')), coerce=lambda value: value == 'true', empty_value=None)


def _multiple(label, relation):
    return forms.ModelMultipleChoiceField(label=label, required=False,
        queryset=relation.remote_field.model.objects.all(),
        widget=AutocompleteSelectMultiple(relation, bodysteel_admin_site))


def audience_form_fields():
    fields = {
        'platforms': forms.MultipleChoiceField(label='Платформы', required=False, choices=PushDevice.Platform.choices),
        'languages': forms.MultipleChoiceField(label='Язык приложения', required=False, choices=(('ru', 'Русский'), ('uz', 'Узбекский'))),
        'device_models': forms.CharField(label='Модели устройств', required=False, max_length=1000,
            help_text='Точные значения из списка устройств, через запятую. Это не возраст или параметры человека.'),
        'app_version': forms.CharField(label='Версия приложения (точно)', required=False, max_length=40),
        'os_version_prefix': forms.CharField(label='Версия ОС начинается с', required=False, max_length=40),
        'include_staff': forms.BooleanField(label='Включать сотрудников', required=False),
        'one_device_per_user': forms.BooleanField(label='Только последнее подходящее устройство пользователя', required=False),
        'user_ids': _multiple('Конкретные пользователи', PushDevice._meta.get_field('user')),
        'group_ids': forms.ModelMultipleChoiceField(label='Группы доступа', required=False, queryset=Group.objects.all()),
        'phone_verified': _tri('Телефон подтверждён'), 'email_verified': _tri('E-mail подтверждён'),
        'bonus_used': _tri('Приветственный бонус использован'), 'telegram_connected': _tri('Активный Telegram подключён'),
        'order_scope': forms.ChoiceField(label='Какие заказы считать', choices=(
            ('purchases', 'Покупки: куплен / оплачен / доставлен, без отмен и возвратов'),
            ('paid', 'Оплаченные без отмен'), ('delivered', 'Доставленные без возвратов'), ('all', 'Все заказы, включая неоплаченные'))),
        'fulfillment_statuses': forms.MultipleChoiceField(label='Статусы выполнения', required=False, choices=(
            ('new', 'Новый'), ('confirmed', 'Подтверждён'), ('preparing', 'Готовится'), ('ready', 'Готов к выдаче'),
            ('delivering', 'В доставке'), ('delivered', 'Доставлен'), ('cancelled', 'Отменён'))),
        'payment_statuses': forms.MultipleChoiceField(label='Статусы оплаты', required=False, choices=(
            ('unpaid', 'Не оплачен'), ('pending', 'Ожидает оплаты'), ('paid', 'Оплачен'), ('failed', 'Ошибка'), ('refunded', 'Возвращён'))),
        'delivery_methods': forms.CharField(label='Коды способов доставки', required=False, max_length=1000,
            help_text='Коды из заказов через запятую. Фильтр относится к выбранному типу заказов.'),
        'delivery_zones': forms.CharField(label='Коды зон доставки', required=False, max_length=1000,
            help_text='Коды из заказов через запятую.'),
        'used_coupon': _tri('Есть заказ с купоном'), 'has_cart': _tri('Есть товары в открытой корзине'),
        'has_favorites': _tri('Есть избранное'), 'has_course_access': _tri('Есть действующий доступ к курсам'),
        'course_ids': _multiple('Действующий доступ к конкретным курсам', CourseAccess._meta.get_field('course')),
    }
    for prefix, label in [('device_seen', 'Активность устройства'), ('joined', 'Регистрация аккаунта'),
                          ('login', 'Последний вход'), ('last_purchase', 'Последняя выбранная покупка')]:
        for suffix, boundary in [('after', 'с'), ('before', 'по')]:
            fields[prefix + '_' + suffix] = forms.DateTimeField(label=label + ' ' + boundary, required=False,
                widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'))
    for prefix, label in [('order_count', 'Количество выбранных заказов'), ('spend', 'Сумма выбранных заказов, сум')]:
        for suffix, boundary in [('min', 'от'), ('max', 'до')]:
            fields[prefix + '_' + suffix] = forms.IntegerField(label=label + ' ' + boundary, required=False, min_value=0)
    relations = {'product': Basket._meta.get_field('product'), 'category': Product._meta.get_field('category'), 'brand': Product._meta.get_field('brand')}
    for prefix, label in [('purchased', 'Любая выбранная покупка'), ('last_purchase', 'Только последняя выбранная покупка'),
                          ('cart', 'Открытая корзина'), ('favorite', 'Избранное')]:
        for kind, noun in [('product', 'товары'), ('category', 'категории'), ('brand', 'бренды')]:
            fields[prefix + '_' + kind + '_ids'] = _multiple(label + ': ' + noun, relations[kind])
    return fields


class PushCampaignForm(forms.ModelForm):
    class Meta:
        model = PushCampaign
        fields = BASE_FIELDS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(audience_form_fields())
        for key, field in self.fields.items():
            if key not in BASE_FIELDS:
                value = self.instance.audience.get(key)
                if key in ('device_models', 'delivery_methods', 'delivery_zones') and value:
                    value = ', '.join(value)
                if isinstance(field, forms.DateTimeField) and isinstance(value, str):
                    value = parse_datetime(value)
                field.initial = value if value is not None else ('purchases' if key == 'order_scope' else None)

    def clean(self):
        cleaned = super().clean()
        filters = {}
        for key in audience_form_fields():
            value = cleaned.get(key)
            if value is None or value == '' or value == []:
                continue
            if isinstance(value, forms.models.ModelChoiceIteratorValue):
                value = value.value
            if hasattr(value, 'values_list'):
                value = list(value.values_list('pk', flat=True))
            elif key in ('device_models', 'delivery_methods', 'delivery_zones'):
                value = [part.strip() for part in value.split(',') if part.strip()]
            elif hasattr(value, 'isoformat'):
                value = value.isoformat()
            filters[key] = value
        validator = AudienceSerializer(data=filters)
        if not validator.is_valid():
            for key in validator.errors:
                self.add_error(key if key in self.fields else None, 'Проверьте значение и границы фильтра.')
        self.instance.audience = filters
        return cleaned


DEVICE_FIELDS = ('platforms', 'languages', 'device_models', 'app_version', 'os_version_prefix',
                 'device_seen_after', 'device_seen_before', 'one_device_per_user')
ACCOUNT_FIELDS = ('user_ids', 'include_staff', 'group_ids', 'joined_after', 'joined_before', 'login_after',
                  'login_before', 'phone_verified', 'email_verified', 'bonus_used', 'telegram_connected')
PURCHASE_FIELDS = ('order_scope', 'order_count_min', 'order_count_max', 'spend_min', 'spend_max',
                   'last_purchase_after', 'last_purchase_before', 'fulfillment_statuses', 'payment_statuses',
                   'delivery_methods', 'delivery_zones', 'used_coupon') + tuple(
    prefix + '_' + kind + '_ids' for prefix in ('purchased', 'last_purchase') for kind in ('product', 'category', 'brand'))
INTEREST_FIELDS = ('has_cart', 'has_favorites', 'has_course_access', 'course_ids') + tuple(
    prefix + '_' + kind + '_ids' for prefix in ('cart', 'favorite') for kind in ('product', 'category', 'brand'))
