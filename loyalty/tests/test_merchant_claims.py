import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import merchant_blocks as b
import merchant_claims as c

T={'merchant':'Synthetic','program':'Example Club','aliases':['EC']}

def checked(md, offer, completeness='provider_markdown'):
    d=b.build(md,url='https://example.test/',observed_at='2026-09-25T00:00:00Z',completeness=completeness)
    out={'source_sha256':d['source_sha256'],'state':'candidates','notes':'','offers':[offer]}
    return d,b.check(T,d,out)

class AtomicClaims(unittest.TestCase):
    def test_source_bound_atomic_audience_and_benefit_claims(self):
        md='## Example Club\n\nДержателям EC предоставляется скидка 20%.\n'
        offer={'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],
               'conditions':[],'redemption':[],
               'code':{'state':'not_stated','value':'','refs':[]},
               'dates':[],'uncertainties':[]}
        d,r=checked(md,offer)
        bundle=c.generate(T,d,r)
        self.assertEqual(bundle['source_sha256'],d['source_sha256'])
        self.assertEqual([x['kind'] for x in bundle['claims']],['audience','benefit'])
        self.assertEqual(bundle['claims'][0]['evidence_refs'],['b0001'])
        self.assertEqual(bundle['claims'][1]['evidence_refs'],['b0001'])
        self.assertEqual(bundle['claims'][0]['premise'],r['offers'][0]['source_context']['text'])
        self.assertFalse(bundle['publication_allowed'])

    def test_conditions_are_separate_atomic_claims(self):
        md='## Example Club\n\nДержателям EC скидка 20%.\n\nМинимальная сумма 1000 рублей.\n\nНе суммируется с другими скидками.\n'
        offer={'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],
               'conditions':['b0002','b0003'],'redemption':[],
               'code':{'state':'not_stated','value':'','refs':[]},
               'dates':[],'uncertainties':[]}
        d,r=checked(md,offer)
        bundle=c.generate(T,d,r)
        cond=[x for x in bundle['claims'] if x['kind']=='condition']
        self.assertEqual(len(cond),2)
        self.assertEqual([x['evidence_refs'] for x in cond],[['b0002'],['b0003']])

    def test_code_delivery_is_separate_claim(self):
        md='## Example Club\n\nДержателям EC скидка 20%.\n\nПолучите промокод в приложении EC.\n'
        offer={'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],
               'conditions':[],'redemption':['b0002'],
               'code':{'state':'app_or_account','value':'','refs':['b0002']},
               'dates':[],'uncertainties':[]}
        d,r=checked(md,offer)
        bundle=c.generate(T,d,r)
        code=[x for x in bundle['claims'] if x['kind']=='code_delivery']
        self.assertEqual(len(code),1)
        self.assertEqual(code[0]['evidence_refs'],['b0002'])
        self.assertIn('приложении или аккаунте',code[0]['hypothesis'])

    def test_booking_and_stay_claims_do_not_collapse_roles(self):
        md=('## Example Club\n\nДержателям EC скидка 12%.\n\n'
            'Забронировать нужно до 30 ноября 2026 года.\n\n'
            'Период проживания: с 1 декабря 2026 года по 28 февраля 2027 года.\n')
        offer={'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],
               'conditions':[],'redemption':[],
               'code':{'state':'not_stated','value':'','refs':[]},
               'dates':[{'role':'booking','refs':['b0002']},{'role':'stay','refs':['b0003']}],
               'uncertainties':[]}
        d,r=checked(md,offer)
        bundle=c.generate(T,d,r)
        dates=[x for x in bundle['claims'] if x['kind']=='date_role']
        self.assertEqual([x['role'] for x in dates],['booking','stay'])
        self.assertIn('бронирования',dates[0]['hypothesis'])
        self.assertIn('проживания',dates[1]['hypothesis'])
        self.assertNotEqual(dates[0]['hypothesis'],dates[1]['hypothesis'])

    def test_missing_audience_is_incomplete_not_unrestricted(self):
        md='## Example Club\n\nСкидка 20%.\n'
        offer={'program':['b0000'],'audience':[],'benefit':['b0001'],
               'conditions':[],'redemption':[],
               'code':{'state':'not_stated','value':'','refs':[]},
               'dates':[],'uncertainties':[]}
        d,r=checked(md,offer)
        bundle=c.generate(T,d,r)
        self.assertEqual(bundle['status'],'review_required')
        self.assertIn('audience_missing',bundle['reasons'])
        self.assertFalse(any(x['kind']=='audience' for x in bundle['claims']))

    def test_excerpt_provenance_keeps_bundle_review_only(self):
        md='## Example Club\n\nДержателям EC предоставляется скидка 20%.\n'
        offer={'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],
               'conditions':[],'redemption':[],
               'code':{'state':'not_stated','value':'','refs':[]},
               'dates':[],'uncertainties':[]}
        d,r=checked(md,offer,'source_excerpt')
        bundle=c.generate(T,d,r)
        self.assertEqual(bundle['status'],'review_required')
        self.assertIn('source_is_excerpt',bundle['reasons'])

if __name__=='__main__':unittest.main()
