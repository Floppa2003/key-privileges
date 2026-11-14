"""Synthetic retained-row regressions: formula, reader and local threshold ownership."""
import copy
import json
import unittest

from catalogue_clauses import benefit_claim, meaningful_claim
from catalogue_view import build_catalogue, record_row
from normalized import normalize_rates
from unified_normalization import make_input, normalize_record, validate_normalized


NOW = '2026-11-13T00:00:00+00:00'
RESTRICTION = ('В программе «Орбита» скидки не распространяются на товары, '
               'на которые предоставляется скидка во время распродажи.')


class RetainedProductionRegressions(unittest.TestCase):
    def native(self, benefit, conditions='', details=None):
        fields = {
            'Программа': 'Пример Клуб', 'Партнёр': 'Пример Партнёр',
            'Заголовок': 'Предложение клуба', 'Тип записи': 'partner_offer',
            'Выгода': benefit, 'Условия': conditions, 'Как получить': '',
            'Источник': 'https://example.com/offer',
            'Ссылка на бенефит': 'https://example.com/offer',
            'Тип ссылки': 'detail_page', 'Получено UTC': NOW,
            'Статус источника': 'published', 'Промокоды JSON': '[]',
            'Ставки JSON': '[]', 'Ограничения JSON': '[]',
            'Детали JSON': json.dumps(details or {}, ensure_ascii=False),
        }
        row = {'id': 'synthetic:retained-regressions', 'origin': 'parser_offers',
               'row': 2, 'fields': {key: {'value': value} for key, value in fields.items()}}
        original_row = copy.deepcopy(row)
        raw = make_input(row)
        original = copy.deepcopy(raw)
        result = normalize_record(raw, as_of=NOW[:10])
        self.assertEqual(row, original_row)
        self.assertEqual(raw, original)
        self.assertEqual(result['raw'], original)
        self.assertEqual(result['id'], row['id'])
        self.assertEqual(result['provenance']['observed_at'], NOW)
        self.assertEqual(result['raw']['original'], row)
        self.assertEqual(result['costs'], [])
        validate_normalized(result)
        return result

    def minimum_links(self, common):
        conditions = {c['id']: c for c in common['conditions']}
        return sorted((b['value'], b['evidence']['path'], b['scope'].get('purchase_stage'),
                       sorted((conditions[c]['value'], conditions[c]['evidence']['path'])
                              for c in b['condition_ids']
                              if conditions[c]['kind'] == 'minimum_purchase'))
                      for b in common['benefits'] if b['kind'] == 'discount')

    def test_reverse_monetary_formula_keeps_literal_denominator_and_bounds(self):
        cases = (
            ('За каждые потраченные 200 ₽ - 4 мили «Пример Клуб».',
             ('4', '200', 'RUB', 'exact', None)),
            ('За каждые потраченные 2\u202f750,50 руб. — 7,5 мили «Пример Клуб».',
             ('7.5', '2750.5', 'RUB', 'exact', None)),
            ('За каждые 300 RUB – до 9 миль.', ('9', '300', 'RUB', 'up_to', None)),
            ('За каждые потраченные 1 000 рублей: от 2 до 6 миль.',
             ('6', '1000', 'RUB', 'range', '2')),
            ('4 мили за каждые потраченные 200 ₽.', ('4', '200', 'RUB', 'exact', None)),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                rates = normalize_rates(text)
                self.assertEqual([(r['value'], r['basis_amount'], r['basis_unit'],
                                   r['qualifier'], r.get('min_value')) for r in rates], [expected])
                # The lexical API folds horizontal spaces; common evidence/raw
                # still retain the exact native quotation (checked by native()).
                self.assertEqual(rates[0]['evidence'], text.replace('\u202f', ' '))

    def test_native_complete_rule_has_no_incomplete_lexical_duplicate(self):
        for text, value, base in (
            ('За каждые потраченные 200 ₽ - 4 мили «Пример Клуб».', '4', '200'),
            ('За каждые потраченные 2\u202f750,50 руб. — 7,5 мили «Пример Клуб».',
             '7.5', '2750.5'),
        ):
            with self.subTest(text=text):
                rule = {'value': value, 'unit': 'miles', 'qualifier': 'exact',
                        'basis_amount': base, 'basis_unit': 'RUB', 'evidence': text}
                common = self.native(text, details={'earning_rules': [rule]})
                self.assertEqual([(b['kind'], b['value'], b['basis_value'], b['basis_unit'])
                                  for b in common['benefits']], [('earn_miles', value, base, 'RUB')])
                self.assertEqual(common['benefits'][0]['evidence']['path'], '/details/earning_rules/0')

    def test_reverse_formula_does_not_borrow_another_quantity_or_statement(self):
        for separator in (', а ', '; ', '\n', '. '):
            text = ('За каждые потраченные 200 ₽ - 4 мили онлайн' + separator
                    + 'за каждые потраченные 500 ₽ - 4 мили офлайн.')
            with self.subTest(text=text):
                self.assertCountEqual([(r['value'], r['basis_amount']) for r in normalize_rates(text)],
                                      [('4', '200'), ('4', '500')])
        for text in ('За каждые потраченные 200 ₽ - 4 мили не начисляются.',
                     'За каждые потраченные 0 ₽ - 4 мили.',
                     'За каждые потраченные 1 00 ₽ - 4 мили.'):
            with self.subTest(text=text):
                self.assertEqual(normalize_rates(text), [])
        unrelated = 'За каждые потраченные 200 ₽ доставка бесплатна. Подарок — 4 мили.'
        self.assertEqual([(r['value'], r['basis_amount']) for r in normalize_rates(unrelated)],
                         [('4', None)])

    def test_equal_value_native_and_independent_formula_keep_distinct_bases(self):
        text = ('За каждые потраченные 200 ₽ - 4 мили онлайн, '
                'а за каждые потраченные 500 ₽ - 4 мили офлайн.')
        rule = {'value': '4', 'unit': 'miles', 'qualifier': 'exact', 'channel': 'online',
                'basis_amount': '200', 'basis_unit': 'RUB', 'evidence': text}
        common = self.native(text, details={'earning_rules': [rule]})
        self.assertCountEqual([(b['value'], b['basis_value'], b['basis_unit'])
                               for b in common['benefits']], [('4', '200', 'RUB'), ('4', '500', 'RUB')])
        self.assertEqual(common['benefits'][0]['scope']['channel'], 'online')

    def test_nested_exclusion_is_not_an_offer_with_or_without_a_nested_number(self):
        for marker in ('скидка', 'скидка 13%', 'скидка 17,5%'):
            restriction = RESTRICTION.replace('скидка во время', marker + ' во время')
            with self.subTest(restriction=restriction):
                common = self.native(restriction)
                self.assertFalse(benefit_claim(restriction, common['raw']))
                self.assertEqual(common['benefits'], [])
                self.assertEqual(meaningful_claim(common['raw'], restriction), '')
                row, reason = record_row(common, NOW[:10])
                self.assertIsNone(row)
                self.assertIsNotNone(reason)

    def test_reader_selects_live_sibling_and_retains_nested_restriction(self):
        for live in ('Участникам клуба «Орбита» предоставляется скидка в размере 8%.',
                     'Участникам клуба «Орбита» предоставляется скидка в размере 12,5%.',
                     'Бокал лимонада в подарок при заказе меню.'):
            for reverse in (False, True):
                parts = [live, RESTRICTION] if reverse else [RESTRICTION, live]
                body = '\n'.join(parts)
                with self.subTest(live=live, reverse=reverse):
                    common = self.native(body, body)
                    self.assertEqual(meaningful_claim(common['raw'], body), live)
                    catalogue = build_catalogue([common], as_of=NOW[:10])
                    self.assertEqual(catalogue['removed'], [])
                    self.assertEqual(len(catalogue['rows']), 1)
                    self.assertEqual(catalogue['rows'][0][2], live)
                    self.assertIn(RESTRICTION, catalogue['rows'][0][5])

    def test_numeric_nested_reference_is_not_a_second_common_benefit(self):
        restriction = RESTRICTION.replace('скидка во время', 'скидка 13% во время')
        live = 'Участникам клуба «Орбита» предоставляется скидка в размере 8%.'
        common = self.native(restriction + '\n' + live)
        self.assertEqual([(b['kind'], b['value']) for b in common['benefits']], [('discount', '8')])
        self.assertEqual(build_catalogue([common], as_of=NOW[:10])['rows'][0][2], live)

    def test_relative_reference_stops_before_an_independent_positive_clause(self):
        restriction = RESTRICTION.replace('скидка во время', 'скидка 13% во время').rstrip('.')
        for separator in (', но ', ' но ', ', а ', '; ', '. '):
            with self.subTest(separator=separator):
                common = self.native(restriction + separator + 'скидка 8% действует на меню.')
                self.assertEqual([(b['kind'], b['value']) for b in common['benefits']], [('discount', '8')])
                self.assertTrue(benefit_claim(common['raw']['benefit'], common['raw']))

    def test_primary_numeric_discount_and_genuine_positive_sibling_survive(self):
        for text in (
            'Скидка 8% не распространяется на товары, на которые предоставляется скидка во время распродажи.',
            'Скидка 12,5% не распространяется на товары со скидкой 3%.',
            'Скидки не распространяются на алкоголь, но скидка 8% действует на меню.',
            'Скидки не распространяются на алкоголь, но бокал лимонада в подарок при заказе меню.',
        ):
            with self.subTest(text=text):
                common = self.native(text)
                self.assertTrue(benefit_claim(text, common['raw']))
                row, reason = record_row(common, NOW[:10])
                self.assertIsNone(reason)
                self.assertIsNotNone(row)

    def test_each_repeated_field_owns_its_explicit_nonadjacent_minimum(self):
        cases = (
            ('28', '1 700 ₽', '1700',
             'Оформите первый заказ в разделе «Дом» на сумму от 1 700 ₽. '
             'Получите скидку 28% на ваш первый заказ.'),
            ('33', '2 300 ₽', '2300',
             'Оформите первый заказ в разделе «Техника», сложив в корзину товары на сумму от 2 300 рублей. '
             'Получите скидку 33% на ваш первый заказ.'),
            ('12,5', '2\u202f750,50 руб.', '2750.5',
             'Оформите первый заказ в разделе «Книги» на сумму от 2\u202f750,50 RUB. '
             'Получите скидку 12,5% на ваш первый заказ.'),
        )
        for rate, amount, value, conditions in cases:
            benefit = f'Скидка {rate}% на первый заказ от {amount} по промокоду в приложении'
            with self.subTest(benefit=benefit, conditions=conditions):
                common = self.native(benefit, conditions)
                normalized_rate = {'28': '28', '33': '33', '12,5': '12.5'}[rate]
                self.assertEqual(self.minimum_links(common), [
                    (normalized_rate, '/benefit', 'first', [(value, '/benefit')]),
                    (normalized_rate, '/conditions', 'first', [(value, '/conditions')]),
                ])
                self.assertEqual(common['codes'], [])

    def test_nonadjacent_minima_stay_with_their_distinct_components(self):
        for separator in (', ', '. ', '; ', '\n'):
            for stage, expected_stage in (('повторный', 'repeat'), ('первый', 'first')):
                text = ('Скидка 28% на первый заказ в разделе «Дом» на сумму от 1 700 ₽'
                        + separator + f'скидка 33% на {stage} заказ в разделе «Техника» на сумму от 2 300 рублей.')
                with self.subTest(text=text):
                    self.assertEqual(self.minimum_links(self.native(text)), [
                        ('28', '/benefit', 'first', [('1700', '/benefit')]),
                        ('33', '/benefit', expected_stage, [('2300', '/benefit')]),
                    ])

    def test_local_threshold_is_not_copied_from_an_equal_rate_in_another_field(self):
        threshold = 'Оформите первый заказ в разделе «Книги 2027» на сумму от 2 300 ₽.'
        discount = 'Получите скидку 28% на ваш первый заказ.'
        for conditions in (threshold + ' ' + discount, discount + ' ' + threshold):
            with self.subTest(conditions=conditions):
                common = self.native('Скидка 28% на первый заказ от 1 700 ₽ по промокоду в приложении', conditions)
                self.assertEqual(self.minimum_links(common), [
                    ('28', '/benefit', 'first', [('1700', '/benefit')]),
                    ('28', '/conditions', 'first', [('2300', '/conditions')]),
                ])

    def test_qualified_other_field_does_not_supply_an_absent_local_minimum(self):
        common = self.native('Скидка 28% на первый заказ от 1 700 ₽ по промокоду в приложении',
                             'Получите скидку 28% на ваш первый заказ.')
        self.assertEqual(self.minimum_links(common), [
            ('28', '/benefit', 'first', [('1700', '/benefit')]),
            ('28', '/conditions', 'first', []),
        ])

    def test_threshold_cannot_cross_a_sentence_or_a_distinct_reward(self):
        for text in ('Оформите первый заказ в разделе «Дом». Доставка от 1 700 ₽. Скидка 28% на первый заказ.',
                     'Скидка 28% на первый заказ в приложении. Начисляем 4 мили за каждые 1 700 ₽.',
                     'Скидка 28% на первый заказ в разделе «Дом», а пополнение кошелька на сумму от 1 700 ₽.',
                     'Скидка 28% на первый заказ в разделе «Дом» не требует корзины на сумму от 1 700 ₽.'):
            with self.subTest(text=text):
                common = self.native(text)
                self.assertEqual([c for c in common['conditions'] if c['kind'] == 'minimum_purchase'], [])

    def test_local_minimum_cannot_cross_explicit_channel_or_category_conflicts(self):
        for threshold_qualifier, benefit_qualifier in (
            ('в приложении', 'на сайте'),
            ('на сайте', 'в приложении'),
            ('в приложении «Север»', 'в приложении «Юг»'),
            ('на сайте «Север»', 'на сайте «Юг»'),
            ('в разделе «Север»', 'в разделах «Север» или «Юг»'),
            ('в приложении «Север»', 'в приложениях «Север» или «Юг»'),
            ('в разделе «Дом»', 'в разделе «Техника»'),
            ('в разделе «Книги 2027»', 'в разделе «Книги 2028»'),
        ):
            threshold = f'Оформите первый заказ {threshold_qualifier} на сумму от 1 700 ₽.'
            discount = f'Скидка 28% на первый заказ {benefit_qualifier}.'
            for text in (threshold + ' ' + discount, discount + ' ' + threshold):
                with self.subTest(text=text):
                    common = self.native(text)
                    self.assertEqual([(c['value'], c['unit'], c['evidence']['path'])
                                      for c in common['conditions'] if c['kind'] == 'minimum_purchase'],
                                     [('1700', 'RUB', '/benefit')])
                    self.assertEqual(self.minimum_links(common), [('28', '/benefit', 'first', [])])

    def test_matching_or_unqualified_local_benefit_retains_its_threshold(self):
        for threshold_qualifier, benefit_qualifier in (
            ('в приложении', 'в приложении'),
            ('в приложении «Север»', 'в приложении «Север»'),
            ('в разделах «Север» или «Юг»', 'в разделе «Север»'),
            ('в приложениях «Север» или «Юг»', 'в приложении «Север»'),
            ('в разделе «Дом»', 'в разделе «Дом»'),
            ('в разделе «Книги 2027»', ''),
        ):
            text = (f'Оформите первый заказ {threshold_qualifier} на сумму от 2 300 ₽. '
                    f'Скидка 33% на первый заказ {benefit_qualifier}.')
            with self.subTest(text=text):
                self.assertEqual(self.minimum_links(self.native(text)), [
                    ('33', '/benefit', 'first', [('2300', '/benefit')]),
                ])

    def test_prefix_denial_does_not_create_a_positive_minimum(self):
        for prefix in ('Не требуется оформлять', 'Не нужно оформлять'):
            text = f'{prefix} первый заказ в приложении на сумму от 1 700 ₽. Скидка 28% на первый заказ.'
            with self.subTest(text=text):
                common = self.native(text)
                self.assertEqual([c for c in common['conditions'] if c['kind'] == 'minimum_purchase'], [])
                self.assertEqual(self.minimum_links(common), [('28', '/benefit', 'first', [])])
        positive = ('Не требуется предъявлять карту. Оформите первый заказ в приложении '
                    'на сумму от 1 700 ₽. Скидка 28% на первый заказ.')
        self.assertEqual(self.minimum_links(self.native(positive)), [
            ('28', '/benefit', 'first', [('1700', '/benefit')]),
        ])
        siblings = ('Не требуется оформлять повторный заказ в приложении на сумму от 900 ₽. '
                    'Оформите первый заказ в приложении на сумму от 1 700 ₽. Скидка 28% на первый заказ.')
        common = self.native(siblings)
        self.assertEqual([(c['value'], c['unit']) for c in common['conditions']
                          if c['kind'] == 'minimum_purchase'], [('1700', 'RUB')])
        self.assertEqual(self.minimum_links(common), [('28', '/benefit', 'first', [('1700', '/benefit')])])

    def test_postfix_denial_does_not_create_a_positive_minimum(self):
        for amount, rate, value in (('1 700 ₽', '28', '28'),
                                    ('2\u202f750,50 руб.', '12,5', '12.5'),
                                    ('3.600,25 RUB', '33', '33')):
            for predicate in ('не требуется', 'не нужно'):
                for joiner in (' ', ' — '):
                    text = (f'Оформлять первый заказ в приложении на сумму от {amount}{joiner}{predicate}. '
                            f'Скидка {rate}% на первый заказ.')
                    with self.subTest(text=text):
                        common = self.native(text)
                        self.assertEqual([c for c in common['conditions'] if c['kind'] == 'minimum_purchase'], [])
                        self.assertEqual(self.minimum_links(common), [(value, '/benefit', 'first', [])])
                        self.assertEqual([(b['kind'], b['value']) for b in common['benefits']], [('discount', value)])

    def test_postfix_guard_preserves_true_minimum_next_to_an_unrelated_negative(self):
        for amount, expected in (('1 700 ₽', '1700'), ('2\u202f750,50 руб.', '2750.5')):
            for continuation in ('. Предъявлять карту не требуется.',
                                 ', карту предъявлять не требуется.',
                                 ' — не требуется предъявлять карту.',
                                 ' — не нужно вводить промокод.'):
                if amount.endswith('.') and continuation.startswith('.'):
                    continuation = continuation[1:]
                text = (f'Оформите первый заказ в приложении на сумму от {amount}{continuation} '
                        'Скидка 28% на первый заказ.')
                with self.subTest(text=text):
                    common = self.native(text)
                    self.assertEqual([(c['value'], c['unit']) for c in common['conditions']
                                      if c['kind'] == 'minimum_purchase'], [(expected, 'RUB')])
                    self.assertEqual(self.minimum_links(common), [('28', '/benefit', 'first', [(expected, '/benefit')])])

    def test_postfix_denial_is_local_to_its_own_order_requirement(self):
        denied = 'Оформлять повторный заказ в приложении на сумму от 900 ₽ не нужно.'
        required = 'Оформите первый заказ в приложении на сумму от 1 700 ₽.'
        for statements in (denied + ' ' + required, required + ' ' + denied):
            with self.subTest(statements=statements):
                common = self.native(statements + ' Скидка 28% на первый заказ.')
                self.assertEqual([(c['value'], c['unit']) for c in common['conditions']
                                  if c['kind'] == 'minimum_purchase'], [('1700', 'RUB')])
                self.assertEqual(self.minimum_links(common), [('28', '/benefit', 'first', [('1700', '/benefit')])])

    def test_modified_postfix_requirement_denial_does_not_create_a_minimum(self):
        for predicate in ('больше не требуется', 'уже не нужно', 'временно не требуется',
                          'сейчас не нужно', 'пока не обязательно', 'не будет требоваться',
                          'вам уже не нужно', 'не требуется больше', 'не нужно уже',
                          'не требуется временно', 'не нужно сейчас', 'не обязательно пока',
                          'не нужно будет', 'не будет вам требоваться',
                          'вам больше не будет требоваться', 'не потребуется',
                          'вам больше не потребуется', 'не потребуется сейчас',
                          'необязательно', 'вам сейчас необязательно', 'необязательно будет'):
            for amount, rate, value in (('1 700 ₽', '28', '28'),
                                        ('2\u202f750,50 руб.', '12,5', '12.5')):
                text = (f'Оформлять первый заказ в приложении на сумму от {amount} {predicate}. '
                        f'Скидка {rate}% на первый заказ.')
                with self.subTest(text=text):
                    common = self.native(text)
                    self.assertEqual([c for c in common['conditions'] if c['kind'] == 'minimum_purchase'], [])
                    self.assertEqual(self.minimum_links(common), [(value, '/benefit', 'first', [])])
                    self.assertEqual([(b['kind'], b['value']) for b in common['benefits']], [('discount', value)])

    def test_modified_prefix_requirement_denial_does_not_create_a_minimum(self):
        for prefix in ('Больше не требуется оформлять', 'Уже не нужно оформлять',
                       'Временно не требуется оформлять', 'Сейчас не нужно оформлять',
                       'Пока не обязательно оформлять', 'Не будет требоваться оформлять',
                       'Вам уже не нужно оформлять', 'Не требуется больше оформлять',
                       'Не нужно уже оформлять', 'Не требуется временно оформлять',
                       'Не нужно сейчас оформлять', 'Не обязательно пока оформлять',
                       'Не нужно будет оформлять', 'Не будет вам требоваться оформлять',
                       'Не требуется оформлять сейчас', 'Не нужно оформлять пока',
                       'Вам больше не будет требоваться оформлять', 'Не потребуется оформлять',
                       'Вам больше не потребуется оформлять', 'Не потребуется сейчас оформлять',
                       'Необязательно оформлять', 'Вам сейчас необязательно оформлять',
                       'Необязательно будет оформлять'):
            text = (f'{prefix} первый заказ в приложении на сумму от 3.600,25 RUB. '
                    'Скидка 33% на первый заказ.')
            with self.subTest(text=text):
                common = self.native(text)
                self.assertEqual([c for c in common['conditions'] if c['kind'] == 'minimum_purchase'], [])
                self.assertEqual(self.minimum_links(common), [('33', '/benefit', 'first', [])])
                self.assertEqual([(b['kind'], b['value']) for b in common['benefits']], [('discount', '33')])

    def test_modified_affirmative_requirement_keeps_its_minimum(self):
        for predicate in ('сейчас требуется', 'пока нужно', 'вам уже требуется',
                          'будет нужно', 'требуется сейчас', 'нужно пока',
                          'потребуется', 'вам потребуется', 'обязательно', 'сейчас обязательно'):
            purchase = 'первый заказ в приложении на сумму от 2\u202f750,50 ₽'
            for statement in (f'{predicate} оформлять {purchase}.',
                              f'Оформлять {purchase} {predicate}.'):
                with self.subTest(statement=statement):
                    common = self.native(statement + ' Скидка 12,5% на первый заказ.')
                    self.assertEqual([(c['value'], c['unit']) for c in common['conditions']
                                      if c['kind'] == 'minimum_purchase'], [('2750.5', 'RUB')])
                    self.assertEqual(self.minimum_links(common), [
                        ('12.5', '/benefit', 'first', [('2750.5', '/benefit')]),
                    ])

    def test_modified_unrelated_negative_instruction_preserves_a_true_minimum(self):
        threshold = 'Оформите первый заказ в приложении на сумму от 1 700 ₽'
        for statement in (
            'Больше не требуется предъявлять карту. ' + threshold + '.',
            'Не нужно сейчас вводить промокод. ' + threshold + '.',
            'Не потребуется предъявлять карту. ' + threshold + '.',
            'Вам необязательно вводить промокод. ' + threshold + '.',
            threshold + ' — больше не требуется предъявлять карту.',
            threshold + ' — не требуется больше предъявлять карту.',
            threshold + ' — не будет вам требоваться предъявлять карту.',
            threshold + ' — уже не нужно вводить промокод.',
            threshold + ' — не нужно сейчас вводить промокод.',
            threshold + ' — больше не потребуется предъявлять карту.',
            threshold + ' — необязательно вводить промокод.',
            threshold + ' — вам необязательно сейчас предъявлять карту.',
            threshold + ', карту предъявлять уже не нужно.',
        ):
            with self.subTest(statement=statement):
                common = self.native(statement + ' Скидка 28% на первый заказ.')
                self.assertEqual([(c['value'], c['unit']) for c in common['conditions']
                                  if c['kind'] == 'minimum_purchase'], [('1700', 'RUB')])
                self.assertEqual(self.minimum_links(common), [('28', '/benefit', 'first', [('1700', '/benefit')])])

    def test_modified_denial_stays_with_its_own_order_requirement(self):
        required = 'Оформите первый заказ в приложении на сумму от 2\u202f750,50 ₽.'
        for denied in ('Оформлять повторный заказ в приложении на сумму от 900 ₽ больше не требуется.',
                       'Не нужно пока оформлять повторный заказ в приложении на сумму от 900 ₽.'):
            for statements in (denied + ' ' + required, required + ' ' + denied):
                with self.subTest(statements=statements):
                    common = self.native(statements + ' Скидка 12,5% на первый заказ.')
                    self.assertEqual([(c['value'], c['unit']) for c in common['conditions']
                                      if c['kind'] == 'minimum_purchase'], [('2750.5', 'RUB')])
                    self.assertEqual(self.minimum_links(common), [
                        ('12.5', '/benefit', 'first', [('2750.5', '/benefit')]),
                    ])

    def test_short_requirement_predicates_keep_their_negative_polarity(self):
        purchase = 'Первый заказ в приложении на сумму от 2\u202f750,50 ₽'
        for predicate, expected in (
            ('не нужен', []), ('больше не нужен', []),
            ('не обязателен', []), ('сейчас не обязателен', []), ('необязателен', []),
            ('нужен', [('2750.5', 'RUB')]), ('обязателен', [('2750.5', 'RUB')]),
        ):
            with self.subTest(predicate=predicate):
                common = self.native(f'{purchase} {predicate}. Скидка 12,5% на первый заказ.')
                self.assertEqual([(c['value'], c['unit']) for c in common['conditions']
                                  if c['kind'] == 'minimum_purchase'], expected)
                self.assertEqual(self.minimum_links(common), [
                    ('12.5', '/benefit', 'first', [(value, '/benefit') for value, _ in expected]),
                ])

    def test_one_native_channel_owns_only_its_actual_equal_formula_occurrence(self):
        for amount, reward, value, base in (('200 ₽', '4', '4', '200'),
                                             ('300 руб.', '6', '6', '300'),
                                             ('2\u202f750,50 RUB', '7,5', '7.5', '2750.5')):
            online = f'За каждые потраченные {amount} — {reward} мили онлайн'
            offline = f'За каждые потраченные {amount} — {reward} мили офлайн'
            for reverse in (False, True):
                text = (offline + ', а ' + online[0].lower() + online[1:] + '.' if reverse else
                        online + ', а ' + offline[0].lower() + offline[1:] + '.')
                expected_offline = offline if reverse else offline[0].lower() + offline[1:] + '.'
                rule = {'value': value, 'unit': 'miles', 'qualifier': 'exact', 'channel': 'online',
                        'basis_amount': base, 'basis_unit': 'RUB', 'evidence': text}
                with self.subTest(text=text):
                    self.assertEqual(len(normalize_rates(text, with_spans=True)), 2)
                    common = self.native(text, details={'earning_rules': [rule]})
                    self.assertEqual(len(common['benefits']), 2)
                    native, = [b for b in common['benefits'] if b['evidence']['path'] == '/details/earning_rules/0']
                    lexical, = [b for b in common['benefits'] if b['evidence']['path'] == '/benefit']
                    self.assertEqual(native['scope']['channel'], 'online')
                    self.assertEqual((lexical['kind'], lexical['value'], lexical['basis_value'], lexical['basis_unit']),
                                     ('earn_miles', value, base, 'RUB'))
                    self.assertEqual(lexical['evidence']['text'], expected_offline)

    def test_ambiguous_native_owner_cannot_consume_equal_channel_occurrences(self):
        text = ('За каждые потраченные 200 ₽ — 4 мили онлайн, '
                'а за каждые потраченные 200 ₽ — 4 мили офлайн.')
        rule = {'value': '4', 'unit': 'miles', 'qualifier': 'exact',
                'basis_amount': '200', 'basis_unit': 'RUB', 'evidence': text}
        common = self.native(text, details={'earning_rules': [rule]})
        self.assertEqual(len(common['benefits']), 3)
        self.assertCountEqual([b['evidence']['text'] for b in common['benefits']
                               if b['evidence']['path'] == '/benefit'], [
            'За каждые потраченные 200 ₽ — 4 мили онлайн',
            'за каждые потраченные 200 ₽ — 4 мили офлайн.',
        ])
        common = self.native(text, details={'earning_rules': [dict(rule, channel='online'),
                                                                   dict(rule, channel='offline')]})
        self.assertEqual(len(common['benefits']), 2)
        self.assertCountEqual([b['scope']['channel'] for b in common['benefits']], ['online', 'offline'])

    def test_native_channel_reconciliation_keeps_its_own_denial_and_bound(self):
        online = 'За каждые потраченные 200 ₽ — 4 мили не начисляются онлайн'
        offline = 'За каждые потраченные 200 ₽ — 4 мили офлайн'
        for text in (online + ', а ' + offline.lower() + '.',
                     offline + ', а ' + online.lower() + '.'):
            rule = {'value': '4', 'unit': 'miles', 'qualifier': 'exact', 'channel': 'online',
                    'basis_amount': '200', 'basis_unit': 'RUB', 'evidence': text}
            with self.subTest(text=text):
                common = self.native(text, details={'earning_rules': [rule]})
                self.assertEqual([(b['kind'], b['value'], b['basis_value'], b['evidence']['path'])
                                  for b in common['benefits']], [('earn_miles', '4', '200', '/benefit')])
        text = ('За каждые потраченные 200 ₽ — до 4 мили онлайн, '
                'а за каждые потраченные 200 ₽ — 4 мили офлайн.')
        rule = {'value': '4', 'unit': 'miles', 'qualifier': 'exact', 'channel': 'online',
                'basis_amount': '200', 'basis_unit': 'RUB', 'evidence': text}
        common = self.native(text, details={'earning_rules': [rule]})
        self.assertCountEqual([(b['value'], b['basis_value'], b['qualifier'])
                               for b in common['benefits']], [('4', '200', 'up_to'), ('4', '200', 'exact')])

    def test_surviving_local_formula_retains_its_shared_clause_restriction(self):
        text = ('За каждые потраченные 200 ₽ — 4 мили онлайн, '
                'а за каждые потраченные 200 ₽ — 4 мили офлайн. Не суммируется с другими акциями.')
        rule = {'value': '4', 'unit': 'miles', 'qualifier': 'exact', 'channel': 'online',
                'basis_amount': '200', 'basis_unit': 'RUB', 'evidence': text}
        common = self.native(text, details={'earning_rules': [rule]})
        lexical, = [b for b in common['benefits'] if b['evidence']['path'] == '/benefit']
        restriction, = [c for c in common['conditions'] if c['kind'] == 'stacking_restriction']
        self.assertEqual(lexical['evidence']['text'], 'за каждые потраченные 200 ₽ — 4 мили офлайн.')
        self.assertEqual(restriction['evidence']['text'], text)
        self.assertIn(restriction['id'], lexical['condition_ids'])

    def test_quoted_category_alternatives_keep_their_own_basket_minimum(self):
        for rate, amount, value, categories in (
            ('27', '2 600', '2600', '«Север» или «Юг»'),
            ('31,5', '1\u202f200,75', '1200.75', '«Восток 2028» или «Запад 2029»'),
        ):
            benefit = f'Скидка {rate}% на первый заказ от {amount} ₽ по промокоду в приложении'
            conditions = (f'Оформите первый заказ в разделах {categories}, сложив в корзину товары '
                          f'на сумму от {amount} рублей — введите промокод при оформлении заказа '
                          f'— получите скидку {rate}% на ваш заказ.')
            with self.subTest(conditions=conditions):
                common = self.native(benefit, conditions)
                normalized_rate = {'27': '27', '31,5': '31.5'}[rate]
                self.assertEqual(self.minimum_links(common), [
                    (normalized_rate, '/benefit', 'first', [(value, '/benefit')]),
                    (normalized_rate, '/conditions', 'first', [(value, '/conditions')]),
                ])
                local, = [c for c in common['conditions'] if c['kind'] == 'minimum_purchase'
                          and c['evidence']['path'] == '/conditions']
                self.assertEqual(local['evidence']['text'], conditions)
                self.assertEqual(local['unit'], 'RUB')

    def test_quoted_label_does_not_open_an_independent_alternative_action(self):
        for sibling in ('пополните кошелёк на сумму от 2 600 рублей',
                        'получите скидку 9% при покупке на сумму от 2 600 рублей'):
            text = (f'Оформите первый заказ в разделе «Север» или {sibling}. '
                    'Скидка 27% на первый заказ.')
            with self.subTest(text=text):
                common = self.native(text)
                discount, = [b for b in common['benefits'] if b['kind'] == 'discount' and b['value'] == '27']
                conditions = {c['id']: c for c in common['conditions']}
                self.assertEqual([conditions[c] for c in discount['condition_ids']
                                  if conditions[c]['kind'] == 'minimum_purchase'], [])


if __name__ == '__main__':
    unittest.main()
