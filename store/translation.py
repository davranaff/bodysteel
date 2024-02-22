from modeltranslation.translator import translator, TranslationOptions
from store.models import SetOfProducts


class SetOfProductsTranslationOptions(TranslationOptions):
    fields = ('name', '')


translator.register(SetOfProducts, SetOfProductsTranslationOptions)
