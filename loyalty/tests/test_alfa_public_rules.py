"""Public Alfa Only PDF rules: evidence boundaries and dispatcher coverage."""
import asyncio,copy,hashlib,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import alfa_public_rules as a
import collect_normalized as c
from normalized import content_hash,validate_offer
from source_selection import select_sources

NOW='2026-09-18T00:00:00+00:00'


CORE_TEXT = """
Правила программы лояльности
Редакция № 47
Версия № 47 Правил введена в действие с 01.05.2026
Выплата – денежные средства, возвращаемые Участнику за такси, трансфер и каршеринг, но не более 2 500 рублей.
6.1.1. Участник оформляет заявку на Выплату. Операция становится доступной для получения Выплаты в течение 2 рабочих дней. Выплата относится к лимитам Поощрения того месяца, в котором была оформлена заявка.
6.6.3. Выплата БЗ осуществляется в размере фактических расходов, но не более 2 500 рублей за доступ одного лица.
6.6.7. Максимальная сумма Выплаты БЗ составляет 20 000 рублей на одного Участника за один календарный месяц.
Выплата за посещение ресторанов/ кафе/ баров в аэропортах РФ предоставляется в размере фактических расходов, но не более 2 500 рублей при списании 1 Альфа-Балла и не более 5 000 рублей при списании 2 Альфа-Баллов.
6.7.7. Максимальная сумма Выплаты РКБ составляет 20 000 рублей на одного Участника за один календарный месяц.
6.8.2. Для доступа необходимо указать количество лиц, сопровождающих Участника (не более 3 лиц), и нажать на кнопку «Выпустить QR-код».
6.8.3. QR-код может быть возвращен в течение 24 часов после выпуска. Кнопка «Вернуть» доступна в течение 24 часов.
Промо-баллы могут быть использованы на получение Услуги по предоставлению доступа к Подписке на РБК участниками с суммой от 6 000 000 рублей.
6.5.1. В мобильном приложении выбрать раздел «Alfa Only», «Стиль жизни», РБК и авторизоваться через Alfa ID.
"""

CASHBACK_TEXT = """
Правила программы лояльности
Редакция № 101
Редакция № 101 Правил введена в действие с 25.05.2026
УЛК (с оформлением ПУ «Alfa Only») — 5 Категорий. Максимальная сумма 30 000 Альфа-Баллов; по сервисам Банка 50 000 Альфа-Баллов; максимальная сумма одной Операции 500 000 рублей.
"""


class Response:
    status_code=200
    headers={}
    def __init__(self,data=b"%PDF- synthetic"): self.data=data
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def iter_content(self,n): yield self.data


class AlfaPublicRulesTests(unittest.TestCase):
    def test_exact_urls_registered_and_selectable(self):
        config=json.loads(Path(__file__).resolve().parents[1].joinpath("sources_normalized.json").read_text())
        selected=select_sources(config,"alfa_only_public_rules,alfa_only_cashback_rules")
        self.assertEqual([x["url"] for x in selected],[a.CORE_URL,a.CASHBACK_URL])
        self.assertEqual(len({x["id"] for x in config}),len(config))

    def test_fetch_is_exact_allowlist_bounded_no_redirect(self):
        calls=[]
        def get(url,**kwargs):
            calls.append((url,kwargs));return Response()
        self.assertTrue(a.fetch_pdf(a.CORE_URL,get=get).startswith(b"%PDF-"))
        self.assertEqual(calls[0][0],a.CORE_URL)
        self.assertFalse(calls[0][1]["allow_redirects"])
        with self.assertRaises(ValueError):a.fetch_pdf(a.CORE_URL+"?tracking=1",get=get)

    def test_core_parser_emits_five_practical_records(self):
        with patch.object(a,"pdf_text",return_value=CORE_TEXT):
            rows=a.parse_core(b"%PDF-core",NOW)
        self.assertEqual(len(rows),5)
        self.assertEqual([r["native_id"] for r in rows],[
            "core47:taxi-transfer-carsharing","core47:lounge-reimbursement",
            "core47:airport-restaurants","core47:qr-lounges","core47:rbc"])
        for r in rows:
            validate_offer(r)
            self.assertEqual(r["source_status"],"public_rules_document")
            self.assertEqual(r["record_kind"],"tier_benefit")
            self.assertIsNone(r["benefit_url"])
            self.assertFalse(r["details"]["authenticated_catalogue_equivalence"])
            self.assertEqual(r["details"]["document_revision"],47)
        restaurants=rows[2]
        self.assertIn("2 500",restaurants["benefit_text"])
        self.assertIn("5 000",restaurants["benefit_text"])
        self.assertIn("20 000",restaurants["conditions_text"])

    def test_cashback_parser_is_limits_not_personal_rates(self):
        with patch.object(a,"pdf_text",return_value=CASHBACK_TEXT):
            row,=a.parse_cashback(b"%PDF-cashback",NOW)
        validate_offer(row)
        self.assertEqual(row["details"]["document_revision"],101)
        self.assertIn("5 Категорий",row["benefit_text"])
        self.assertIn("30 000",row["benefit_text"])
        self.assertIn("50 000",row["benefit_text"])
        self.assertIn("500 000",row["benefit_text"])
        self.assertIn("не персональные ставки",row["conditions_text"])

    def test_revision_or_effective_date_drift_fails_closed(self):
        with patch.object(a,"pdf_text",return_value=CORE_TEXT.replace("Редакция № 47","Редакция № 48",1)):
            with self.assertRaisesRegex(ValueError,"alfa_core_revision_missing"):a.parse_core(b"%PDF-core",NOW)
        with patch.object(a,"pdf_text",return_value=CASHBACK_TEXT.replace("25.05.2026","26.05.2026")):
            with self.assertRaisesRegex(ValueError,"alfa_cashback_effective_date_missing"):a.parse_cashback(b"%PDF-cashback",NOW)

    def test_validator_rejects_relabel_or_authenticated_equivalence(self):
        with patch.object(a,"pdf_text",return_value=CORE_TEXT):
            row=a.parse_core(b"%PDF-core",NOW)[0]
        for mutate in (
            lambda r:r.update(source_status="published"),
            lambda r:r["details"].update(authenticated_catalogue_equivalence=True),
            lambda r:r.update(source_url=a.CASHBACK_URL),
        ):
            bad=copy.deepcopy(row);mutate(bad);bad["content_sha256"]=content_hash(bad)
            with self.assertRaises(ValueError):validate_offer(bad)

    def test_dispatcher_collects_public_rules_without_browser(self):
        async def exercise():
            cfg={"id":"alfa_only_public_rules","name":"Alfa public","mode":"probe","url":a.CORE_URL,"timeout_seconds":60}
            with patch.object(a,"fetch_pdf",return_value=b"%PDF-core"),patch.object(a,"pdf_text",return_value=CORE_TEXT),patch.object(c,"PublicSource") as ps:
                report,rows=await c.one(None,cfg,NOW,500)
                ps.assert_not_called()
            self.assertEqual(report["status"],"ok")
            self.assertEqual(report["discovered"],5)
            self.assertEqual(len(rows),5)
        asyncio.run(exercise())

    def test_authenticated_catalogue_probe_remains_separate_zero_source(self):
        config=json.loads(Path(__file__).resolve().parents[1].joinpath("sources_normalized.json").read_text())
        ids={x["id"] for x in config}
        self.assertTrue({"alfa_only_partner_offers","alfa_only_public_rules","alfa_only_cashback_rules"}<=ids)


if __name__=="__main__":unittest.main()
