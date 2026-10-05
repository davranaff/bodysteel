from django.conf import settings
from django.db import models


class SavdoqShopperSession(models.Model):
    """Reused SAVDOQ widget session: one per customer, language and sign-in.

    SAVDOQ keeps one conversation per widget session, so reusing it keeps the
    web widget on the same conversation across page loads. The access token is
    short-lived; rotating the customer's DRF token makes the row unusable.
    """

    class Language(models.TextChoices):
        RU = 'ru', 'Русский'
        UZ = 'uz', 'Oʻzbekcha'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='+',
    )
    language = models.CharField(max_length=2, choices=Language.choices)
    credential_digest = models.CharField(max_length=64)
    access_token = models.TextField()
    session_id = models.UUIDField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Сессия AI-чата'
        verbose_name_plural = 'Сессии AI-чата'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'language'],
                name='users_savdoq_session_user_language_unique',
            ),
        ]
        indexes = [models.Index(fields=['expires_at'], name='users_savdoq_session_exp_idx')]
