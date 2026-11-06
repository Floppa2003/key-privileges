"""Native JSON amounts and decoded HTML survive the real publication path."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters import mir_detail
from fixtures import fixture
from public_reward_projection import make_record
from test_catalogue_expansion import OLD, coupon, x5
from test_dom_card_boundaries import project


class NativePriceBoundariesTests(unittest.TestCase):
    def evidence(self, source, amount):
        if source == 'x5_partners_public':
            evidence = x5()
            evidence['heading'] = evidence['card']['nameOffer'] = 'Скидка 7% на бронирование'
            evidence['card']['cost'] = amount
        else:
            evidence = coupon()
            evidence['data']['price']['new'] = amount
        return evidence

    def test_exact_amount_reaches_common_conditions_without_rounding(self):
        cases = [(12345.67, '12345.67'), (1000005, '1000005'),
                 (9007199254740993, '9007199254740993'),
                 (0.0000001, '0.0000001'), (200.0, '200')]
        for source in ('x5_partners_public', 'gorod_public'):
            for amount, literal in cases:
                with self.subTest(source=source, amount=amount):
                    evidence = self.evidence(source, amount)
                    before = copy.deepcopy(evidence)
                    row = make_record(source, evidence, OLD)
                    common = project(row)
                    expected = ('Получение: ' + literal + ' баллов X5 Клуба.'
                                if source == 'x5_partners_public' else
                                'Цена купона: ' + literal + '; допустимые средства оплаты: жетоны «Город».')
                    self.assertEqual(row['conditions_text'].splitlines()[0], expected)
                    self.assertEqual(common['raw']['conditions'].splitlines()[0], expected)
                    self.assertEqual(evidence, before)
                    self.assertEqual(common['raw']['details']['public_reward_evidence'], before)

    def test_nonfinite_costs_fail_instead_of_becoming_published_text(self):
        for source in ('x5_partners_public', 'gorod_public'):
            for amount in (float('inf'), float('-inf'), float('nan')):
                with self.subTest(source=source, amount=amount):
                    with self.assertRaises(ValueError):
                        make_record(source, self.evidence(source, amount), OLD)

    def test_bool_string_and_negative_costs_still_fail(self):
        for source in ('x5_partners_public', 'gorod_public'):
            for amount in (True, False, '200', None, -1, -0.01):
                with self.subTest(source=source, amount=amount):
                    with self.assertRaises(ValueError):
                        make_record(source, self.evidence(source, amount), OLD)

    def test_zero_keeps_each_sources_existing_cost_semantics(self):
        for amount in (0, 0.0):
            with self.subTest(amount=amount):
                x5_common = project(make_record('x5_partners_public', self.evidence('x5_partners_public', amount), OLD))
                gorod_common = project(make_record('gorod_public', self.evidence('gorod_public', amount), OLD))
                self.assertEqual(x5_common['raw']['conditions'].splitlines()[0], 'Получение: 0 баллов X5 Клуба.')
                self.assertEqual(gorod_common['raw']['conditions'].splitlines()[0], 'Получение купона бесплатно.')

    def test_unknown_quest_cost_is_not_replaced_with_zero(self):
        evidence = self.evidence('x5_partners_public', None)
        evidence['card']['type'] = 'quest'
        common = project(make_record('x5_partners_public', evidence, OLD))
        self.assertIn('Цена получения в баллах X5 не указана.', common['raw']['conditions'])
        self.assertNotIn('Получение: 0', common['raw']['conditions'])

    def test_exchange_still_rejects_nonfinite_cost_without_claiming_a_rate(self):
        evidence = self.evidence('x5_partners_public', float('inf'))
        evidence['card']['type'] = 'exchange'
        with self.assertRaises(ValueError):
            make_record('x5_partners_public', evidence, OLD)


class MirJsonHtmlBoundariesTests(unittest.TestCase):
    def test_each_json_html_field_is_decoded_once_before_common_projection(self):
        source = json.loads(fixture('mir_detail.json'))
        promo = source['data']['content']['promoDetail']['promo']['promoAction']
        promo['desc'] = {
            'number': {'PREFIX': '<b>Кешбэк</b>', 'AMOUNT': '<strong>5</strong>%'},
            'text': '<p>Для тарифа &lt;VIP&gt;. Метка &amp;copy;. Промокод SOURCE15.</p>',
        }
        before = copy.deepcopy(source)
        row = mir_detail(source, 'https://vamprivet.ru' + promo['url'], OLD)[0]
        common = project(row)
        expected = 'Кешбэк 5% Для тарифа <VIP>. Метка &copy;. Промокод SOURCE15.'
        self.assertEqual(row['benefit_text'], expected)
        self.assertEqual(common['raw']['benefit'], expected)
        self.assertEqual([(rate['kind'], rate['value']) for rate in row['rates']], [('cashback', '5')])
        self.assertEqual(row['promo_codes'], ['SOURCE15'])
        self.assertEqual(row['conditions_text'], 'Условия\nМаксимальный кешбэк 1 500 ₽ в месяц.')
        self.assertNotIn('SYNTHETIC_CANARY', json.dumps(row))
        self.assertEqual(source, before)


if __name__ == '__main__':
    unittest.main()
