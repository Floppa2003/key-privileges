"""Cancellation belongs to an occurrence, including wrapped source context."""
import copy
import unittest

from catalogue_view import record_row
from hse_alumni import CODE_LABEL_PATTERNS, hse_codes, parse_catalog
from normalized import make_offer
from promo_codes import extract_promocodes, reconcile_promocode
from test_dom_card_boundaries import project
import test_coupon_semantic_boundaries as coupon_fixtures
import test_hse_alumni as hse_fixture
from unified_normalization import normalize_record


NOW = '2026-11-13T00:00:00+00:00'


class PromoContextContinuations(unittest.TestCase):
    def source(self, text, *, hse=False):
        if hse:
            return parse_catalog(hse_fixture.page(hse_fixture.card('a'), hse_fixture.section(
                'a', '<p>Скидка 10%.</p><p>' + text.replace('\n', '<br>') + '</p>')), NOW)[0]
        return make_offer('moskvich', 'coupon-continuations', 'Карта', 'Example',
                          'Скидка 10% на меню.',
                          'https://moskvichmag.ru/programma-loyalnosti/', NOW,
                          conditions=text)

    def assert_common_codes(self, common, expected):
        self.assertEqual([c['value'] for c in common['codes'] if c['delivery'] == 'literal'],
                         expected)
        reader, reason = record_row(common, NOW[:10])
        self.assertIsNone(reason)
        self.assertEqual(reader[3], '\n'.join('Код: ' + c for c in expected))

    def test_replacement_continuation_does_not_revive_cancelled_literal(self):
        for text, expected in (
            ('Промокод OLD10 отменён и заменён на промокод NEW10.', ['NEW10']),
            ('Промокод prior23 больше не действует — примените промокод next41.', ['next41']),
            ('Промокод «OLD CLUB» недействителен – введите промокод «NEW CLUB».', ['NEW CLUB']),
            ('Промокод BEFORE73 аннулирован и заменён на промокод AFTER91.', ['AFTER91']),
        ):
            with self.subTest(text=text):
                self.assertEqual(extract_promocodes(text)['codes'], expected)

    def test_parenthesized_cancellation_is_still_unconditional(self):
        for text in (
            'Промокод OLD10 отменён (акция завершена). Примените промокод NEW10.',
            'Промокод OLD10 (отменён). Примените промокод NEW10.',
            'Промокод OLD10 больше не действует (вместо него используйте промокод NEW10).',
        ):
            with self.subTest(text=text):
                self.assertEqual(extract_promocodes(text)['codes'], ['NEW10'])

    def test_causal_explanation_does_not_revive_cancelled_literal(self):
        for reason in ('по решению партнёра', 'по причине завершения акции',
                       'из-за завершения акции', 'поскольку акция завершена',
                       'потому что акция завершена'):
            with self.subTest(reason=reason):
                text = 'Промокод OLD10 отменён ' + reason + '. Примените промокод NEW10.'
                self.assertEqual(extract_promocodes(text)['codes'], ['NEW10'])

    def test_negative_instruction_ends_before_dash_replacement(self):
        text = 'Не используйте промокод OLD10 — примените промокод NEW10.'
        self.assertEqual(extract_promocodes(text)['codes'], ['NEW10'])

    def test_line_wrap_does_not_erase_conditional_antecedent(self):
        for text, expected in (
            ('Если заказ отменён,\nпромокод NEW10 аннулирован.', ['NEW10']),
            ('Если\nзаказ отменён,\nпромокод NEW10 аннулирован.', ['NEW10']),
            ('Если заказ\nотменён, промокод NEW10 аннулирован.', ['NEW10']),
            ('При отмене заказа,\nоформленного вчера,\nпромокод NEW10 отменён.', ['NEW10']),
            ('После отмены заказа\nпромокод NEW10 аннулирован.', ['NEW10']),
            ('При заказе используйте промокод FIRST21, если заказ отменён,\n'
             'промокод NEW10 аннулирован.', ['FIRST21', 'NEW10']),
        ):
            with self.subTest(text=text):
                self.assertEqual(extract_promocodes(text)['codes'], expected)

    def test_wrapped_conditional_reference_can_own_another_literal(self):
        text = 'Если используется промокод FIRST21,\nпромокод SECOND35 отменён.'
        self.assertEqual(extract_promocodes(text)['codes'], ['FIRST21', 'SECOND35'])

    def test_prior_coupon_condition_cannot_leak_across_independent_lines(self):
        for prefix in ('При заказе используйте промокод FIRST21',
                       'Промокод FIRST21 действует при заказе',
                       'Промокод FIRST21 не действует на алкоголь'):
            for separator in ('\n', ',\n', '\n\n'):
                with self.subTest(prefix=prefix, separator=separator):
                    text = prefix + separator + 'промокод OLD10 отменён.'
                    self.assertEqual(extract_promocodes(text)['codes'], ['FIRST21'])

    def test_completed_coupon_statement_closes_its_condition_at_next_line(self):
        for prefix in ('При заказе промокод FIRST21 действует',
                       'При оплате промокод FIRST21 действителен',
                       'Если заказ оформлен, промокод FIRST21 действует',
                       'Если заказ оформлен,\nпромокод FIRST21\nдействует'):
            for separator in ('\n', ',\n', '\r\n'):
                with self.subTest(prefix=prefix, separator=separator):
                    text = prefix + separator + 'для молодежи промокод OLD10 отменён.'
                    self.assertEqual(extract_promocodes(text)['codes'], ['FIRST21'])
                    self.assertIsNone(reconcile_promocode('OLD10', [text]))
                    raw = project(self.source(text))['raw']
                    raw['codes'] = ['FIRST21', 'OLD10']
                    self.assert_common_codes(normalize_record(raw, as_of=NOW[:10]), ['FIRST21'])

    def test_coupon_predicate_inside_if_antecedent_does_not_close_it(self):
        for prefix in ('Если используется промокод FIRST21',
                       'Если промокод FIRST21 действует',
                       'Если при заказе промокод FIRST21 действует',
                       'При использовании промокода FIRST21'):
            with self.subTest(prefix=prefix):
                text = prefix + ',\nпромокод SECOND35 отменён.'
                self.assertEqual(extract_promocodes(text)['codes'], ['FIRST21', 'SECOND35'])
                self.assertEqual(reconcile_promocode('SECOND35', [text]), 'SECOND35')

    def test_source_specific_completed_coupon_cannot_rescue_cancelled_sibling(self):
        for label in ('П ромо-код', 'Кодовое слово', 'Промокод на 15% -'):
            with self.subTest(label=label):
                text = (f'При заказе {label.lower()} FIRST21 действует\n'
                        f'{label.lower()} OLD10 отменён.')
                self.assertEqual(hse_codes(text)['codes'], ['FIRST21'])
                source = self.source(text, hse=True)
                self.assertEqual(source['promo_codes'], ['FIRST21'])
                raw = project(source)['raw']
                raw['codes'] = ['FIRST21', 'OLD10']
                self.assert_common_codes(normalize_record(raw, as_of=NOW[:10]), ['FIRST21'])

    def test_condition_cannot_cross_a_paragraph_or_completed_sentence(self):
        for separator in ('\n\n', '\n \n', '.\n', ';\n'):
            with self.subTest(separator=separator):
                text = 'Если заказ отменён' + separator + 'промокод OLD10 аннулирован.'
                self.assertEqual(extract_promocodes(text)['codes'], [])

    def test_partial_and_date_restrictions_remain_literal_evidence(self):
        for suffix in ('не действует на алкоголь.', 'не действует — на алкоголь.',
                       'не действует (на алкоголь).', '(не действует на алкоголь).',
                       'не действует только на алкоголь.', 'не действует по выходным.',
                       'не действует до 31 декабря.', 'не действует 15 ноября.',
                       'не действует (до 31 декабря).',
                       'не действует — если заказ включает алкоголь.',
                       'отменён, если заказ отменён.'):
            with self.subTest(suffix=suffix):
                text = 'Промокод NEW10 ' + suffix
                self.assertEqual(extract_promocodes(text)['codes'], ['NEW10'])

    def test_plural_replacement_discards_each_cancelled_member(self):
        text = ('Промокоды «OLD CLUB» и «prior23» отменены '
                'и заменены на промокод «NEW CLUB».')
        self.assertEqual(extract_promocodes(text)['codes'], ['NEW CLUB'])
        self.assertIsNone(reconcile_promocode('OLD CLUB', [text]))
        self.assertIsNone(reconcile_promocode('prior23', [text]))

    def test_independent_live_occurrence_of_same_literal_survives(self):
        text = ('Промокод SAME27 отменён и заменён на промокод NEW10. '
                'Для пенсионеров промокод SAME27 действует.')
        self.assertEqual(extract_promocodes(text)['codes'], ['NEW10', 'SAME27'])
        self.assertEqual(reconcile_promocode('SAME27', [text]), 'SAME27')
        self.assertEqual(reconcile_promocode('SAME27', [
            'Промокод SAME27 отменён (акция завершена).',
            'Для пенсионеров промокод SAME27 действует.',
        ]), 'SAME27')

    def test_source_common_and_reader_share_continuation_semantics(self):
        for text, expected in (
            ('Промокод OLD10 отменён и заменён на промокод NEW10.', ['NEW10']),
            ('Промокод OLD10 отменён (акция завершена). Примените промокод NEW10.', ['NEW10']),
            ('Если заказ отменён,\nпромокод NEW10 аннулирован.', ['NEW10']),
        ):
            with self.subTest(text=text):
                source = self.source(text)
                before = copy.deepcopy(source)
                self.assertEqual(source['promo_codes'], expected)
                common = project(source)
                self.assert_common_codes(common, expected)
                self.assertEqual(common['raw']['conditions'], text)
                self.assertEqual(common['id'], source['id'])
                self.assertEqual(common['raw']['observed_at'], NOW)
                self.assertEqual(source, before)

    def test_retained_native_codes_use_full_context(self):
        for text, retained, expected in (
            ('Промокод OLD10 отменён и заменён на промокод NEW10.', ['OLD10', 'NEW10'], ['NEW10']),
            ('Промокод OLD10 (отменён). Примените промокод NEW10.', ['OLD10', 'NEW10'], ['NEW10']),
            ('Если заказ отменён,\nпромокод NEW10 аннулирован.', ['NEW10'], ['NEW10']),
        ):
            with self.subTest(text=text):
                raw = project(self.source(text))['raw']
                raw['codes'] = retained
                before = copy.deepcopy(raw)
                common = normalize_record(raw, as_of=NOW[:10])
                self.assert_common_codes(common, expected)
                self.assertEqual(common['raw'], before)
                self.assertEqual(raw, before)

    def test_source_specific_labels_keep_occurrence_ownership(self):
        for label in ('П ромо-код', 'Кодовое слово', 'Промокод на 15% -'):
            for text, retained, expected in (
                (f'{label} OLD10 отменён и заменён на {label.lower()} NEW10.',
                 ['OLD10', 'NEW10'], ['NEW10']),
                (f'Если заказ отменён,\n{label.lower()} NEW10 аннулирован.',
                 ['NEW10'], ['NEW10']),
                (f'При заказе используйте {label.lower()} NEW10\n'
                 f'{label.lower()} OLD10 отменён.', ['NEW10', 'OLD10'], ['NEW10']),
            ):
                with self.subTest(label=label, text=text):
                    self.assertEqual(hse_codes(text)['codes'], expected)
                    self.assertEqual(reconcile_promocode('NEW10', [text], labels=CODE_LABEL_PATTERNS),
                                     'NEW10')
                    source = self.source(text, hse=True)
                    self.assertEqual(source['promo_codes'], expected)
                    raw = project(source)['raw']
                    raw['codes'] = retained
                    before = copy.deepcopy(raw)
                    common = normalize_record(raw, as_of=NOW[:10])
                    self.assert_common_codes(common, expected)
                    self.assertEqual(common['raw'], before)
                    self.assertEqual(raw, before)

    def test_retained_source_projectors_reconcile_continued_cancellation(self):
        fixtures = coupon_fixtures.SpecializedCouponBoundaries()
        self.addCleanup(fixtures.doCleanups)
        for adapter in ('public_rewards', 'alfa', 'konsierge'):
            for text, retained in (
                ('Промокод OLD10 отменён и заменён на промокод NEW10.', ['OLD10', 'NEW10']),
                ('Если заказ отменён,\nпромокод NEW10 аннулирован.', ['NEW10']),
            ):
                with self.subTest(adapter=adapter, text=text):
                    raw = project(fixtures.source(adapter, text))['raw']
                    raw['codes'] = retained
                    before = copy.deepcopy(raw)
                    common = normalize_record(raw, as_of=raw['observed_at'][:10])
                    self.assertEqual([c['value'] for c in common['codes'] if c['delivery'] == 'literal'],
                                     ['NEW10'])
                    reader, reason = record_row(common, raw['observed_at'][:10])
                    self.assertIsNone(reason)
                    self.assertIn('Код: NEW10', reader[3])
                    self.assertNotIn('OLD10', reader[3])
                    self.assertEqual(common['raw'], before)
                    self.assertEqual(raw, before)


if __name__ == '__main__':
    unittest.main()
