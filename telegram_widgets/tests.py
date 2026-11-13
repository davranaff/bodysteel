from django.test import SimpleTestCase

from customer_telegram.shop.labels import WIDGET
from teleg.cards import LABELS as STAFF_LABELS
from telegram_widgets.html import (
    MAXIMUM_COMPRESSED_BYTES,
    TEMPLATE_NAMES,
    WidgetTooLarge,
    check_size,
    compressed_size,
    render,
    safe_json,
)
from telegram_widgets.state import MAXIMUM_STATE_BYTES, clip, fit_rows, fits, size, valid_request


class WidgetHtmlTests(SimpleTestCase):
    def test_every_template_fits_with_both_languages_and_leaves_room_for_data(self):
        # The product card bakes in its own photo and labels, see test_shop_product_card.
        for name in set(TEMPLATE_NAMES) - {'product'}:
            for language in ('ru', 'uz'):
                with self.subTest(template=name, language=language):
                    html = render(name, WIDGET[language], None)
                    # A full 1024-byte state compresses to well under 1100 bytes.
                    self.assertLess(compressed_size(html), MAXIMUM_COMPRESSED_BYTES - 1100)

    def test_baked_data_cannot_close_the_script(self):
        html = render('card', STAFF_LABELS, {'t': ['</script><b onclick=x>&']})
        self.assertNotIn('</script><b', html)
        self.assertIn('\\u003c/script\\u003e', html)
        self.assertEqual(safe_json('<>&'), '"\\u003c\\u003e\\u0026"')

    def test_oversized_html_is_refused_before_it_reaches_telegram(self):
        noise = [str(index * 7919 % 104729) * 30 for index in range(400)]
        with self.assertRaises(WidgetTooLarge):
            render('card', STAFF_LABELS, {'t': noise})

    def test_nul_in_data_is_escaped_and_raw_nul_is_refused(self):
        self.assertNotIn('\x00', render('card', STAFF_LABELS, {'t': ['\x00']}))
        with self.assertRaises(WidgetTooLarge):
            check_size('<p>\x00</p>')


class WidgetStateTests(SimpleTestCase):
    def test_clip_counts_utf8_bytes_and_never_splits_a_letter(self):
        value = clip('Протеин ' * 40, 20)
        self.assertLessEqual(len(value.encode('utf-8')), 20)
        self.assertTrue(value.endswith('…'))
        self.assertEqual(clip('  a   b ', 10), 'a b')

    def test_fit_rows_shortens_titles_then_drops_rows_to_stay_under_1024_bytes(self):
        rows = [[index, 'Очень длинное название протеина номер {} '.format(index) * 4, 100_000] for index in range(30)]
        state = {'v': 'l'}
        hidden = fit_rows(state, 'i', rows)
        self.assertTrue(fits(state))
        self.assertLessEqual(size(state), MAXIMUM_STATE_BYTES)
        self.assertEqual(len(state['i']) + hidden, 30)
        self.assertGreater(len(state['i']), 5)

    def test_request_data_is_one_to_64_bytes(self):
        self.assertTrue(valid_request('a:1'))
        self.assertFalse(valid_request(''))
        self.assertFalse(valid_request('я' * 33))
        self.assertFalse(valid_request(None))
