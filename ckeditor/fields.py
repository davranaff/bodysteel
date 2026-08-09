from django.db import models


class RichTextField(models.TextField):
    """TextField shim used only while replaying historical store migrations."""
