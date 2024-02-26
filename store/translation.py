from modeltranslation.translator import TranslationOptions, register
from store.models import SetOfProduct, Menu, Filial, Category, Blog, Product


@register(SetOfProduct)
class SetOfProductsTranslationOptions(TranslationOptions):
    fields = ('name',)


@register(Menu)
class MenusTranslationOptions(TranslationOptions):
    fields = ('about', 'blog', 'set_product', 'delivery_and_payment')


@register(Filial)
class FilialTranslationOptions(TranslationOptions):
    fields = ('name', 'day_off')


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ('name',)


@register(Blog)
class BlogsTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


@register(Product)
class ProductsTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'country', 'composition')