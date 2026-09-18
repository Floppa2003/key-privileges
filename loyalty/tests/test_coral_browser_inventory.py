import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import coral_browser_inventory as b
from test_coral_catalog import doc

class InventoryTests(unittest.TestCase):
    def page(self,key='new',offer='fresh',rate='Changed source'):
        url=b.c.CLUB+key+'/'
        return {'url':url,'final_url':url,'origin_http_status':200,'html':doc('<section><h1>'+key+'</h1><div id="categoryProductsList"><div class="product-box referal"><a href="'+url+offer+'/">'+rate+'</a></div><div class="product-box base">Ordinary item</div></div></section>',url)}
    def test_current_rendered_membership_not_fixed_inventory(self):
        p=self.page();r=b.assemble([{'url':p['url'],'title':'new'}],[],[p],{})
        self.assertTrue(r['complete']);self.assertEqual(r['interactive_not_sitemap'],[p['url']+'fresh/']);self.assertEqual(r['excluded_merchandise_boxes'],1)
        q=self.page(offer='replacement');self.assertNotEqual(b.assemble([{'url':q['url'],'title':'new'}],[],[q],{})['interactive_offer_urls'],r['interactive_offer_urls'])
    def test_incomplete_or_failed_category_not_empty_success(self):
        p=self.page();cats=[{'url':p['url'],'title':'new'}]
        self.assertFalse(b.assemble(cats,[],[],{})['complete'])
        self.assertFalse(b.assemble(cats,[],[{'url':p['url'],'error':'origin_http_403'}],{})['complete'])
    def test_foreign_duplicate_or_wrong_response_rejected(self):
        p=self.page();cats=[{'url':p['url'],'title':'new'}]
        for pages in [[p,p],[{**p,'final_url':b.c.CLUB}],[{**p,'origin_http_status':403}]]:
            with self.assertRaises(ValueError):b.assemble(cats,[],pages,{})
    def test_unrendered_template_not_accepted_as_empty(self):
        p=self.page();p['html']=doc('<section><h1>new</h1>{{products}}<div id="categoryProductsList"></div></section>',p['url'])
        with self.assertRaises(ValueError):b.assemble([{'url':p['url'],'title':'new'}],[],[p],{})
    def test_caps_do_not_change_existing_reader_or_new_cron(self):
        self.assertEqual(b.MAX_CREDITS,222)
        source=Path(b.__file__).read_text();self.assertIn('max_credits=111,max_requests=12',source)
        self.assertIn('if reader.halted:raise',source)

if __name__=='__main__':unittest.main()
