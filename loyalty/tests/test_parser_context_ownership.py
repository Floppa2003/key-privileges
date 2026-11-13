"""Literal context failures exercised through source, stored input and reader."""
import copy
import unittest

from catalogue_view import record_row
from normalized import make_offer, normalize_rates
from test_dom_card_boundaries import project
from test_unified_normalization import record
from unified_normalization import normalize_record, validate_normalized


NOW = '2026-11-13T00:00:00+00:00'


class ParserContextOwnership(unittest.TestCase):
    def chain(self, body, conditions=''):
        source = make_offer('moskvich', 'context-fixture', 'Карта', 'Пример', body,
                            'https://moskvichmag.ru/programma-loyalnosti/', NOW,
                            conditions=conditions)
        before = copy.deepcopy(source)
        common = project(source)
        self.assertEqual(source, before)
        # The source API folds horizontal whitespace before publication;
        # re-normalizing the retained row must preserve that source snapshot.
        self.assertEqual(common['raw']['benefit'], before['benefit_text'])
        self.assertEqual(common['raw']['conditions'], before['conditions_text'])
        self.assertEqual(common['provenance']['observed_at'], NOW)
        validate_normalized(common)
        return source, common

    def linked(self, common, kind):
        conditions = {c['id']: c for c in common['conditions']}
        return [(b['value'], b['scope'].get('purchase_stage'),
                 sorted(conditions[c]['value'] for c in b['condition_ids']
                        if conditions[c]['kind'] == kind))
                for b in common['benefits']]

    def test_cancelled_and_unavailable_discounts_cannot_supply_a_headline(self):
        for number in ('16', '23,5'):
            for denial in ('отменена', 'аннулирована', 'недоступна',
                           'не предусмотрена', 'временно недоступна'):
                dead = f'Скидка {number}% {denial}.'
                active = 'Скидка 9% действует на меню.'
                for parts in ((dead, active), (active, dead)):
                    with self.subTest(parts=parts):
                        source, common = self.chain(' '.join(parts))
                        self.assertEqual([(r['kind'], r['value']) for r in source['rates']],
                                         [('discount', '9')])
                        self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                         [('discount', '9')])
                        row, reason = record_row(common, NOW[:10])
                        self.assertIsNone(reason)
                        self.assertEqual(row[2], active)
                        self.assertIn(dead, row[5])

    def test_denied_nonnumeric_offer_does_not_displace_live_sibling(self):
        for dead in ('Бесплатная доставка отменена.',
                     'Бесплатная доставка недоступна.',
                     'Скидка не предусмотрена.'):
            with self.subTest(dead=dead):
                _, common = self.chain(dead + ' Скидка 9% действует на меню.')
                row, reason = record_row(common, NOW[:10])
                self.assertIsNone(reason)
                self.assertEqual(row[2], 'Скидка 9% действует на меню.')

    def test_prefix_denial_and_own_equal_positive_occurrence(self):
        for body in ('Не предусмотрена скидка 16%. Скидка 9% на меню.',
                     'Отменена скидка 16%. Скидка 9% на меню.',
                     'Скидка 9% отменена. Скидка 9% на меню.'):
            with self.subTest(body=body):
                _, common = self.chain(body)
                self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                 [('discount', '9')])

    def test_partial_restrictions_and_negated_cancellation_preserve_benefits(self):
        for body in ('Скидка 16% не действует на алкоголь.',
                     'Скидка 16% недоступна для акционных товаров.',
                     'Скидка 16% не отменена.',
                     'Скидка 16% не будет отменена.',
                     'Скидка 16% предусмотрена.',
                     'Скидка 16% действует. Предоплата отменена.'):
            with self.subTest(body=body):
                _, common = self.chain(body)
                self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                 [('discount', '16')])
                self.assertIsNotNone(record_row(common, NOW[:10])[0])

    def test_labelled_caps_belong_to_their_own_channels(self):
        cases = (
            ('Скидка 21% онлайн (максимальная скидка 650 ₽), '
             'скидка 12% офлайн (максимальная скидка 430 ₽).',
             [('21', None, ['650']), ('12', None, ['430'])]),
            ('Скидка 12,5% офлайн (лимит скидки 4\u202f350,75 руб.), '
             'скидка 27% онлайн (максимальная скидка 6\u202f550,25 рублей).',
             [('12.5', None, ['4350.75']), ('27', None, ['6550.25'])]),
            ('Скидка 21% онлайн (максимальная скидка 650 ₽), '
             'скидка 12% офлайн (максимальная скидка 650 ₽).',
             [('21', None, ['650']), ('12', None, ['650'])]),
        )
        for body, expected in cases:
            with self.subTest(body=body):
                _, common = self.chain(body)
                self.assertEqual(self.linked(common, 'benefit_cap'), expected)
                self.assertTrue(all(b['unit'] == 'percent' for b in common['benefits']))

    def test_labelled_caps_belong_to_their_own_purchase_stages(self):
        for separator in (', ', '. ', '; ', '\n'):
            body = ('Скидка 21% на первый заказ (максимальная скидка 650 ₽)'
                    + separator +
                    'скидка 12% на повторный заказ (максимальная скидка 430 ₽).')
            with self.subTest(body=body):
                _, common = self.chain(body)
                self.assertEqual(self.linked(common, 'benefit_cap'),
                                 [('21', 'first', ['650']), ('12', 'repeat', ['430'])])

    def test_cap_stages_do_not_invent_a_separate_discount_or_cross_a_sentence(self):
        body = ('Скидка 500 ₽ на первый заказ. '
                'Максимальная скидка 1000 ₽ на повторный заказ.')
        _, common = self.chain(body)
        self.assertEqual(self.linked(common, 'benefit_cap'), [('500', 'first', [])])
        caps = [c for c in common['conditions'] if c['kind'] == 'benefit_cap']
        self.assertEqual([(c['value'], c['scope']) for c in caps],
                         [('1000', {'purchase_stage': 'repeat'})])

    def test_plain_caps_and_shared_plain_rate_list_remain_linked(self):
        cases = (
            ('Скидка 21% онлайн (не более 650 ₽), скидка 12% офлайн (не более 430 ₽).',
             [('21', None, ['650']), ('12', None, ['430'])]),
            ('Скидка 21% или 12% (максимальная скидка 650 ₽).',
             [('21', None, ['650']), ('12', None, ['650'])]),
        )
        for body, expected in cases:
            with self.subTest(body=body):
                _, common = self.chain(body)
                self.assertEqual(self.linked(common, 'benefit_cap'), expected)

    def test_short_minimum_denial_is_preserved_in_source_and_common(self):
        for amount in ('2700 ₽', '4\u202f350,75 руб.', '6550 RUB'):
            for denial in ('не требуется', 'уже не нужен', 'больше не обязателен'):
                body = f'Скидка 16% на первый заказ. Первый заказ от {amount} {denial}.'
                with self.subTest(body=body):
                    source, common = self.chain(body)
                    self.assertEqual([c for c in source['details']['lexical_conditions']
                                      if c['kind'] == 'minimum_purchase'], [])
                    self.assertEqual([c for c in common['conditions']
                                      if c['kind'] == 'minimum_purchase'], [])
                    self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                     [('discount', '16')])

    def test_short_minimum_prefix_denial_and_unrelated_negative_controls(self):
        for body in ('Не требуется оформлять первый заказ от 2700 ₽. Скидка 16% на первый заказ.',
                     'Необязательно совершать первый заказ от 2700 ₽. Скидка 16% на первый заказ.'):
            with self.subTest(body=body):
                source, common = self.chain(body)
                self.assertEqual([c for c in common['conditions'] if c['kind'] == 'minimum_purchase'], [])
                self.assertEqual([c for c in source['details']['lexical_conditions']
                                  if c['kind'] == 'minimum_purchase'], [])
        for suffix in ('; предъявлять карту не требуется.',
                       ' — не требуется предъявлять карту.',
                       '. Повторный заказ от 1900 ₽ не требуется.'):
            with self.subTest(suffix=suffix):
                _, common = self.chain('Скидка 16% на первый заказ от 2700 ₽' + suffix)
                self.assertEqual(self.linked(common, 'minimum_purchase'), [('16', 'first', ['2700'])])

    def test_each_text_code_gets_its_own_purchase_stage_in_both_routes(self):
        for separator in (', ', '. ', '; ', '\n'):
            for reverse in (False, True):
                pieces = ['Промокод FIRST16 на первый заказ',
                          'промокод AGAIN9 на повторный заказ']
                if reverse:
                    pieces.reverse()
                body = 'Скидка 16%. ' + separator.join(pieces) + '.'
                with self.subTest(body=body):
                    _, stored = self.chain(body)
                    direct = normalize_record(record(benefit=body, conditions='', activation=''),
                                              as_of=NOW[:10])
                    for common in (stored, direct):
                        self.assertCountEqual([(c['value'], c['scope'].get('purchase_stage'))
                                               for c in common['codes']],
                                              [('FIRST16', 'first'), ('AGAIN9', 'repeat')])

    def test_shared_and_unowned_coupon_scopes_are_not_invented(self):
        cases = (
            ('Скидка 16% на первый заказ и 9% на повторный заказ. Введите промокод SHARED16.',
             [('SHARED16', 'multiple_stages')]),
            ('Промокоды «SHARED16» и «SHARED9» на первый заказ.',
             [('SHARED16', 'first'), ('SHARED9', 'first')]),
            ('Промокод SHARED16 на первый и повторный заказ.',
             [('SHARED16', 'multiple_stages')]),
            ('Промокод SHARED16 на первый заказ. Промокод SHARED16 на повторный заказ.',
             [('SHARED16', 'first'), ('SHARED16', 'repeat')]),
        )
        for body, expected in cases:
            with self.subTest(body=body):
                _, common = self.chain(body)
                self.assertCountEqual([(c['value'], c['scope'].get('purchase_stage'))
                                       for c in common['codes']], expected)

    def test_wrapped_conditional_keeps_its_native_audience(self):
        for body in ('Если заказ отменён,\nдля молодежи промокод NEW10 аннулирован.',
                     'Для молодежи, если заказ отменён,\nпромокод NEW10 аннулирован.'):
            with self.subTest(body=body):
                _, common = self.chain(body)
                raw = copy.deepcopy(common['raw'])
                raw['details']['audiences'] = [
                    {'audience': 'youth', 'promo_code': 'NEW10', 'evidence': ['промокод NEW10']}]
                common = normalize_record(raw, as_of=NOW[:10])
                self.assertEqual([(c['value'], c['scope']) for c in common['codes']],
                                 [('NEW10', {'audience': 'youth'})])
        for prefix in ('При заказе используйте промокод FIRST21',
                       'Промокод FIRST21 действует при заказе'):
            with self.subTest(prefix=prefix):
                _, common = self.chain(prefix + '\nдля молодежи промокод OLD10 отменён.')
                raw = copy.deepcopy(common['raw'])
                raw['details']['audiences'] = [
                    {'audience': 'youth', 'promo_code': 'OLD10',
                     'evidence': ['для молодежи промокод OLD10']}]
                common = normalize_record(raw, as_of=NOW[:10])
                self.assertEqual([c['value'] for c in common['codes']], ['FIRST21'])

    def test_activation_repeat_does_not_add_an_unscoped_coupon(self):
        for field in ('benefit', 'conditions'):
            raw = record(benefit='Скидка 16%.', conditions='', activation='Введите промокод FIRST16.')
            raw[field] = 'Скидка 16% на первый заказ по промокоду FIRST16.'
            for native in ([], ['FIRST16']):
                with self.subTest(field=field, native=native):
                    raw['codes'] = native
                    common = normalize_record(raw, as_of=NOW[:10])
                    self.assertEqual([(c['value'], c['scope']) for c in common['codes']],
                                     [('FIRST16', {'purchase_stage': 'first'})])

    def test_excluded_coupon_stage_is_not_positive_applicability(self):
        for text in ('Промокод FIRST16 не действует на первый заказ.',
                     'Промокод FIRST16 не предоставляется на повторный заказ.'):
            with self.subTest(text=text):
                _, common = self.chain('Скидка 16%.', text)
                self.assertEqual([(c['value'], c['scope']) for c in common['codes']],
                                 [('FIRST16', {})])

    def test_conditional_benefit_cancellation_preserves_its_component(self):
        for prefix in ('Если заказ отменён,', 'При возврате заказа', 'После возврата заказа'):
            for predicate in ('аннулирована', 'отменена'):
                text = f'{prefix} скидка 16% {predicate}. Скидка 9% на меню.'
                with self.subTest(text=text):
                    _, common = self.chain(text)
                    self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                     [('discount', '16'), ('discount', '9')])
        for text in ('При заказе скидка 16% действует, а скидка 9% отменена.',
                     'При заказе скидка 16% действует, скидка 9% отменена.',
                     'Скидка 16% действует при заказе, скидка 9% отменена.'):
            with self.subTest(text=text):
                _, common = self.chain(text)
                self.assertEqual([b['value'] for b in common['benefits']], ['16'])
        for predicate in ('аннулированы', 'недоступны', 'отменены'):
            with self.subTest(shared=predicate):
                _, common = self.chain(f'Если заказ отменён, скидка 16% и кешбэк 9% {predicate}.')
                self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                 [('discount', '16'), ('cashback', '9')])

    def test_conditional_benefit_line_wrap_preserves_original_context(self):
        for prefix in ('Если заказ отменён,', 'Для молодежи, если заказ отменён,',
                       'При возврате заказа', 'После возврата заказа'):
            with self.subTest(prefix=prefix):
                text = prefix + '\nскидка 16% аннулирована. Скидка 9% на меню.'
                source, common = self.chain(text)
                self.assertEqual([r['value'] for r in source['rates']], ['16', '9'])
                self.assertEqual([b['value'] for b in common['benefits']], ['16', '9'])
                self.assertIn('\n', common['benefits'][0]['evidence']['text'])
        for separator in ('\n\n', '.\n', ';\n'):
            with self.subTest(separator=separator):
                _, common = self.chain('Если заказ отменён' + separator +
                                       'скидка 16% аннулирована. Скидка 9% на меню.')
                self.assertEqual([b['value'] for b in common['benefits']], ['9'])

    def test_conditional_eligibility_denial_does_not_create_a_benefit(self):
        for separator in (' ', '\n'):
            with self.subTest(separator=separator):
                text = ('Если участнику положен бесплатный вход,' + separator +
                        'скидка 7% не предоставляется, денежный эквивалент не выплачивается. '
                        'Скидка 11% в магазине.')
                _, common = self.chain(text)
                self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                 [('discount', '11')])

    def test_conditional_instruction_does_not_absorb_a_bare_benefit_heading(self):
        for heading in ('Скидки', 'Скидка участникам программы', 'Скидка применяется автоматически'):
            text = 'При заказе зарегистрируйтесь в приложении\n' + heading
            with self.subTest(heading=heading):
                _, common = self.chain('Скидка 11%.', text)
                self.assertTrue(all(c['evidence']['text'] != text for c in common['conditions']))
                self.assertTrue(any(c['evidence']['text'] == text.split('\n')[0]
                                    for c in common['conditions']))

    def test_single_coupon_does_not_borrow_stage_from_later_offer(self):
        for native in (False, True):
            text = ('Первый магазин: бонусы за первую покупку. Введите промокод DEMO. '
                    'Другой магазин: бонусы за первый заказ и за последующие заказы.')
            with self.subTest(native=native):
                _, common = self.chain(text)
                if not native:
                    raw = copy.deepcopy(common['raw'])
                    raw['codes'] = []
                    common = normalize_record(raw, as_of=NOW[:10])
                self.assertEqual([(c['value'], c['scope']) for c in common['codes']],
                                 [('DEMO', {'purchase_stage': 'first'})])

    def test_plural_cancellation_owns_the_whole_plain_benefit_list(self):
        for predicate in ('аннулированы', 'недоступны', 'отменены'):
            text = f'Скидка 16% и кешбэк 9% {predicate}. Скидка 4% на меню.'
            with self.subTest(text=text):
                _, common = self.chain(text)
                self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                 [('discount', '4')])
                self.assertEqual(record_row(common, NOW[:10])[0][2], 'Скидка 4% на меню.')

    def test_reconciled_native_literal_keeps_its_owned_stage(self):
        raw = record(benefit='Скидка 16%.', conditions='',
                     activation='Введите промокод NEW10 НА САЙТЕ на первый заказ.')
        raw['codes'] = ['NEW10 НА САЙТЕ']
        common = normalize_record(raw, as_of=NOW[:10])
        self.assertEqual([(c['value'], c['scope']) for c in common['codes']],
                         [('NEW10', {'purchase_stage': 'first'})])

    def test_literal_coupon_spelling_cannot_supply_a_purchase_stage(self):
        for text, expected in (
                ('Промокод REPEAT16.', [('REPEAT16', {})]),
                ('Промокод «FIRST ORDER».', [('FIRST ORDER', {})]),
                ('Промокод «REPEAT CUSTOMER» на первый заказ.',
                 [('REPEAT CUSTOMER', {'purchase_stage': 'first'})])):
            for native in (False, True):
                with self.subTest(text=text, native=native):
                    _, common = self.chain('Скидка 16%.', text)
                    if not native:
                        raw = copy.deepcopy(common['raw'])
                        raw['codes'] = []
                        common = normalize_record(raw, as_of=NOW[:10])
                    self.assertEqual([(c['value'], c['scope']) for c in common['codes']], expected)


if __name__ == '__main__':
    unittest.main()
