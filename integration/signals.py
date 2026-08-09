from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

from integration.orders.events import enqueue_completed_order
from integration.webhooks.events import enqueue_inventory_events, enqueue_product_events
from store.models import Brand, Category, Order, Product, ProductImage


def bump_products(product_ids):
    ids = tuple(sorted({product_id for product_id in product_ids if product_id is not None}))
    if ids:
        Product.objects.filter(pk__in=ids).update(updated_at=timezone.now())
        enqueue_product_events('product.updated', ids)


@receiver(pre_save, sender=Product)
def remember_previous_product_quantity(sender, instance, **kwargs):
    if not instance.pk:
        return
    instance._integration_previous_quantity = (
        Product.objects.filter(pk=instance.pk).values_list('quantity', flat=True).first()
    )


@receiver(post_save, sender=Product)
def product_saved(sender, instance, created, **kwargs):
    enqueue_product_events(
        'product.created' if created else 'product.updated',
        (instance.pk,),
        instance.updated_at,
    )
    previous_quantity = getattr(instance, '_integration_previous_quantity', None)
    if created or previous_quantity != instance.quantity:
        enqueue_inventory_events((instance.pk,), instance.updated_at)


@receiver(post_delete, sender=Product)
def product_deleted(sender, instance, **kwargs):
    enqueue_product_events('product.deleted', (instance.pk,))


@receiver(pre_save, sender=ProductImage)
def remember_previous_image_product(sender, instance, **kwargs):
    if not instance.pk:
        return
    instance._integration_previous_product_id = (
        ProductImage.objects.filter(pk=instance.pk).values_list('product_id', flat=True).first()
    )


@receiver(post_save, sender=ProductImage)
def product_image_saved(sender, instance, **kwargs):
    bump_products({
        instance.product_id,
        getattr(instance, '_integration_previous_product_id', None),
    })


@receiver(post_delete, sender=ProductImage)
def product_image_deleted(sender, instance, origin=None, **kwargs):
    if isinstance(origin, Product):
        return
    bump_products((instance.product_id,))


@receiver(post_save, sender=Brand)
@receiver(pre_delete, sender=Brand)
def brand_changed(sender, instance, **kwargs):
    bump_products(instance.products.values_list('pk', flat=True))


@receiver(post_save, sender=Category)
@receiver(pre_delete, sender=Category)
def category_changed(sender, instance, **kwargs):
    bump_products(instance.products.values_list('pk', flat=True))


@receiver(m2m_changed, sender=Product.category.through)
def product_categories_changed(sender, instance, action, reverse, pk_set, **kwargs):
    if action not in {'post_add', 'pre_remove', 'pre_clear'}:
        return
    if not reverse:
        bump_products((instance.pk,))
        return
    if action == 'pre_clear':
        bump_products(instance.products.values_list('pk', flat=True))
    else:
        bump_products(pk_set or ())


@receiver(pre_save, sender=Order)
def remember_previous_order_status(sender, instance, **kwargs):
    if not instance.pk:
        return
    instance._integration_previous_status = (
        Order.objects.filter(pk=instance.pk).values_list('status', flat=True).first()
    )


@receiver(post_save, sender=Order)
def order_saved(sender, instance, created, **kwargs):
    previous_status = getattr(instance, '_integration_previous_status', None)
    if instance.status == 'purchased' and previous_status != 'purchased':
        enqueue_completed_order(instance)
