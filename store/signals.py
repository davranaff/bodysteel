from django.db.models.signals import post_save
from django.dispatch import receiver
from store.models import Review

@receiver(post_save, sender=Review)
def add_bonus_to_user(sender, instance, created, **kwargs):
    pass

