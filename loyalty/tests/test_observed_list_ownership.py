"""Observed source formulations: list labels, delivery ownership and ceilings.

The wording and numbers below are minimal excerpts encountered in the native
source review; identifying programme/partner labels alone are anonymized.
"""
import copy
import json
import unittest

from normalized import normalize_rates
from unified_normalization import make_input, normalize_record


class ObservedListOwnershipTests(unittest.TestCase):
    def common(self, body, *, activation=''):
        fields = {
            'Программа': 'Карта', 'Партнёр': 'Партнёр',
            'Заголовок': 'Предложение', 'Тип записи': 'partner_offer',
            'Выгода': body, 'Условия': body, 'Как получить': activation,
            'Источник': 'https://example.com/offer',
            'Тип ссылки': 'page_block', 'Получено UTC': '2026-11-14T00:00:00Z',
            'Статус источника': 'published', 'Промокоды JSON': '[]',
            'Ставки JSON': '[]', 'Ограничения JSON': '[]',
            'Детали JSON': json.dumps({}),
        }
        raw = make_input({'id': 'observed:source-list', 'origin': 'parser_offers',
                          'row': 2, 'fields': {k: {'value': v} for k, v in fields.items()}})
        original = copy.deepcopy(raw)
        result = normalize_record(raw, as_of='2026-11-14')
        self.assertEqual(raw, original)
        self.assertEqual(result['raw'], original)
        for term in result['benefits'] + result['conditions']:
            if term['evidence']['path'] in ('/benefit', '/conditions', '/activation'):
                self.assertIn(term['evidence']['text'], raw[term['evidence']['path'][1:]])
        return result

    def assert_rates(self, body, expected):
        source = normalize_rates(body)
        self.assertEqual([(r['kind'], r['value']) for r in source], expected)
        for rate in source:
            self.assertIn(rate['evidence'], body)
        common = self.common(body)
        self.assertEqual([(b['kind'], b['value']) for b in common['benefits']], expected)
        return common

    def test_explicit_discount_heading_owns_its_two_tour_bullets(self):
        body = ('Держателям карты предоставляются следующие скидки:\n'
                '- 5% на однодневные экскурсии по Карелии;\n'
                '- 8% на многодневные туры по Карелии при предъявлении карты в офисе перед оплатой.\n'
                'Скидка по карте распространяется на все туры и экскурсии, указанные на сайте, '
                'и не суммируется с другими акциями и предложениями.')
        result = self.assert_rates(body, [('discount', '5'), ('discount', '8')])
        self.assertIn('однодневные', result['benefits'][0]['evidence']['text'])
        self.assertIn('многодневные', result['benefits'][1]['evidence']['text'])

    def test_cashback_heading_owns_card_level_bullets_in_activation(self):
        activation = ('– Оплачивайте любой курс на сайте или в кассах учебных центров '
                      'зарегистрированной картой «Мир» или Mir Supreme и получайте кешбэк:\n'
                      '7% — для премиальных карт Mir Supreme,\n'
                      '5% — для других карт «Мир»\n'
                      '– Список адресов учебных центров, участвующих в акции, указан ниже в пункте «Адреса»')
        self.assertEqual([(r['kind'], r['value']) for r in normalize_rates(activation)],
                         [('cashback', '7'), ('cashback', '5')])
        result = self.common('за оплату курсов от учебного центра', activation=activation)
        self.assertEqual([(b['kind'], b['value'], b['evidence']['path']) for b in result['benefits']],
                         [('cashback', '7', '/activation'), ('cashback', '5', '/activation')])

    def test_service_name_before_the_rate_keeps_heading_ownership(self):
        body = ('Держателям карты при предъявлении карты администратору центра до совершения '
                'оплаты предоставляются скидки:\n'
                '- на все массажи – 22%;\n'
                '- консультация специалиста Аюрведы – 33%;\n'
                '- на все СПА-программы – 60%.')
        self.assert_rates(body, [('discount', '22'), ('discount', '33'), ('discount', '60')])

    def test_library_list_does_not_turn_filling_percent_into_a_discount(self):
        body = ('Держателям карты предоставляются скидки на следующие услуги:\n'
                '- 32% на распечатку текста на принтере: черно-белая печать, форматы А4, А3, '
                '28% - на цветную печать, форматы А4, А3;\n'
                '- 10% на распечатку иллюстрированного материала на принтере '
                '(от 50% заполнения листа, черно-белая и цветная печать, форматы А4, А3);\n'
                '- 12% на ксерокопирование иллюстрированных документов '
                '(от 50% заполнения листа, черно-белая и цветная печать) форматы А4, А3.')
        self.assert_rates(body, [('discount', '32'), ('discount', '28'),
                                 ('discount', '10'), ('discount', '12')])

    def test_separate_bonus_service_does_not_inherit_discount_heading(self):
        body = ('Держателям карты при предъявлении карты перед оплатой тура в офисе туроператора '
                'предоставляются следующие скидки:\n'
                '– 3% на путевки детского отдыха в Крым;\n'
                '– 5% на авторские интерактивные программы;\n'
                '– бонусная услуга в размере 3% от суммы договора на организацию выпускного '
                'праздника: украшение шарами, видеоклип, фотосъемка, торт, тиражирование дисков.')
        self.assert_rates(body, [('discount', '3'), ('discount', '5')])

    def test_bare_list_rate_retains_the_following_service_scope(self):
        body = ('Держателям карты предоставляются следующие скидки:\n'
                '10%\n'
                '- на проведение компьютерной томографии, магнитно-резонансной томографии;\n'
                '- кастрацию кота (при проведении операции инъекционным наркозом, без учета '
                'стоимости доп. исследований, расходных материалов и лекарственных средств);')
        result = self.assert_rates(body, [('discount', '10')])
        evidence = result['benefits'][0]['evidence']['text']
        self.assertIn('компьютерной томографии', evidence)
        self.assertIn('кастрацию кота', evidence)
        self.assertIn('без учета', evidence)

    def test_same_sentence_wrapped_second_discount_keeps_its_rate(self):
        body = ('Держателям карты при предъявлении карты перед оплатой предоставляется '
                'скидка 10% на диагностику\nи 5% на хирургическое лечение.\n'
                'Скидка не суммируется с другими акциями и предложениями.')
        self.assert_rates(body, [('discount', '10'), ('discount', '5')])

    def test_free_delivery_minimum_is_not_a_masterclass_discount_minimum(self):
        body = ('Держателям карты предоставляется скидка 10% на участие в мастер-классе '
                'по росписи карельских пряников, а также бесплатная доставка по всей России '
                'при сумме заказа от 2500 рублей при предъявлении карты перед оплатой '
                'мастер-класса, а также при указании промокода в комментариях к заказу.')
        result = self.common(body)
        minimum, = [c for c in result['conditions'] if c['kind'] == 'minimum_purchase']
        self.assertEqual((minimum['value'], minimum['unit']), ('2500', 'RUB'))
        discount, = result['benefits']
        self.assertEqual((discount['kind'], discount['value']), ('discount', '10'))
        self.assertNotIn(minimum['id'], discount['condition_ids'])

    def test_combined_discount_ceiling_is_a_condition_not_an_extra_reward(self):
        body = ('Скидки по карте суммируются с другими акциями и предложениями Центра, '
                'но общая сумма скидок не должна превышать 15%.')
        self.assertEqual(normalize_rates(body), [])
        result = self.common(body)
        self.assertEqual(result['benefits'], [])
        cap, = [c for c in result['conditions'] if c['kind'] == 'benefit_cap']
        self.assertEqual((cap['value'], cap['unit'], cap['qualifier']), ('15', 'percent', 'up_to'))

    def test_bonus_equivalence_does_not_assert_an_upfront_discount(self):
        body = ('Для держателей карты действует бонусная программа. Бонусы начисляются по '
                'основному перечню медицинских услуг, за исключением услуг Отделения ВРТ '
                'и медицинских анализов.\n'
                'Размер начисленных бонусов соответствует скидке 11%.\n'
                'Бонусами можно оплатить до 25% стоимости медицинских услуг.\n'
                'Списание бонусов в счет оплаты медицинских услуг возможно на следующий '
                'день с момента начисления бонусов.')
        self.assertEqual(normalize_rates(body), [])
        result = self.common(body)
        self.assertEqual(result['benefits'], [])
        self.assertIn('11%', result['raw']['benefit'])
        self.assertIn('25%', result['raw']['benefit'])


if __name__ == '__main__':
    unittest.main()
