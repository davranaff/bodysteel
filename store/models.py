from ckeditor.fields import RichTextField
from django.db import models


def category_directory_path(instance, filename):
    return 'categories/{0}/{1}'.format(instance.name, filename)


def blog_directory_path(instance, filename):
    return 'blog/{0}/{1}'.format(instance.name, filename)


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class SetOfProducts(BaseModel):
    name = models.CharField(max_length=255, verbose_name="Название комплекта", null=False, blank=False)
    photo = models.ImageField(upload_to='set/%Y/%m/%d', verbose_name="Картинка комплекта", null=False, blank=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Комплект"
        verbose_name_plural = "Комплекты"
        unique_together = ('name',)


class Category(BaseModel):
    name = models.CharField(max_length=255, verbose_name="Название категории", null=False, blank=False)
    photo = models.ImageField(upload_to=category_directory_path, verbose_name="Картинка категории", null=False,
                              blank=False)
    sort = models.PositiveIntegerField(verbose_name="Сортировка Категории",
                                       help_text='сортируется по возрастанию, у каждой категории должен быть уникальный номер',
                                       null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        unique_together = ('name', 'sort')


class Blog(BaseModel):
    name = models.CharField(max_length=255, verbose_name="Название блога", unique=True, null=False, blank=False)
    photo = models.ImageField(upload_to=category_directory_path, verbose_name="Картинка блога", null=False, blank=False)

    description = RichTextField(verbose_name="Описание блога", null=False, blank=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Блог"
        verbose_name_plural = "Блоги"


