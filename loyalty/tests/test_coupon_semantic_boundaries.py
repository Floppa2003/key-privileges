"""Literal expectations across source, publication, common and reader boundaries."""
import copy
import unittest

from catalogue_view import record_row
from normalized import make_offer
from test_dom_card_boundaries import project
from unified_normalization import normalize_record

NOW = '2026-11-13T00:00:00+00:00'


class CouponSemanticBoundaries(unittest.TestCase):
    def source(self, text, tables=None):
        return make_offer('moskvich', 'coupon-boundaries', 'Карта', 'Example',
                          'Скидка 10% на меню.',
                          'https://moskvichmag.ru/programma-loyalnosti/', NOW,
                          conditions=text, tables=tables)

    def assert_codes(self, common, expected):
        self.assertEqual([c['value'] for c in common['codes'] if c['delivery'] == 'literal'], expected)
        reader, reason = record_row(common, NOW[:10])
        self.assertIsNone(reason)
        self.assertEqual(reader[3], '\n'.join('Код: ' + c for c in expected))

    def chain(self, text, expected):
        source = self.source(text)
        before = copy.deepcopy(source)
        common = project(source)
        self.assertEqual(source['promo_codes'], expected)
        self.assert_codes(common, expected)
        self.assertEqual(source, before)
        self.assertEqual(common['raw']['conditions'], text)
        self.assertEqual(common['raw']['observed_at'], NOW)
        self.assertEqual(common['id'], source['id'])
        return common

    def test_cancelled_occurrence_does_not_expose_old_code(self):
        for cancelled in ('Промокод OLD10 больше не действует.',
                          'Не используйте промокод OLD10.',
                          'Промокод OLD10 отменён.',
                          'Промокод OLD10 отменен.',
                          'Промокод OLD10 недействителен.'):
            for separator in (' ', '\n'):
                with self.subTest(cancelled=cancelled, separator=separator):
                    self.chain(cancelled + separator + 'Примените промокод NEW10.', ['NEW10'])

    def test_plural_cancelled_list_keeps_only_live_replacement_at_all_boundaries(self):
        for denial in ('отменены', 'больше не действуют', 'недействительны',
                       'аннулированы', 'ОТМЕНЕНЫ'):
            text = f'Промокоды «OLD10» и «OLD20» {denial}. Примените промокод NEW10.'
            source = self.source(text)
            common = project(source)
            with self.subTest(denial=denial, boundary='source'):
                self.assertEqual(source['promo_codes'], ['NEW10'])
            with self.subTest(denial=denial, boundary='common/reader'):
                self.assert_codes(common, ['NEW10'])
            raw = copy.deepcopy(common['raw'])
            raw['codes'] = ['OLD10', 'OLD20', 'NEW10']
            before = copy.deepcopy(raw)
            with self.subTest(denial=denial, boundary='retained/common/reader'):
                repaired = normalize_record(raw, as_of=NOW[:10])
                self.assert_codes(repaired, ['NEW10'])
                self.assertEqual(repaired['raw'], before)
            self.assertEqual(raw, before)
            self.assertEqual(common['raw']['conditions'], text)
            self.assertEqual(common['id'], source['id'])
            self.assertEqual(common['raw']['observed_at'], NOW)

    def test_plural_list_cancellation_owns_each_member_not_its_live_sibling(self):
        for live in ('OLD10', 'OLD20'):
            for separator in (' и ', ', ', ' / ', ' или '):
                text = (f'Промокоды «OLD10»{separator}«OLD20» отменены. '
                        f'Примените промокод {live}.')
                with self.subTest(live=live, separator=separator):
                    self.chain(text, [live])
                    raw = project(self.source(text))['raw']
                    raw['codes'] = ['OLD10', 'OLD20']
                    self.assert_codes(normalize_record(raw, as_of=NOW[:10]), [live])

    def test_plural_partial_restrictions_preserve_each_quoted_literal(self):
        for suffix in ('не действуют на алкоголь.', 'не действуют в этот день.',
                       'не действуют\nна алкоголь.',
                       'не действуют, если заказ включает алкоголь.',
                       'не действуют:\n– на рейсах партнёров.'):
            text = f'Промокоды «MOSKVICH MAG» и «NEW10 НА САЙТЕ» {suffix}'
            with self.subTest(suffix=suffix):
                self.chain(text, ['MOSKVICH MAG', 'NEW10 НА САЙТЕ'])
                raw = project(self.source(text))['raw']
                raw['codes'] = ['MOSKVICH MAG', 'NEW10 НА САЙТЕ']
                self.assert_codes(normalize_record(raw, as_of=NOW[:10]),
                                  ['MOSKVICH MAG', 'NEW10 НА САЙТЕ'])

    def test_negative_instruction_cancels_whole_licensed_list(self):
        text = 'Не используйте промокоды «OLD10» и «OLD20». Примените промокод NEW10.'
        self.chain(text, ['NEW10'])
        raw = project(self.source(text))['raw']
        raw['codes'] = ['OLD10', 'OLD20', 'NEW10']
        self.assert_codes(normalize_record(raw, as_of=NOW[:10]), ['NEW10'])

    def test_cancelled_quoted_list_preserves_independent_table_and_audience(self):
        text = 'Промокоды «OLD10» и «OLD20» отменены.'
        tables = [[['Тип карты', 'Скидка', 'Промокод'], ['Золотая', '7%', 'OLD20']]]
        common = project(self.source(text, tables))
        self.assertEqual([(c['value'], c['scope']) for c in common['codes']],
                         [('OLD20', {'card_type': 'Золотая'})])
        raw = project(self.source(text))['raw']
        raw['codes'] = ['OLD10', 'OLD20']
        raw['details']['audiences'] = [
            {'audience': 'youth', 'promo_code': 'OLD20', 'evidence': [text]},
            {'audience': 'senior', 'promo_code': 'OLD20',
             'evidence': ['Для пенсионеров промокод OLD20 действует.']},
        ]
        common = normalize_record(raw, as_of=NOW[:10])
        self.assertEqual([(c['value'], c['scope']) for c in common['codes']],
                         [('OLD20', {'audience': 'senior'})])
        self.assertEqual(common['raw'], raw)

    def test_cancelled_list_cannot_strip_live_quoted_multiword_literal(self):
        text = ('Промокоды «MOSKVICH MAG» и «NEW10 НА САЙТЕ» отменены. '
                'Примените промокод «NEW10 НА САЙТЕ».')
        self.chain(text, ['NEW10 НА САЙТЕ'])
        raw = project(self.source(text))['raw']
        raw['codes'] = ['MOSKVICH MAG', 'NEW10 НА САЙТЕ']
        self.assert_codes(normalize_record(raw, as_of=NOW[:10]), ['NEW10 НА САЙТЕ'])

    def test_denial_and_live_same_literal_keep_live_occurrence(self):
        for separator in ('. ', '; ', ', а '):
            with self.subTest(separator=separator):
                self.chain('Промокод SAME27 больше не действует' + separator +
                           'Примените промокод SAME27.', ['SAME27'])

    def test_cancellation_owns_its_literal_across_wrapped_source_lines(self):
        for cancelled in ('Промокод OLD10\nбольше не действует.',
                          'Промокод OLD10 БОЛЬШЕ НЕ ДЕЙСТВУЕТ.'):
            with self.subTest(cancelled=cancelled):
                self.chain(cancelled + '\nПримените промокод NEW10.', ['NEW10'])

    def test_uppercase_instructions_are_not_part_of_unquoted_literal(self):
        for instruction in ('НА САЙТЕ', 'ПРИ ЗАКАЗЕ', 'ДЛЯ ЗАКАЗА', 'на сайте'):
            with self.subTest(instruction=instruction):
                self.chain('Введите промокод NEW10 ' + instruction + '.', ['NEW10'])

    def test_multiword_and_quoted_literals_keep_exact_spelling(self):
        for text, codes in (
            ('Введите промокод MOSKVICH MAG при заказе.', ['MOSKVICH MAG']),
            ('Введите промокод «NEW10 НА САЙТЕ».', ['NEW10 НА САЙТЕ']),
        ):
            with self.subTest(text=text):
                self.chain(text, codes)

    def test_partial_exclusions_and_conditional_annulment_keep_literal(self):
        for text in (
            'Промокод NEW10 не действует на алкоголь.',
            'Промокод NEW10 не действует для тарифов корпоративного сегмента.',
            'Промокод NEW10 не действует при покупке медицинской техники.',
            'Промокод NEW10 в этот день не действует.',
            'Промокод NEW10 не действует в этот день.',
            'Промокод NEW10 не действует:\n– на рейсах партнёров;\n– на чартерных рейсах.',
            'После использования промокод NEW10 аннулируется и не может быть использован повторно.',
            'Если не активировать промокод NEW10 до истечения срока действия, он будет аннулирован.',
            'При использовании промокода NEW10 кэшбэк может быть отменен.',
            'При использовании промокода NEW10 заказ может быть отменен.',
        ):
            with self.subTest(text=text):
                self.chain(text, ['NEW10'])

    def test_wrapped_and_comma_restrictions_keep_their_literal(self):
        for text in (
            'Промокод NEW10 не действует\nна алкоголь.',
            'Промокод NEW10 не действует\nв этот день.',
            'Промокод NEW10 не действует, если заказ включает алкоголь.',
        ):
            with self.subTest(text=text):
                self.chain(text, ['NEW10'])

    def test_restriction_continuation_cannot_rescue_cancelled_sibling(self):
        for separator in ('\n', ', ', ', а '):
            for live in ('Промокод NEW10 не действует\nна алкоголь.',
                         'для пенсионеров промокод NEW10 действует.'):
                with self.subTest(separator=separator, live=live):
                    self.chain('Промокод OLD10 не действует' + separator + live, ['NEW10'])

    def test_negative_instruction_keeps_its_boundary_before_live_sibling(self):
        for separator in ('\n', ', ', ', а '):
            with self.subTest(separator=separator):
                self.chain('Не используйте промокод OLD10' + separator +
                           'Примените промокод NEW10.', ['NEW10'])

    def test_wrapped_restriction_survives_text_only_normalization(self):
        raw = project(self.source('Промокод NEW10 не действует\nна алкоголь.'))['raw']
        raw['codes'] = []
        common = normalize_record(raw, as_of=NOW[:10])
        self.assert_codes(common, ['NEW10'])
        self.assertEqual(common['raw'], raw)

    def test_retained_audience_keeps_its_wrapped_or_conditional_restriction(self):
        for suffix in ('\nна алкоголь.', '\nв этот день.', ', если заказ включает алкоголь.'):
            with self.subTest(suffix=suffix):
                raw = project(self.source('Для молодежи промокод NEW10 не действует' + suffix))['raw']
                raw['details']['audiences'] = [{'audience': 'youth', 'promo_code': 'NEW10',
                                               'evidence': ['Для молодежи промокод NEW10']}]
                common = normalize_record(raw, as_of=NOW[:10])
                self.assertEqual([(c['value'], c['scope']) for c in common['codes']],
                                 [('NEW10', {'audience': 'youth'})])
                self.assertEqual(common['raw'], raw)

    def test_wrapped_audience_restriction_ends_before_next_sentences_coupon(self):
        raw = project(self.source('Для молодежи промокод NEW10 не действует\nна алкоголь. '
                                  'Примените промокод OTHER20.'))['raw']
        raw['details']['audiences'] = [{'audience': 'youth', 'promo_code': 'NEW10',
                                       'evidence': ['Для молодежи промокод NEW10']}]
        common = normalize_record(raw, as_of=NOW[:10])
        self.assertEqual([(c['value'], c['scope']) for c in common['codes']],
                         [('NEW10', {'audience': 'youth'}), ('OTHER20', {})])

    def test_retained_native_codes_reconcile_against_complete_original_text(self):
        for text, retained in (
            ('Промокод OLD10 больше не действует. Примените промокод NEW10.', ['OLD10', 'NEW10']),
            ('Не используйте промокод OLD10. Примените промокод NEW10.', ['OLD10', 'NEW10']),
            ('Промокод OLD10 отменён. Примените промокод NEW10.', ['OLD10', 'NEW10']),
            ('Промокод OLD10 БОЛЬШЕ НЕ ДЕЙСТВУЕТ. Примените промокод NEW10.', ['OLD10', 'NEW10']),
            ('Введите промокод NEW10 НА САЙТЕ.', ['NEW10 НА САЙТЕ']),
            ('Введите промокод NEW10 ПРИ ЗАКАЗЕ.', ['NEW10 ПРИ ЗАКАЗЕ']),
        ):
            with self.subTest(text=text):
                raw = project(self.source(text))['raw']
                raw['codes'] = retained
                raw['details']['promo_code_evidence'] = [
                    {'code': c, 'evidence': 'Промокод ' + c} for c in retained]
                before = copy.deepcopy(raw)
                common = normalize_record(raw, as_of=NOW[:10])
                self.assert_codes(common, ['NEW10'])
                self.assertEqual(common['raw'], before)
                self.assertEqual(raw, before)

    def test_retained_code_without_contradictory_original_evidence_is_preserved(self):
        raw = project(self.source('Предъявите карту участника.'))['raw']
        raw['codes'] = ['NATIVE42', 'NEW10 НА САЙТЕ']
        self.assert_codes(normalize_record(raw, as_of=NOW[:10]), ['NATIVE42', 'NEW10 НА САЙТЕ'])

    def test_quoted_native_literal_is_not_replaced_by_unquoted_sibling_prefix(self):
        raw = project(self.source('Введите промокод NEW10 НА САЙТЕ. '
                                  'Другой промокод «NEW10 НА САЙТЕ».'))['raw']
        raw['codes'] = ['NEW10 НА САЙТЕ']
        common = normalize_record(raw, as_of=NOW[:10])
        self.assert_codes(common, ['NEW10 НА САЙТЕ', 'NEW10'])
        native = next(c for c in common['codes'] if c['evidence']['path'] == '/codes/0')
        self.assertEqual(native['value'], 'NEW10 НА САЙТЕ')

    def test_reader_keeps_meaningful_scoped_prose_annotation(self):
        text = 'Для первого заказа примените промокод NEW10.'
        raw = project(self.source(text))['raw']
        raw['codes'] = []
        common = normalize_record(raw, as_of=NOW[:10])
        self.assertEqual(common['codes'][0]['scope'], {'purchase_stage': 'first'})
        reader, reason = record_row(common, NOW[:10])
        self.assertIsNone(reason)
        self.assertEqual(reader[3], 'Код: NEW10 — Для первого заказа примените промокод NEW10.')

    def test_audience_cancellation_cannot_borrow_same_value_live_occurrence(self):
        text = ('Для молодежи промокод SAME27 отменён. '
                'Для пенсионеров промокод SAME27 действует.')
        raw = project(self.source(text))['raw']
        raw['codes'] = ['SAME27']
        raw['details']['audiences'] = [
            {'audience': 'youth', 'age_min': 16, 'age_max': 25,
             'promo_code': 'SAME27', 'evidence': ['Для молодежи промокод SAME27']},
            {'audience': 'senior', 'women_age_min': 55, 'men_age_min': 60,
             'promo_code': 'SAME27', 'evidence': ['Для пенсионеров промокод SAME27 действует.']},
        ]
        before = copy.deepcopy(raw)
        common = normalize_record(raw, as_of=NOW[:10])
        self.assertEqual([(c['value'], c['scope']) for c in common['codes']], [
            ('SAME27', {'audience': 'senior', 'women_age_min': 55, 'men_age_min': 60})])
        self.assertEqual(common['raw'], before)
        self.assertEqual(raw, before)

    def test_native_audience_codes_without_label_remain_scoped(self):
        raw = project(self.source('Для молодежи YOUNG42; для старшего поколения SENIOR42.'))['raw']
        raw['codes'] = []
        raw['details']['audiences'] = [
            {'audience': 'youth', 'age_min': 16, 'age_max': 25,
             'promo_code': 'YOUNG42', 'evidence': ['от 16 до 25 лет', 'Для молодежи YOUNG42']},
            {'audience': 'senior', 'women_age_min': 55, 'men_age_min': 60,
             'promo_code': 'SENIOR42', 'evidence': ['для старшего поколения SENIOR42']},
        ]
        common = normalize_record(raw, as_of=NOW[:10])
        self.assertEqual([(c['value'], c['scope']['audience']) for c in common['codes']],
                         [('YOUNG42', 'youth'), ('SENIOR42', 'senior')])
        self.assertEqual(common['raw'], raw)

    def test_scoped_excerpt_cannot_extend_into_same_sentence_live_sibling(self):
        for separator in (', а ', ', ', '; ', '\n'):
            with self.subTest(separator=separator):
                raw = project(self.source('Для молодежи промокод SAME27 отменён' + separator +
                                          'для пенсионеров промокод SAME27 действует.'))['raw']
                raw['codes'] = ['SAME27']
                raw['details']['audiences'] = [
                    {'audience': 'youth', 'promo_code': 'SAME27',
                     'evidence': ['Для молодежи промокод SAME27']},
                    {'audience': 'senior', 'promo_code': 'SAME27',
                     'evidence': ['для пенсионеров промокод SAME27 действует.']},
                ]
                common = normalize_record(raw, as_of=NOW[:10])
                self.assertEqual([(c['value'], c['scope']) for c in common['codes']],
                                 [('SAME27', {'audience': 'senior'})])

    def test_independent_native_table_code_keeps_its_card_scope(self):
        tables = [[['Тип карты', 'Скидка', 'Промокод'], ['Золотая', '7%', 'SAME27']]]
        source = self.source('Промокод SAME27 отменён.', tables)
        common = project(source)
        self.assertEqual([(c['value'], c['scope']) for c in common['codes']],
                         [('SAME27', {'card_type': 'Золотая'})])
        self.assertEqual(common['raw']['details']['tables'], tables)

    def test_cancelled_native_table_component_does_not_borrow_live_sibling(self):
        text = 'Для синей карты промокод SAME27 отменён. Для золотой карты промокод SAME27 действует.'
        raw = project(self.source(text))['raw']
        raw['details']['table_benefits'] = {'components': [
            {'scope': {'kind': 'card_type', 'value': 'Синяя'}, 'rate': None,
             'promo_codes': ['SAME27'], 'evidence': 'Для синей карты промокод SAME27 отменён.'},
            {'scope': {'kind': 'card_type', 'value': 'Золотая'}, 'rate': None,
             'promo_codes': ['SAME27'], 'evidence': 'Для золотой карты промокод SAME27 действует.'},
        ], 'issues': []}
        common = normalize_record(raw, as_of=NOW[:10])
        self.assertEqual([(c['value'], c['scope']) for c in common['codes']],
                         [('SAME27', {'card_type': 'Золотая'})])
        self.assertEqual(common['raw'], raw)

    def test_native_table_cell_cannot_override_its_own_explicit_cancellation(self):
        raw = project(self.source('Условия по каждой карте приведены в таблице.'))['raw']
        raw['details']['table_benefits'] = {'components': [
            {'scope': {'kind': 'card_type', 'value': 'Синяя'}, 'rate': None,
             'promo_codes': ['SAME27'], 'evidence': {'table_index': 0, 'row_index': 1,
                 'header': ['Тип карты', 'Промокод', 'Условия'],
                 'row': ['Синяя', 'SAME27', 'Промокод SAME27 отменён.']}},
            {'scope': {'kind': 'card_type', 'value': 'Золотая'}, 'rate': None,
             'promo_codes': ['SAME27'], 'evidence': {'table_index': 0, 'row_index': 2,
                 'header': ['Тип карты', 'Промокод', 'Условия'],
                 'row': ['Золотая', 'SAME27', 'Промокод SAME27 действует.']}},
        ], 'issues': []}
        common = normalize_record(raw, as_of=NOW[:10])
        self.assertEqual([(c['value'], c['scope']) for c in common['codes']],
                         [('SAME27', {'card_type': 'Золотая'})])
        self.assertEqual(common['raw'], raw)


class SpecializedCouponBoundaries(unittest.TestCase):
    def source(self, adapter, text):
        if adapter == 'hse':
            import test_hse_alumni as fixture
            from hse_alumni import parse_catalog
            return parse_catalog(fixture.page(fixture.card('a'), fixture.section(
                'a', '<p>Скидка 10%.</p><p>' + text.replace('\n', '<br>') + '</p>')), NOW)[0]
        if adapter == 'public_rewards':
            import test_public_reward_sources as fixture
            from bs4 import BeautifulSoup
            document = BeautifulSoup(fixture.html('backit-kuper.html'), 'html.parser')
            document.select_one('.shop-conditions').append(text)
            return fixture.kuper(str(document))
        if adapter == 'alfa':
            import alfa_partner_rules as alfa
            import test_alfa_partner_rules as fixture
            from unittest.mock import patch
            # Only PDF decoding is replaced; owned rules, validation and
            # publication use the actual source entrypoint.
            with patch.object(alfa, 'pdf_text', return_value=fixture.fixture() + '\n' + text):
                return alfa.parse_document(alfa.DOCS[0], b'%PDF-coupon-fixture', NOW)
        if adapter == 'konsierge':
            import test_konsierge_catalog as fixture
            capture = fixture.KonsiergeTests()
            capture.setUp()
            self.addCleanup(capture.doCleanups)
            for page in capture.report['network_pages']:
                for item in page['items']:
                    if item['id'] == 2079:
                        item['description'] = text + ' Кодовое слово «Консьерж-Пять».'
            return capture.row(2079)
        raise AssertionError(adapter)

    def test_hse_fallback_and_retained_arrays_share_plural_list_ownership(self):
        for label in ('Промокоды', 'Промокоды:', 'Промокоды —'):
            for live_label in ('промокод', 'кодовое слово', 'п ромо-код'):
                text = f'{label} «OLD10» и «OLD20» отменены, для пенсионеров {live_label} NEW10 действует.'
                source = self.source('hse', text)
                common = project(source)
                with self.subTest(label=label, live_label=live_label, boundary='source'):
                    self.assertEqual(source['promo_codes'], ['NEW10'])
                with self.subTest(label=label, live_label=live_label, boundary='common'):
                    self.assertEqual([c['value'] for c in common['codes']], ['NEW10'])
                raw = copy.deepcopy(common['raw'])
                raw['codes'] = ['OLD10', 'OLD20', 'NEW10']
                with self.subTest(label=label, live_label=live_label, boundary='retained/reader'):
                    repaired = normalize_record(raw, as_of=NOW[:10])
                    self.assertEqual([c['value'] for c in repaired['codes']], ['NEW10'])
                    reader, reason = record_row(repaired, NOW[:10])
                    self.assertIsNone(reason)
                    self.assertEqual(reader[3], 'Код: NEW10')
                    self.assertEqual(repaired['raw'], raw)

    def test_hse_fallback_cannot_restore_cancelled_source_literal(self):
        for label in ('Промокод', 'П ромо-код', 'Кодовое слово'):
            for cancelled in (f'{label} OLD10 больше не действует.',
                              f'Не используйте {label.lower()} OLD10.',
                              f'{label} OLD10 отменён.'):
                with self.subTest(label=label, cancelled=cancelled):
                    source = self.source('hse', cancelled + f' Примените {label.lower()} NEW10.')
                    self.assertEqual(source['promo_codes'], ['NEW10'])
                    self.assertEqual([c['value'] for c in project(source)['codes']], ['NEW10'])

    def test_hse_variant_keeps_live_same_value_and_partial_exclusion(self):
        for label in ('Промокод', 'П ромо-код', 'Кодовое слово'):
            with self.subTest(label=label):
                source = self.source('hse', f'{label} SAME27 отменён; '
                                     f'{label} SAME27 не действует на алкоголь.')
                self.assertEqual(source['promo_codes'], ['SAME27'])
                self.assertEqual([c['value'] for c in project(source)['codes']], ['SAME27'])
                self.assertEqual(source['details']['promo_code_evidence'], [
                    {'code': 'SAME27', 'evidence': label + ' SAME27'}])

    def test_retained_hse_variants_keep_only_live_codes(self):
        for label in ('П ромо-код', 'Кодовое слово', 'Промокод на 15% -', 'Промокод и скидка:'):
            for text, retained, expected in (
                (f'{label} OLD10 отменён. Примените {label.lower()} NEW10.', ['OLD10', 'NEW10'], ['NEW10']),
                (f'{label} SAME27 отменён; {label} SAME27 не действует на алкоголь.', ['SAME27'], ['SAME27']),
                (f'Примените {label.lower()} NEW10.', ['NEW10'], ['NEW10']),
            ):
                with self.subTest(label=label, text=text):
                    source = self.source('hse', text)
                    self.assertEqual(source['promo_codes'], expected)
                    raw = project(source)['raw']
                    raw['codes'] = retained
                    before = copy.deepcopy(raw)
                    common = normalize_record(raw, as_of=raw['observed_at'][:10])
                    self.assertEqual([(c['value'], c['delivery']) for c in common['codes']],
                                     [(value, 'literal') for value in expected])
                    reader, reason = record_row(common, raw['observed_at'][:10])
                    self.assertIsNone(reason)
                    self.assertEqual(reader[3], '\n'.join('Код: ' + value for value in expected))
                    self.assertEqual(common['raw'], before)
                    self.assertEqual(raw, before)

    def test_generic_code_word_does_not_become_a_coupon(self):
        source = CouponSemanticBoundaries().source('Кодовое слово NEW10.')
        self.assertEqual(source['promo_codes'], [])
        self.assertEqual(project(source)['codes'], [])

    def test_sibling_condition_cannot_rescue_current_cancelled_coupon(self):
        for adapter, separator in (('generic', ', а '), ('hse', ', а '),
                                   ('generic', ', '), ('hse', ', ')):
            text = 'При заказе используйте промокод NEW10' + separator + 'промокод OLD10 отменён.'
            source = (CouponSemanticBoundaries().source(text) if adapter == 'generic'
                      else self.source(adapter, text))
            before = copy.deepcopy(source)
            common = project(source)
            with self.subTest(adapter=adapter, separator=separator, boundary='source'):
                self.assertEqual(source['promo_codes'], ['NEW10'])
            with self.subTest(adapter=adapter, separator=separator, boundary='publication/common'):
                self.assertEqual([c['value'] for c in common['codes']], ['NEW10'])
            with self.subTest(adapter=adapter, separator=separator, boundary='reader'):
                reader, reason = record_row(common, NOW[:10])
                self.assertIsNone(reason)
                self.assertEqual(reader[3], 'Код: NEW10')
            self.assertEqual(source, before)
            self.assertIn(text, common['raw']['conditions'])
            self.assertEqual(common['id'], source['id'])
            self.assertEqual(common['raw']['observed_at'], NOW)

    def test_retained_cancelled_coupon_cannot_borrow_sibling_condition(self):
        for adapter, separator in (('generic', ', а '), ('hse', ', а '),
                                   ('generic', ', '), ('hse', ', ')):
            text = 'При заказе используйте промокод NEW10' + separator + 'промокод OLD10 отменён.'
            source = (CouponSemanticBoundaries().source(text) if adapter == 'generic'
                      else self.source(adapter, text))
            raw = project(source)['raw']
            raw['codes'] = ['NEW10', 'OLD10']
            before = copy.deepcopy(raw)
            common = normalize_record(raw, as_of=NOW[:10])
            with self.subTest(adapter=adapter, separator=separator, boundary='retained/common'):
                self.assertEqual([c['value'] for c in common['codes']], ['NEW10'])
            with self.subTest(adapter=adapter, separator=separator, boundary='retained/reader'):
                reader, reason = record_row(common, NOW[:10])
                self.assertIsNone(reason)
                self.assertEqual(reader[3], 'Код: NEW10')
            self.assertEqual(common['raw'], before)
            self.assertEqual(raw, before)

    def test_current_coupon_keeps_its_comma_bearing_condition(self):
        for text, expected in (
            ('При отмене заказа, оформленного вчера, промокод NEW10 отменён.', ['NEW10']),
            ('Если заказ отменён, промокод NEW10 аннулирован.', ['NEW10']),
            ('Если используется промокод NEW10, промокод OLD10 отменён.', ['NEW10', 'OLD10']),
            ('При заказе используйте промокод NEW10, если заказ отменён, '
             'промокод OLD10 аннулирован.', ['NEW10', 'OLD10']),
            ('При заказе используйте промокод NEW10, а при отмене заказа, '
             'оформленного вчера, промокод OLD10 отменён.', ['NEW10', 'OLD10']),
        ):
            for adapter in ('generic', 'hse'):
                with self.subTest(adapter=adapter, text=text):
                    source = (CouponSemanticBoundaries().source(text) if adapter == 'generic'
                              else self.source(adapter, text))
                    self.assertEqual(source['promo_codes'], expected)
                    raw = project(source)['raw']
                    raw['codes'] = expected[:]
                    common = normalize_record(raw, as_of=NOW[:10])
                    self.assertEqual([c['value'] for c in common['codes']], expected)
                    self.assertEqual(common['raw'], raw)

    def test_hse_live_variant_is_not_cancelled_by_same_value_generic_label(self):
        for label in ('П ромо-код', 'Кодовое слово'):
            with self.subTest(label=label):
                source = self.source('hse', 'Промокод SAME27 отменён. ' + label + ' SAME27 действует.')
                self.assertEqual(source['promo_codes'], ['SAME27'])
                common = project(source)
                self.assertEqual([(c['value'], c['delivery']) for c in common['codes']], [('SAME27', 'literal')])
                reader, reason = record_row(common, common['raw']['observed_at'][:10])
                self.assertIsNone(reason)
                self.assertEqual(reader[3], 'Код: SAME27')

    def test_hse_mixed_label_siblings_agree_at_source_common_and_reader(self):
        for label in ('кодовое слово', 'п ромо-код'):
            for separator in (', ', '\n'):
                for old, new, expected in (('OLD10', 'NEW10', ['NEW10']),
                                           ('SAME27', 'SAME27', ['SAME27'])):
                    with self.subTest(label=label, separator=separator, old=old, new=new):
                        text = f'Промокод {old} отменён{separator}для пенсионеров {label} {new} действует.'
                        source = self.source('hse', text)
                        before = copy.deepcopy(source)
                        self.assertEqual(source['promo_codes'], expected)
                        common = project(source)
                        self.assertEqual([(c['value'], c['delivery']) for c in common['codes']],
                                         [(value, 'literal') for value in expected])
                        reader, reason = record_row(common, common['raw']['observed_at'][:10])
                        self.assertIsNone(reason)
                        self.assertEqual(reader[3], '\n'.join('Код: ' + value for value in expected))
                        self.assertEqual(source, before)
                        self.assertIn(text, common['raw']['conditions'])

    def test_hse_mixed_labels_preserve_conditional_and_wrapped_restrictions(self):
        for restriction in ('Промокод FIRST10 не действует, если заказ включает алкоголь.',
                            'Промокод FIRST10 не действует\nна алкоголь.'):
            for label in ('кодовое слово', 'п ромо-код'):
                with self.subTest(restriction=restriction, label=label):
                    source = self.source('hse', restriction + f' Для пенсионеров {label} SECOND20 действует.')
                    self.assertEqual(source['promo_codes'], ['FIRST10', 'SECOND20'])
                    common = project(source)
                    self.assertEqual([c['value'] for c in common['codes']], ['FIRST10', 'SECOND20'])

    def test_hse_independent_table_occurrence_keeps_its_own_evidence(self):
        from hse_alumni import hse_codes
        text = 'Промокод SAME27 отменён, для пенсионеров кодовое слово NEW10 действует.'
        table = [['Тип карты', 'Промокод'], ['Золотая', 'SAME27']]
        result = hse_codes(text, [table])
        self.assertEqual(result['codes'], ['SAME27', 'NEW10'])
        native = next(item for item in result['evidence'] if item['code'] == 'SAME27')
        self.assertEqual(native.get('kind'), 'source_table')
        self.assertEqual(native['row'], ['Золотая', 'SAME27'])

    def test_retained_arrays_reconcile_through_each_owned_projector(self):
        for adapter in ('hse', 'public_rewards', 'alfa', 'konsierge'):
            for text, stale in (
                ('Промокод OLD10 больше не действует. Примените промокод NEW10.', ['OLD10', 'NEW10']),
                ('Введите промокод NEW10 НА САЙТЕ.', ['NEW10 НА САЙТЕ']),
            ):
                with self.subTest(adapter=adapter, text=text):
                    raw = project(self.source(adapter, text))['raw']
                    raw['codes'] = stale
                    before = copy.deepcopy(raw)
                    try:
                        common = normalize_record(raw, as_of=raw['observed_at'][:10])
                    except ValueError as exc:
                        self.fail('Evidence-grounded retained code repair was rejected: ' + str(exc))
                    self.assertEqual([c['value'] for c in common['codes'] if c['delivery'] == 'literal'],
                                     ['NEW10'])
                    reader, reason = record_row(common, raw['observed_at'][:10])
                    self.assertIsNone(reason)
                    self.assertIn('Код: NEW10', reader[3])
                    self.assertNotIn('OLD10', reader[3])
                    self.assertNotIn('NEW10 НА САЙТЕ', reader[3])
                    self.assertEqual(common['raw'], before)
                    self.assertEqual(raw, before)
                    if adapter == 'konsierge':
                        self.assertEqual([(c['value'], c['delivery']) for c in common['codes']
                                          if c['delivery'] == 'code_word'], [('Консьерж-Пять', 'code_word')])

    def test_konsierge_guard_still_rejects_ungrounded_native_addition(self):
        raw = project(self.source('konsierge', 'Примените промокод NEW10.'))['raw']
        raw['codes'] = ['NEW10', 'FABRICATED42']
        with self.assertRaisesRegex(ValueError, 'common_codes'):
            normalize_record(raw, as_of=raw['observed_at'][:10])

    def test_unchanged_native_scoped_codes_keep_reader_display(self):
        for adapter in ('hse', 'public_rewards', 'alfa', 'konsierge'):
            with self.subTest(adapter=adapter):
                common = project(self.source(adapter, 'Примените промокод NEW10.'))
                literal = [c for c in common['codes'] if c['delivery'] == 'literal']
                self.assertEqual([c['value'] for c in literal], ['NEW10'])
                if adapter != 'public_rewards':
                    self.assertTrue(literal[0]['scope'])
                reader, reason = record_row(common, common['raw']['observed_at'][:10])
                self.assertIsNone(reason)
                self.assertEqual(reader[3].splitlines()[0], 'Код: NEW10')

    def test_native_without_contradiction_is_preserved_where_contract_permits(self):
        for adapter in ('hse', 'public_rewards', 'alfa'):
            with self.subTest(adapter=adapter):
                raw = project(self.source(adapter, 'Предъявите карту участника.'))['raw']
                raw['codes'] = ['NATIVE42', 'NEW10 НА САЙТЕ']
                common = normalize_record(raw, as_of=raw['observed_at'][:10])
                self.assertEqual([c['value'] for c in common['codes']], ['NATIVE42', 'NEW10 НА САЙТЕ'])
                self.assertEqual(common['raw'], raw)


if __name__ == '__main__':
    unittest.main()
