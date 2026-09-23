"""Current active Tsvetnoy brand matrix, with tier columns and footnotes intact."""
from __future__ import annotations
import io,re,subprocess,xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from pypdf import PdfReader
from public_reward_projection import plain,one,make_record
from expansion_common import compact,sha,identity,ExcludedOffer,reported,PROGRAMS

SOURCE='tsvetnoy_public';ROOT='https://tsvetnoy.com/loyality'
TIERS=('Старт','Стандарт','Плюс')

def current_document(data):
    if not isinstance(data,list):raise ValueError('tsvetnoy_document_inventory')
    active=[d for d in data if d.get('active') is True and d.get('type')=='loyalyty_program_discount']
    if len(active)!=1 or not re.fullmatch(r'[a-zA-Z0-9_-]+\.pdf',active[0].get('key','')):
        raise ValueError('tsvetnoy_active_document_ambiguity')
    return {k:active[0].get(k) for k in ('_id','key','type','active','createAt','fileName')}

def matrix(data):
    if not data.startswith(b'%PDF-') or len(data)>6000000:raise ValueError('tsvetnoy_pdf_identity')
    reader=PdfReader(io.BytesIO(data))
    if not 1<=len(reader.pages)<=20:raise ValueError('tsvetnoy_pdf_page_bound')
    text='\n'.join(p.extract_text() or '' for p in reader.pages)
    if not all(x in text for x in ('СПИСОК БРЕНДОВ','Старт','Стандарт','Плюс','Скидки по специальным предложениям')):
        raise ValueError('tsvetnoy_matrix_headers')
    # Existing poppler dependency supplies word bounding boxes, NOT OCR. The
    # PDF's actual clipping rectangles supply row bounds; no brand names/rates
    # or row counts are hard-coded. Unknown table geometry stops publication.
    proc=subprocess.run(['pdftotext','-bbox-layout','-','-'],input=data,capture_output=True,timeout=30,check=True)
    pages=[n for n in ET.fromstring(proc.stdout).iter() if n.tag.rsplit('}',1)[-1]=='page']
    if len(pages)!=len(reader.pages):raise ValueError('tsvetnoy_pdf_page_mismatch')
    columns=((48,191.3),(191.3,255),(255,333),(333,411),(411,481),(481,574))
    output=[];floor=None
    for pi,(p,xp) in enumerate(zip(reader.pages,pages),1):
        if abs(float(p.mediabox.width)-595.44)>1:raise ValueError('tsvetnoy_page_geometry')
        rects={tuple(round(float(a),2) for a in args) for args,op in p.get_contents().operations if op==b're'
            and 20<float(args[2])<590 and 3<float(args[3])<700}
        bounds=sorted([q for q in rects if abs(q[0]-48.98)<.5 and (abs(q[2]-142.3)<.5 or abs(q[2]-524.83)<.5)],key=lambda q:-(q[1]+q[3]))
        if not bounds:raise ValueError('tsvetnoy_matrix_rows_not_found')
        words=[]
        height=float(xp.attrib['height'])
        for line in xp.iter():
            if line.tag.rsplit('}',1)[-1]!='line':continue
            baseline=height-(float(line.attrib['yMin'])+float(line.attrib['yMax']))/2
            for w in line:
                if w.tag.rsplit('}',1)[-1]=='word':words.append((float(w.attrib['xMin']),baseline,w.text or ''))
        for x,y,width,h in bounds:
            inside=sorted([w for w in words if y<=w[1]<=y+h and 48<=w[0]<574],key=lambda w:(-round(w[1],0),w[0]))
            if width>200:
                label=compact(' '.join(w[2] for w in inside))
                if re.fullmatch(r'-?\s*\d\s+этаж',label):floor=label
                continue
            cells=[compact(' '.join(w[2]for w in inside if a<=w[0]<b)) for a,b in columns]
            if cells[0].startswith('Наименование'):continue
            if not floor or not cells[0] or any(not re.fullmatch(r'(?:\d+\s*%\.?|-)',v) for v in cells[1:4]):
                raise ValueError('tsvetnoy_matrix_row_shape')
            if cells[4] not in ('-','\uf0fc','✓',''):raise ValueError('tsvetnoy_accumulation_mark')
            output.append({'page':pi,'floor':floor,'cells':cells})
    if not output or len(output)>500:raise ValueError('tsvetnoy_matrix_bound')
    # Exact source footnotes, outside the grid, retained with each discount.
    tail=text.rsplit('* В накоплениях',1)
    if len(tail)!=2:raise ValueError('tsvetnoy_footnote_missing')
    notes='* В накоплениях'+tail[1].split('Жирным шрифтом',1)[0]
    header=compact(text.split('-1 этаж',1)[0])
    header=header[header.index('Старт'): ]
    return output,compact(notes)+'\nГраницы уровней в таблице PDF: '+header

def source_fields(e):
    identity(e,SOURCE)
    if e.get('kind')=='tier':
        tier=e['tier'];body=e['body']
        if tier not in TIERS or e['native']!='tier:'+tier or e['url']!=ROOT:raise ValueError('tsvetnoy_tier_identity')
        useful=[x for x in body.splitlines() if not re.search(r'Новости|Приглашения|приглашения|специальные предложения от партнеров',x)]
        claims=[x for x in useful if re.search(r'бесплатн|двойные накопления|скидка',x,re.I)]
        if not claims:raise ExcludedOffer('no_concrete_partner_benefit')
        benefit='\n'.join(claims)
        return dict(native=e['native'],program=PROGRAMS[SOURCE],partner='Универмаг Цветной',title='Цветной — уровень '+tier,
            benefit=benefit,conditions='\n'.join(useful),activation=e['registration'],url=ROOT,category='Москва / универмаг / привилегии',
            kind='tier_benefit',link_kind='page_block',locator='loyality-terms; '+tier,
            scope={'member_tier':tier,'location':'Универмаг Цветной, Москва'},terms=[dict(kind='partner_privilege',fragment=benefit)])
    doc=e['document'];cells=e['row']['cells'];floor=e['row']['floor']
    if e['url']!='https://tsvetnoy.com/pdf/'+doc['key'] or len(cells)!=6:raise ValueError('tsvetnoy_brand_identity')
    native='brand:'+floor+':'+cells[0]
    if native!=e['native'] or not e['footnotes']:raise ValueError('tsvetnoy_brand_native')
    notes=cells[5];terms=[];lines=[]
    for tier,cell in zip(TIERS,cells[1:4]):
        v=re.fullmatch(r'(\d+)\s*%\.?',cell)
        if v:
            if not 0<=int(v[1])<=100:raise ValueError('tsvetnoy_invalid_discount')
            line=tier+': '+v[1]+'%';lines.append(line)
            if int(v[1])>0:terms.append(dict(kind='discount',value=v[1],unit='percent',qualifier='exact',fragment=line,scope={'member_tier':tier}))
        else:lines.append(tier+': скидка не указана')
    if not terms:
        if 'Золотая карта' in notes:
            lines=[notes];terms=[dict(kind='partner_privilege',fragment=notes)]
        else:raise ExcludedOffer('card_not_applicable' if 'не действует' in notes else 'accumulation_only_no_discount')
    conditions=[floor,notes,e['footnotes'],e['tier_conditions']]
    return dict(native=native,program=PROGRAMS[SOURCE],partner=cells[0],title='Цветной → '+cells[0]+' ('+floor+')',
        benefit='; '.join(lines),conditions='\n'.join(x for x in conditions if x),activation=e['registration']+'\nПредъявить карту лояльности при покупке; индивидуальные требования см. в примечании.',
        url=e['url'],category='Москва / универмаг / '+floor,link_kind='document_section',locator='PDF page '+str(e['row']['page'])+'; '+cells[0],
        terms=terms,scope={'location':'Универмаг Цветной, Москва','floor':floor},
        warnings=['accumulation_mark_is_status_progress_not_cashback','source_pdf_creation_date_not_offer_valid_from','tier_boundary_wording_preserved_separately'])

def tier_evidence(raw):
    soup=BeautifulSoup(raw,'html.parser');cards=soup.select('.loyality-terms__slide')
    if len(cards)!=3:
        headings=soup.select('h3.loyality-terms__card-title');cards=[h.parent.parent for h in headings]
    result={}
    for c in cards:
        tier=plain(one(c,'h3.loyality-terms__card-title'));body=plain(c)
        if tier not in TIERS or tier in result:raise ValueError('tsvetnoy_tier_table')
        result[tier]=body
    if set(result)!=set(TIERS):raise ValueError('tsvetnoy_missing_tier')
    get=one(soup,'.loyality-get-card');registration=plain(get)
    if 'Зарегистрируйтесь' not in registration or 'Цифровая карта' not in registration:raise ValueError('tsvetnoy_registration_missing')
    return result,registration

async def collect(client,cfg,report,now,limit):
    from read_budget import within_source_budget
    if cfg['id']!=SOURCE or cfg['url']!=ROOT:raise ValueError('tsvetnoy_config')
    doc=current_document(await within_source_budget(client,lambda:client.json('https://tsvetnoy.com/api/v1/documents')))
    url='https://tsvetnoy.com/pdf/'+doc['key'];data=await within_source_budget(client,lambda:client.read_pdf(url))
    rows,footnotes=matrix(data)
    raw=await within_source_budget(client,lambda:client.read(ROOT,render=True))
    await within_source_budget(client,lambda:client.page.locator('h3.loyality-terms__card-title').first.wait_for(state='attached',timeout=12000))
    raw=await client.page.content();tiers,registration=tier_evidence(raw)
    records=[];excluded={};inventory=[]
    practical_tiers='\n'.join(x for t in tiers.values() for x in t.splitlines() if re.search(r'^Старт$|^Стандарт$|^Плюс$|Приобретите|сохранения статуса',x))
    candidates=[dict(native='tier:'+tier,url=ROOT,kind='tier',tier=tier,body=body,registration=registration,page_sha256=sha(raw)) for tier,body in tiers.items()]
    candidates.extend(dict(native='brand:'+r['floor']+':'+r['cells'][0],url=url,document=doc,row=r,footnotes=footnotes,
        tier_conditions=practical_tiers,registration=registration,page_sha256=sha(data)) for r in rows)
    if len(candidates)>limit:raise ValueError('tsvetnoy_record_limit')
    for e in candidates:
        inventory.append(e['native'])
        try:records.append(make_record(SOURCE,e,now))
        except ExcludedOffer as exc:excluded[e['native']]=str(exc)
    reported(report,records,inventory,excluded,document=doc,pdf_sha256=sha(data),pages=len(PdfReader(io.BytesIO(data)).pages),scope='active_brand_matrix_and_three_public_card_tiers')
    return records
