from django import forms
from django.core.files.uploadedfile import UploadedFile

from courses.models import Lesson


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single = not isinstance(data, (list, tuple))
        values = [data] if single else data
        clean_value = super().clean
        cleaned = [clean_value(value, initial) for value in values if value]
        if not cleaned and self.required:
            raise forms.ValidationError(self.error_messages['required'], code='required')
        return cleaned


class LessonMaterialUploadForm(forms.Form):
    lesson = forms.ModelChoiceField(
        label='Урок',
        queryset=Lesson.objects.select_related('module__course').order_by(
            'module__course__title_ru', 'module__position', 'position', 'id',
        ),
        empty_label='Выберите урок',
    )
    files = MultipleFileField(
        label='Файлы урока',
        help_text='Можно выбрать несколько изображений, видео, аудио или документов одновременно.',
        widget=MultipleFileInput(attrs={'accept': 'image/*,video/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.zip'}),
    )
    is_downloadable = forms.BooleanField(label='Разрешить скачивание', required=False, initial=True)

    def clean_files(self):
        files = self.cleaned_data['files']
        for uploaded in files:
            if not isinstance(uploaded, UploadedFile):
                raise forms.ValidationError('Некорректный файл.')
        return files
