"""Known-rule side fields preserve the same literal DOM text as their bodies."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from known_rules import CONFIG, parse_known_rule
from normalized import validate_offer
import test_known_rules as known_fixtures
from test_public_product_rules import sample as gpb_fixture

NOW = '2026-11-06T00:00:00+00:00'


def parse(source, html):
    rows = parse_known_rule(source, html, CONFIG[source]['url'], NOW)
    for row in rows:
        validate_offer(row)
    return rows


class KnownRuleDomLiterals(unittest.TestCase):
    def test_link_labels_preserve_inline_words_and_literal_entities(self):
        html = known_fixtures.RETAIL.replace('</div>', '<a href="https://example.com/rules.pdf">'
                              'SUM<span>MER</span>26 &lt;VIP&gt; &amp;lt;tag&amp;gt;</a></div>')
        row = parse('af_bootwood_rules', html)[0]
        self.assertEqual(row['details']['linked_documents'], [{
            'label': 'SUMMER26 <VIP> &lt;tag&gt;',
            'url': 'https://example.com/rules.pdf', 'fetched': False}])

    def test_gpb_inline_numbers_keep_their_subscription(self):
        html = (gpb_fixture().replace('1,5 мили', '1<b>,</b>5 мили', 1)
                .replace('3 000</p>', '3 <span>000</span></p>')
                .replace('399 ₽', '3<span>99</span> ₽')
                .replace('Без Газпром', 'Без Газ<span>пром</span>'))
        row = parse('af_gpb_rules', html)[0]
        options = row['details']['mileage_options']
        self.assertEqual([(x['miles'], x['monthly_cap_miles'], x['monthly_subscription_rub'])
                          for x in options], [('1.5', '3000', '0'), ('2.5', '5000', '399')])
        self.assertEqual(options[0]['label'], 'Без Газпром Бонус «Плюс»')
        self.assertNotIn('Кешбэк 100%', row['conditions_text'])

    def test_gpb_wrapped_owned_heading_keeps_scope(self):
        html = gpb_fixture().replace('Условия по карте', 'Усло<span>вия</span><br>по карте')
        row = parse('af_gpb_rules', html)[0]
        self.assertEqual(row['details']['fees']['notifications_after_first_month_rub'], '99')
        self.assertIn('Условия\nпо карте', row['conditions_text'])
        self.assertNotIn('Другая акция', row['conditions_text'])

    def test_gpb_duplicate_heading_cannot_replace_a_required_section(self):
        html = gpb_fixture().replace('Условия программы лояльности «Аэрофлот Бонус»',
                                     'Условия по карте')
        with self.assertRaises(ValueError):
            parse('af_gpb_rules', html)

    def test_gpb_parent_wrapper_depth_does_not_expand_scope_to_whole_page(self):
        html = (gpb_fixture().replace('<div><div class="Accordion_root__trigger_title__abc">',
                                     '<div class="Accordion_root__trigger_title__abc">')
                .replace('</div></div><p>', '</div><p>'))
        row = parse('af_gpb_rules', html)[0]
        self.assertNotIn('Кешбэк 100%', row['conditions_text'])
        self.assertNotIn('Другая акция', row['conditions_text'])
        self.assertEqual(row['details']['monthly_minimum_purchases_rub'], '5000')

    def test_gpb_missing_owned_accordion_container_is_rejected(self):
        html = gpb_fixture().replace('class="Accordion_root__abc"', 'class="unowned"')
        with self.assertRaises(ValueError):
            parse('af_gpb_rules', html)

    def test_native_table_cells_are_consistent_with_visible_text(self):
        html = ('<div class="spb-asset-content">Бизнес отель GLORIA. Крылья.</div>'
                '<div class="spb-asset-content">Как получить скидку: покажите карту.</div>'
                '<div class="spb-asset-content"><table><tr><th>Уровень</th><th>Скидка</th></tr>'
                '<tr><td>Gold &lt;VIP&gt; &amp;lt;tag&amp;gt;</td><td>1<span>5</span>%</td></tr>'
                '</table></div>')
        row = parse('ural_gloria_rules', html)[0]
        self.assertEqual(row['tables'], [[['Уровень', 'Скидка'],
                                         ['Gold <VIP> &lt;tag&gt;', '15%']]])
        self.assertIn('15%', row['conditions_text'])

    def test_smartavia_inline_plan_label_keeps_identity_and_traveler_count(self):
        raw = known_fixtures.SmartaviaTests().fixture()
        baseline = parse('smartavia_rules', raw)[0]
        html = raw.replace('Тариф 1+0.', '<div>Тариф</div><div class="sm-title-extra">'
                           '1+<b>0</b></div>')
        row = parse('smartavia_rules', html)[0]
        self.assertEqual(row['id'], baseline['id'])
        self.assertEqual(row['details']['subscription_plan']['label'], '1+0')
        self.assertEqual(row['details']['subscription_plan']['additional_travelers'], 0)

    def test_rgo_heading_allows_a_real_line_break(self):
        html = ('<div class="accordion"><div class="accordion__title-text">'
                'Перечень<br>льготных категорий</div><p>На скидку в 15% имеют право '
                'члены Русского географического общества.</p></div>')
        row = parse('rgo_headquarters_rules', html)[0]
        self.assertIn('Перечень\nльготных категорий', row['conditions_text'])
        self.assertIn('15', {x['value'] for x in row['rates']})


if __name__ == '__main__':
    unittest.main()
