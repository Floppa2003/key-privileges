"""Bounded anonymous page capture. No merchant-specific extraction or publication.

Keep the original screen, a cookie-overlay-cleaned derivative, lossless tiled
PDF for reading, native text PDF, and a source/coverage receipt. Cookie overlays
are hidden in a derivative only: this neither clicks consent nor bypasses login.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
import fitz


def tile_spans(height: int, tile_height: int = 1600, overlap: int = 120) -> list[tuple[int,int]]:
    if any(type(v) is not int for v in (height,tile_height,overlap)) or height<1 or tile_height<1 or not 0<=overlap<tile_height:
        raise ValueError('invalid_tile_geometry')
    spans=[]; top=0
    while top<height:
        bottom=min(height,top+tile_height);spans.append((top,bottom))
        if bottom==height:break
        top=bottom-overlap
    return spans


def screenshot_pdf(image_path: Path, out_path: Path) -> list[dict]:
    """PNG pixels -> PDF pages without HTML reflow or JPEG recompression."""
    pages=[]
    with Image.open(image_path) as image, fitz.open() as doc:
        image=image.convert('RGB')
        for n,(top,bottom) in enumerate(tile_spans(image.height),1):
            tile=image.crop((0,top,image.width,bottom))
            buf=io.BytesIO();tile.save(buf,format='PNG')
            page=doc.new_page(width=image.width*0.75,height=(bottom-top)*0.75)
            page.insert_image(page.rect,stream=buf.getvalue())
            pages.append({'page':n,'top':top,'bottom':bottom,'width':image.width,
                          'coordinate_unit':'screenshot_pixel','overlap':120 if n>1 else 0})
        doc.save(out_path,deflate=True)
    return pages


async def hide_cookie_overlays(page) -> list[dict]:
    """Only fixed/sticky small cookie panes; never paywalls/auth or ordinary prose."""
    return await page.evaluate(r'''() => {
      const cookie=/(?:\bcookies?\b|куки|куки-файл)/i;
      const gate=/(?:для доступа|войти|авториз|подписк|оплат|captcha|sign.?in|log.?in|subscribe|paywall)/i;
      const candidates=[];
      for(const el of document.body.querySelectorAll('*')){
        const st=getComputedStyle(el),r=el.getBoundingClientRect();
        if(!['fixed','sticky'].includes(st.position)||st.display==='none'||st.visibility==='hidden'||!r.width||!r.height)continue;
        const text=(el.innerText||'').trim();
        if(text.length<10||text.length>2500||!cookie.test(text)||gate.test(text))continue;
        if(r.height>innerHeight*.7||el.querySelector('input[type=password],iframe'))continue;
        candidates.push(el);
      }
      const chosen=candidates.filter(e=>!candidates.some(p=>p!==e&&p.contains(e)));
      return chosen.slice(0,5).map((el,i)=>{
        const r=el.getBoundingClientRect();
        const receipt={text:el.innerText,tag:el.tagName,rect:{x:r.x,y:r.y,width:r.width,height:r.height},
          action:'visual_derivative_hide_only',consent_clicked:false};
        el.setAttribute('data-capture-cookie-hidden',String(i));
        el.style.setProperty('visibility','hidden','important');
        el.style.setProperty('pointer-events','none','important');
        return receipt;
      });
    }''')


async def capture_page(page, folder: Path, *, max_height: int = 32000) -> dict:
    folder.mkdir(parents=True,exist_ok=True)
    warnings=[]
    await page.emulate_media(media='screen',reduced_motion='reduce')
    try: await page.evaluate('() => Promise.race([document.fonts.ready,new Promise((_,r)=>setTimeout(()=>r(Error("font_wait_timeout")),5000))])')
    except Exception:warnings.append('fonts_wait_not_confirmed')
    reached=False
    for _ in range(42):
        size=await page.evaluate('({y:scrollY,h:innerHeight,total:document.documentElement.scrollHeight})')
        if size['total']>max_height:
            raise ValueError('capture_height_budget_no_truncation')
        if size['y']+size['h']>=size['total']-2:reached=True;break
        await page.evaluate('window.scrollBy(0,750)');await page.wait_for_timeout(160)
    if not reached:raise ValueError('lazy_scroll_budget_no_truncation')
    await page.evaluate('window.scrollTo(0,0)');await page.wait_for_timeout(800)
    pre=await page.locator('body').inner_text()
    await page.screenshot(path=str(folder/'screen-original.png'),full_page=True,animations='disabled',timeout=25000)
    modifications=await hide_cookie_overlays(page)
    await page.wait_for_timeout(100)
    text=await page.locator('body').inner_text()
    await page.screenshot(path=str(folder/'screen.png'),full_page=True,animations='disabled',timeout=25000)
    tiles=screenshot_pdf(folder/'screen.png',folder/'reading.pdf')
    (folder/'visible-text.txt').write_text(text,encoding='utf-8')
    # Coordinates locate source wording for visual inspection, not extraction rules.
    text_boxes=await page.evaluate(r'''() => {
      let result=[]; const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
      while(walker.nextNode()){
        const n=walker.currentNode,t=n.textContent.trim();if(!t||!n.parentElement)continue;
        const st=getComputedStyle(n.parentElement);if(st.visibility==='hidden'||st.display==='none')continue;
        if(n.parentElement.closest('script,style,noscript,[data-capture-cookie-hidden]'))continue;
        const range=document.createRange();range.selectNodeContents(n);const r=range.getBoundingClientRect();
        if(r.width>0&&r.height>0)result.push({text:t,x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height});
        if(result.length>=10000)break;
      } return result;
    }''')
    (folder/'text-boxes.json').write_text(json.dumps(text_boxes,ensure_ascii=False),encoding='utf-8')
    try:
        await page.pdf(path=str(folder/'native.pdf'),width='1280px',height='1800px',
                       margin={k:'0' for k in ('top','bottom','left','right')},
                       print_background=True,display_header_footer=False,prefer_css_page_size=False,timeout=25000)
    except Exception as exc:warnings.append('native_pdf_failed:'+type(exc).__name__)
    final_text=await page.locator('body').inner_text()
    if final_text!=text:warnings.append('text_changed_during_capture')
    closed=await page.locator('details:not([open])').count()
    collapsed=await page.locator('[aria-expanded="false"]').count()
    if closed or collapsed:warnings.append('collapsed_controls_not_opened')
    return {'capture_status':'captured_needs_review','warnings':warnings,'modifications':modifications,
            'text_unchanged_during_capture':text==final_text,'native_pdf_is_secondary':True,
            'reading_pdf_kind':'lossless_screenshot_tiles','text_layer_in_reading_pdf':False,
            'closed_details':closed,'collapsed_controls':collapsed,'tiles':tiles,
            'original_text_sha256':hashlib.sha256(pre.encode()).hexdigest(),
            'clean_text_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'publication_allowed':False}


async def run_batch(targets: list[dict], out: Path, concurrency: int = 2) -> dict:
    from playwright.async_api import async_playwright
    from public_transport import PublicSource
    if not 1<=len(targets)<=40 or not 1<=concurrency<=3:raise ValueError('batch_budget')
    ids=[t['id'] for t in targets]
    if len(ids)!=len(set(ids)) or any(not re.fullmatch(r'[a-z0-9_\-]{1,60}',i) for i in ids):raise ValueError('target_ids')
    out.mkdir(parents=True,exist_ok=True);results={};sem=asyncio.Semaphore(concurrency)
    # Same origin is processed serially even when different domains are parallel.
    from urllib.parse import urlsplit
    host_locks={urlsplit(t['url']).hostname:asyncio.Lock() for t in targets}
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        async def one(target):
            async with sem,host_locks[urlsplit(target['url']).hostname]:
                folder=out/target['id'];folder.mkdir(exist_ok=True)
                item={**target,'observed_at':datetime.now(timezone.utc).isoformat(),
                      'browser_version':browser.version,'publication_allowed':False,
                      'login_performed':False,'commercial_action_performed':False}
                try:
                    async with asyncio.timeout(150):
                        async with PublicSource(browser,target['url']) as source:
                            await source.page.set_viewport_size({'width':1280,'height':960})
                            await source.robots();item['robots']=source.robots_info
                            await source.read(target['url'],render=True)
                            item.update(final_url=source.page.url,title=await source.page.title())
                            item.update(await capture_page(source.page,folder))
                except Exception as exc:
                    # Do not retry HTTP authentication/rate limits or ignore robots.
                    item.update(capture_status='capture_failed',error_type=type(exc).__name__,error=str(exc)[:500])
                item['files']={f.name:{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
                               for f in sorted(folder.iterdir()) if f.is_file() and f.name!='capture.json'}
                (folder/'capture.json').write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf-8')
                results[target['id']]=item
                print(target['id'],item['capture_status'],flush=True)
        await asyncio.gather(*(one(t) for t in targets));await browser.close()
    report={'version':'merchant-visual-batch-v1','results':[results[i] for i in ids],
            'target_count':len(ids),'capture_count':sum(v['capture_status']=='captured_needs_review' for v in results.values()),
            'publication_allowed':False,'inference_performed':False}
    (out/'capture-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--targets',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--concurrency',type=int,default=2);a=p.parse_args()
    asyncio.run(run_batch(json.loads(a.targets.read_text()),a.out,a.concurrency))

if __name__=='__main__':main()
