import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_blocks as b
import merchant_semantic_guard as g

T={'merchant':'Synthetic','program':'Example Club','aliases':['EC']}

def checked(md, out):
    d=b.build(md,url='https://example.test/',observed_at='2026-09-25T00:00:00Z')
    return b.check(T,d,{**out,'source_sha256':d['source_sha256'],'notes':''})

class SemanticGuard(unittest.TestCase):
    def test_clean_cardholder_offer_passes_guard_only(self):
        md='## Example Club\n\nДержателям EC предоставляется скидка 20%.\n'
        r=checked(md,{'state':'candidates','offers':[{'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],'conditions':[],'redemption':[],'code':{'state':'not_stated','value':'','refs':[]},'dates':[],'uncertainties':[]}]})
        a=g.assess_result(T,r)
        self.assertEqual(a['status'],'guard_pass_needs_independent_review')
        self.assertFalse(a['publication_allowed'])

    def test_past_school_event_rejected(self):
        md='## ЕКП\n\n24 марта прошло мероприятие для школьников.\n\nВ конце мероприятия всем участникам были вручены бесплатные билеты.\n'
        d=b.build(md,url='https://example.test/',observed_at='x')
        out={'source_sha256':d['source_sha256'],'state':'candidates','notes':'','offers':[{'program':['b0000'],'audience':[],'benefit':['b0002'],'conditions':[],'redemption':[],'code':{'state':'not_stated','value':'','refs':[]},'dates':[],'uncertainties':[]}]}
        r=b.check({'merchant':'X','program':'ЕКП','aliases':['Единая карта петербуржца']},d,out)
        a=g.assess_result({'merchant':'X','program':'ЕКП','aliases':['Единая карта петербуржца']},r)
        self.assertIn('event_not_cardholder_entitlement',a['offers'][0]['reasons'])

    def test_generic_visitors_are_not_cardholders(self):
        md='## EC\n\nДля всех гостей скидка 20%.\n'
        r=checked(md,{'state':'candidates','offers':[{'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],'conditions':[],'redemption':[],'code':{'state':'not_stated','value':'','refs':[]},'dates':[],'uncertainties':[]}]})
        self.assertIn('audience_not_explicit_beneficiary',g.assess_result(T,r)['offers'][0]['reasons'])

    def test_booking_date_cannot_be_relabeled_stay(self):
        md='## Example Club\n\nДержателям EC скидка 12%. Забронировать нужно до 30 ноября 2026 года.\n'
        d=b.build(md,url='https://example.test/',observed_at='x')
        out={'source_sha256':d['source_sha256'],'state':'candidates','notes':'','offers':[{'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],'conditions':[],'redemption':[],'code':{'state':'not_stated','value':'','refs':[]},'dates':[{'role':'stay','refs':['b0001']}],'uncertainties':[]}]}
        r=b.check(T,d,out)
        self.assertIn('date_role_not_explicit:stay',g.assess_result(T,r)['offers'][0]['reasons'])

    def test_booking_role_is_lexically_supported(self):
        md='## Example Club\n\nДержателям EC скидка 12%. Забронировать нужно до 30 ноября 2026 года.\n'
        d=b.build(md,url='https://example.test/',observed_at='x')
        out={'source_sha256':d['source_sha256'],'state':'candidates','notes':'','offers':[{'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],'conditions':[],'redemption':[],'code':{'state':'not_stated','value':'','refs':[]},'dates':[{'role':'booking','refs':['b0001']}],'uncertainties':[]}]}
        r=b.check(T,d,out)
        a=g.assess_result(T,r)
        self.assertNotIn('date_role_not_explicit:booking',a['offers'][0]['reasons'])

    def test_code_state_requires_code_language(self):
        md='## Example Club\n\nДержателям EC скидка 20%.\n\nОткройте приложение EC.\n'
        d=b.build(md,url='https://example.test/',observed_at='x')
        out={'source_sha256':d['source_sha256'],'state':'candidates','notes':'','offers':[{'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],'conditions':[],'redemption':['b0002'],'code':{'state':'app_or_account','value':'','refs':['b0002']},'dates':[],'uncertainties':[]}]}
        r=b.check(T,d,out)
        self.assertIn('code_role_not_explicit',g.assess_result(T,r)['offers'][0]['reasons'])

    def test_no_merchant_specific_names(self):
        code=Path(g.__file__).read_text()
        for s in ('academia-suites','elcom-kids','teplohodspb','artstudiom103'):
            self.assertNotIn(s,code)


if __name__=='__main__': unittest.main()
