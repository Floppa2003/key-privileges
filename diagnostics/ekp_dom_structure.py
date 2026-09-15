"""Instrument the existing public renderer test; never change its card decisions."""
import asyncio
import hashlib
import json
from urllib.parse import urljoin,urlsplit,parse_qsl
from bs4 import BeautifulSoup
import renderer_control as runner
from source_readiness import public_dom

original=runner.cards
samples=[]

def inspected(raw):
    # No raw response scripts, headers, query values or browser state are retained.
    clean=public_dom(raw,runner.TARGETS['ekp'])
    soup=BeautifulSoup(raw,'html.parser');links=[]
    for a in soup.select('a[href]'):
        u=urlsplit(urljoin(runner.TARGETS['ekp'],a['href']))
        if '/capabilities/loyalty/tiles/' not in u.path:continue
        links.append({'host':u.hostname,'path':u.path,'scheme':u.scheme,
            'query_keys':sorted({k for k,_ in parse_qsl(u.query,keep_blank_values=True)}),
            'has_fragment':bool(u.fragment),'in_main':a.find_parent('main') is not None,
            'has_card_owner':a.find_parent(class_='v-card') is not None})
    try:result=original(raw);error=None
    except Exception as exc:result=[];error=type(exc).__name__
    data=clean.encode();(runner.OUT/'last-public-dom.html').write_bytes(data)
    sample={'sha256':hashlib.sha256(data).hexdigest(),'raw_parser_cards':len(result),
        'sanitized_parser_cards':len(original(clean)),'parser_error':error,
        'main_count':len(soup.select('main')),'numeric_card_link_candidates':links}
    if not samples or samples[-1]!=sample:samples.append(sample)
    (runner.OUT/'card-probes.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2))
    if error:raise RuntimeError('card_extraction_error')
    return result

runner.cards=inspected
if __name__=='__main__':asyncio.run(runner.run('ekp'))
