"""Practical, reader-facing catalogue; raw evidence is not a discount.

No network/LLM/guessed rates. All rendered claims come from their own record.
The private source tables are untouched. Rebuild on every verified publication;
do not reintroduce a checkbox that turns raw posts/documents into offers.
"""
from __future__ import annotations

import re
import unicodedata
from bs4 import BeautifulSoup
from collections import Counter
from datetime import date

VERSION = "practical-catalogue-v2"
HEADERS = ["Партнёр","Программа","Выгода","Промокод / получение","Как получить",
           "Условия","Срок из источника","Категория","Проверено / получено UTC",
           "Источник","Комментарий","Тип записи","Статус срока","ID","Набор",
           "Строка","Заголовок"]
NOISE_KIND = {"announcement", "raw_page", "source_observation"}
TECHNICAL = re.compile(
    r"^(?:Подробнее[.; ]*|(?:Microsoft (?:Word|PowerPoint)|Презентация PowerPoint)\b.*|"
    r"special:[a-f0-9]+|Пресс-центр|Назад к списку|На главную|Главная|"
    r"Меню|Войти|Регистрация|Поделиться|Все права защищены.*|Показать еще|Показать ещё|Найти|"
    r"Любой возраст|Все клиники|Сейчас открыто|Условия акции:?|Правила акции|Подробнее о сроках|"
    r"Подробнее об участниках акции|Все преимущества карты Mir Supreme|"
    r"Политика (?:конфиденциальности|обработки персональных данных).*|"
    r"Согласие на обработку персональных данных.*|Промокод скопирован|"
    r"Скопировать промокод|Получайте|Для получения бонусов необходимо перейти по ссылке|Специально для вас:|Реклама[.: ].*|erid[: ].*|"
    r"Что-то пошло не так.*|Сервис недоступен.*|502 Bad Gateway|Возврат к списку|"
    r"Подробнее о сроках здесь|Сайт партнёра|ВАЖНО!|Перейти на сайт партнёра|"
    r"Условия проведения и|Наши партнёры|О партнёре|Услуги и сервисы)$", re.I)
OFFER = re.compile(
    r"[сc]кидк|к[еэ]шб[еэ]к|cashback|discount|\bfree\b|бесплат|"
    r"в подарок|дарим|дарит|комплимент|угоща|"
    r"(?:двойн|дополнительн|начисл|получ|копи|накапл|трать|обмен|оплат|"
    r"использ|возвращ|возмещ).{0,70}?(?:мил[яьиией]|балл|бонус|₽|руб)|"
    r"(?:мил[яьиией]|балл|бонус).{0,55}?(?:\d|начисл|потрач|покуп|копи|оплат)|"
    r"специальн\w* (?:цен|тариф)|льготн|сниженн\w* цен|"
    r"ранн\w* заезд|поздн\w* выезд|повышени\w* категори|апгрейд|upgrade|"
    r"приоритетн\w* (?:бронирован|обслуживан|размещен)|"
    r"(?:доступ|подписк|статус).{0,60}(?:в состав|включ|предоставл|Silver|Bronze)|"
    r"\d.{0,15}(?:вместо|\bГБ\b|gigabyte)|"
    r"(?:десерт|коктейль|бокал|напиток).{0,100}(?:заказ|предъяв|демонстрац)|"
    r"гаранти\w*.{0,50}номера|без сборов|без комисси|"
    r"без доплат|сбор не оплачивается|доступ в бизнес|приоритетная бронь|"
    r"сохранени\w* уровн|повышени\w* класса обслуживания|"
    r"(?:SIM-карту|статус).{0,50}Selection|"
    r"при демонстрации карты|при предъявлении карты|специальные условия|"
    r"эксклюзивн\w* предложен|сертификат.{0,35}\d|"
    r"(?:\d[\d \u00a0]*\s*(?:балл\w*|бонус\w*|мил[ьи]|ГБ|Мб)\b)|"
    r"за 1\s*(?:₽|руб)|промокод на подписку|спецтариф|special rates|"
    r"\d.{0,12}мил(?:я|и|ей|ями)|мил(?:я|и|ей|ями).{0,70}\d|"
    r"оплачивайте.{0,60}балл|предоставляется статус", re.I)
ACTION = re.compile(
    r"промокод|кодовое слово|код[: ]|предъяв|покаж|демонстр|"
    r"воспользова|получить (?:скидк|промо|код|предлож)|"
    r"активир|авториз|зарегистр|перейд|перейти|введи|ввод|"
    r"укаж|указа|заброни|брониров|оформ|заказ|подключ|"
    r"при оплат|оплатить|запис|обрати|свяж|позвон|звонк|телефон|"
    r"\bhttps?://|\bwww\.|[\w.+-]+@[\w.-]+", re.I)
RULE = re.compile(
    r"услов|огранич|не (?:действ|распростр|суммир|совмещ|участв|начисл|предостав|"
    r"может|допуска|примен|включ|более|менее)|за исключени|кроме|исключен|"
    r"только|исключительно|при наличии|на усмотрени|"
    r"перв\w* (?:заказ|покуп|визит)|повторн|последующ|"
    r"минимальн|максимальн|лимит|стоимост|цен[аеыу]|тариф|"
    r"возврат|отмен|срок|период|дат[аыу]|действу|действия|"
    r"начисл|списан|оплат|баланс|уровн|категори\w* (?:карт|номер)|"
    r"участник|владел|держател|член\w* |клиент\w* сервис|"
    r"день рожд|ежемесяч|суток|часов|ночей|дней|месяц|"
    r"понедельник|вторник|сред[ау]|четверг|пятниц|суббот|воскресень|"
    r"январ|феврал|март|апрел|ма[йяе]|июн|июл|август|сентябр|октябр|ноябр|декабр|"
    r"доставк|курьер|СБП|QR|MCC|алкогол|табач|акцион|"
    r"нужн|необходим|обязательн|включен|исключен|"
    r"member|eligible|minimum|maximum|valid|only|except|exclude|not combin|"
    r"first|subsequent|purchase|booking|registration|validity|expires", re.I)
EMPTY_RULE = re.compile(
    r"^(?:По условиям конкретного предложения на странице программы|"
    r"По условиям карточки партн[её]ра|По условиям партн[её]ра|"
    r"Актуально|Требует проверки|Не указан[оы]?|Not specified|"
    r"Условия уточняйте на сайте|Скидки и акции|Привилегия|"
    r"Полный каталог официальной страницы программы|Текущий по каталогу|"
    r"Список доступных для замены сервисов|Сведения есть только в старой подборке|"
    r"Услугу предоставляет .+ИНН \d+|Рекламодатель[: ].+)$", re.I)
DEAD = re.compile(
    r"текущей активной кампании .*не найдено|"
    r"(?:акция|предложение|кампания) (?:завершена|завершено|закончилась|не действует)|"
    r"^Промокод не найден$|^Нет действующих", re.I)
ROLE = {"partner_offer":"Предложение","legacy_offer":"Предложение",
        "tier_benefit":"Привилегия уровня","membership_plan":"Условия участия",
        "campaign":"Акция","program_rules":"Привилегия / правила"}
DELIVERY = {"app":"в приложении","account":"в личном кабинете","sms":"по SMS",
            "email":"по электронной почте","concierge":"через консьержа",
            "phone":"по телефону","form":"через форму","personal_manager":"у менеджера"}

def text(value):
    return "" if value is None else str(value)

def compact(value):
    return re.sub(r"\s+", " ", text(value)).strip()

def key(value):
    return compact(unicodedata.normalize("NFKC", text(value))).casefold().replace("ё","е")

def clause_key(value):
    return re.sub(r"^[–—•* -]+|[.;: ]+$","",key(value))

def unique_clauses(parts):
    seen=set();out=[]
    for part in parts:
        k=clause_key(part)
        if k and k not in seen:seen.add(k);out.append(part)
    return out

def clean_plain(value):
    """Whitespace, rendering debris and exact non-content lines, not paraphrase."""
    value=text(value).replace("\u00ad","").replace("\ufeff","").replace("\u200b","")
    value=re.sub(r"\[Страница \d+; позиция \d+\]\s*", "", value)
    value=re.sub(r"[ \t\u00a0\u202f]+", " ", value)
    value=re.sub(r" – (?=(?:Зарегистр|Ваш |Предъяв|Кешбэк|Оплат|Перед |При |Введ|Бонус|Скидк|Получ|Для |Воспольз|Список|Правила|Участв|Выбер|Подтверд|Акци|Перейд|Успей|Проверь))", "\n– ",value)
    lines=[]
    for line in value.splitlines():
        line=line.strip()
        if not re.search(r"[A-Za-zА-Яа-яЁё0-9]",line):continue
        line=re.sub(r"^[•●▪▫►▶➤✓✔✅🔸🔹🟡🟢⚪❤️\s]+","",line).strip()
        if TECHNICAL.fullmatch(line):continue
        if lines and line==lines[-1]:continue
        lines.append(line)
    return "\n".join(lines)

def units(value):
    """Keep paragraph ownership. Join line wraps only within one sentence."""
    lines=clean_plain(value).splitlines(); combined=[]
    for line in lines:
        if combined and (
            re.match(r"^[а-яёa-z]",line)
            or re.search(r"(?:\bи|\bили|\bна|\bот|\bдо|\bпри|\bс|\bза|\bв|\bиз|дарит|дарим|составляет|[«\"])\s*$",combined[-1],re.I)
        ) and not re.match(r"^(?:https?://|www\.)",line):
            combined[-1]+=" "+line
        else:combined.append(line)
    parts=[]
    for block in combined:
        for value in re.split(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z«])",block):
            value=value.strip()
            if value and not TECHNICAL.fullmatch(value) and not EMPTY_RULE.fullmatch(value):
                parts.append(value)
    return unique_clauses(parts)

def is_boilerplate(s):
    return bool(TECHNICAL.fullmatch(s) or EMPTY_RULE.fullmatch(s))

GENERIC_LEGAL = re.compile(
    r"^(?:Настоящие [Уу]словия.*определяют порядок|"
    r"Сведения об организаторе Акции|Написанные с заглавной буквы термины|"
    r"С Правилами Программы лояльности можно ознакомиться|Информация об Акции, а также товарах|"
    r"Полный именованный состав .*по официальной справке|Официальная (?:страница|карточка)|"
    r"Изображени[ея].*носят информационн|Использование Сайта означает|"
    r"Пользовательское соглашение и технические характеристики|"
    r"ИНН \d+|ОГРН \d+|"
    r"Участие в программе позволяет копить|Получить мили можно за перелеты|"
    r"Вы сможете использовать мили на авиабилеты|Вы ещё? не являетесь участником|"
    r"Вступите в программу прямо сейчас|Теперь при покупке техники|"
    r"Теперь Вы можете не только копить|Теперь вы можете копить|"
    r"Сейчас — самое время|Готовьте ресторанные блюда|Летайте и готовьте|"
    r"Теперь выгоды от приготовления|И от полетов|Вот так просто|"
    r"Рассказываем, как пользоваться|Подробнее о сроках|"
    r"Мы предлагаем \d+ номеров|Гостиница создавалась|Каждый гость будет|"
    r"Признан ЮНЕСКО|Почему родители выбирают|Высокий сервис|"
    r"Резиденты получают навыки|Защита данных|Присоединяйтесь к нам)", re.I)
DESCRIPTIVE = re.compile(
    r"^(?:Мечтаете|Откройте для себя|Добро пожаловать|Здесь |"
    r"Наша миссия|Мы верим|Философия|В ассортименте|"
    r"Жилой комплекс .{0,100}[—–-]|"
    r".{1,65}[—–] (?:это|российск|международн|крупнейш|ведущ|лайфстайл|производител|"
    r"федеральн|уникальн|современн)|"
    r"(?:Пусть ваш|Жемчужина курортного|Для Вашего безупречного отдыха|Они уже на Вашем сч[её]те|"
    r"На помощь приходят|Иногда кажется|Ассортимент|Найдете вс[её]|Коллекции обновляются|Это вещи,|"
    r"Мы —|В основе |Вдохнов|Бренд .{0,70}это|Всего .{0,30}просторных квартир|"
    r"Если вы устали|Это не массовая|Каждый аспект|Выберите квартиру мечты)|"
    r"Компания .{1,70}воплотит вашу мечту|"
    r"Семья, забота|На сегодняшний день|Более \d+ лет)", re.I)
MARKETING = re.compile(
    r"^(?:В меню |В ресторане |Главная деталь интерьера|"
    r"Плюс домашняя|Кофе обжаривают|Коктейльная карта|С \d+:\d+ до .{0,100}здесь подают|"
    r"Умение работать с данными|Поэтому у нас для вас подарок|"
    r"Желаем вам |Школа аналитики .{0,100}помогает|Главная особенность школы|"
    r"О бренде |Мы созда[её]м|Для B2B-аудитории|Компаниям и брендам:|"
    r"Экспертам, психологам|[—–-] фирменные подарки|[—–-] корпоративные инструменты|"
    r"[—–-] игровые продукты|[—–-] авторские игры|[—–-] практические инструменты|"
    r"[—–-] продукты для продвижения|Мы превращаем подготовку|Почему именно|"
    r"(?:\d+\. )?(?:Комплексный All-in-one|Преподаватели 99-го|Гибкие форматы обучения)|"
    r"Собрали все, что потребуется|Без траты времени|Программа обучения была разработана|"
    r"У нас можно заниматься|Мы поможем вам|Одноименный|Одноимённый)",re.I)

def practical_terms(value, *, labels=()):
    src=units(value);kept=[]
    labelkeys={key(x) for x in labels if x}
    for s in src:
        if key(s) in labelkeys or is_boilerplate(s) or GENERIC_LEGAL.search(s):continue
        if MARKETING.search(s) and not re.search(r"скидк|к[еэ]шб[еэ]к|бесплат|промокод",s,re.I):continue
        if re.fullmatch(r"\d+[.)]|Сайт|Telegram|ВКонтакте|Магазин на OZON",s,re.I):continue
        if DESCRIPTIVE.search(s) and not re.search(r"скидк|к[еэ]шб[еэ]к|в подарок|бесплат|бонус\w* (?:за|при)|промокод",s,re.I):continue
        # Unknown conditions remain; only reviewed boilerplate is omitted.
        kept.append(s)
    return "\n".join(unique_clauses(kept))

def benefit_claim(s, raw=None):
    """A percentage or a normal breakfast is not, by itself, a privilege."""
    if not s or is_boilerplate(s) or ((DESCRIPTIVE.search(s) or MARKETING.search(s)) and not re.search(r"[сc]кидк|к[еэ]шб[еэ]к|в подарок|бесплат",s,re.I)):return False
    if re.search(r"двойную выгоду|родител\w* отмечают|\d+% успешных|процентил|"
                 r"поэтому .{0,30}подарок|фирменные подарки для|"
                 r"скидк\w* (?:не предоставля|не действ|не распространя)",s,re.I):return False
    if re.search(r"(?:дарит|дарим|скидка|кешбэк|бонусы|составляет|от|до|за|при|на)\s*$",s,re.I):return False
    if OFFER.search(s):return True
    if raw and len(s)<350 and re.search(r"\d\s*%",s) and (
        s in units(raw.get("benefit","")) or raw.get("details",{}).get("public_partner")
    ) and not re.search(r"успеваем|родител|населен|успешных|рынк|доходност|исследовани[яй] показ|"
                       r"оплат[аы] 100%|предоплат[аы] 100%",s,re.I):return True
    d=(raw or {}).get("details",{})
    if d.get("public_item") and re.search(r"завтрак|кредит.{0,35}(?:USD|EUR|доллар|евро)|"
                                        r"(?:USD|EUR|доллар|евро).{0,35}кредит",s,re.I):return True
    return False


def meaningful_claim(raw, terms):
    benefit=clean_plain(raw.get("benefit"))
    candidates=units(benefit)
    for i,v in enumerate(candidates[:-1]):
        if v.endswith(":") and OFFER.search(v) and re.search(r"\d",candidates[i+1]):
            candidates[i]=v+" "+candidates[i+1]
    usable=[v for v in candidates if benefit_claim(v,raw)]
    if not usable:usable=[v for v in units(terms) if benefit_claim(v,raw)]
    if not usable:
        if raw["kind"]=="legacy_offer" and benefit and len(benefit)<400 and not is_boilerplate(benefit) and not DEAD.search(benefit):return benefit
        return ""
    # Other benefit clauses and restrictions remain in the conditions.
    for value in usable:
        if len(value)<=800 and not (value.endswith(":") and not re.search(r"\d",value)):return value
    return ""

def full_code_display(n):
    literals=[]; retrieval=[]
    for c in n.get("codes",[]):
        value=c.get("value")
        if c.get("delivery")=="literal" and value:
            item="Код: "+text(value)
            if c.get("scope",{}):
                ev=c.get("evidence",{}).get("text","")
                if ev and compact(ev)!=compact(value) and len(ev)<350:item+=" — "+compact(ev)
            if item not in literals:literals.append(item)
        elif c.get("delivery"):
            method=DELIVERY.get(c["delivery"])
            if method and method not in retrieval:retrieval.append(method)
    return "\n".join(literals+["Получение: "+x for x in retrieval])
