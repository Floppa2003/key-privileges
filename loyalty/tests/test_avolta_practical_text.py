"""Practical Avolta clauses, not destination advertising or merchant statistics."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from avolta_source import practical_text

class AvoltaPracticalText(unittest.TestCase):
    def test_actual_reward_ratio_beats_generic_airline_heading(self):
        claim,terms,action=practical_text('Накапливайте баллы Radisson Rewards, совершая покупки',
            'Получайте 3 балла за 1$, потраченный на покупки в аэропорту в Швейцарии и Швеции с программой Radisson Rewards',
            'Наслаждайтесь эксклюзивными предложениями и накапливайте баллы, совершая покупки в Швейцарии и Швеции\nДля того чтобы связать Ваши аккаунты, перейдите в раздел «Аккаунт» в приложении Club Avolta.')
        self.assertIn('3 балла за 1$',claim);self.assertIn('Швейцарии и Швеции',claim)
        self.assertNotIn('Наслаждайтесь',terms);self.assertIn('Аккаунт',action)
    def test_new_customer_volume_and_extra_discount_survive_without_ratings(self):
        claim,terms,action=practical_text('Получите 2 дня БЕСПЛАТНОГО мобильного Интернета',
            'Бесплатная карта eSIM на 1 ГБ от Kolet для каждого участника',
            'Рейтинг 4,9/5 в App Store и 4,7/5 на Trustpilot\nКРОМЕ ТОГО, участники Club Avolta получают скидку 10 % на каждый последующий тарифный план Kolet.\nПодробности — в приложении Club Avolta. Предложение действительно только для новых пользователей eSIM от Kolet.')
        self.assertIn('2 дня',claim)
        for v in ('1 ГБ','10 %','только для новых'):self.assertIn(v,terms)
        self.assertNotIn('Рейтинг',terms);self.assertIn('приложении',action)
    def test_merchant_volume_not_benefit_and_rules_remain(self):
        claim,terms,_=practical_text('Сэкономьте 5% на билетах на паром','Путешествуйте на пароме выгоднее с Direct Ferries',
            'Более 4400 паромных маршрутов и свыше 900 портов в разных странах мира.\nДействуют правила и условия')
        self.assertEqual(claim,'Сэкономьте 5% на билетах на паром')
        self.assertNotIn('4400',terms);self.assertIn('условия',terms)
    def test_nonpercentage_and_geography_not_lost(self):
        _,terms,actions=practical_text('Больше бонусов для участников с Power Pass','',
            'Зарегистрируйтесь в программе King Power NAVY и получите купоны на скидку до 20 %.\nУчастники Club Avolta могут пользоваться привилегиями в Таиланде.\nАкция «Два по цене одного» на аттракционы TukTuk Quest и Mahanakhon SkyRide\nБолее подробную информацию можно найти в приложении Club Avolta.')
        for value in ('Два по цене одного','в Таиланде'):self.assertIn(value,terms)
        self.assertIn('приложении',actions)

if __name__=='__main__':unittest.main()
