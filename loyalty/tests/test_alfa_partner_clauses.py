"""Do not truncate geography or omit how to join a reviewed public promotion."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import alfa_partner_rules as a
from normalized import validate_offer, content_hash

NOW = '2026-09-19T00:00:00+00:00'


def source_text():
    return '''
    ПРАВИЛА проведения Акции «Кэшбэк до 10% за первую покупку Alfa Only».
    Акция Партнера – Акция «Кэшбэк до 10% за первую покупку Alfa Only», проводимая
    Партнером в период с «01» февраля 2026г. – «30» ноября 2026г. включительно.
    Партнер – ООО «СОМ», ОГРН 1237800072377.
    Участник Акции – Клиент, обслуживающийся в рамках Пакета услуг «Alfa Only»,
    который присоединился к участию в Акции Партнера.
    2.2. Акция Партнера проводится на территории РФ, а именно в г.Москва,
    г.Санкт-Петербург, г. Владивосток.
    2.3. Совершение Клиентом первой Расходной операции с использованием Карты/
    Карты AlfaTravel является согласием на участие в Акции Партнера (акцепт Правил).
    Для Клиентов, не являющихся участниками Программы, это акцепт Правил Программы.
    2.4. Правила размещены на сайте Банка.
    3.1. Для получения Альфа-Баллов/ Бонусных Миль необходимо совершить не менее
    1 (одной) Расходной операции с использованием Карты/ Карты AlfaTravel.
    3.2. Участники получают Альфа-Баллы/ Бонусные Мили по ставке 10 %, но не более
    1 500 Альфа-Баллов/ Бонусных Миль от суммы первой Расходной операции,
    совершенной в ТСП в течение календарного месяца.
    Альфа-Баллы/ Бонусные Мили не суммируются с иными Акциями Партнера;
    применяются условия с наибольшим значением.
    Начисление производится Банком в течение 10 дней с даты окончания календарного месяца.
    Список ТСП Партнера: 1 «FRESA» г. Санкт-Петербург, Вознесенский пр, 6.
    '''


def record(raw=None):
    with patch.object(a, 'pdf_text', return_value=raw or source_text()):
        return a.parse_document(a.BY_ID['fresa_0226'], b'%PDF-synthetic', NOW)


class ClauseTests(unittest.TestCase):
    def test_all_cities_are_kept_not_just_first_comma_delimited_name(self):
        row = record()
        self.assertIn('г.Москва, г.Санкт-Петербург, г. Владивосток.', row['conditions_text'])

    def test_redemption_contains_source_joining_and_payment_clauses(self):
        row = record()
        self.assertIn('2.3. Совершение Клиентом', row['redemption_text'])
        self.assertIn('Карты/ Карты AlfaTravel', row['redemption_text'])
        self.assertIn('3.1. Для получения', row['redemption_text'])
        self.assertNotIn('2.4.', row['redemption_text'])
        self.assertNotIn('3.2.', row['redemption_text'])
        self.assertEqual(row['details']['transaction_scope'], 'first_transaction_each_calendar_month')

    def test_missing_or_duplicate_clause_boundary_is_not_silently_accepted(self):
        for raw in (source_text().replace('2.4.', '2.9.'),
                    source_text().replace('3.1.', '3.9.'),
                    source_text() + ' 2.2. Акция Партнера проводится в другом городе. 2.3. '):
            with self.assertRaisesRegex(ValueError, 'alfa_partner_pdf_clause_'):
                record(raw)

    def test_validator_detects_changed_geography_or_redemption_after_rehash(self):
        row = record()
        for field in ('conditions_text', 'redemption_text'):
            bad = copy.deepcopy(row)
            bad[field] = 'invented source term'
            bad['content_sha256'] = content_hash(bad)
            with self.assertRaises(ValueError):
                validate_offer(bad)

    def test_source_payment_changes_are_preserved_not_canned(self):
        row = record(source_text().replace('не менее\n    1 (одной)', 'не менее 2 (двух)'))
        self.assertIn('2 (двух)', row['redemption_text'])
        self.assertNotIn('1 (одной)', row['redemption_text'])

    def test_practical_clauses_are_visible_conditions_not_only_preserved_raw(self):
        from sheets_normalized import prepare, SCHEMAS
        from unified_normalization import make_input, normalize_record
        row = record()
        report = dict(source_id=a.SOURCE_ID, name='Alfa', root='https://alfabank.servicecdn.ru/',
                      status='ok', discovered=1, normalized=1, failed=0, coverage='fixture',
                      region=None, errors=[], observed_at=NOW)
        bundle = dict(schema_version=2, run_id='fixture:1', observed_at=NOW, records=[row], sources=[report])
        values = prepare(bundle)['parser_offers'][0]
        raw = make_input(dict(id=row['id'], origin='parser_offers', row=2,
            fields={h:{'value':v} for h,v in zip(SCHEMAS['parser_offers'],values)}))
        common = normalize_record(raw, as_of='2026-09-19')
        conditions = {c['kind']:c['evidence']['text'] for c in common['conditions']}
        self.assertEqual(conditions.get('activation'), row['redemption_text'])
        self.assertEqual(conditions.get('limitations'), row['details']['practical_clauses']['territory'])
        self.assertIsNone(common['eligibility_verified'])

if __name__ == '__main__':
    unittest.main()
