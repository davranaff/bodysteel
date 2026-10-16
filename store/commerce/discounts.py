"""Checkout discount pricing shared by the quote endpoint and order creation.

Both callers must use :func:`price_discounts` so the quoted total can never
diverge from the amount an order is charged. Order creation passes
``lock=True`` and then applies the side effects (bonus spent, coupon used).
"""
from dataclasses import dataclass

from store.content.models import Menu
from store.commerce.models import Coupon
from users.models import User


@dataclass(frozen=True)
class DiscountPricing:
    subtotal: int
    bonus_discount: int
    coupon_discount: int
    coupon: Coupon | None
    user: User | None
    bonus_eligible: bool

    @property
    def discount(self):
        return self.bonus_discount + self.coupon_discount

    @property
    def discounted_subtotal(self):
        return self.subtotal - self.discount

    @property
    def coupon_applied(self):
        return self.coupon is not None


def price_discounts(subtotal, actor, coupon_code, lock=False):
    """Apply the one-time account bonus first, then the coupon percentage."""
    subtotal = int(subtotal)
    user = _customer(actor, lock)
    bonus = _available_bonus(user)
    after_bonus = max(0, subtotal - bonus) if bonus is not None else subtotal
    coupon = _usable_coupon(coupon_code, lock)
    after_coupon = after_bonus
    if coupon is not None:
        discount = int(after_bonus * (coupon.discount_percent / 100))
        after_coupon = max(0, after_bonus - discount)
    return DiscountPricing(
        subtotal=subtotal,
        bonus_discount=subtotal - after_bonus,
        coupon_discount=after_bonus - after_coupon,
        coupon=coupon,
        user=user,
        bonus_eligible=bonus is not None,
    )


def _customer(actor, lock):
    if not getattr(actor, 'is_authenticated', False):
        return None
    queryset = User.objects.select_for_update() if lock else User.objects
    return queryset.get(pk=actor.pk)


def _available_bonus(user):
    """Return the unused one-time bonus amount, or ``None`` when not eligible."""
    if user is None or user.bonus_used:
        return None
    bonus = Menu.objects.filter(is_active=True).values_list('bonus', flat=True).first()
    return None if bonus is None else int(bonus)


def _usable_coupon(code, lock):
    if not code:
        return None
    queryset = Coupon.objects.select_for_update() if lock else Coupon.objects
    coupon = queryset.filter(code__iexact=code, is_active=True).first()
    if coupon is None or not coupon.can_use():
        return None
    return coupon
