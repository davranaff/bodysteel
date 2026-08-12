from django.db import models

from store.content.html import sanitize_html
from store.widgets import RichHtmlWidget


class SanitizedHtmlField(models.TextField):
    def formfield(self, **kwargs):
        # ModelAdmin supplies its generic AdminTextareaWidget override for TextField.
        # Replace it here so every sanitized HTML field gets the source editor.
        kwargs['widget'] = RichHtmlWidget
        form_field = super().formfield(**kwargs)
        guidance = (
            'Поддерживаются HTML-теги форматирования, ссылки, изображения, таблицы и списки. '
            'Скрипты, iframe и обработчики событий удаляются при сохранении.'
        )
        form_field.help_text = '{} {}'.format(form_field.help_text or '', guidance).strip()
        return form_field

    def pre_save(self, model_instance, add):
        value = super().pre_save(model_instance, add)
        sanitized = sanitize_html(value)
        setattr(model_instance, self.attname, sanitized)
        return sanitized
