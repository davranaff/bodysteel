from django.apps import AppConfig


class IntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'integration'

    def ready(self):
        from integration import checks  # noqa: F401
        from integration import signals  # noqa: F401
