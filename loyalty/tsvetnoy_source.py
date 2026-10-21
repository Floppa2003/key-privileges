"""Current active Tsvetnoy brand matrix, with tier columns and footnotes intact."""
from __future__ import annotations
import io,re,subprocess,xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from pypdf import PdfReader
from public_reward_projection import plain,one,make_record
from expansion_common import compact,sha,identity,ExcludedOffer,reported,PROGRAMS

SOURCE='tsvetnoy_public';ROOT='https://tsvetnoy.com/loyality'
LEGACY_TIERS=('Старт','Стандарт','Плюс')
from content_discovery import clean_dom, literal_benefits

def current_document(data):
    if not isinstance(data,list):raise ValueError('tsvetnoy_document_inventory')
    active=[d for d in data if d.get('active') is True and d.get('type')=='loyalyty_program_discount']
    if len(active)!=1 or not re.fullmatch(r'[a-zA-Z0-9_-]+\.pdf',active[0].get('key','')):
        raise ValueError('tsvetnoy_active_document_ambiguity')
    return {k:active[0].get(k) for k in ('_id','key','type','active','createAt','fileName')}

def matrix(data, tier_names):
    """Read column meaning from current headers and geometry from actual cells.

    The trailing columns remain accumulation and notes; they are not rewards.
    No page width, number of tiers, tier name, brand name or rate is frozen.
    """
    if not data.startswith(b'%PDF-') or len(data)>6000000:raise ValueError('tsvetnoy_pdf_identity')
    if not tier_names or len(set(tier_names))!=len(tier_names):raise ValueError('tsvetnoy_tier_inventory')
    reader=PdfReader(io.BytesIO(data))
    if not 1<=len(reader.pages)<=20:raise ValueError('tsvetnoy_pdf_page_bound')
    proc=subprocess.run(['pdftotext','-bbox-layout','-','-'],input=data,capture_output=True,timeout=30,check=True)
    pages=[n for n in ET.fromstring(proc.stdout).iter() if n.tag.rsplit('}',1)[-1]=='page']
    if len(pages)!=len(reader.pages):raise ValueError('tsvetnoy_pdf_page_mismatch')
    output=[];floor=None;context=[];previous_names=None;previous_grid=None;column_context=[]
    for pi,(page,xp) in enumerate(zip(reader.pages,pages),1):
        height=float(xp.attrib['height']);words=[];page_names=None
        for line in xp.iter():
            if line.tag.rsplit('}',1)[-1]!='line':continue
            baseline=height-(float(line.attrib['yMin'])+float(line.attrib['yMax']))/2
            for w in line:
                if w.tag.rsplit('}',1)[-1]=='word':words.append((float(w.attrib['xMin']),baseline,w.text or ''))
        rects={tuple(round(float(a),2) for a in args) for args,op in page.get_contents().operations
               if op==b're' and len(args)==4 and float(args[2])>3 and float(args[3])>3}
        groups={}
        for x,y,w,h in rects:groups.setdefault((round(y,1),round(y+h,1)),[]).append((x,x+w))
        grids=[]
        for (bottom,top),intervals in groups.items():
            # Drop outer row frames, keeping the individual cell rectangles.
            cells=sorted((a,b) for a,b in intervals if not any(a<=c and d<=b and d-c<b-a-.5 for c,d in intervals))
            if len(cells)!=len(tier_names)+3:continue
            if any(abs(b-c)>.8 for (a,b),(c,d) in zip(cells,cells[1:])):continue
            grids.append((bottom,top,cells))
        if not grids:raise ValueError('tsvetnoy_matrix_rows_not_found')
        def cell_text(bottom,top,left,right):
            inside=sorted((w for w in words if bottom<=w[1]<=top and left<=w[0]<right),key=lambda w:(-round(w[1],0),w[0]))
            return compact(' '.join(w[2] for w in inside))
        # The most frequent actual grid is the table. Other grids of the same
        # arity are ambiguous rather than silently assigned old coordinates.
        signatures={tuple((round(a,1),round(b,1)) for a,b in g[2]) for g in grids}
        if len(signatures)!=1:raise ValueError('tsvetnoy_ambiguous_column_geometry')
        grid=grids[0][2];used=[]
        for bottom,top,cells in sorted(grids,key=lambda g:-g[1]):
            values=[cell_text(bottom,top,a,b) for a,b in cells]
            rate_cells=values[1:-2]
            if all(re.fullmatch(r'(?:\d+(?:[.,]\d+)?\s*%\.?|[-–—])',v) for v in rate_cells):
                if not values[0]:raise ValueError('tsvetnoy_brand_name_missing')
                if page_names is None:
                    # A continuation page can omit its header only when its
                    # actual column geometry matches the preceding page.
                    candidates=[]
                    for a,b in cells[1:-2]:
                        header=cell_text(top,height,a,b)
                        candidates.append([t for t in tier_names if re.search(
                            r'(?<!\w)'+re.escape(t)+r'(?!\w)',header,re.I)])
                    if all(len(matches)==1 for matches in candidates):
                        observed=[matches[0] for matches in candidates]
                        if set(observed)!=set(tier_names):raise ValueError('tsvetnoy_column_header_mismatch')
                        page_names=observed
                        for name,(left,right) in zip(observed,cells[1:-2]):
                            matching=[(x,y,w,h) for x,y,w,h in rects if abs(x-left)<.8 and abs(x+w-right)<.8
                                      and y>top and re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',
                                                             cell_text(y,y+h,left,right),re.I)]
                            if matching:
                                x,y,w,h=min(matching,key=lambda q:q[3])
                                column_context.append(name+': '+cell_text(y,y+h,left,right))
                    elif (all(not matches for matches in candidates) and previous_names is not None and
                          len(cells)==len(previous_grid) and all(abs(a-c)<.8 and abs(b-d)<.8
                          for (a,b),(c,d) in zip(cells,previous_grid))):
                        page_names=list(previous_names)
                    else:raise ValueError('tsvetnoy_column_header_ambiguity')
                    previous_names=list(page_names);previous_grid=cells
                # Floor labels come from the current source, not fixed row offsets.
                lines={}
                for x,y,word in words:
                    if y>top:lines.setdefault(round(y,0),[]).append((x,word))
                preceding=[]
                for y,ws in lines.items():
                    label=compact(' '.join(w for _,w in sorted(ws)))
                    if re.fullmatch(r'-?\s*\d+\s+этаж|Floor\s+-?\d+',label,re.I):preceding.append((y,label))
                if preceding:floor=min(preceding)[1]
                if not floor:raise ValueError('tsvetnoy_floor_missing')
                # A tick grants status progress, never money or an extra rate.
                if values[-2] not in ('-','–','—','\uf0fc','✓',''):raise ValueError('tsvetnoy_accumulation_mark')
                output.append({'page':pi,'floor':floor,'cells':values,'tier_names':list(page_names)})
                used.append((bottom,top))
            elif not any(re.search(r'наименован|бренд|^Brand$',v,re.I) for v in values[:1]) and not all(
                any(re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',v,re.I) for t in tier_names) for v in rate_cells):
                # A mixed/new textual rate must not vanish as a guessed header.
                raise ValueError('tsvetnoy_matrix_row_shape')
        # Keep every non-data line: current header thresholds and notes, without
        # guessing a footnote's exact opening words or a prior programme name.
        lines={}
        for x,y,word in words:
            if not any(a<=y<=b for a,b in used):lines.setdefault(round(y,0),[]).append((x,word))
        context.extend(compact(' '.join(w for _,w in sorted(ws))) for y,ws in sorted(lines.items(),reverse=True))
    if not output or len(output)>2500:raise ValueError('tsvetnoy_matrix_bound')
    if not context:raise ValueError('tsvetnoy_matrix_context_missing')
    return output,'\n'.join(context+['Заголовки и условия столбцов PDF:']+list(dict.fromkeys(column_context)))


def legacy_source_fields(e):
    identity(e,SOURCE)
    if e.get('kind')=='tier':
        tier=e['tier'];body=e['body']
        if tier not in LEGACY_TIERS or e['native']!='tier:'+tier or e['url']!=ROOT:raise ValueError('tsvetnoy_tier_identity')
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
    for tier,cell in zip(LEGACY_TIERS,cells[1:4]):
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
    soup=clean_dom(raw);cards=soup.select('.loyality-terms__slide')
    if not cards:
        # A class-name change may leave the card heading; take the nearest
        # container with content and exactly one heading, never a fixed count.
        for h in soup.select('h3.loyality-terms__card-title'):
            node=h.parent
            while node.parent and plain(node)==plain(h):node=node.parent
            cards.append(node)
    result={}
    for c in cards:
        tier=plain(one(c,'h3.loyality-terms__card-title'));body=plain(c)
        if not tier or tier.casefold() in {t.casefold() for t in result}:raise ValueError('tsvetnoy_tier_table')
        result[tier]=body
    if not 1<=len(result)<=100:raise ValueError('tsvetnoy_missing_tier')
    registration=plain(one(soup,'.loyality-get-card'))
    if not registration:raise ValueError('tsvetnoy_registration_missing')
    return result,registration


def source_fields(e):
    if e.get('projection_version') is None:return legacy_source_fields(e)
    if e.get('projection_version')!=2:raise ValueError('tsvetnoy_projection_version')
    identity(e,SOURCE)
    names=e.get('tier_names')
    if (not isinstance(names,list) or not 1<=len(names)<=100 or
        any(not isinstance(t,str) or not t.strip() for t in names) or len(set(names))!=len(names)):
        raise ValueError('tsvetnoy_tier_inventory')
    if e.get('kind')=='tier':
        tier=e['tier'];body=e['body']
        if tier not in names or e['native']!='tier:'+tier or e['url']!=ROOT:raise ValueError('tsvetnoy_tier_identity')
        claims,terms=literal_benefits(body)
        # Loyalty progress is not a bank cashback or a discount on every brand.
        claims.extend(x for x in body.splitlines() if re.search(r'двойные накопления',x,re.I) and x not in claims)
        benefit='\n'.join(claims) if claims else body
        return dict(native=e['native'],program=PROGRAMS[SOURCE],partner='Универмаг Цветной',title='Цветной — уровень '+tier,
            benefit=benefit,conditions=body,activation=e['registration'],url=ROOT,category='Москва / универмаг / привилегии',
            kind='tier_benefit' if claims else 'source_observation',link_kind='page_block',locator='loyality-terms; '+tier,
            scope={'member_tier':tier,'location':'Универмаг Цветной, Москва'},
            terms=[dict(kind='partner_privilege',fragment=c) for c in claims])
    doc=e['document'];cells=e['row']['cells'];floor=e['row']['floor'];count=len(names)
    if e['url']!='https://tsvetnoy.com/pdf/'+doc['key'] or len(cells)!=count+3:raise ValueError('tsvetnoy_brand_identity')
    native='brand:'+floor+':'+cells[0]
    if native!=e['native'] or not e['footnotes']:raise ValueError('tsvetnoy_brand_native')
    notes=cells[-1];terms=[];lines=[]
    for tier,cell in zip(names,cells[1:1+count]):
        v=re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*%\.?',cell)
        if v:
            value=v[1].replace(',','.')
            if not 0<=float(value)<=100:raise ValueError('tsvetnoy_invalid_discount')
            line=tier+': '+value+'%';lines.append(line)
            if float(value)>0:terms.append(dict(kind='discount',value=value,unit='percent',qualifier='exact',fragment=line,scope={'member_tier':tier}))
        elif cell in ('-','–','—',''):
            lines.append(tier+': скидка не указана')
        else:raise ValueError('tsvetnoy_invalid_discount_cell')
    kind='partner_offer'
    if not terms:
        # A note about status accumulation is not a customer reward. A new
        # textual privilege needs a positive source claim, not a known name.
        claims,_=literal_benefits(notes)
        if claims:
            lines=claims;terms=[dict(kind='partner_privilege',fragment=c) for c in claims]
        elif re.search(r'не действует|не предостав',notes,re.I):raise ExcludedOffer('card_not_applicable')
        elif notes in ('','-','–','—') or re.search(r'накоплен',notes,re.I):
            raise ExcludedOffer('accumulation_only_no_discount')
        else:
            kind='source_observation';lines=[notes]
    return dict(native=native,program=PROGRAMS[SOURCE],partner=cells[0],title='Цветной → '+cells[0]+' ('+floor+')',
        benefit='; '.join(lines),conditions='\n'.join(x for x in (floor,notes,e['footnotes'],e['tier_conditions']) if x),
        activation=e['registration'],url=e['url'],category='Москва / универмаг / '+floor,kind=kind,link_kind='document_section',
        locator='PDF page '+str(e['row']['page'])+'; '+cells[0],terms=terms,scope={'location':'Универмаг Цветной, Москва','floor':floor},
        warnings=['accumulation_mark_is_status_progress_not_cashback','source_pdf_creation_date_not_offer_valid_from','tier_boundary_wording_preserved_separately'])

async def collect(client,cfg,report,now,limit):
    from read_budget import within_source_budget
    if cfg['id']!=SOURCE or cfg['url']!=ROOT:raise ValueError('tsvetnoy_config')
    doc=current_document(await within_source_budget(client,lambda:client.json('https://tsvetnoy.com/api/v1/documents')))
    url='https://tsvetnoy.com/pdf/'+doc['key'];data=await within_source_budget(client,lambda:client.read_pdf(url))
    raw=await within_source_budget(client,lambda:client.read(ROOT,render=True))
    await within_source_budget(client,lambda:client.page.locator('h3.loyality-terms__card-title').first.wait_for(state='attached',timeout=12000))
    raw=await client.page.content();tiers,registration=tier_evidence(raw)
    rows,footnotes=matrix(data, list(tiers))
    records=[];excluded={};inventory=[]
    practical_tiers='\n'.join(tiers.values())
    candidates=[dict(projection_version=2,tier_names=list(tiers),native='tier:'+tier,url=ROOT,kind='tier',tier=tier,body=body,registration=registration,page_sha256=sha(raw)) for tier,body in tiers.items()]
    candidates.extend(dict(projection_version=2,tier_names=r['tier_names'],native='brand:'+r['floor']+':'+r['cells'][0],url=url,document=doc,row=r,footnotes=footnotes,
        tier_conditions=practical_tiers,registration=registration,page_sha256=sha(data)) for r in rows)
    if len(candidates)>limit:raise ValueError('tsvetnoy_record_limit')
    for e in candidates:
        inventory.append(e['native'])
        try:records.append(make_record(SOURCE,e,now))
        except ExcludedOffer as exc:excluded[e['native']]=str(exc)
    reported(report,records,inventory,excluded,document=doc,pdf_sha256=sha(data),pages=len(PdfReader(io.BytesIO(data)).pages),scope='active_brand_matrix_and_observed_public_card_tiers')
    return records
