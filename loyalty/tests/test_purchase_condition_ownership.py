"""Purchase amounts follow their literal components, never numeric coincidence."""
import copy
import unittest

from catalogue_view import record_row
from normalized import make_offer
from test_dom_card_boundaries import project
from test_unified_normalization import record
from unified_normalization import normalize_record, validate_normalized

NOW = '2026-11-13T00:00:00+00:00'


class PurchaseConditionOwnershipTests(unittest.TestCase):
    def common(self, text, **updates):
        raw = record(benefit=text, conditions='', activation='', **updates)
        original = copy.deepcopy(raw)
        result = normalize_record(raw, as_of=NOW[:10])
        self.assertEqual(raw, original)
        self.assertEqual(result['raw'], original)
        self.assertEqual(result['provenance']['observed_at'], original['observed_at'])
        self.assertEqual(result['id'], original['id'])
        validate_normalized(result)
        return result

    def linked(self, result, kind):
        conditions = {c['id']: c for c in result['conditions']}
        return [(b['value'], b['scope'].get('purchase_stage'),
                 sorted(conditions[c]['value'] for c in b['condition_ids']
                        if conditions[c]['kind'] == kind)) for b in result['benefits']]

    def test_each_minimum_belongs_only_to_its_component(self):
        for separator in (', ', '. ', '; ', '\n'):
            for first, repeat, expected in (
                ('5000 ₽', '2000 ₽', [('20', 'first', ['5000']), ('10', 'repeat', ['2000'])]),
                ('7000 руб.', '7000 руб.', [('20', 'first', ['7000']), ('10', 'repeat', ['7000'])]),
                ('4.500,50 руб.', '1\u202f250,75 руб.',
                 [('20', 'first', ['4500.5']), ('10', 'repeat', ['1250.75'])]),
            ):
                boundary = ' ' if first.endswith('.') and separator == '. ' else separator
                tail = '' if repeat.endswith('.') else '.'
                text = f'Скидка 20% на первый заказ от {first}{boundary}Скидка 10% на повторный заказ от {repeat}{tail}'
                with self.subTest(text=text):
                    result = self.common(text)
                    self.assertCountEqual(self.linked(result, 'minimum_purchase'), expected)
                    self.assertCountEqual([(c['value'], c['scope'].get('purchase_stage'))
                                           for c in result['conditions'] if c['kind'] == 'minimum_purchase'],
                                          [(expected[0][2][0], 'first'), (expected[1][2][0], 'repeat')])

    def test_equal_or_absent_stages_do_not_cross_link_different_minima(self):
        for stage, expected_stage in (('', None), (' на первый', 'first'), (' на повторный', 'repeat')):
            text = (f'Скидка 20%{stage} заказ от 5000 ₽, '
                    f'скидка 10%{stage} заказ от 2000 ₽.')
            with self.subTest(text=text):
                self.assertCountEqual(self.linked(self.common(text), 'minimum_purchase'),
                                      [('20', expected_stage, ['5000']), ('10', expected_stage, ['2000'])])

    def test_minimum_before_rate_keeps_its_component(self):
        text = 'На первый заказ от 5000 ₽ скидка 20%, на повторный заказ от 2000 ₽ скидка 10%.'
        self.assertCountEqual(self.linked(self.common(text), 'minimum_purchase'),
                              [('20', 'first', ['5000']), ('10', 'repeat', ['2000'])])

    def test_explicit_shared_minimum_stays_shared(self):
        for text in ('При покупке от 5000 ₽ скидка 20% и 10%.',
                     'При покупке от 5000 ₽ скидка 20% на обувь и 10% на одежду.',
                     'Скидка 20% и 10% при покупке от 5000 ₽.'):
            with self.subTest(text=text):
                self.assertCountEqual(self.linked(self.common(text), 'minimum_purchase'),
                                      [('20', None, ['5000']), ('10', None, ['5000'])])

    def test_purchase_maximum_is_not_a_reward_cap(self):
        for noun in ('заказа', 'покупки', 'чека'):
            text = f'Скидка 10% при сумме {noun} не более 5000 рублей.'
            with self.subTest(text=text):
                result = self.common(text)
                self.assertEqual([c for c in result['conditions'] if c['kind'] == 'benefit_cap'], [])
                self.assertEqual([(c['value'], c['qualifier']) for c in result['conditions']
                                  if c['kind'] == 'maximum_amount_reference'], [('5000', 'up_to')])
                self.assertEqual([(b['kind'], b['value']) for b in result['benefits']], [('discount', '10')])

    def test_explicit_reward_cap_owns_purchase_nouns_used_as_its_basis(self):
        for rule in ('лимит скидки на заказ — не более 5000 рублей',
                     'максимальный размер кешбэка за покупку — не более 5000 рублей',
                     'компенсация оплаты в ресторане — не более 5000 рублей за каждый чек'):
            with self.subTest(rule=rule):
                result = self.common('Скидка 10%. ' + rule + '.')
                self.assertEqual([(c['kind'], c['value']) for c in result['conditions']
                                  if c['value'] == '5000'], [('benefit_cap', '5000')])

    def test_sibling_caps_keep_their_own_numeric_linkage(self):
        for stage, expected_stage in (('', None), (' на первый заказ', 'first')):
            text = (f'Скидка 20%{stage} (не более 500 рублей), '
                    f'скидка 10%{stage} (не более 200 рублей).')
            with self.subTest(text=text):
                self.assertCountEqual(self.linked(self.common(text), 'benefit_cap'),
                                      [('20', expected_stage, ['500']), ('10', expected_stage, ['200'])])

    def test_purchase_maxima_keep_their_component_scope(self):
        text = ('Скидка 20% на первый заказ при сумме заказа не более 5000 рублей, '
                'скидка 10% на повторный заказ при сумме заказа не более 2000 рублей.')
        result = self.common(text)
        self.assertEqual([c for c in result['conditions'] if c['kind'] == 'benefit_cap'], [])
        self.assertCountEqual([(c['value'], c['scope'].get('purchase_stage'))
                               for c in result['conditions'] if c['kind'] == 'maximum_amount_reference'],
                              [('5000', 'first'), ('2000', 'repeat')])

    def test_gift_component_keeps_its_minimum(self):
        text = 'Кофе в подарок на первый заказ от 5000 ₽, скидка 10% на повторный заказ от 2000 ₽.'
        self.assertCountEqual(self.linked(self.common(text), 'minimum_purchase'),
                              [(None, 'first', ['5000']), ('10', 'repeat', ['2000'])])

    def test_independent_payment_and_fee_limits_do_not_link_to_reward(self):
        for owner in ('Предоплата', 'Оплата наличными', 'Комиссия', 'Стоимость покупки'):
            text = f'Скидка 10% на первый заказ. {owner} не более 5000 рублей на первый заказ.'
            with self.subTest(owner=owner):
                result = self.common(text)
                self.assertEqual(self.linked(result, 'maximum_amount_reference'), [('10', 'first', [])])
                self.assertEqual([c for c in result['conditions'] if c['kind'] == 'benefit_cap'], [])
                self.assertEqual([c['value'] for c in result['conditions']
                                  if c['kind'] == 'maximum_amount_reference'], ['5000'])

    def test_shared_non_numeric_rules_keep_their_original_linkage(self):
        text = ('Скидка 20% на первый заказ от 5000 ₽, скидка 10% на повторный заказ от 2000 ₽, '
                'не суммируется с другими акциями.')
        result = self.common(text)
        rule, = [c for c in result['conditions'] if c['kind'] == 'stacking_restriction']
        self.assertTrue(all(rule['id'] in b['condition_ids'] for b in result['benefits']))
        self.assertEqual(rule['evidence']['text'], text)

    def test_explicit_reward_cap_preserves_singular_and_count_bases(self):
        for basis in ('за одну покупку', 'за одно бронирование', 'на один заказ',
                      'за 2 покупки', 'за две покупки', 'за каждый чек'):
            with self.subTest(basis=basis):
                result = self.common(f'Кешбэк 10%. Максимальный размер кешбэка {basis} — не более 5000 рублей.')
                self.assertEqual([(c['kind'], c['value']) for c in result['conditions']
                                  if c['value'] == '5000'], [('benefit_cap', '5000')])
                self.assertEqual(self.linked(result, 'benefit_cap'), [('10', None, ['5000'])])
        result = self.common('Кешбэк 10%. Максимальный размер кешбэка при сумме заказа не более 5000 рублей.')
        self.assertEqual([(c['kind'], c['value']) for c in result['conditions']
                          if c['value'] == '5000'], [('maximum_amount_reference', '5000')])
        self.assertEqual(self.linked(result, 'benefit_cap'), [('10', None, [])])

    def published_minima(self, header, rule, field):
        source = make_offer('s7', 'repeated-purchase-fixture', 'Карта', 'Example', header,
                            'https://marketplace.s7.ru/partners/offer/example', NOW,
                            **{field: rule})
        before = copy.deepcopy(source)
        result = project(source)
        self.assertEqual(source, before)
        self.assertEqual(result['raw']['id'], source['id'])
        self.assertEqual(result['provenance']['observed_at'], NOW)
        conditions = {c['id']: c for c in result['conditions']}
        linked = [(b['evidence']['path'], b['kind'], b['value'], b['scope'].get('purchase_stage'),
                   sorted(conditions[c]['value'] for c in b['condition_ids']
                          if conditions[c]['kind'] == 'minimum_purchase')) for b in result['benefits']]
        return result, linked

    def test_repeated_discount_keeps_minimum_from_activation_or_conditions(self):
        for field, path in (('redemption', '/activation'), ('conditions', '/conditions')):
            for rate, minimum, expected_rate, expected_minimum in (
                ('17', '1 500', '17', '1500'), ('23,5', '2 780,75', '23.5', '2780.75')):
                header = f'Скидка {rate}% на первый заказ на «Example» и 500 миль в подарок'
                rule = f'Получите промокод на скидку {rate}% на первый заказ от {minimum} рублей.'
                with self.subTest(field=field, rate=rate):
                    result, linked = self.published_minima(header, rule, field)
                    self.assertCountEqual(linked, [
                        ('/benefit', 'discount', expected_rate, 'first', [expected_minimum]),
                        ('/benefit', 'earn_miles', '500', None, []),
                        ('/benefit', 'gift', None, None, []),
                        (path, 'discount', expected_rate, 'first', [expected_minimum])])
                    reader, reason = record_row(result, NOW[:10])
                    self.assertIsNone(reason)
                    self.assertIn(rule, '\n'.join(reader[3:6]))

    def test_cross_field_minimum_does_not_cross_sibling_rate_or_stage(self):
        header = 'Скидка 17% на первый заказ, скидка 9% на первый заказ и скидка 17% на повторный заказ.'
        rule = 'Получите промокод на скидку 17% на первый заказ от 1500 рублей. Предоплата 50%.'
        _, linked = self.published_minima(header, rule, 'redemption')
        self.assertCountEqual(linked, [
            ('/benefit', 'discount', '17', 'first', ['1500']),
            ('/benefit', 'discount', '9', 'first', []),
            ('/benefit', 'discount', '17', 'repeat', []),
            ('/activation', 'discount', '17', 'first', ['1500'])])

    def test_ambiguous_or_conflicting_representations_do_not_acquire_minimum(self):
        rule = 'Получите промокод на скидку 17% на первый заказ от 1500 рублей.'
        for header, expected in (
            ('Скидка 17% на первый заказ обуви, скидка 17% на первый заказ одежды.',
             [('17', 'first', [])]),
            ('Скидка 17% на первый заказ от 3000 рублей.', [('17', 'first', ['3000'])]),
            ('Скидка 17% на заказ.', [('17', None, [])]),
            ('Скидка до 17% на первый заказ.', [('17', 'first', [])]),
        ):
            with self.subTest(header=header):
                _, linked = self.published_minima(header, rule, 'conditions')
                self.assertCountEqual([(value, stage, values) for path, kind, value, stage, values in linked
                                       if path == '/benefit'], expected)

    def test_unrepresented_product_or_channel_rule_is_not_assumed_shared(self):
        header = 'Скидка 17% на первый заказ.'
        for suffix in (' на обувь', ' только онлайн', ' только в магазине'):
            rule = 'Скидка 17% на первый заказ от 1500 рублей' + suffix + '.'
            with self.subTest(suffix=suffix):
                _, linked = self.published_minima(header, rule, 'conditions')
                self.assertCountEqual(linked, [
                    ('/benefit', 'discount', '17', 'first', []),
                    ('/conditions', 'discount', '17', 'first', ['1500'])])

    def test_conflicting_cross_field_rules_do_not_guess_a_header_minimum(self):
        source = make_offer('s7', 'conflicting-purchase-fixture', 'Карта', 'Example',
                            'Скидка 17% на первый заказ.',
                            'https://marketplace.s7.ru/partners/offer/example', NOW,
                            conditions='Скидка 17% на первый заказ от 3000 рублей.',
                            redemption='Скидка 17% на первый заказ от 1500 рублей.')
        result = project(source)
        conditions = {c['id']: c for c in result['conditions']}
        self.assertCountEqual([(b['evidence']['path'], sorted(conditions[c]['value']
                               for c in b['condition_ids'] if conditions[c]['kind'] == 'minimum_purchase'))
                               for b in result['benefits']],
                              [('/benefit', []), ('/conditions', ['3000']), ('/activation', ['1500'])])

    def test_plain_sibling_cannot_authorize_a_product_specific_minimum(self):
        header = 'Скидка 19% на первый заказ.'
        rule = ('Скидка 17% на первый заказ от 1500 рублей. '
                'Скидка 19% на первый заказ от 3000 рублей только на обувь.')
        _, linked = self.published_minima(header, rule, 'conditions')
        self.assertCountEqual(linked, [('/benefit', 'discount', '19', 'first', []),
                                      ('/conditions', 'discount', '17', 'first', ['1500']),
                                      ('/conditions', 'discount', '19', 'first', ['3000'])])

    def test_source_owned_ordered_rules_remain_a_full_container(self):
        from hse_alumni import parse_catalog
        from test_hse_alumni import card, page, section
        body = ('<p>Скидка 10% на повторные заказы и 20% на первый заказ.</p>'
                '<p>Как воспользоваться скидкой 10%?</p><p>Сделайте заказ от 3000 ₽</p>'
                '<p>Получите скидку 10% (но не более 350 ₽)</p>'
                '<p>Как воспользоваться скидкой 20% на первый заказ?</p>'
                '<p>Сделайте заказ от 900 ₽</p><p>Получите скидку 20%</p>')
        source, = parse_catalog(page(card('owned-money'), section('owned-money', body)), NOW)
        result = project(source)
        rules, = [c for c in result['conditions'] if c['kind'] == 'owned_partner_rules']
        self.assertEqual([c for c in result['conditions']
                          if c['kind'] in ('minimum_purchase', 'benefit_cap')], [])
        self.assertEqual(rules['evidence']['text'], source['conditions_text'])
        self.assertTrue(result['benefits'])
        self.assertTrue(all(rules['id'] in b['condition_ids'] for b in result['benefits']))
        self.assertTrue(all(b['condition_linkage'] == 'full_owned_record_rules' for b in result['benefits']))

    def test_source_owned_monthly_aggregate_is_not_a_per_order_cap(self):
        from public_reward_projection import make_record
        from test_catalogue_expansion import x5
        evidence = x5()
        evidence['conditions'] = 'Общая сумма покупок в течение месяца — не более 30 000 руб.'
        source = make_record('x5_partners_public', evidence, NOW)
        result = project(source)
        rules, = [c for c in result['conditions'] if c['kind'] == 'owned_programme_rules']
        self.assertEqual([c for c in result['conditions']
                          if c['kind'] in ('minimum_purchase', 'benefit_cap', 'maximum_amount_reference')], [])
        self.assertEqual(rules['evidence']['text'], source['conditions_text'])
        self.assertTrue(all(rules['id'] in b['condition_ids'] for b in result['benefits']))

    def test_source_publication_common_reader_preserve_purchase_conditions(self):
        text = 'Скидка 20% на первый заказ от 5000 ₽, скидка 10% на повторный заказ от 2000 ₽.'
        source = make_offer('moskvich', 'purchase-owner-fixture', 'Карта', 'Example', text,
                            'https://moskvichmag.ru/programma-loyalnosti/', NOW)
        common = project(source)
        self.assertCountEqual(self.linked(common, 'minimum_purchase'),
                              [('20', 'first', ['5000']), ('10', 'repeat', ['2000'])])
        reader, reason = record_row(common, NOW[:10])
        self.assertIsNone(reason)
        self.assertIn(text, reader[2])
        self.assertEqual(common['raw']['id'], source['id'])
        self.assertEqual(common['provenance']['observed_at'], NOW)


if __name__ == '__main__':
    unittest.main()
