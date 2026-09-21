from django.test import RequestFactory, SimpleTestCase, TestCase

from store.admin_catalog import ProductAdmin
from store.admin_site import bodysteel_admin_site
from store.catalog.search import smart_product_ids, smart_search_score
from store.models import Brand, Product


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

    def test_matches_terms_across_name_and_brand_with_mixed_alphabets(self):
        score = smart_search_score(
            'Спортс Research витамин D3 K2',
            ('Vitamin D3 + K2, 160 капсул', 'Sports Research'),
        )
        self.assertGreater(score, 0)

    def test_corrects_one_wrong_layout_word_in_mixed_query(self):
        score = smart_search_score('ghjntby Optimum', ('Протеин Gold Standard', 'Optimum Nutrition'))
        self.assertGreater(score, 0)

    def test_accepts_latin_lookalike_inside_cyrillic_word(self):
        score = smart_search_score('Cпорт', ('Спорт',))
        self.assertGreater(score, 0)


class SmartAdminSearchTests(TestCase):
    def test_catalog_admin_finds_brand_and_sku_and_respects_filters(self):
        brand = Brand.objects.create(name='Sports Research')
        product = Product.objects.create(
            name_ru='Витамин D3 + K2, 160 капсул', name_uz='Vitamin D3 K2, 160 kapsula',
            slug='sports-research-d3-k2-test', price=485000, quantity=15,
            regos_item_code='SR-D3K2-160', brand=brand,
        )
        other = Product.objects.create(
            name_ru='Витамин C, 100 капсул', name_uz='Vitamin C, 100 kapsula',
            slug='vitamin-c-test', price=100000, quantity=0,
        )
        admin = ProductAdmin(Product, bodysteel_admin_site)
        request = RequestFactory().get('/admin/store/product/')
        results, duplicates = admin.get_search_results(
            request, Product.objects.all(), 'Sport Research Vitamin D3 K2 160',
        )
        self.assertFalse(duplicates)
        self.assertEqual(list(results.values_list('pk', flat=True)), [product.pk])
        self.assertEqual(smart_product_ids(Product.objects.filter(pk=other.pk), 'SR-D3K2-160'), [])
        self.assertEqual(smart_product_ids(Product.objects.all(), 'SR-D3K2-160'), [product.pk])
