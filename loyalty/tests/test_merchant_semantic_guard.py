import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_blocks as b
import merchant_semantic_guard as g
import merchant_claims as claims

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


class AtomicClaims(unittest.TestCase):
    def test_claims_use_only_selected_evidence(self):
        md='## Example Club\n\nДержателям EC предоставляется скидка 20%.\n\n## Other Club\n\nБесплатный подарок.\n'
        r=checked(md,{'state':'candidates','offers':[{'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],'conditions':[],'redemption':[],'code':{'state':'not_stated','value':'','refs':[]},'dates':[],'uncertainties':[]}]})
        out=claims.build_claims(T,r)
        benefit=next(x for x in out['offers'][0]['claims'] if x['kind']=='benefit')
        self.assertEqual(benefit['evidence_block_ids'],['b0001'])
        self.assertEqual(benefit['evidence_text'],'Держателям EC предоставляется скидка 20%.\n')
        self.assertNotIn('Other Club',benefit['evidence_text'])

    def test_missing_audience_is_explicit_completeness_gap(self):
        md='## Example Club\n\nСкидка 20%.\n'
        r=checked(md,{'state':'candidates','offers':[{'program':['b0000'],'audience':[],'benefit':['b0001'],'conditions':[],'redemption':[],'code':{'state':'not_stated','value':'','refs':[]},'dates':[],'uncertainties':[]}]})
        out=claims.build_claims(T,r)
        self.assertEqual(out['offers'][0]['coverage']['missing_required'],['audience'])
        self.assertFalse(any(x['kind']=='audience' for x in out['offers'][0]['claims']))

    def test_booking_and_stay_claims_are_distinct(self):
        md='## Example Club\n\nДержателям EC скидка 12%.\n\nЗабронировать до 30 ноября 2026 года.\n\nПериод проживания: с 1 декабря 2026 по 28 февраля 2027.\n'
        d=b.build(md,url='https://example.test/',observed_at='x')
        o={'source_sha256':d['source_sha256'],'state':'candidates','notes':'','offers':[{'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],'conditions':[],'redemption':[],'code':{'state':'not_stated','value':'','refs':[]},'dates':[{'role':'booking','refs':['b0002']},{'role':'stay','refs':['b0003']}],'uncertainties':[]}]}
        out=claims.build_claims(T,b.check(T,d,o))
        dates=[x for x in out['offers'][0]['claims'] if x['kind']=='date']
        self.assertEqual([x['role'] for x in dates],['booking','stay'])
        self.assertEqual(dates[0]['hypothesis'],'The cited text states a booking date, booking period, or booking deadline for the target loyalty-program offer.')
        self.assertEqual(dates[1]['hypothesis'],'The cited text states a stay date, stay period, check-in date, or check-out date for the target loyalty-program offer.')

    def test_app_code_claim_does_not_invent_literal(self):
        md='## Example Club\n\nДержателям EC скидка 20%.\n\nПолучите промокод в приложении EC.\n'
        d=b.build(md,url='https://example.test/',observed_at='x')
        o={'source_sha256':d['source_sha256'],'state':'candidates','notes':'','offers':[{'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],'conditions':[],'redemption':['b0002'],'code':{'state':'app_or_account','value':'','refs':['b0002']},'dates':[],'uncertainties':[]}]}
        out=claims.build_claims(T,b.check(T,d,o))
        code=next(x for x in out['offers'][0]['claims'] if x['kind']=='code')
        self.assertEqual(code['role'],'app_or_account')
        self.assertIsNone(code['normalized_value'])
        self.assertEqual(code['evidence_block_ids'],['b0002'])

if __name__=='__main__': unittest.main()
