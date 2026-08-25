from django.apps import AppConfig


class CustomerTelegramConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'customer_telegram'
    verbose_name = 'Telegram для клиентов'

    def ready(self):
        from customer_telegram import checks  # noqa: F401
