"""Small hand-checked fixtures of observed public structures, not full snapshots.
Negative canaries are synthetic. Live counts must come from a fresh Actions run.
"""
import json

def noname():
    groups=[('rec907001896',[(24,'EX bags','5% скидка при покупке до 200 000 ₽; скидка 10 000 ₽ от 200 000 ₽',296),(258,'Roses and Lace','Скидка 10%; при покупке от 150 000 ₽ аксессуар в подарок',296),(493,'My Dear Petra','Скидка 20% на первую покупку, скидка 7% на последующие',296),(729,'Studio 29','Cкидка 10% при демонстрации карты',296)]),('rec907013812',[(18,'Lobster Studio','Бронь зала от 5 часов скидка 15%, двух залов от 3 часов скидка 20%',296)]),('rec907017271',[(24,'Времена года кинотеатр','Скидка на аренду зала в размере 15%',317)])]
    out=[]
    for rid, cards in groups:
        elements=[]
        for i,(left,name,benefit,top) in enumerate(cards):
            # Deliberately reversed DOM ordering reproduces the observed Tilda trap.
            for suffix,y,t in [('benefit',top,benefit),('name',262,name)]:
                elements.append(f'<div class="t396__elem" data-elem-id="{i}-{suffix}" data-field-left-value="{left}" data-field-top-value="{y}"><div class="tn-atom">{t}</div></div>')
        out.append(f'<div class="t-rec" id="{rid}">'+''.join(elements)+'</div>')
    return ''.join(out)

F={
 'noname.html':noname(),
 'moskvich.html':''.join(f'<div class="lpp-card"><h3 class="lpp-card__name">{name}</h3><div class="lpp-card__conditions">{benefit}</div></div>' for name,benefit in [('Кафе Перспектива','Скидка 15% на безалкогольные напитки'),('Lenger Bistro','Скидка 20% до 18:00 и 10% после; алкоголь исключен'),('Санто Джованни','Просекко в подарок при заказе по меню')]),
 'ural.html':''.join(f'<li id="partner_{i}"><div class="uk-accordion-title">Отель {i}</div><div class="uk-accordion-content"><div class="uan-styled-text"><p>Скидка при предъявлении карты</p><table><tr><th>Синий</th><th>Серебряный</th><th>Золотой</th></tr><tr><td>5%</td><td>10%</td><td>15%</td></tr></table><p>Не суммируется с акциями</p></div></div></li>' for i in range(1,5)),
 'rgo_detail.html':'<h1>Гостиница Паддок</h1><div class="section-text__inner text">Скидка 10% на бронирование номера + 10 минут проката картинга в подарок. Предъявите членский билет.</div>',
 'sogaz_medi.html':'<div class="content"><p>Клиентам СОГАЗ, кроме ОМС</p><ul><li>Скидка 10% на услуги, не оплачиваемые страховщиком</li><li>27% на лазерную коррекцию зрения</li></ul></div>',
 'rusimp.html':''.join(f'<div class="w-tab-pane"><div class="product-card__heading"><h3>{title}</h3><span class="h4">{price}</span></div><div class="museum-friend"><div class="museum-friend-adv">{benefit}</div></div></div>' for title,price,benefit in [('Индивидуальная','5 000 ₽','Посещение музея, скидка 10% на мероприятия'),('Индивидуальная + гость','7 500 ₽','Посещение музея для вас и гостя, скидка 15% на мероприятия')]),
 'promomiles.html':'<h2>Завершенные акции</h2>'+''.join(f'<a class="promotion-mini" href="/act/archive{i}"><div class="promotion-mini__title">Акция {i}</div><div class="promotion-mini__text">Скидки и мили</div><div class="promotion-mini__info">Архив</div></a>' for i in range(4)),
 'ekp_neva.html':'<h1>Нева Тревел</h1><div class="stock-left-contentId">Скидка 5% онлайн; 100 руб в кассе. Не суммируется с акциями.</div><aside>Другая акция: скидка 50%</aside>',
 'azimut.html':'<table><thead><tr><th>Привилегия</th><th>Бонус</th><th>Серебряный</th><th>Золотой</th><th>Платиновый</th></tr></thead><tbody><tr><td>Бесплатный завтрак</td>'+''.join('<td><img src="/content/bonus/b-'+flag+'-icon.svg"></td>' for flag in ['no','no','no','yes'])+'</tr></tbody></table><div class="t-note1">Только в отелях.</div>',
}
S7={'offer':{'partners':{'flowwow':{'offer':{'code':'flowwow','content2':'Скидка 17% на первый заказ и 500 миль','outLink':'https://example.invalid/DO_NOT_COPY'},'partner':{'code':'flowwow','description':'Флаувау — маркетплейс подарков','priorityDetails':{'rule':'Скидка 17% на первый заказ на «Флаувау» и 500 миль в подарок','details':'Скидка не суммируется с другими акциями.','steps':['Оформите первый заказ от 1500 ₽.']}},'category':{'content1':'Подарки'},'otherOffers':[{'description':'UNRELATED_CANARY 99%'}]}}}}
P={'xml_id':'mir-aeroexpress-fixture','url':'/promo/transport/ekspress-v-aeroport-s-vygodoy-i-komfortom-1/','name':'Аэроэкспресс','owner':{'name':'Аэроэкспресс'},'desc':{'number':{'PREFIX':'Кешбэк ','AMOUNT':'5%'},'text':'за оплату через СБП'},'startDate':'01.05.2026','endDate':'30.09.2026','status':'active','promoBadges':[{'text':'СБП'}],'templates':[{'templateName':'conditions','templateTitle':'Условия','templateText':'Максимальный кешбэк 1 500 ₽ в месяц.'}],'freeFormBlock':'Оплата через СБП','iframe':{'token':'SYNTHETIC_CANARY'}}
MIR={'data':{'content':{'promoDetail':{'promo':{'promoAction':P}}}}}
F['s7_detail.json']=json.dumps(S7,ensure_ascii=False)
F['mir_detail.json']=json.dumps(MIR,ensure_ascii=False)
def fixture(name):return F[name]
