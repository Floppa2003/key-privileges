"""Real collector scopes: disabling attachments must not disable offers."""
import json,tempfile,unittest
from datetime import datetime
from pathlib import Path
from test_rzd_external import r,Network,NOW,PDF
from test_coral_linked_rules import rules,parent

class PracticalCollectionTests(unittest.TestCase):
    def test_rzd_keeps_tour_offer_and_bank_link_without_pdf_download(self):
        net=Network()
        with tempfile.TemporaryDirectory() as d:
            reader=r.Reader(d,get=net,sleep=lambda _:None)
            b=r.collect(reader,'7:1',NOW,include_bank_documents=False)
        self.assertNotIn(PDF,[u for u,_ in net.calls])
        self.assertEqual({x['source_id'] for x in b['records']},{'rzd_tour_conditions','rzd_unicredit_reference'})
        report=next(x for x in b['sources'] if x['source_id']=='rzd_unicredit_rules')
        self.assertEqual(report['status'],'out_of_scope');self.assertEqual(report['failed'],0)
        bank=next(x for x in b['records'] if x['source_id']=='rzd_unicredit_reference')
        self.assertEqual(bank['details']['public_bank']['documents'][0]['url'],PDF)
    def test_coral_discovery_keeps_lounge_but_not_general_contract(self):
        a=parent(link='https://coralbonus.ru/pravila-programmy/')
        b=parent(link='https://coralbonus.ru/pravila-oformleniya-zayavki-v-biznes-zal/')
        found=rules.discover([a,b])
        self.assertEqual([x['url'] for x in found],['https://coralbonus.ru/pravila-oformleniya-zayavki-v-biznes-zal/'])
