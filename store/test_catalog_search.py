from django.test import SimpleTestCase

from store.catalog.search import smart_search_score


class SmartCatalogSearchTests(SimpleTestCase):
    def test_accepts_typo_in_product_name(self):
        score = smart_search_score('протин', ('Сывороточный протеин Whey',))
        self.assertGreater(score, 0)

    def test_accepts_transposed_letters(self):
        score = smart_search_score('proetin', ('Whey Protein',))
        self.assertGreater(score, 0)

    def test_accepts_cyrillic_product_searched_in_latin(self):
        score = smart_search_score('protein', ('Сывороточный протеин',))
        self.assertGreaterEqual(score, 100)

    def test_corrects_english_keyboard_used_for_russian_word(self):
        score = smart_search_score('ghjntby', ('Протеин',))
        self.assertGreaterEqual(score, 100)

    def test_matches_brand_and_category(self):
        score = smart_search_score('optimum', ('Gold Standard', 'Optimum Nutrition', 'Протеин'))
        self.assertGreaterEqual(score, 100)

    def test_rejects_unrelated_short_word(self):
        score = smart_search_score('масса', ('Омега 3', 'Витамины', 'NOW Foods'))
        self.assertEqual(score, 0)
