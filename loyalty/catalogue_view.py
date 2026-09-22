"""Source-owned practical offer projection, without raw posts or documents."""
from __future__ import annotations
import re
from bs4 import BeautifulSoup
from collections import Counter
from datetime import date
from catalogue_clauses import (VERSION, HEADERS, NOISE_KIND, TECHNICAL, DEAD,
    ROLE, RULE, ACTION, MARKETING, DESCRIPTIVE, text, compact, key, clause_key,
    unique_clauses, clean_plain, units, is_boilerplate, practical_terms,
    benefit_claim, meaningful_claim, full_code_display)


def owned_source_text(raw):
    """Separate actual offer panels from publisher boilerplate, without a fetch."""
    raw=dict(raw);d=raw.get("details",{})
    for field in ("benefit","conditions","activation"):
        value=text(raw.get(field))
        # The programme's own offer starts after unrelated merchant marketing.
        if d.get("retrieval_method")=="google_import_public_text_v1" and raw.get("program")=="РЖД Бонус":
            m=re.search(r"Получайте\s+(?:\d|$)",value,re.M)
            if m:value=value[m.start():]
            value=re.sub(r"РЖД\s+Бонус", "РЖД Бонус", value)
            value=re.split(r'Программа [«"]РЖД\s+Бонус[»"] не несет ответственность',value,1)[0]
            value=re.split(r"\nРеклама[.\s]",value,1)[0]
        if raw.get("source_status")=="public_api_google_import" and field=="conditions":
            heading=re.search(r"(?m)^(?:Начисление миль|Как накопить мили|Использование миль)\s*$",value)
            if heading:value=value[heading.start():]
            value=re.split(r"\nНачисление: поля тарифов источника",value,1)[0]
        value=re.split(r"Сведения об организаторе Акции, Правилах проведения Акции",value,1)[0]
        value=re.sub(r"(?:Подробнее о сроках здесь|Сайт партнёра)\s*$","",value).strip()
        value=value.replace("Возврат к списку","")
        raw[field]=value
    if raw.get("program","").endswith("членов РГО"):
        for field in ("benefit","conditions","activation"):
            value=text(raw.get(field))
            match=re.search(r"(?:При предъявлении|Для (?:членов|участников)).{0,70}РГО",value)
            if match:raw[field]=value[match.start():]
    if d.get("document_part"):
        for field in ("benefit","conditions","activation"):
            value=text(raw.get(field))
            value=re.sub(r"\[Страница \d+; позиция \d+\]\s*","",value)
            # Join native PDF word wraps, retaining punctuation and every number.
            if len(value.splitlines())>20 and sum(len(x)<20 for x in value.splitlines())/max(1,len(value.splitlines()))>.65:
                raw[field]=compact(value)
    if raw.get("program","").startswith("Аэрофлот Бонус"):
        for field in ("benefit","conditions","activation"):
            value=text(raw.get(field))
            value=re.split(r'[«"]Аэрофлот Бонус[»"]\s*[–—-]\s*это программа лояльности',value,1)[0] if not value.startswith("О партнёре") else value
            if value.startswith("О партнёре"):
                start=re.search(r"Как воспользоваться\?",value)
                if start:value=value[start.start():]
            raw[field]=value
        body=raw.get("conditions","")
        rate=re.search(r"(?m)^(?:[-–—] )?(?:\d[\d ]* мил[яь]|За каждые потраченные \d)[^\n]*",body)
        if rate and len(text(raw.get("benefit")))>500:raw["benefit"]=rate.group(0)
    if raw.get("source_status")=="public_hse_partner_detail":
        for field in ("benefit","conditions","activation"):
            pieces=units(raw.get(field))
            raw[field]="\n".join(v for v in pieces if (
                benefit_claim(v,raw) or RULE.search(v) or ACTION.search(v)
            ) and not MARKETING.search(v))
    if d.get("public_post"):
        for field in ("benefit","conditions","activation"):
            value=text(raw.get(field)).replace("\u2800"," ")
            raw[field]=value
    templates=d.get("templates")
    if isinstance(templates,list) and d.get("catalog_profiles") and any(t.get("name")=="conditions" for t in templates):
        kept=[t for t in templates if t.get("name") not in ("site","rules") and text(t.get("text")).strip()]
        raw["conditions"]="\n".join(
            ((text(t.get("title"))+"\n") if t.get("title") else "")+text(t["text"])
            for t in kept)
        raw["activation"]=""
        # Keep material disclaimer changes, e.g. bonus currency after October 1.
        raw["conditions"]=re.sub(r'Организатор акции: АО [«"]НСПК[»"]\.',"",raw["conditions"],flags=re.I)
        raw["conditions"]=re.sub(r"Информация об организаторе, правилах проведения акции, партнерах акции, размере кешбэка доступны на сайте vamprivet\.ru\.","",raw["conditions"],flags=re.I)
    if d.get("general_rules_excerpt") and d.get("qualification"):
        general=text(d["general_rules_excerpt"])
        own=text(raw.get("conditions")).replace(general,"")
        relevant=[v for v in units(general) if re.search(
            r"После совершения двух перелетов|Оплатить бонусами возможно только тариф|"
            r"Сборы, а также|Все неиспользованные начисленные бонусы|"
            r"Бонусы не начисляются|только на личные полеты|"
            r"начисляются за фактически лично|СНГ|сгора|аннулир",v,re.I)]
        raw["conditions"]=own+"\n"+"\n".join(relevant)
    if raw.get("source_url")=="https://medsi.ru/actions/aeroflot-bonus-v-klinikakh-medsi/":
        value=text(raw.get("conditions"))
        start=re.search(r"Кто может воспользоваться акцией:",value)
        if start:value=value[start.start():]
        end=re.search(r"Клиники, участвующие в акции:",value)
        if end:value=value[:end.start()]+"Список участвующих клиник: "+raw["source_url"]
        raw["conditions"]=value
    if raw.get("program")=="Уральские авиалинии — «Крылья»":
        for field in ("benefit","conditions","activation"):
            value=text(raw.get(field))
            panel=re.search(r"Как получить (?:бонусы/скидку|привилегии)[:?]?",value,re.I)
            if panel:raw[field]=value[panel.end():].lstrip(": \n")
        body=text(raw.get("conditions"))
        boundary=re.search(r'Специальное предложение для участников [«"]Крылья[»"]:',body)
        if boundary:
            raw["conditions"]=body[boundary.start():]
            raw["benefit"]=body[boundary.end():].split("Контакты",1)[0]
    if d.get("public_post"):
        # Loyals puts its card offer after the restaurant review.
        for field in ("benefit","conditions","activation"):
            parts=units(raw.get(field))
            hits=[i for i,v in enumerate(parts) if re.search(r"(?:карт[аыау]|обладател|держател|пост).{0,50}Loyals|Loyals.{0,50}(?:скидк|комплимент)|Покажите официанту",v,re.I)]
            if hits:raw[field]="\n".join(parts[min(hits):])
    if d.get("public_item"):
        body=raw.get("conditions","")
        boundary=re.search(r"(?m)^Как подключить [^\n]+\?",body)
        if boundary:
            raw["activation"]=body[boundary.start():]
            before=body[:boundary.start()]
            lines=clean_plain(before).splitlines()
            chosen=[v for v in lines if re.search(r"в подарок|на баланс|Пакет заботы",v,re.I)]
            raw["conditions"]="\n".join(chosen)
    block=d.get("public_coral_block")
    if block:
        body=text(block.get("body"))
        # Generic inventory (400000 free books) is not the Coral gift.
        start=re.search(r"Только для владельцев|Эксклюзивное предложение только для держателей",body,re.I)
        if start:body=body[start.start():]
        body=re.split(r"\nРеклама[.\s]",body,1)[0]
        boundary=re.search(r"(?m)^(?:Условия акции|Как воспользоваться предложением|Как получить бонусы|Правила и сроки проведения)[:?]?\s*$",body)
        if boundary:
            prefix=body[:boundary.start()]
            pieces=units(prefix)
            useful=[t for t in pieces if (
                re.search(r"скидк.{0,50}\d|\d.{0,30}(?:бонус|в подарок|за 0 руб)|"
                          r"только для владельц|для держателей карт|промокод",t,re.I)
                and not DESCRIPTIVE.search(t))]
            body="\n".join(useful)+"\n"+body[boundary.start():]
        raw["conditions"]=body
    return raw


def record_row(n, as_of):
    raw=owned_source_text(n["raw"]); d=raw.get("details",{}); kind=raw["kind"]
    from source_lifecycle import reader_hold
    hold=reader_hold(raw,as_of)
    if hold:return None,hold
    if kind in NOISE_KIND:return None,"неразобранный источник"
    if raw.get("source_status")=="archived":return None,"архив источника"
    if n.get("validity",{}).get("status")=="expired":return None,"истёкший срок"
    if d.get("public_editorial_information") or d.get("public_coral_block",{}).get("public_editorial_information"):
        return None,"реклама программы"
    source=raw.get("benefit_url") or raw.get("source_url") or ""
    if re.search(r"В старой официальной подборке|Только в старой",raw.get("benefit",""),re.I) or DEAD.search(raw.get("benefit","")) or re.search(r"срок акции уже ист[её]к|акция (?:шла|действовала) .{0,80}20(?:2[0-5])",raw.get("conditions",""),re.I):
        return None,"неактивное предложение"
    if kind=="campaign" and re.search(r"шансы на победу|победителям|розыгрыш|разыгрываем",raw.get("benefit",""),re.I):
        return None,"розыгрыш"
    if raw.get("source_status")=="public_rules_ocr_unverified":return None,"неразобранный документ"
    if kind=="program_rules" and (
        not clean_plain(raw.get("benefit")) or TECHNICAL.fullmatch(text(raw.get("benefit")).strip())
        or re.match(r"^(?:Microsoft |Дебетовая карта$|Презентация |Порядок оказания услуг|Правила оформления заявки)",text(raw.get("title")),re.I)
        or len(text(raw.get("conditions")))>4000):
        return None,"документ вместо предложения"
    name=compact(raw.get("partner") or raw.get("title"))
    if not name or TECHNICAL.fullmatch(name):return None,"нет названия предложения"
    raw=dict(raw)
    if d.get("public_partner"):
        item=d["public_partner"]
        html=item.get("discountScheme") or ""
        if html and not re.search(r"Ознакомиться с подробными условиями Программы лояльности",html,re.I):
            soup=BeautifulSoup(html,"html.parser")
            for br in soup.select("br"):br.replace_with("\n")
            for node in soup.select("p,li"):node.append("\n")
            plain=soup.get_text("",strip=False)
            plain=re.sub(r"\s+[–—] (?=[А-Я])","\n– ",plain)
            raw["conditions"]="\n".join(dict.fromkeys(x for x in (raw.get("conditions",""),plain) if x))
    conditions=practical_terms(raw.get("conditions",""),labels=(name,raw.get("title","")))
    if d.get("region"):conditions="Город: "+text(d["region"])+"\n"+conditions
    activation=practical_terms(raw.get("activation",""),labels=(name,))
    if key(activation)==key(conditions) or key(raw.get("activation"))==key(raw.get("conditions")):activation=""
    extra=practical_terms(raw.get("benefit",""),labels=(name,raw.get("title","")))
    terms="\n".join(dict.fromkeys(x for x in (conditions,extra) if x))
    headline=meaningful_claim(raw,terms)
    if not headline:return None,"нет конкретной выгоды"
    if re.fullmatch(r"(?:Привилегия|Подробнее|Подарочный сертификат|Дебетовая карта|"
                    r"Доступ к эксклюзивным предложениям и (?:закрытым )?распродажам)",headline,re.I):
        return None,"нет конкретной выгоды"
    if kind in ("tier_benefit","program_rules","membership_plan"):
        title=compact(raw.get("title"))
        if title and not TECHNICAL.fullmatch(title) and not re.fullmatch(r"Подробнее|Дебетовая карта",title,re.I):name=title
        if d.get("tier") and key(d["tier"]) not in key(name):name+=" — "+text(d["tier"])
    code=full_code_display(n)
    explicit=d.get("explicit_code_cell")
    if explicit and not code:code=clean_plain(explicit)
    if not source and raw["origin"]!="parser_offers":source=""
    if not activation:
        actions=[s for s in units(terms) if re.search(r"предъяв|демонстр|покаж|введите|укажите|перейдите|"
                  r"зарегистриру|авторизуй|активиру|нажмите|обратитесь|позвоните|проверьте|приложите|напишите|можно написать",s,re.I)]
        activation="\n".join(actions[:3])  # Remaining instructions stay in terms.
    term_parts=unique_clauses(units(conditions)+units(extra))
    presented={clause_key(x) for x in units(headline)+units(activation)}
    term_parts=[s for s in term_parts if clause_key(s) not in presented and not is_boilerplate(s)]
    term_parts=[s for s in term_parts if not (len(s)>90 and any(s!=other and key(s) in key(other) for other in term_parts))]
    terms="\n".join(term_parts)
    if key(terms)==key(activation):terms=""
    status="Срок не указан"
    start=raw.get("valid_from");end=raw.get("valid_until")
    period=" — ".join(x for x in (start,end) if x)
    if start and not end:period="с "+start
    if end and not start:period="до "+end
    if end:status="В пределах срока" if end>=as_of else "Истекло"
    if start and start>as_of:status="Ещё не началось"
    warn=" ".join(raw.get("source_warnings",[]))
    if "conflict" in warn or "expiry_metadata" in warn:status="Проверь срок"
    if not period:
        v=raw.get("validity_raw")
        if v and not is_boilerplate(text(v)):period=text(v)
    comments=raw.get("original",{}).get("fields",{}).get("Ручной комментарий",{}).get("value","")
    if "promotion_year_inferred_from_current_page_month" in warn:
        status="Год срока определён по контексту страницы"
        comments="\n".join(filter(None,[text(comments),"В периоде акции год не написан; использован текущий месяц и год заголовка страницы."]))
    if "partial_restaurant_reward_only" in warn:
        status="Только ресторанная скидка"
    row=[name,raw.get("program") or "",headline,code,activation,terms,period or "",
         raw.get("category") or "",raw.get("observed_at") or "",source,text(comments),
         ROLE.get(kind,"Предложение"),status,raw["id"],raw["origin"],str(raw["source_row"]),raw.get("title") or ""]
    return row,None


def build_catalogue(records, *, as_of):
    date.fromisoformat(as_of)
    rows=[];removed=[];rewritten=0
    for n in records:
        row,reason=record_row(n,as_of)
        if reason:removed.append({"id":n["id"],"reason":reason});continue
        if compact(row[2])!=compact(n["raw"].get("benefit","")) or compact(row[5])!=compact(n["raw"].get("conditions","")):rewritten+=1
        rows.append(row)
    seen={};unique=[]
    for row in rows:
        signature=tuple(key(row[j]) for j in (0,1,2,3,4,5,6,7,9,10,11,12))
        if signature in seen:
            removed.append({"id":row[13],"reason":"точный дубль","same_as":seen[signature]});continue
        seen[signature]=row[13];unique.append(row)
    # Only the reviewed manual/live mirror pattern is consolidated. The key
    # retains programme, merchant, rate, code, period and exact source URL.
    # All distinct practical/access/comment clauses survive on the live card.
    def mirror_key(row):
        return tuple(clause_key(row[j]) for j in (0,1,2,3,6,9))
    mirrors={mirror_key(r):r for r in unique if r[14]=="parser_offers"
             and r[1] in ("Карта «Москвича»","No Name Card")}
    mirrored=[]
    for row in unique:
        live=mirrors.get(mirror_key(row))
        if row[14]=="loyalty_partner_benefits" and live:
            for col in (4,5,10):live[col]="\n".join(unique_clauses(units(live[col])+units(row[col])))
            removed.append({"id":row[13],"reason":"дубль ручного каталога","same_as":live[13]})
        else:mirrored.append(row)
    unique=mirrored
    unique.sort(key=lambda r:(key(r[0]),key(r[1]),r[13]))
    if len({r[13] for r in unique})!=len(unique):raise ValueError("Duplicate catalogue ID")
    if any(not r[0] or not r[1] or not r[2] for r in unique):raise ValueError("Unusable catalogue row")
    if any(len(text(c))>45000 for r in unique for c in r):raise ValueError("Catalogue cell exceeds safe size")
    return {"version":VERSION,"rows":unique,"removed":removed,
            "counts":{"input":len(records),"kept":len(unique),"removed":len(removed),
                      "rewritten":rewritten,"reasons":dict(Counter(x["reason"] for x in removed))}}
