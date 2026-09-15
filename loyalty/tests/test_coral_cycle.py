"""The complementary run changes selection, never the observation timestamp."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1]))
import coral_catalog as c
from free_access_probe import ProbeError
from test_coral_catalog import root, promo, NOW


class CycleTests(unittest.TestCase):
    def collect(self, other_half=False):
        reads=[]
        class Reader:
            def __init__(self,*a,**kw):
                self.allowed=set();self.reserved=0;self.calls=0;self.known_charged_credits=0;self.halted=False
            def preflight(self):pass
            def read(self,url,*,browser):
                reads.append(url);self.calls+=1
                if url.endswith('/robots.txt'):return 200,'User-agent: *\nAllow: /',1
                if url==c.PROMO+'future/':return 200,promo(),1
                raise ProbeError('provider_http_404')
        with tempfile.TemporaryDirectory() as tmp:
            sources=[]
            for sid,url in [('coral',c.CLUB),('coral_promo',c.PROMO)]:
                raw=root(sid);Path(tmp,sid+'.html').write_text(raw)
                sources.append({'source_id':sid,'status':'candidate_requires_review','origin_http_status':200,
                    'final_url':url,'sanitized_dom_sha256':hashlib.sha256(raw.encode()).hexdigest()})
            with patch.object(c,'FreeReader',Reader), patch.object(c,'now',lambda:NOW):
                result=c.collect({'sources':sources,'run_id':'fixture','commit':'fixture'},tmp,'fixture',NOW,
                    sleep=lambda _:None,other_half=other_half)
        return result,reads

    def test_complement_is_disjoint_and_covers_current_index(self):
        first,_=self.collect();second,_=self.collect(True)
        a=first['coral']['meta'];b=second['coral']['meta']
        self.assertEqual(a['category_shard']+b['category_shard'],1)
        self.assertFalse(set(a['selected_categories']) & set(b['selected_categories']))
        self.assertEqual(set(a['selected_categories'])|set(b['selected_categories']),{c.CLUB+'one/',c.CLUB+'two/'})
        self.assertEqual(a['selection_mode'],'utc_day_half')
        self.assertEqual(b['selection_mode'],'complementary_half')

    def test_timestamp_and_promo_selection_are_not_changed(self):
        a,ar=self.collect();b,br=self.collect(True)
        self.assertEqual(a['coral_promo']['records'],b['coral_promo']['records'])
        self.assertEqual(a['coral_promo']['records'][0]['observed_at'],NOW)
        self.assertEqual([u for u in ar if '/promo/' in u],[u for u in br if '/promo/' in u])

    def test_non_boolean_selector_rejected_before_transport(self):
        for value in ('1',1,None):
            with self.subTest(value=value),patch.object(c,'FreeReader') as reader,self.assertRaises(ValueError):
                c.collect({},'does-not-exist','fixture',NOW,other_half=value)
            reader.assert_not_called()


if __name__=='__main__':unittest.main()
