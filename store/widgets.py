from django import forms
from django.urls import reverse


class RichHtmlWidget(forms.Textarea):
    """Progressively enhanced visual editor for sanitized store-authored HTML."""

    class Media:
        css = {'all': ('admin/css/body-steel-rich-html.css',)}
        js = ('admin/js/body-steel-rich-html.js',)

    def __init__(self, attrs=None):
        defaults = {
            'class': 'bs-rich-html-source',
            'rows': 18,
            'spellcheck': 'true',
            'placeholder': '<p>Введите HTML-контент...</p>',
            'data-rich-html-editor': 'true',
            'data-upload-url': reverse('bodysteel_admin:rich-html-upload'),
        }
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults)
