"""One-time source registration checked against reviewed pre/post bytes."""
from pathlib import Path
import hashlib
before={'loyalty/mir_ui.py':'26e5ae501c57ad0eb6938e24e9f76f3825e01cf50a56be0667b494ab898115c7','loyalty/collect_normalized.py':'bebb3aedd776fcf5df438a3e00493302465c7541a1152e167132e9f43d8c889c'}
for name,sha in before.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Unexpected baseline '+name)
insert='''LISTING_REGIONS = {
    'msk': {'label':'Москва и МО','title_suffix':'в Москве и МО'},
    'spb': {'label':'Санкт-Петербург и ЛО','title_suffix':'в Санкт-Петербурге и ЛО'},
}


async def select_listing_region(page,captured,first,key):
    """Use the actual public selector; a previous-region response is not evidence."""
    if key not in LISTING_REGIONS:raise ValueError('unknown_mir_region')
    region=LISTING_REGIONS[key]
    def matches(item):
        return item['page']==1 and str(item.get('page_title','')).endswith(region['title_suffix'])
    selected=(await page.locator('.region-button__title').inner_text()).strip()
    if selected==region['label']:
        if not matches(first):raise RuntimeError('mir_region_response_mismatch')
        return first
    yes=page.locator('.region-confirmation-modal__controls').get_by_role('button',name='Да',exact=True)
    if await yes.count() and await yes.is_visible():await yes.click(timeout=5000)
    offset=len(captured.catalogs)
    await page.locator('button.region-button').click(timeout=5000)
    await page.locator('.region-menu__link').get_by_text(region['label'],exact=True).click(timeout=5000)
    await page.wait_for_function("label=>document.querySelector('.region-button__title')?.textContent.trim()===label",arg=region['label'],timeout=15000)
    return await captured.wait(captured.catalogs,offset,matches)


'''
p=Path('loyalty/mir_ui.py');s=p.read_text().replace('async def collect_mir(client,cfg,report,now,limit):',insert+'async def collect_mir(client,cfg,report,now,limit):')
s=s.replace("        default=first['payment_type']","        if cfg.get('listing_region'):\n            first=await select_listing_region(page,captured,first,cfg['listing_region'])\n        default=first['payment_type']")
s=s.replace("report['discovered']=len(candidates)","report['discovered']=len(candidates)\n        report['discovered_urls']=[urljoin(cfg['url'],path) for path in candidates]");p.write_text(s)
p=Path('loyalty/collect_normalized.py');s=p.read_text().replace('from mir_ui import collect_mir','from mir_regions import collect_mir').replace("if cfg['mode']!='t2':await client.robots()","if cfg['mode'] not in ('t2','mir'):await client.robots()");p.write_text(s)
after={'loyalty/mir_ui.py':'b25a752d498bdcec789c2013fff041aa118450f3f1937c6728f5e23d5de2702d','loyalty/collect_normalized.py':'8fba0102ca316ccfb3f7899a03c73e785de1e3659d2f204e4415da35fa06b909','loyalty/mir_regions.py':'06de4ccc8073c86bcf742ce49bd7de33c92c5e4dd795e191c5d6eaae23885eb1','loyalty/tests/test_mir_regions.py':'6b7761b110e634a4eaffc08916d86663ca91a8fd64ac03a2545a98b6bcaae461'}
for name,sha in after.items():
 if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:raise ValueError('Unexpected transfer bytes '+name)
print('All registered Mir files match locally tested bytes.')
