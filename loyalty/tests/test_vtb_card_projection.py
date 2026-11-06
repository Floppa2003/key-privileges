"""Stored VTB ownership guards and the independent activation boundary."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from unified_normalization import make_input, normalize_record
from vtb_card_projection import project_stored_card

URL = 'https://www.vtb.ru/privilegia/karty/debetovye/privilegiya-aeroflot/'
ALIAS = '3 мили\nЗа каждые потраченные 90 ₽ по карте Привилегия Аэрофлот'
LABEL = 'Кешбэк в ресторанах: White Rabbit Family, Рестораны Арама Мнацаканова'
DETAIL = 'За каждые 90 ₽\nОт трат по карте вы получите 3 мили'


def stored():
    sections = [
        'Дебетовая карта Привилегия Аэрофлот',
        'До 6% на WB\nСкидка с картой ВТБ\n' + ALIAS + '\n7%\n' + LABEL
        + '\n2 990 ₽\nЕжегодная комиссия за предоставление в пользование',
        'Получите до 6% скидки на WB',
        'Как начисляются мили по карте ВТБ\n' + DETAIL + ' вместо стандартного кешбэка в рублях',
    ]
    details = {
        '_source': {'source_id': 'af_vtb_rules'},
        'evidence_role': 'supplementary_rules_not_incremental_discount',
        'sections': sections, 'earning_conditions': sections[3],
        'earning_rules': [{
            'value': '3', 'unit': 'miles', 'basis_amount': '90',
            'basis_unit': 'RUB', 'qualifier': 'exact', 'evidence': DETAIL,
        }],
    }
    values = {
        'Программа': 'Аэрофлот Бонус', 'Партнёр': 'ВТБ', 'Заголовок': 'VTB fixture',
        'Тип записи': 'program_rules', 'Статус источника': 'public_rules_text',
        'Источник': URL, 'Выгода': '\n'.join(sections), 'Условия': '\n'.join(sections),
        'Детали JSON': json.dumps(details, ensure_ascii=False),
        'Получено UTC': '2026-11-06T02:53:08.952947+00:00', 'SHA256': 'a' * 64,
    }
    return make_input({'id': 'fixture:vtb-card', 'origin': 'parser_offers', 'row': 2,
                       'fields': {key: {'value': value} for key, value in values.items()}})


class VtbCardProjectionTests(unittest.TestCase):
    def test_full_contract_returns_original_owned_fragments_without_mutation(self):
        raw = stored()
        before = copy.deepcopy(raw)
        owned = project_stored_card(raw)
        self.assertIsNotNone(owned)
        self.assertEqual(raw, before)
        self.assertEqual(owned['covered_quotes'], {
            '/benefit': [ALIAS], '/conditions': [ALIAS],
        })
        self.assertEqual(owned['cashback'], {
            'path': '/details/sections/1', 'evidence': '7%\n' + LABEL,
            'value': '7', 'unit': 'percent', 'qualifier': 'exact',
            'scope': {'merchant_scope_text': LABEL, 'card_product': 'Привилегия Аэрофлот'},
        })

    def test_source_identity_status_and_role_are_mandatory(self):
        for field, value in (
            ('origin', 'loyalty_partner_benefits'), ('source_id', 'other_bank'),
            ('source_url', URL + '?other=1'), ('kind', 'partner_offer'),
            ('source_status', 'public_announcement_not_full_rules'),
        ):
            with self.subTest(field=field):
                raw = stored()
                raw[field] = value
                self.assertIsNone(project_stored_card(raw))
        for key, value in (
            ('_source', {}), ('_source', {'source_id': 'other_bank'}),
            ('evidence_role', 'other'), ('pages', [{'number': 1, 'text': ALIAS}]),
        ):
            with self.subTest(detail=key, value=value):
                raw = stored()
                raw['details'][key] = value
                self.assertIsNone(project_stored_card(raw))

    def test_each_display_field_must_match_all_original_sections(self):
        for field in ('benefit', 'conditions'):
            with self.subTest(field=field):
                raw = stored()
                raw[field] += '\nСкидка 20% для другой карты'
                self.assertIsNone(project_stored_card(raw))
        for sections in (None, [], ['valid', None], 'not-a-section-list'):
            with self.subTest(sections=sections):
                raw = stored()
                raw['details']['sections'] = sections
                self.assertIsNone(project_stored_card(raw))

    def test_canonical_rule_is_rederived_and_must_match_in_full(self):
        for field, value in (
            ('value', '4'), ('basis_amount', '70'), ('unit', 'points'),
            ('basis_unit', 'USD'), ('qualifier', 'up_to'), ('evidence', DETAIL + '.'),
        ):
            with self.subTest(field=field):
                raw = stored()
                raw['details']['earning_rules'][0][field] = value
                self.assertIsNone(project_stored_card(raw))
        raw = stored()
        raw['details']['earning_rules'].append(copy.deepcopy(raw['details']['earning_rules'][0]))
        self.assertIsNone(project_stored_card(raw))
        raw = stored()
        raw['details']['earning_conditions'] += '\nextra'
        self.assertIsNone(project_stored_card(raw))

    def test_duplicate_canonical_section_and_related_card_leave_prior_projection(self):
        for extra in ('canonical', 'Прайм Аэрофлот'):
            with self.subTest(extra=extra):
                raw = stored()
                sections = raw['details']['sections']
                sections.append(sections[3] if extra == 'canonical' else extra)
                raw['benefit'] = raw['conditions'] = '\n'.join(sections)
                self.assertIsNone(project_stored_card(raw))

    def test_missing_or_oversized_canonical_basis_leaves_prior_projection(self):
        for label, basis in (('missing', '   '), ('oversized', '9' * 5000)):
            with self.subTest(case=label):
                raw = stored()
                sections = raw['details']['sections']
                sections[3] = sections[3].replace('За каждые 90 ₽', 'За каждые ' + basis + ' ₽')
                raw['details']['earning_conditions'] = sections[3]
                raw['benefit'] = raw['conditions'] = '\n'.join(sections)
                self.assertIsNone(project_stored_card(raw))

    def test_empty_or_out_of_range_cashback_label_does_not_enable_masking(self):
        for replacement in ('101%\n' + LABEL, '7%\nКешбэк в ресторанах: ', '7%\nКомиссия в ресторанах: A'):
            with self.subTest(replacement=replacement):
                raw = stored()
                sections = raw['details']['sections']
                sections[1] = sections[1].replace('7%\n' + LABEL, replacement)
                raw['benefit'] = raw['conditions'] = '\n'.join(sections)
                self.assertIsNone(project_stored_card(raw))

    def test_identical_activation_quote_remains_an_independent_mileage_claim(self):
        raw = stored()
        raw['activation'] = ALIAS
        before = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-06')
        miles = [item for item in result['benefits'] if item['kind'] == 'earn_miles']
        self.assertEqual(len(miles), 2)
        self.assertEqual(
            [(item['value'], item['basis_value']) for item in miles], [('3', '90'), ('3', None)],
        )
        self.assertEqual(miles[1]['evidence'], {'path': '/activation', 'text': '3 мили'})
        self.assertEqual(raw, before)
        self.assertEqual(result['raw'], before)
        self.assertEqual(result['provenance']['observed_at'], before['observed_at'])

    def test_helper_import_and_projection_need_only_the_standard_library(self):
        code = '''
import builtins, json, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'requests','bs4','playwright','pypdf','normalized','recovered_sources'}:
        raise ImportError('collector dependency forbidden: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
sys.path.insert(0, sys.argv[1])
from vtb_card_projection import project_stored_card
print(json.dumps(project_stored_card(json.load(sys.stdin)), ensure_ascii=False))
'''
        result = subprocess.run([sys.executable, '-I', '-c', code, str(ROOT)],
                                input=json.dumps(stored(), ensure_ascii=False), text=True,
                                capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['cashback']['value'], '7')


if __name__ == '__main__':
    unittest.main()
