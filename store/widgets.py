from django import forms


class RichHtmlWidget(forms.Textarea):
    """A readable HTML source editor for sanitized store-authored content."""

    class Media:
        css = {'all': ('admin/css/body-steel-rich-html.css',)}

    def __init__(self, attrs=None):
        defaults = {
            'class': 'bs-rich-html-source',
            'rows': 18,
            'spellcheck': 'false',
            'placeholder': '<p>Введите HTML-контент...</p>',
        }
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults)
