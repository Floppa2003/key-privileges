"""A missing link target must not merge the next partner into the preceding one."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hse_alumni import parse_catalog,ROOT
from normalized import validate_offer,content_hash
from test_hse_alumni import card,page,section,NOW,common

TITLE='Морда довольна. Студия печати'
def fixture(value='23',code='PRINT_ONLY'):
    cards=card('before','Design')+card('mordapechat','Морда довольна')+card('after','Other')
    detail=section('before','<h2>Design</h2><p>Скидка 7% по промокоду DESIGN_ONLY</p>')
    detail+=f'<div class="builder-section"><h2>{TITLE}</h2><p>Скидка {value}% по промокоду {code}</p><p>Заказ по почте print@example.test; доставка отдельно.</p></div>'
    detail+=section('after','<h2>Other</h2><p>Скидка 11% по промокоду OTHER_ONLY</p>')
    return page(cards,detail)

class UnanchoredTests(unittest.TestCase):
    def test_previous_anchor_does_not_consume_other_partner(self):
        before,printed,after=parse_catalog(fixture(),NOW)
        self.assertEqual(before['promo_codes'],['DESIGN_ONLY'])
        self.assertNotIn(TITLE,before['conditions_text'])
        self.assertEqual([r['value'] for r in before['rates']],['7'])
        self.assertEqual(after['promo_codes'],['OTHER_ONLY'])
    def test_exact_reviewed_heading_recovers_own_live_terms(self):
        for value,code in [('23','PRINT_ONLY'),('16.5','CHANGED_ONLY')]:
            row=parse_catalog(fixture(value,code),NOW)[1]
            self.assertEqual(row['record_kind'],'partner_offer')
            self.assertEqual(row['promo_codes'],[code])
            self.assertEqual([r['value'] for r in row['rates']],[value])
            self.assertIn('print@example.test',row['conditions_text']);validate_offer(row)
    def test_real_root_link_not_nonexistent_anchor(self):
        row=parse_catalog(fixture(),NOW)[1]
        self.assertEqual(row['native_id'],'anchor:mordapechat')
        self.assertEqual(row['source_url'],ROOT);self.assertIsNone(row['benefit_url'])
        self.assertEqual(row['link_kind'],'page_block');self.assertIn(TITLE,row['locator'])
        self.assertEqual(common(row)['benefits'][0]['value'],'23')
    def test_missing_heading_has_no_invented_fallback(self):
        row=parse_catalog(fixture().replace('<h2>'+TITLE+'</h2>','<h2>Different business</h2>'),NOW)[1]
        self.assertEqual(row['record_kind'],'source_observation');self.assertEqual(row['promo_codes'],[])
    def test_duplicate_matching_heading_fails_closed(self):
        raw=fixture().replace('<h2>Other</h2>',f'<h2>{TITLE}</h2>')
        with self.assertRaises(ValueError):parse_catalog(raw,NOW)
    def test_explicit_different_anchor_cannot_be_borrowed(self):
        raw=fixture().replace(f'<h2>{TITLE}</h2>',f'<a name="different"></a><h2>{TITLE}</h2>')
        with self.assertRaises(ValueError):parse_catalog(raw,NOW)
    def test_added_real_anchor_takes_precedence_without_duplicate(self):
        raw=fixture().replace(f'<div class="builder-section"><h2>{TITLE}',f'<div class="builder-section"><a name="mordapechat"></a></div><div class="builder-section"><h2>{TITLE}')
        rows=parse_catalog(raw,NOW);self.assertEqual(len(rows),3)
        self.assertEqual(rows[1]['source_url'],ROOT+'#mordapechat');validate_offer(rows[1])
    def test_heading_recovery_rejects_rehashed_identity_substitution(self):
        row=parse_catalog(fixture(),NOW)[1]
        row['details']['public_catalog_block']['detail_heading']='Other business'
        from hse_alumni import block_hash
        row['details']['public_catalog_block']['identity_method']='reviewed_heading'
        row['details']['source_block_sha256']=block_hash(row['details']['public_catalog_block'])
        row['content_sha256']=content_hash(row)
        with self.assertRaises(ValueError):validate_offer(row)
    def test_hidden_heading_and_other_programme_body_not_used(self):
        raw=fixture().replace(f'<div class="builder-section"><h2>{TITLE}',f'<div class="builder-section" hidden><h2>{TITLE}')
        row=parse_catalog(raw,NOW)[1]
        self.assertEqual(row['record_kind'],'source_observation')

if __name__=='__main__':unittest.main()
