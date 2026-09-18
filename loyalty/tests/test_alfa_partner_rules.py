"""Boundaries for reviewed public Alfa Only partner-promotion PDFs."""
import asyncio,copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import alfa_partner_rules as a
import collect_normalized as c
from normalized import content_hash,validate_offer
from source_selection import select_sources

NOW='2026-09-19T00:00:00+00:00'

def fixture(*,start='01 января 2026',end='31 декабря 2026',legal='ООО «ЛИНДЕН»',
            ogrn='1207800041833',city='г. Санкт-Петербург',scope='всех',
            address='г.Санкт-Петербург, 9-я Советская ул., 1',first=False):
    action='Кэшбэк до 10% за первую покупку Alfa Only' if first else 'Кэшбэк до 10% за покупки Alfa Only'
    return f"""
    ПРАВИЛА проведения Акции «{action}».
    Акция Партнера – Акция «{action}» для физических лиц, являющихся Клиентами Банка,
    проводимая Партнером в период с «{start.split()[0]}» {start.split()[1]} {start.split()[2]}г. –
    «{end.split()[0]}» {end.split()[1]} {end.split()[2]}г. включительно.
    Партнер – {legal}, ОГРН {ogrn}.
    Участник Акции – Клиент, обслуживающийся в рамках Пакета услуг «Alfa Only»,
    который присоединился к участию в Акции Партнера.
    2.2. Акция Партнера проводится на территории РФ, а именно в {city}.
    3.2. Участники получают Альфа-Баллы/ Бонусные Мили по ставке 10 %, но не более
    1 500 Альфа-Баллов/ Бонусных Миль от суммы {scope} Расходных операций,
    совершенных в ТСП в течение календарного месяца.
    Альфа-Баллы/ Бонусные Мили не суммируются с Альфа-Баллами/ Бонусными Мили,
    начисленными в рамках иных Акций Партнера. Участнику начисляются Альфа-Баллы/
    Бонусные Мили на условиях проводимых Акций Партнера с наибольшим значением.
    Начисление предусмотренных Акцией Партнера Альфа-Баллов производится Банком
    в течение 10 дней с даты окончания календарного месяца.
    Список ТСП Партнера: № 1 {address}
    """

class Response:
    status_code=200
    headers={}
    def __init__(self,data=b'%PDF-fixture'):self.data=data
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def iter_content(self,n):yield self.data

class AlfaPartnerPdfTests(unittest.TestCase):
    def test_registered_once_and_exact_root(self):
        cfg=json.loads(Path(__file__).resolve().parents[1].joinpath('sources_normalized.json').read_text())
        selected=select_sources(cfg,a.SOURCE_ID)
        self.assertEqual(len(selected),1)
        self.assertEqual(selected[0]['url'],'https://alfabank.servicecdn.ru/')
        self.assertEqual(len({x['id'] for x in cfg}),len(cfg))

    def test_fetch_allowlist_and_no_redirect(self):
        calls=[]
        def get(url,**kw):calls.append((url,kw));return Response()
        self.assertTrue(a.fetch_pdf(a.DOCS[0]['url'],get=get).startswith(b'%PDF-'))
        self.assertFalse(calls[0][1]['allow_redirects'])
        with self.assertRaises(ValueError):a.fetch_pdf(a.DOCS[0]['url']+'?x=1',get=get)

    def test_betulla_exact_rate_cap_dates_and_scope(self):
        spec=a.DOCS[0]
        with patch.object(a,'pdf_text',return_value=fixture()):
            row=a.parse_document(spec,b'%PDF-betulla',NOW)
        validate_offer(row)
        self.assertEqual(row['partner_name'],'Betulla')
        self.assertEqual(row['valid_from'],'2026-01-01')
        self.assertEqual(row['valid_until'],'2026-12-31')
        self.assertEqual(row['rates'][0]['value'],'10')
        self.assertEqual(row['rates'][0]['qualifier'],'exact')
        self.assertEqual(row['details']['transaction_scope'],'all_transactions_in_calendar_month')
        self.assertIn('1 500',row['benefit_text'])
        self.assertEqual(row['validity_status'],'within_published_period')

    def test_r14_first_transaction_each_month(self):
        spec=a.DOCS[1]
        raw=fixture(end='31 октября 2026',legal='ООО «ЗЕН»',ogrn=spec['ogrn'],
                    address='Санкт-Петербург, Ул. Академика Павлова, 5В',scope='первой',first=True)
        with patch.object(a,'pdf_text',return_value=raw):
            row=a.parse_document(spec,b'%PDF-r14',NOW)
        self.assertEqual(row['partner_name'],'Р14')
        self.assertEqual(row['details']['transaction_scope'],'first_transaction_each_calendar_month')
        self.assertEqual(row['valid_until'],'2026-10-31')

    def test_fresa_current_first_transaction_and_multi_tsp_appendix(self):
        spec=a.BY_ID['fresa_0226']
        raw=fixture(start='01 февраля 2026',end='30 ноября 2026',legal='ООО «СОМ»',
                    ogrn=spec['ogrn'],city='г.Москва, г.Санкт-Петербург, г.Владивосток',
                    address='1 «FRESA» г. Санкт-Петербург, Вознесенский пр, 6; 2 «Saviv Moscow» г. Москва, Петровка, 30/7',
                    scope='первой',first=True)
        with patch.object(a,'pdf_text',return_value=raw):
            row=a.parse_document(spec,b'%PDF-fresa',NOW)
        self.assertEqual(row['valid_until'],'2026-11-30')
        self.assertEqual(row['details']['transaction_scope'],'first_transaction_each_calendar_month')
        self.assertEqual(row['validity_status'],'within_published_period')
        self.assertEqual(row['rates'][0]['value'],'10')

    def test_takhauli_expiry_is_source_derived_not_search_inferred(self):
        spec=a.DOCS[2]
        raw=fixture(start='01 февраля 2026',end='31 августа 2026',legal='ООО «ОЛИВЬЕ»',
                    ogrn=spec['ogrn'],city='г.Москва',address='Ресторан «Такахули» г. Москва, ул. Малая Бронная, 10с1')
        with patch.object(a,'pdf_text',return_value=raw):
            row=a.parse_document(spec,b'%PDF-tkh',NOW)
        self.assertEqual(row['valid_until'],'2026-08-31')
        self.assertEqual(row['validity_status'],'expired_by_published_end')

    def test_legal_or_tsp_mismatch_fails_closed(self):
        spec=a.DOCS[0]
        for raw,reason in [
            (fixture(ogrn='1207800041834'),'alfa_partner_pdf_legal_identity'),
            (fixture(address='somewhere else'),'alfa_partner_pdf_tsp_identity'),
        ]:
            with patch.object(a,'pdf_text',return_value=raw):
                with self.assertRaisesRegex(ValueError,reason):a.parse_document(spec,b'%PDF-x',NOW)

    def test_validator_rejects_auth_equivalence_or_relabel(self):
        spec=a.DOCS[0]
        with patch.object(a,'pdf_text',return_value=fixture()):
            row=a.parse_document(spec,b'%PDF-x',NOW)
        for mutate in (
            lambda r:r['details'].update(authenticated_catalogue_equivalence=True),
            lambda r:r.update(source_status='published'),
            lambda r:r.update(partner_name='Other'),
        ):
            bad=copy.deepcopy(row);mutate(bad);bad['content_sha256']=content_hash(bad)
            with self.assertRaises(ValueError):validate_offer(bad)

    def test_collector_keeps_per_pdf_failures_and_good_rows(self):
        cfg={'id':a.SOURCE_ID,'url':'https://alfabank.servicecdn.ru/'}
        report={'errors':[]}
        texts={
            'betulla_0126':fixture(),
            'r14_0126':fixture(end='31 октября 2026',legal='ООО «ЗЕН»',ogrn='1047855044203',
                              address='Санкт-Петербург, Ул. Академика Павлова, 5В',scope='первой',first=True),
            'fresa_0226':fixture(start='01 февраля 2026',end='30 ноября 2026',legal='ООО «СОМ»',
                                ogrn='1237800072377',city='г.Москва, г.Санкт-Петербург, г.Владивосток',
                                address='1 «FRESA» г. Санкт-Петербург, Вознесенский пр, 6',scope='первой',first=True),
        }
        original_parse=a.parse_document
        async def exercise():
            def fake_fetch(url):return b'%PDF-'+a.BY_URL[url]['native_id'].encode()
            def fake_parse(spec,data,observed):
                if spec['native_id']=='takhauli_0226':raise ValueError('fresh_source_conflict')
                with patch.object(a,'pdf_text',return_value=texts[spec['native_id']]):
                    return original_parse(spec,data,observed)
            with patch.object(a,'fetch_pdf',side_effect=fake_fetch),patch.object(a,'parse_document',side_effect=fake_parse):
                return await a.collect(cfg,report,NOW,20)
        rows=asyncio.run(exercise())
        self.assertEqual(len(rows),3)
        self.assertEqual(report['discovered'],4)
        self.assertEqual(report['errors'][0]['native_id'],'takhauli_0226')

if __name__=='__main__':unittest.main()
