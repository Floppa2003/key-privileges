"""Two reviewed text-PDF rules. Full page text stays authoritative over fields.

No OCR, JavaScript execution, annotations, attachments or external PDF links.
Unsupported/empty/oversized documents fail rather than becoming valid offers.
"""
from __future__ import annotations
import hashlib
import io
import re
from datetime import datetime
from normalized import make_offer,number
from read_budget import within_source_budget

PDF_RULES={
 'rzd_finuslugi_rules':{
  'url':'https://assets.finuslugi.ru/sc-disclosure/293d2bf4-16c4-46c6-87a5-0a2d35d18ad8',
  'program':'РЖД Бонус','partner':'Финуслуги','title':'Правила начисления баллов за первый вклад',
  'required':['Финуслугах','РЖД Бонус','7.1.10.','Заключительные положения']},
 'af_primbank_rules':{
  'url':'https://www.primbank.ru/d/tariffs-aeroflot-bonus',
  'program':'Аэрофлот Бонус','partner':'Банк Приморье','title':'Тариф карты: начисление миль и ограничения',
  'required':['Аэрофлот Бонус','Мир Продвинутая','ОБЩИЕ УСЛОВИЯ','Приветственные мили']},
}


def compact(value):
    return re.sub(r'\s+',' ',value).strip()


def require(pattern,value):
    found=re.search(pattern,compact(value),re.I)
    if not found:raise ValueError('pdf_rule_shape_changed:'+pattern[:60])
    return found


def pdf_pages(data: bytes) -> list[str]:
    if not isinstance(data,bytes) or not data.startswith(b'%PDF-') or not 100<=len(data)<=3000000:
        raise ValueError('invalid_or_oversized_pdf')
    # Imported only in collection, never needed by the Google publisher.
    from pypdf import PdfReader
    reader=PdfReader(io.BytesIO(data),strict=True)
    if reader.is_encrypted or not 1<=len(reader.pages)<=80:
        raise ValueError('pdf_encrypted_or_page_limit')
    pages=[]
    for page_number,page in enumerate(reader.pages,1):
        stream=page.get_contents()
        if stream is None or len(stream.get_data())>4000000:
            raise ValueError('pdf_content_stream_empty_or_oversized')
        value=page.extract_text()
        if not value or not value.strip():
            raise ValueError('pdf_missing_text_layer_review_required')
        pages.append(value)
    if sum(map(len,pages))>35000:
        raise ValueError('pdf_text_too_large_no_truncation')
    return pages


def parse_pdf_pages(source: str,pages: list[str],observed_at: str,*,document_sha256: str) -> dict:
    cfg=PDF_RULES[source]
    if not 1<=len(pages)<=80 or not re.fullmatch('[0-9a-f]{64}',document_sha256):
        raise ValueError('invalid_pdf_pages_or_digest')
    full='\n\n'.join(f'[Страница {i}]\n{p.strip()}' for i,p in enumerate(pages,1))
    all_text=compact(full)
    if any(s.casefold() not in all_text.casefold() for s in cfg['required']):
        raise ValueError('pdf_identity_or_rules_not_found')
    details={'evidence_role':'supplementary_rules_not_incremental_discount',
             'extraction_method':'native_pdf_text_with_reviewed_clause_parser',
             'document_sha256':document_sha256,'page_count':len(pages),
             'page_text_sha256':[hashlib.sha256(p.encode()).hexdigest() for p in pages],
             'scope':'full_document_text_and_named_clauses','all_named_documents_fetched':False}
    warnings=['rule_bundle_not_additive_discount','user_eligibility_not_verified',
              'named_external_rules_not_fetched','pdf_layout_change_may_require_review']
    start=end=None
    if source=='rzd_finuslugi_rules':
        section=all_text.split('7.1.10.',1)[1].split('7.1.11.',1)[0]
        clauses=[x.strip() for x in section.split('•')[1:]]
        if not 1<=len(clauses)<=50 or any(not x for x in clauses):raise ValueError('deposit_tiers_missing_or_unbounded')
        tiers=[]
        for clause in clauses:
            reward=require(r'(\d+) баллов только за первый вклад',clause)
            interval=require(r'на сумму от ([\d ]+)\s*\([^)]*\)(?:\s+до ([\d ]+)\s*\([^)]*\))? рублей',clause)
            months=require(r'не менее чем на (\d+)\s*\([^)]*\) календарный месяц',clause)
            lo,hi=number(interval[1].strip()),number(interval[2].strip()) if interval[2] else None
            if int(lo)<=0 or (hi is not None and int(hi)<int(lo)) or int(months[1])<1:
                raise ValueError('invalid_deposit_interval')
            tiers.append({'points':number(reward[1]),'deposit_min_rub':lo,'deposit_max_rub':hi,
                          'term_min_months':int(months[1]),'reward_unit':'RZD_Bonus_points',
                          'evidence':clause})
        if len({t['deposit_min_rub'] for t in tiers})!=len(tiers):raise ValueError('duplicate_deposit_tier')
        period=require(r'Акция проводится в рамках срока с (\d{2}\.\d{2}\.\d{4}) г\. по (\d{2}\.\d{2}\.\d{4}) г\.',all_text)
        start,end=[datetime.strptime(s,'%d.%m.%Y').date().isoformat() for s in period.groups()]
        credit=require(r'в течение (\d+) календарных дней после истечения Периода охлаждения',all_text)
        cooling=require(r'Период охлаждения\s*[–—-].{0,100}?по (\d+)\s*\(',all_text)
        details.update(deposit_reward_tiers=tiers,credit_wait_days=int(credit[1]),
                       cooling_days=int(cooling[1]),validity_evidence=period[0],
                       credit_wait_evidence=credit[0],cooling_evidence=cooling[0])
        benefit=section
        warnings.append('loyalty_account_number_is_not_a_public_promocode')
    else:
        p=compact(' '.join(pages))
        section=p.split('За каждые потраченные на покупки',1)[1].split('Дополнительные привилегии',1)[0]
        section='За каждые потраченные на покупки'+section
        basis=require(r'За каждые потраченные на покупки (\d+) руб',section)
        tiers=[]
        for m in re.finditer(r'(\d+) мил[яи] при сумме покупок по карте в месяц от ([\d ]+) руб\.\s+до ([\d ]+) руб',section):
            lo,hi=number(m[2].strip()),number(m[3].strip())
            if int(lo)>=int(hi):raise ValueError('invalid_card_spend_interval')
            tiers.append({'miles':m[1],'monthly_spend_from_rub':lo,'monthly_spend_to_rub':hi,
                          'lower_inclusive':None,'upper_inclusive':None,'evidence':m[0]})
        # Every earning-tier clause must be recognized, including newly added tiers.
        # No fixed number of rows and no silent dropping of unsupported rows.
        expected=len(re.findall(r'\bпри сумме покупок по карте в месяц\b',section,re.I))
        if (not 1<=len(tiers)<=50 or len(tiers)!=expected
                or len({t['monthly_spend_from_rub'] for t in tiers})!=len(tiers)):
            raise ValueError('card_tiers_missing_duplicate_or_unparsed')
        cap=require(r'Максимальный лимит выплаты кешбэк/миль в месяц[^\d]*([\d ]+) миль',section)
        welcome=require(r'(\d+) приветственных миль',section)
        service=p.split('Обслуживание карты',1)[1].split('Обслуживание платежного стикера',1)[0] if 'Обслуживание платежного стикера' in p else p.split('Обслуживание карты',1)[1].split('Начисление кешбэк/миль',1)[0]
        details.update(spend_reward_tiers=tiers,earning_basis_rub=basis[1],earning_basis_evidence=basis[0],
                       monthly_miles_cap=number(cap[1].strip()),monthly_miles_cap_evidence=cap[0],
                       welcome_miles=welcome[1],welcome_miles_evidence=welcome[0],service_fee_conditions=service)
        benefit=section
        warnings.extend(['boundary_inclusivity_not_resolved','spend_outside_published_ranges_not_inferred',
                         'card_lifetime_is_not_offer_expiry'])
    return make_offer(source,'rules:pdf',cfg['program'],cfg['partner'],benefit,cfg['url'],observed_at,
                      title=cfg['title'],record_kind='program_rules',conditions=full,
                      locator='PDF pages 1-'+str(len(pages))+'; named clauses with full text',
                      details=details,warnings=warnings,valid_from=start,valid_until=end)


async def collect_pdf_rule(client,cfg,now):
    data=await within_source_budget(client,lambda:client.read_pdf(cfg['url']))
    pages=pdf_pages(data)
    return [parse_pdf_pages(cfg['id'],pages,now,document_sha256=hashlib.sha256(data).hexdigest())]
