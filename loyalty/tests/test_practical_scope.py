"""Keep usable offers while excluding identified bulk document expansions."""
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:import practical_scope as p
except ImportError:p=None

class PracticalScopeTests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(p,'Practical publication scope has not been implemented')
    def test_offer_and_short_rule_are_not_removed_by_kind_or_missing_rate(self):
        for kind in ('partner_offer','program_rules','source_observation'):
            self.assertIsNone(p.exclusion_reason({},'https://example.test/offer','Карта',kind))
    def test_short_pdf_privilege_is_kept_without_inventing_a_rate(self):
        d={'live_document_text':True,'page_count':1,'document_part':{'number':1,'total':1}}
        self.assertIsNone(p.exclusion_reason(d,'https://example.test/offer.pdf','20% ко дню рождения','program_rules'))
    def test_multipart_contract_and_long_unparsed_pdf_are_out_of_scope(self):
        for d in ({'live_document_text':True,'page_count':33,'document_part':{'number':1,'total':6}},
                  {'live_document_text':True,'page_count':8,'document_part':{'number':1,'total':1}}):
            self.assertEqual(p.exclusion_reason(d),'bulk_document')
    def test_pharmacy_lists_are_not_offers_even_with_small_page_text(self):
        self.assertEqual(p.exclusion_reason({'products_are_exclusions_not_offers':True}),'product_exclusion_list')
    def test_scoped_pdf_clause_parser_is_not_removed_with_full_transcripts(self):
        self.assertIsNone(p.exclusion_reason({'page_count':8,'extraction_method':'native_pdf_text_with_reviewed_clause_parser','deposit_reward_tiers':[{}]}))
    def test_general_coral_contract_not_short_lounge_instructions(self):
        self.assertEqual(p.exclusion_reason({},'https://coralbonus.ru/pravila-programmy/'),'general_contract')
        self.assertIsNone(p.exclusion_reason({},'https://coralbonus.ru/pravila-oformleniya-zayavki-v-biznes-zal/'))
    def test_clinic_exclusions_and_price_appendices_are_not_discount_records(self):
        d={'live_document_text':True,'page_count':2,'retrieval_method':'ekp_source_linked_rules_v1'}
        self.assertEqual(p.exclusion_reason(d),'bulk_appendix')
        self.assertIsNone(p.exclusion_reason({'retrieval_method':'ekp_source_linked_rules_v1'},'https://vamprivet.ru/supreme-restaurants'))
    def test_pre_download_general_rule_link_filter_keeps_specific_privilege(self):
        self.assertFalse(p.follow_document_link('https://ut0.ru/new','Полные правила программы'))
        self.assertTrue(p.follow_document_link('https://ut0.ru/other','Персональная скидка на мерч'))
    def test_worksheet_projection_does_not_mutate_source_or_claim_source_failure(self):
        def row(i,d):
            r=['']*25;r[0]=i;r[1]='Programme';r[5]='program_rules';r[17]='https://example.test/'+i;r[20]=json.dumps(d);return r
        report=['r:s','r','s','Programme','https://example.test/','ok','2','2','0','catalogue','','[]','2026-09-18','v']
        rows={'parser_offers':[row('large',{'products_are_exclusions_not_offers':True}),row('useful',{})],'parser_coverage':[report]}
        before=copy.deepcopy(rows);out=p.publication_rows(rows)
        self.assertEqual(rows,before)
        self.assertEqual([r[0] for r in out['parser_offers']],['useful'])
        self.assertEqual(out['parser_coverage'][0][5],'ok')
        self.assertEqual(out['parser_coverage'][0][8],'0')
        self.assertIn('publication_scope',json.loads(out['parser_coverage'][0][9]))
    def test_input_guard_does_not_hide_private_legacy_rows(self):
        rows=[{'id':'a','origin':'parser_offers','details':{'products_are_exclusions_not_offers':True}},
              {'id':'b','origin':'parser_offers','details':{},'kind':'program_rules'},
              {'id':'c','origin':'VG_community_offers','details':{'products_are_exclusions_not_offers':True}}]
        kept,excluded=p.select_inputs(rows)
        self.assertEqual([r['id'] for r in kept],['b','c']);self.assertEqual(excluded,{'product_exclusion_list':1})

if __name__=='__main__':unittest.main()
