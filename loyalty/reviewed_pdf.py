"""Recognize one visually reviewed image-PDF; changed bytes require a new review.

The document's useful text is rasterized. This is deliberately NOT a generic OCR
or PDF parser. Live bytes must match the reviewed version before fields are used.
"""
import hashlib
from normalized import make_offer

RGO_BEELINE_URL='https://rgo.ru/upload/medialibrary/2ed/jm89ty2fg8j8an3g362l5uq6lij95owe/Moya_Kompaniya_RGO_belaya_20.01.26.pdf'
RGO_BEELINE_SHA256='905bb3b03f3b98709054b14c5ae08974a6f7be775857819cf8cd2cb688be683b'
BENEFIT='''Тарифные планы доступны от 450 р/мес.
Перенос остатков интернета и минут на следующий месяц.
Безлимитные звонки на билайн. Звонки на билайн РФ не расходуют пакет минут.
Безлимит на мессенджеры — не расходуют пакет интернета.
Раздача интернета: получатели рядом с вами — включить мобильную точку доступа, подключай сколько угодно устройств — бесплатно.
Получатели интернета где угодно в РФ — включить опцию «Интернет на все», подключай до 5 устройств — 100 ₽/мес.'''
TERMS='''Предложение только для членов Русского географического общества.
Программа доступна для сотрудников и обладателей членского билета РГО.
Для получения специального предложения свяжитесь с менеджером билайн: Елена Динер, EDiner@beeline.ru.
Подключить новый номер: отправьте запрос менеджеру по email; заполните документ; отправьте ответным письмом заполненное заявление и фото членского билета; заберите SIM-карту в офисе билайна.
Перейти в билайн с сохранением номера (MNP): укажите номер, который нужно перенести, и заполните анкету; выберите временный тарифный план (после переноса номера подключим предложение для членов сообщества); получите новую SIM в офисе билайна или с курьером; на новую SIM через 8 дней будет перенесен ваш номер; отправьте запрос менеджеру по email (номер, тарифный план, членский билет, паспорт и заявление).'''


def make_beeline_offer(observed_at):
    return make_offer('rgo','beeline-reviewed-pdf','Программа лояльности членов РГО','Билайн',BENEFIT,
        RGO_BEELINE_URL,observed_at,conditions=TERMS,redemption=TERMS,
        category='Мобильная связь',locator='PDF page 1; reviewed image fields',
        details={'extraction_method':'digest_bound_visual_review','document_sha256':RGO_BEELINE_SHA256,
          'reviewed_pages':[1],'reviewed_at':'2026-09-12',
          'price_components':[
             {'name':'Тарифный план','value':'450','unit':'RUB','period':'month','qualifier':'at_least','evidence':'Тарифные планы доступны от 450 р/мес'},
             {'name':'Интернет на все','value':'100','unit':'RUB','period':'month','qualifier':'exact','evidence':'подключай до 5 устройств — 100 ₽/мес'}],
          'additional_services_named':['Привет / Привет+','билайн книги','Облако билайн'],
          'additional_services_inclusion':'not_stated',
          'source_document_is_image_based':True},
        warnings=['visual_review_profile_not_generic_ocr','changed_pdf_requires_new_review','filename_date_is_not_offer_validity','eligibility_and_exact_tariff_require_partner_confirmation'])


def extract_rgo_pdf(data: bytes,url: str,observed_at: str):
    if url!=RGO_BEELINE_URL:raise ValueError('not_the_reviewed_url')
    if not data.startswith(b'%PDF-'):raise ValueError('not_a_pdf')
    if hashlib.sha256(data).hexdigest()!=RGO_BEELINE_SHA256:
        raise ValueError('pdf_changed_review_required')
    return [make_beeline_offer(observed_at)]
