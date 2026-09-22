"""Source-observed dotted shop slug and disabled inventory labels."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from backit_source import card_url, ROOT, inventory

def page(disabled=''):
    return '<div class="offers"><div class="offer-cards"><a class="mu-store__wrapper" href="/ru/cashback/shops/22.10.ru"><span class="mu-store__title">22.10.ru</span>'+disabled+'</a></div></div><div class="mu-pagination" total="1" pagesize="40" currentpage="1"></div>'

class InventoryVariants(unittest.TestCase):
    def test_dotted_shop_slug_from_actual_thirteenth_page(self):
        self.assertEqual(card_url(ROOT+'/22.10.ru'),ROOT+'/22.10.ru')
    def test_path_traversal_compilations_and_queries_stay_rejected(self):
        for tail in ['/../kuper','/..','/.','/22..10.ru','/compilation/shopsozon','/kuper?x=1','/kuper#x']:
            with self.assertRaises(ValueError):card_url(ROOT+tail)
    def test_disabled_card_counted_but_not_claimed_active(self):
        cards,total,size=inventory(page('<span>Временно отключен</span>'),1)
        self.assertEqual((total,size,len(cards)),(1,40,1))
        self.assertTrue(cards[0]['inactive'])
    def test_active_card_without_disabled_label(self):
        cards,_,_=inventory(page(),1)
        self.assertFalse(cards[0].get('inactive',False))

if __name__=='__main__':unittest.main()
