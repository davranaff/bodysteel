from django.db import models

from store.content.html import sanitize_html


class SanitizedHtmlField(models.TextField):
    def pre_save(self, model_instance, add):
        value = super().pre_save(model_instance, add)
        sanitized = sanitize_html(value)
        setattr(model_instance, self.attname, sanitized)
        return sanitized
