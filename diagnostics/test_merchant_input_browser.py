"""Actual Chromium/production capture with only HTTP replaced by finite fixtures."""
import asyncio
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'loyalty')]
from playwright.async_api import async_playwright
import merchant_konsierge_capture as c
import merchant_extract as m
from merchant_evidence import InputNotReady


def item(ident,name,description):
    return {'id':ident,'name':name,'offer':'Предложение','description':description,'link':None,
            'enabled':True,'date_of_expiry':None,'date_of_release':None,'created_at':None,'updated_at':None,'rubrics':[]}


class BrowserProxy:
    def __init__(self,browser,pages,*,height=200):self.browser=browser;self.pages=pages;self.height=height
    async def new_context(self,**kwargs):
        real=await self.browser.new_context(**kwargs);owner=self
        class Context:
            async def route(self,*args,**kw):
                async def fixture(route):
                    url=route.request.url
                    if '/api/client/v1/benefits' in url:
                        from urllib.parse import parse_qs,urlsplit
                        n=int(parse_qs(urlsplit(url).query).get('page',['1'])[0])
                        entries=owner.pages[n-1]
                        payload={'result':entries,'page':{'current_page':n,'next_page':n+1 if n<len(owner.pages) else None}}
                        await route.fulfill(status=200,content_type='application/json',headers={'Access-Control-Allow-Origin':'*'},body=json.dumps(payload))
                    elif url.startswith('https://konsierge.com/benefits'):
                        html='''<!doctype html><style>qy-benefit-teaser{display:block;width:600px;height:HEIGHTpx;border:1px solid;margin:12px}body{min-height:1400px}</style><div id="loader">Loading</div><main></main><script>
                        let n=0,busy=false;
                        async function load(){if(busy||n>=PAGES)return;busy=true;
                        const d=await(await fetch('https://benefits.konsierge.com/api/client/v1/benefits?page='+(++n)+'&per=12')).json();
                        document.querySelector('#loader').remove?.();
                        for(const i of d.result){const e=document.createElement('qy-benefit-teaser');
                        const title=document.createElement('div');title.className='BenefitTeaser-Title';title.textContent=i.name;e.append(title);
                        const offer=document.createElement('div');offer.className='BenefitTeaser-OfferText';offer.textContent=i.offer;e.append(offer);
                        const id=document.createElement('div');id.textContent='source id '+i.id;e.append(id);
                        document.querySelector('main').append(e);}busy=false;}
                        setTimeout(load,250);window.addEventListener('wheel',()=>{if(!busy)load()});
                        </script>'''.replace('HEIGHT',str(owner.height)).replace('PAGES',str(len(owner.pages))).replace("document.querySelector('#loader').remove?.();","document.querySelector('#loader')?.remove();")
                        await route.fulfill(status=200,content_type='text/html',body=html)
                    else:await route.abort()
                await real.route('**/*',fixture)
            async def new_page(self):return await real.new_page()
            async def close(self):await real.close()
        return Context()


class BrowserEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pw=await async_playwright().start();self.browser=await self.pw.chromium.launch(headless=True)
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    async def asyncTearDown(self):
        await self.browser.close();await self.pw.stop();self.tmp.cleanup()
    def target(self,raw):
        return {'id':'unseen','url':c.ROOT,'source_id':c.SOURCE,'partner':raw['name'],'program':'P',
            'source_records':[{'source_id':c.SOURCE,'native_id':str(raw['id']),'observed_at':'2026-10-20T00:00:00Z',
                               'details':{'public_item':raw}}]}
    async def capture(self,pages,target,**kw):
        spec=await c.capture(BrowserProxy(self.browser,pages,**kw),target,self.root)
        (self.root/'manifest.json').write_text(json.dumps({'documents':[spec]}))
        return spec,m.load_manifest(self.root/'manifest.json')[0]
    async def test_delayed_target_after_neighbouring_page_keeps_full_object(self):
        raw=item(8357,'New Unicode 名','All conditions\nSecond paragraph\nFinal condition')
        spec,doc=await self.capture([[item(7,'Other','Wrong offer')],[raw]],self.target(raw))
        self.assertTrue(spec['capture_scope']['target_resolved'])
        native=json.loads((self.root/'unseen/native-source.json').read_text())['items']
        self.assertEqual(native,[raw]);self.assertIn('Final condition',doc['text']);self.assertNotIn('Wrong offer',doc['text'])
        self.assertGreater(len(doc['images']),0)
    async def test_live_data_replaces_old_description_not_redressed_as_fresh(self):
        old=item(8444,'Target','OLD DISCOUNT 20');live=item(8444,'Target','NEW DISCOUNT 37')
        spec,doc=await self.capture([[live]],self.target(old))
        self.assertIn('NEW DISCOUNT 37',doc['text']);self.assertNotIn('OLD DISCOUNT 20',doc['text'])
        archive=json.loads((self.root/'unseen/collector-records.json').read_text())
        self.assertEqual(archive[0]['details']['public_item'],old)
    async def test_missing_target_is_not_invented_from_stale_snapshot(self):
        target=self.target(item(91,'Gone','Historical conditions'))
        with self.assertRaises(InputNotReady):await self.capture([[item(92,'Other','Current')]],target)
    async def test_duplicate_title_and_label_use_native_identity_not_first_card(self):
        first=item(11,'Same name','Neighbour terms');target=item(12,'Same name','Target terms')
        spec,doc=await self.capture([[first,target]],self.target(target))
        self.assertIn('Target terms',doc['text']);self.assertNotIn('Neighbour terms',doc['text'])
        html=(self.root/'unseen/target-cards.html').read_text()
        self.assertIn('source id 12',html);self.assertNotIn('source id 11',html)
    async def test_tall_card_keeps_all_image_tiles(self):
        raw=item(42,'Tall','Complete terms')
        spec,doc=await self.capture([[raw]],self.target(raw),height=2300)
        self.assertEqual(len(doc['images']),3)
    async def test_native_attachment_tampering_is_detected_before_model(self):
        raw=item(55,'Target','Original')
        spec,doc=await self.capture([[raw]],self.target(raw))
        (self.root/'unseen/native-source.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'source_hash_mismatch'):m.load_manifest(self.root/'manifest.json')

if __name__=='__main__':unittest.main()
