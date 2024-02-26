from modeltranslation.translator import translator, TranslationOptions
from store.models import SetOfProduct, Menu, Filial, Category, Blog, Product


@translator.register(SetOfProduct)
class SetOfProductsTranslationOptions(TranslationOptions):
    fields = ('name',)


@translator.register(Menu)
class MenusTranslationOptions(TranslationOptions):
    fields = ('about', 'blog', 'set_product', 'delivery_and_payment')


@translator.register(Filial)
class FilialTranslationOptions(TranslationOptions):
    fields = ('name',)


@translator.register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ('name',)


@translator.register(Blog)
class BlogsTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


@translator.register(Product)
class ProductsTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'country', 'composition')