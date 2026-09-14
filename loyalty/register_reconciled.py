"""One-time checksum-bound registration of locally tested code. Removed before merge."""
from pathlib import Path
import json,hashlib
from bs4 import BeautifulSoup
L=Path('loyalty')
BEFORE={'known_rules.json':'e5e365bb942ed67132e347c72196c575008219b9e72187e020022050d41d59ed','sources_normalized.json':'e79e416e30a3624fb7339848b6077d51dd78346b329d8f5b815d58e15ce211c4','known_rules.py':'4ab582c9738775f6a368d73c486072dd837226dad1aa4b8d70387b86c9a92426','normalized.py':'68114641c6410b016dd1e4f5099292b9707b532000e98a4039e3fe4bcef9d0cc','announcements.py':'7f61a0c067e462d28b8788961baeaff56f387770b1a824a6dc0f66e956e522dc'}
for f,h in BEFORE.items():
 if hashlib.sha256((L/f).read_bytes()).hexdigest()!=h:raise ValueError('unexpected baseline '+f)
SPECS={
 'ural_ramada_rules':('https://ramadayekaterinburg.com/wings/','Рамада Екатеринбург',['.dop-inner__info'],['Крылья','Рамада Екатеринбург','не распространяется на специальные предложения'],'135854d63ccd06e27fbe.html'),
 'ural_seagalaxy_rules':('https://seagalaxy.com/spec/programma-loyalnosti-krylya-offer','Sea Galaxy Hotel Congress & Spa',['.section.m-70.mt-20'],['Крылья','предъявлении карты'],'b14b3d75372e4d2a5b33.html'),
 'ural_smart_rules':('https://online.smart-inc.ru/smartmedia/partner-projects/smart-ural-airlines','Smart',['#rec754529990 [data-elem-id="'+i+'"]' for i in ['1716884715199','1716885536547','1716885536523','1716885722000','1716885767656','1716885817793','1716885817771','1716885851111','1716885851096']],['Крылья','От Smart','Синей','Серебряной','Золотой'],'85e1292d3a9c5c27384e.html'),
 'ural_airharbour_rules':('https://hotel.iktport.ru/ru/akcii/drugie.html','Воздушная гавань',[".item-page [itemprop='articleBody'] > p:not(hr ~ p)"],['Крылья','Синей','Серебряной','Золотой'],'cabe37051c7791e2aa5a.html'),
 'ural_carsgo_rules':('https://sykt.arendacar.ru/news/novyj-partnjor-kompanii-uralskie-avialinii/','Cars&GO',['.ft.offset__24'],['Крылья','Крылья5','Крылья10','Крылья15'],'81a543ce4c58ae771fea.html'),
 'ural_gloria_rules':('https://hotelamur.com/partners-bonus-ural-airlines/','GLORIA',['.spb-asset-content:-soup-contains("Бизнес отель GLORIA")','.spb-asset-content:-soup-contains("Как получить скидку:")','.spb-asset-content:has(table)'],['GLORIA','Крылья','Вид карты'],'f6374a0e0a88b241b352.html'),
 'ural_triangle_rules':('https://gthotel.ru/offers/uralskie-avialinii/','Золотой Треугольник',['.content.-detail .ustyle'],['Крылья','URALAIRLINES'],'845c7018d1d0a3a39318.html'),
 'ural_visotsky_rules':('https://visotsky-hotel.ru/special-offers','Высоцкий',['li.b-special-offers-list__item:has(h2:-soup-contains("Программа лояльности «Крылья»"))'],['Крылья','Silver','Gold','Делюкс'],'cf93e9d31bde8da23d73.html'),
 'ural_angara_rules':('https://angarahotel.ru/stock/skidki-dlya-uchastnikov-programmy-krylya/','Ангара',['.stock-detail__content'],['Крылья','Ангара','синей','серебряной','золотой'],'e8a86120d1ffac3e03fd.html'),
 'ural_ecospa_rules':('https://ecospa-visotsky.ru/about/actions/item/154-programma-loyalnosti-krylya-ot-aviakompanii-uralskie-avialinii','EcoSpa Высоцкий',['.itemFullText'],['Крылья','акционные'],'14cb86bd0676212fc175.html'),
}
new={};fdir=L/'tests/fixtures/reconciled';fdir.mkdir(parents=True,exist_ok=True)
report=json.loads(Path('public-evidence/discovery.json').read_text())
known={r.get('file'):r for r in report['results'] if r.get('status')=='read'}
for k,(u,name,sels,required,f) in SPECS.items():
 raw=(Path('public-evidence')/f).read_bytes()
 if known[f]['url']!=u or hashlib.sha256(raw).hexdigest()!=known[f]['sha256']:raise ValueError('public fixture integrity '+f)
 soup=BeautifulSoup(raw.decode(),'html.parser');selected=[]
 for sel in sels:
  found=soup.select(sel)
  if not found or (k!='ural_airharbour_rules' and len(found)!=1):raise ValueError('fixture scope '+k)
  selected+=found
 keep={id(n) for s in selected for n in [s,*s.descendants,*s.parents]}
 for n in list(soup.find_all(True)):
  if n.parent is not None and id(n) not in keep:n.decompose()
 for n in soup.find_all(True):n.attrs={key:v for key,v in n.attrs.items() if key in ('id','class','itemprop','data-elem-id','href','src','alt')}
 (fdir/(k+'.html')).write_text(str(soup),encoding='utf8')
 cfg={'url':u,'program':'Уральские авиалинии — «Крылья»','partner':name,'title':name+' — подробные условия «Крыльев»','selectors':sels,'required':required,'record_kind':'program_rules','supplements':['ural']}
 if k=='ural_airharbour_rules':cfg.update(single_selectors=False,link_kind='page_block')
 if k=='ural_visotsky_rules':cfg.update(link_kind='page_block',warnings=['rates_are_room_categories_not_card_tiers'])
 if k=='ural_seagalaxy_rules':cfg['warnings']=['tier_labels_in_images_not_structurally_verified','partnership_start_is_not_offer_expiry']
 if k=='ural_gloria_rules':cfg.update(capture_tables=True,warnings=['partner_name_taken_from_page_not_domain'])
 new[k]=cfg
p=L/'known_rules.json';old=json.loads(p.read_text());old.update(new);p.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
p=L/'sources_normalized.json';conf=json.loads(p.read_text())
for k,c in new.items():conf.append({'id':k,'name':c['title'],'url':c['url'],'mode':'known_rules'})
channels={'mir_announcements':'promomir','bspb_announcements':'mybspb'}
names={'mir_announcements':'Платёжная система «Мир» — официальные объявления','bspb_announcements':'Банк «Санкт-Петербург» — объявления о привилегиях'}
for k,ch in channels.items():conf.append({'id':k,'channel':ch,'name':names[k],'url':'https://t.me/s/'+ch,'mode':'announcements','lookback_days':180,'max_pages':60})
p.write_text(json.dumps(conf,ensure_ascii=False,indent=2)+'\n')
p=L/'known_rules.py';s=p.read_text().replace("    return [make_offer(source,'rules:page'", "    # Opt-in native tables from already scoped sections, never a fabricated table.\n    tables=[[[text(cell.get_text(' ',strip=True)) for cell in row.find_all(['th','td'],recursive=False)]\n             for row in table.select('tr')] for node in nodes for table in node.select('table')] if cfg.get('capture_tables') else []\n    return [make_offer(source,'rules:page'")
s=s.replace("warnings=warnings,valid_from=start,valid_until=end)]", "warnings=warnings,valid_from=start,valid_until=end,tables=tables)]");p.write_text(s)
p=L/'normalized.py';s=p.read_text().replace("VERSION = '2.6.0'","VERSION = '2.7.0'")
s=s.replace("HOSTS['rzd_announcements']=['t.me']", "HOSTS['rzd_announcements']=['t.me']\nHOSTS['mir_announcements']=['t.me']\nHOSTS['bspb_announcements']=['t.me']")
s=s.replace("('ekp_announcements','rzd_announcements')", "('ekp_announcements','rzd_announcements','mir_announcements','bspb_announcements')")
s=s.replace("{'ekp_announcements':'ekpcard','rzd_announcements':'fpcrussia'}", "{'ekp_announcements':'ekpcard','rzd_announcements':'fpcrussia','mir_announcements':'promomir','bspb_announcements':'mybspb'}");p.write_text(s)
p=L/'announcements.py';s=p.read_text().replace("CHANNELS = {'ekp_announcements': 'ekpcard', 'rzd_announcements': 'fpcrussia'}", "CHANNELS = {'ekp_announcements':'ekpcard', 'rzd_announcements':'fpcrussia',\n            'mir_announcements':'promomir', 'bspb_announcements':'mybspb'}")
s=s.replace("    if cards:\n        return True", "    if cfg['id'] in ('mir_announcements','bspb_announcements'):\n        # A bank's interest rate or a channel's audience statistics is not a perk.\n        reward=re.search(r'скидк|к[еэ]шб[еэ]к|промокод|подар',body,re.I)\n        context=(cfg['id']=='mir_announcements' or bool(re.search(r'ЯРКО|ЕКП|лояльност|един\\w*\\s+карт',body,re.I)))\n        return bool(context and reward and NUMERIC_BENEFIT.search(body)\n                    and not re.search(r'опрос|голосован|мониторинг\\s+активност',body,re.I))\n    if cards:\n        return True")
s=s.replace("            elif u.hostname in ('rzd-bonus.ru','www.rzd-bonus.ru'):", "            elif cfg['id']=='mir_announcements' and u.hostname in ('vamprivet.ru','privetmir.ru'):\n                cards.append(link)\n            elif u.hostname in ('rzd-bonus.ru','www.rzd-bonus.ru'):");p.write_text(s)
AFTER={'known_rules.json':'f0bbc6a180cfb4d359a5196348fcb07491dcfc885397d540d97d9636f833c3dc','sources_normalized.json':'920eef525f48a741a73a24ce47badc5db4434e6511f3a754537cf45f424313d3','known_rules.py':'aad2232692646bb520c5dd83bcfa74b106b54c6ae288624d1ce3d90b4279fa54','normalized.py':'b017e2d93685a7bbfc0bde885ad4f67e5678192a7791f32b963053c16a7fb0a1','announcements.py':'43b2a73bde1b24473de0e3f91a70eeec751ab1c2b7054efccaf11a0830e12001'}
for f,h in AFTER.items():
 if hashlib.sha256((L/f).read_bytes()).hexdigest()!=h:raise ValueError('code transfer mismatch '+f)
print('Reviewed code hashes verified.')
