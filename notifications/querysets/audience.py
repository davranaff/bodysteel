from datetime import timedelta

from django.conf import settings
from django.db.models import BigIntegerField, Count, Exists, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from courses.models import CourseAccess
from customer_telegram.models import CustomerTelegramChat
from notifications.models import PushDevice
from notifications.serializers.audience import AudienceSerializer
from store.models import Basket, Favorite, Order
from users.models import User


def audience_values(values):
    serializer = AudienceSerializer(data=values)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def eligible_devices(now=None):
    current = now or timezone.now()
    return PushDevice.objects.filter(
        is_active=True, marketing_opt_in=True, permission__in=('authorized', 'provisional'),
        user__is_active=True, user__deleted_at__isnull=True, user__auth_token__isnull=False,
        last_seen_at__gte=current - timedelta(days=settings.PUSH_DEVICE_STALE_DAYS),
    ).exclude(token_digest__isnull=True)


def audience_devices(filters, now=None):
    values = audience_values(filters)
    users = audience_users(values, now)
    devices = eligible_devices(now).filter(user_id__in=users.values('pk'))
    for key, field in [('platforms', 'platform__in'), ('languages', 'language__in'),
                       ('device_models', 'model__in'), ('app_version', 'app_version'),
                       ('os_version_prefix', 'os_version__startswith'),
                       ('device_seen_after', 'last_seen_at__gte'), ('device_seen_before', 'last_seen_at__lte')]:
        if values.get(key):
            devices = devices.filter(**{field: values[key]})
    if values['one_device_per_user']:
        newest = devices.filter(user_id=OuterRef('user_id')).order_by('-last_seen_at', '-pk')
        devices = devices.filter(pk=Subquery(newest.values('pk')[:1]))
    return devices.order_by('pk')


def audience_users(values, now=None):
    current = now or timezone.now()
    users = User.objects.filter(is_active=True, deleted_at__isnull=True)
    if not values['include_staff']:
        users = users.filter(is_staff=False, is_superuser=False)
    for key, field in [('user_ids', 'pk__in'), ('group_ids', 'groups__pk__in'),
                       ('joined_after', 'date_joined__gte'), ('joined_before', 'date_joined__lte'),
                       ('login_after', 'last_login__gte'), ('login_before', 'last_login__lte'), ('bonus_used', 'bonus_used')]:
        if key in values and values[key] != []:
            users = users.filter(**{field: values[key]})
    for key in ('phone_verified', 'email_verified'):
        if key in values:
            users = users.filter(**{key.replace('_verified', '_verified_at__isnull'): not values[key]})
    linked = CustomerTelegramChat.objects.filter(user_id=OuterRef('pk'), is_active=True)
    users = _exists(users, values, 'telegram_connected', linked)
    users = _purchase_users(users, values)
    cart = Basket.objects.filter(user_id=OuterRef('pk'), order_id__isnull=True)
    favorites = Favorite.objects.filter(user_id=OuterRef('pk'))
    users = _exists(users, values, 'has_cart', cart)
    users = _exists(users, values, 'has_favorites', favorites)
    for prefix, items in [('cart', cart), ('favorite', favorites)]:
        if any(values.get(prefix + '_' + kind + '_ids') for kind in ('product', 'category', 'brand')):
            users = users.filter(Exists(_product_filters(items, prefix, values)))
    accesses = CourseAccess.objects.filter(user_id=OuterRef('pk'), status='active').filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=current))
    users = _exists(users, values, 'has_course_access', accesses)
    if values.get('course_ids'):
        users = users.filter(Exists(accesses.filter(course_id__in=values['course_ids'])))
    return users.distinct()


def _purchase_users(users, values):
    orders = _orders(values, OuterRef('pk'))
    if any(values.get(key) for key in ('fulfillment_statuses', 'payment_statuses', 'delivery_methods', 'delivery_zones')):
        users = users.filter(Exists(orders))
    users = _exists(users, values, 'used_coupon', orders.filter(coupon__isnull=False))
    aggregates = orders.order_by().values('user_id')
    for prefix, aggregate in [('order_count', Count('pk')), ('spend', Sum('total_price'))]:
        if prefix + '_min' in values or prefix + '_max' in values:
            query = aggregates.annotate(value=aggregate).values('value')
            users = users.annotate(**{'_push_' + prefix: Coalesce(Subquery(query[:1]), Value(0), output_field=BigIntegerField())})
            for suffix, operation in [('min', 'gte'), ('max', 'lte')]:
                if prefix + '_' + suffix in values:
                    users = users.filter(**{'_push_' + prefix + '__' + operation: values[prefix + '_' + suffix]})
    latest = orders.order_by('-created_at', '-pk')
    if 'last_purchase_after' in values or 'last_purchase_before' in values:
        users = users.annotate(_push_last_date=Subquery(latest.values('created_at')[:1]))
        for suffix, operation in [('after', 'gte'), ('before', 'lte')]:
            if 'last_purchase_' + suffix in values:
                users = users.filter(**{'_push_last_date__' + operation: values['last_purchase_' + suffix]})
    for prefix in ('purchased', 'last_purchase'):
        if any(values.get(prefix + '_' + kind + '_ids') for kind in ('product', 'category', 'brand')):
            if prefix == 'last_purchase':
                users = users.annotate(_push_last_order=Subquery(latest.values('pk')[:1]))
                items = Basket.objects.filter(order_id=OuterRef('_push_last_order'))
            else:
                qualified = _orders(values, OuterRef(OuterRef('pk')))
                items = Basket.objects.filter(order_id__in=qualified.values('pk'))
            users = users.filter(Exists(_product_filters(items, prefix, values)))
    return users


def _orders(values, reference):
    orders = Order.objects.filter(user_id=reference)
    scope = values['order_scope']
    if scope == 'purchases':
        orders = orders.exclude(fulfillment_status='cancelled').exclude(payment_status='refunded').filter(
            Q(status='purchased') | Q(payment_status='paid') | Q(fulfillment_status='delivered'))
    elif scope == 'paid':
        orders = orders.filter(payment_status='paid').exclude(fulfillment_status='cancelled')
    elif scope == 'delivered':
        orders = orders.filter(fulfillment_status='delivered').exclude(payment_status='refunded')
    for key, field in [('fulfillment_statuses', 'fulfillment_status__in'), ('payment_statuses', 'payment_status__in'),
                       ('delivery_methods', 'delivery_method_code__in'), ('delivery_zones', 'delivery_zone_code__in')]:
        if values.get(key):
            orders = orders.filter(**{field: values[key]})
    return orders


def _product_filters(items, prefix, values):
    for kind, field in [('product', 'product_id'), ('category', 'product__category__pk'), ('brand', 'product__brand_id')]:
        if values.get(prefix + '_' + kind + '_ids'):
            items = items.filter(**{field + '__in': values[prefix + '_' + kind + '_ids']})
    return items


def _exists(users, values, key, query):
    return users.filter(Exists(query) if values[key] else ~Exists(query)) if key in values else users
