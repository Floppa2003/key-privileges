"""Published VTB sections preserve the ownership of separate summary claims."""
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from normalized import validate_offer
from recovered_sources import parse_bank_page
from sheets_normalized import prepare
from unified_inputs import HEADERS, inputs_from_tables
from unified_normalization import INPUT_TABS, normalize_inputs, validate_normalized

NOW = '2026-11-06T02:53:08.952947+00:00'
MERCHANTS = 'Кешбэк в ресторанах: White Rabbit Family, Novikov Group'
FEE = '2 990 ₽\nЕжегодная комиссия за предоставление в пользование'
CASES = (('current_source', '3', '90', '7'), ('different_numbers', '4', '70', '8'))


def section(body):
    return '<section class="xNativeSection">' + body + '</section>'


def card(value, label):
    return f'<div><p>{value}</p><p>{label}</p></div>'


def page(*, miles='3', basis='90', cashback='7', hero_miles=None,
         hero_basis=None, hero_product='Привилегия Аэрофлот',
         split_cashback=False, duplicate_alias=False, duplicate_section=False,
         extra_sections=''):
    """Minimal valid HTML; no unobserved native card class is assumed."""
    alias = card(
        f'{hero_miles if hero_miles is not None else miles} мили',
        'За каждые потраченные '
        f'{hero_basis if hero_basis is not None else basis} ₽ по карте {hero_product}',
    )
    hero = card('До 6% на WB', 'Скидка с картой ВТБ') + alias
    if duplicate_alias:
        hero += alias
    fee = card('2 990 ₽', 'Ежегодная комиссия за предоставление в пользование')
    hero += (fee + f'<p>{cashback}%</p>' if split_cashback
             else card(f'{cashback}%', MERCHANTS) + fee)
    return (
        section('<h1>Дебетовая карта Привилегия Аэрофлот</h1>')
        + section(hero)
        + (section(hero) if duplicate_section else '')
        + (section(f'<p>{MERCHANTS}</p>') if split_cashback else '')
        + section('<p>Получите до 6% скидки на WB</p>'
                  '<p>Оформите премиальную дебетовую карту ВТБ-Аэрофлот прямо сейчас</p>')
        + section('<h2>Как начисляются мили по карте ВТБ</h2>'
                  f'<p>За каждые {basis} ₽</p>'
                  f'<p>От трат по карте вы получите {miles} мили '
                  'вместо стандартного кешбэка в рублях</p>')
        + extra_sections
    )


class RecoveredVtbSummaryProjectionTests(unittest.TestCase):
    def project(self, html, *, published_changes=None):
        row = json.loads(json.dumps(parse_bank_page('af_vtb_rules', html, NOW),
                                    ensure_ascii=False))
        validate_offer(row)
        source_before = copy.deepcopy(row)
        report = {
            'source_id': 'af_vtb_rules', 'name': 'VTB rules', 'root': row['source_url'],
            'status': 'ok', 'discovered': 1, 'normalized': 1, 'failed': 0,
            'errors': [], 'region': None, 'coverage': 'owned VTB bank rules',
            'observed_at': NOW,
        }
        bundle = {
            'schema_version': 2, 'run_id': 'test:vtb-summary', 'observed_at': NOW,
            'records': [row], 'sources': [report],
        }
        cells = prepare(json.loads(json.dumps(bundle)))['parser_offers'][0] + ['']
        for name, value in (published_changes or {}).items():
            cells[HEADERS['parser_offers'].index(name)] = value
        tables = {
            tab: [[] for _ in range(header - 1)] + [[{'value': h} for h in HEADERS[tab]]]
            for tab, (header, _) in INPUT_TABS.items()
        }
        tables['parser_offers'].append([{'value': value} for value in cells])
        inputs, _ = inputs_from_tables(tables)
        before = copy.deepcopy(inputs)
        result = normalize_inputs(inputs, as_of='2026-11-06')['records'][0]
        validate_normalized(result)
        self.assertEqual(inputs, before)
        self.assertEqual(result['raw'], before[0])
        self.assertEqual(row, source_before)
        self.assertEqual(result['provenance']['observed_at'], NOW)
        self.assertEqual(result['provenance']['source_id'], 'af_vtb_rules')
        self.assertEqual(result['raw']['original']['fields']['SHA256']['value'],
                         row['content_sha256'])
        self.assertEqual(row['details']['page_sha256'],
                         hashlib.sha256(html.encode('utf-8')).hexdigest())
        self.assertEqual({key: result['raw']['details'][key] for key in row['details']},
                         row['details'])
        self.assertEqual(result['raw']['details']['tables'], row['tables'])
        return row, result

    def benefits(self, result, kind):
        return [item for item in result['benefits'] if item['kind'] == kind]

    def assert_miles(self, result, expected):
        self.assertCountEqual(
            [(item['value'], item['unit'], item['basis_value'], item['basis_unit'])
             for item in self.benefits(result, 'earn_miles')], expected,
        )

    def test_summary_does_not_create_unbased_duplicate_miles(self):
        for name, miles, basis, cashback in CASES:
            with self.subTest(case=name):
                _, result = self.project(page(miles=miles, basis=basis, cashback=cashback))
                self.assert_miles(result, [(miles, 'miles', basis, 'RUB')])
                reward = self.benefits(result, 'earn_miles')[0]
                self.assertEqual(reward['evidence']['path'], '/details/earning_rules/0')
                self.assertEqual(json.loads(reward['evidence']['text'])['evidence'],
                                 f'За каждые {basis} ₽\nОт трат по карте вы получите {miles} мили')

    def test_restaurant_percent_is_bound_to_its_literal_label(self):
        for name, miles, basis, cashback in CASES:
            with self.subTest(case=name):
                row, result = self.project(page(miles=miles, basis=basis, cashback=cashback))
                rewards = self.benefits(result, 'cashback')
                self.assertEqual(len(rewards), 1)
                reward = rewards[0]
                self.assertEqual((reward['value'], reward['unit'], reward['qualifier']),
                                 (cashback, 'percent', 'exact'))
                self.assertEqual(reward['evidence']['path'], '/details/sections/1')
                self.assertEqual(reward['evidence']['text'], f'{cashback}%\n{MERCHANTS}')
                self.assertIn(reward['evidence']['text'], row['conditions_text'])
                self.assertEqual(reward['scope']['merchant_scope_text'], MERCHANTS)
                self.assertEqual(reward['scope']['card_product'], 'Привилегия Аэрофлот')

    def test_source_text_hashes_wb_and_fees_survive_projection(self):
        for name, miles, basis, cashback in CASES:
            with self.subTest(case=name):
                row, result = self.project(page(miles=miles, basis=basis, cashback=cashback))
                self.assertEqual(result['raw']['benefit'], row['benefit_text'])
                self.assertEqual(result['raw']['conditions'], row['conditions_text'])
                self.assertEqual(row['benefit_text'], '\n'.join(row['details']['sections']))
                self.assertEqual(row['conditions_text'], '\n'.join(row['details']['sections']))
                self.assertEqual(result['raw']['activation'], '')
                self.assertEqual(
                    [(item['value'], item['unit'], item['qualifier'])
                     for item in self.benefits(result, 'discount')],
                    [('6', 'percent', 'up_to')],
                )
                self.assertIn(FEE, row['details']['fees'][0])
                fee = [item for item in result['costs']
                       if item['evidence']['path'] == '/details/fees']
                self.assertEqual(len(fee), 1)
                self.assertEqual(json.loads(fee[0]['evidence']['text']), row['details']['fees'])
                self.assertNotIn('2990', [item['value'] for item in result['benefits']])

    def test_independent_bare_miles_in_another_section_remain(self):
        for placement in ('before', 'after'):
            with self.subTest(placement=placement):
                independent = section('<p>Другой бонус за отдельное действие</p><p>3 мили</p>')
                html = page(extra_sections=independent) if placement == 'after' else independent + page()
                _, result = self.project(html)
                self.assert_miles(result, [('3', 'miles', '90', 'RUB'),
                                          ('3', 'miles', None, None)])
                candidate = [item for item in self.benefits(result, 'earn_miles')
                             if item['basis_value'] is None]
                self.assertEqual(candidate[0]['evidence']['text'], '3 мили')
                self.assertEqual(len(self.benefits(result, 'cashback')), 1)

    def test_mismatched_summary_does_not_claim_canonical_ownership(self):
        for name, changes, unbased in (
            ('value', {'hero_miles': '4'}, '4'),
            ('basis', {'hero_basis': '100'}, '3'),
            ('card', {'hero_product': 'Карта путешествий'}, '3'),
        ):
            with self.subTest(case=name):
                _, result = self.project(page(**changes))
                self.assert_miles(result, [('3', 'miles', '90', 'RUB'),
                                          (unbased, 'miles', None, None)])
                self.assertEqual(self.benefits(result, 'cashback'), [])

    def test_ambiguous_or_cross_section_summaries_keep_prior_interpretation(self):
        for name, changes in (
            ('percent_and_label_in_different_sections', {'split_cashback': True}),
            ('repeated_mileage_quote', {'duplicate_alias': True}),
            ('repeated_summary_section', {'duplicate_section': True}),
        ):
            with self.subTest(case=name):
                row, result = self.project(page(**changes))
                if changes.get('split_cashback'):
                    fragment = f'7%\n{MERCHANTS}'
                    self.assertIn(fragment, row['conditions_text'])
                    self.assertFalse(any(fragment in block for block in row['details']['sections']))
                self.assert_miles(result, [('3', 'miles', '90', 'RUB'),
                                          ('3', 'miles', None, None)])
                self.assertEqual(self.benefits(result, 'cashback'), [])

    def test_edited_published_conditions_cannot_borrow_the_saved_sections(self):
        _, result = self.project(page(), published_changes={'Условия': 'Изменённые условия карты'})
        self.assert_miles(result, [('3', 'miles', '90', 'RUB'),
                                  ('3', 'miles', None, None)])
        self.assertEqual(self.benefits(result, 'cashback'), [])
        self.assertEqual(result['raw']['conditions'], 'Изменённые условия карты')


if __name__ == '__main__':
    unittest.main()
