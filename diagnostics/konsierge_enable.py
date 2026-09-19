"""One-time, hash-guarded integration into the existing collector; no global gate edits."""
import hashlib
import json
from pathlib import Path
BASE=Path('loyalty')
EXPECTED={'collect_normalized.py':'d397b83b1f0eea0470803c8b8cc41569ab841b42',
          'konsierge_catalog.py':'e7ce9ab6ef9733f2cbf4642fa1bdc9f904bce706',
          'sources_normalized.json':'ae7c3c56523e2a3b9f630c545a1da90c254a2168'}
for file, sha in EXPECTED.items():
    raw=(BASE/file).read_bytes()
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==sha, file

def replace(file, old, new):
    p=BASE/file; text=p.read_text(); assert text.count(old)==1, (file, old)
    p.write_text(text.replace(old,new), encoding='utf-8')

replace('collect_normalized.py','from greatlist_alfa import collect as collect_greatlist',
        'from greatlist_alfa import collect as collect_greatlist\nfrom konsierge_source import collect as collect_konsierge')
replace('collect_normalized.py',"        elif cfg['id']=='alfa_only_partner_pdf_offers':records=await collect_alfa_partner_pdfs(cfg,report,now,limit)",
        "        elif cfg['id']=='alfa_only_partner_pdf_offers':records=await collect_alfa_partner_pdfs(cfg,report,now,limit)\n        elif cfg['id']=='konsierge_public':records=await collect_konsierge(browser,cfg,report,now,limit)")
replace('konsierge_catalog.py','Collection is manual until the main-origin robots transport is accepted. Root and',
        'Manual and recurring captures preserve distinct acquisition provenance. Root and')
replace('konsierge_catalog.py',"METHOD = 'konsierge_public_browser_capture_v1'",
        "METHOD = 'konsierge_public_browser_capture_v1'\nRECURRING_MODE = 'recurring_public_browser'\nROBOTS_POLICY = 'skip_konsierge_public_by_user_2026_09_19'")
replace('konsierge_catalog.py',"            'manual_capture_not_recurring_collection','source_cache_age_not_provided']",
        "            'source_cache_age_not_provided']")
replace('konsierge_catalog.py',"def derived(item, observed_at):\n    item_fields(item)\n    body = text(item['description']); warnings = list(WARNINGS)",
        """def record_mode(details):
    mode = details.get('collection_mode', 'manual')
    require(mode in ('manual', RECURRING_MODE), 'collection_mode')
    if mode == RECURRING_MODE:
        require(details.get('robots_policy') == ROBOTS_POLICY, 'recurring_robots_policy')
    return mode


def derived(item, observed_at, collection_mode='manual'):
    item_fields(item)
    require(collection_mode in ('manual', RECURRING_MODE), 'collection_mode')
    body = text(item['description']); warnings = list(WARNINGS)
    warnings.insert(4, 'manual_capture_not_recurring_collection' if collection_mode == 'manual'
                    else 'robots_preflight_skipped_by_project_owner')""")
replace('konsierge_catalog.py',"derived(item,row['observed_at'])", "derived(item,row['observed_at'],record_mode(d))")
replace('konsierge_catalog.py',"    require(report.get('one_off_public_ui_inspection') is True and report.get('source_account_login') is False",
        """    mode = record_mode(report)
    require(report.get('one_off_public_ui_inspection') is (mode == 'manual')
            and (mode == 'manual' or report.get('robots_requests') == 0)
            and report.get('source_account_login') is False""")
replace('konsierge_catalog.py',"derived(item,report['observed_at'])", "derived(item,report['observed_at'],mode)")
replace('konsierge_catalog.py',"details={'retrieval_method':METHOD,'public_item':item,'item_sha256':digest(item),",
        "details={**({'collection_mode':mode,'robots_policy':ROBOTS_POLICY} if mode == RECURRING_MODE else {}),\n                     'retrieval_method':METHOD,'public_item':item,'item_sha256':digest(item),")
replace('konsierge_catalog.py',"'coverage':'complete_public_root_and_all_visible_rubrics; manual_capture; eligibility_not_verified'",
        "'coverage':'complete_public_root_and_all_visible_rubrics; '+('manual_capture' if mode == 'manual' else 'recurring_public_browser; robots_preflight_not_requested')+'; eligibility_not_verified'")
replace('konsierge_catalog.py',"derived(item,raw['observed_at'])", "derived(item,raw['observed_at'],record_mode(d))")
p=BASE/'sources_normalized.json'; sources=json.loads(p.read_text())
assert not any(x['id']=='konsierge_public' for x in sources)
sources.append({'id':'konsierge_public','name':'Konsierge — публичные привилегии',
    'mode':'konsierge','url':'https://konsierge.com/benefits',
    'robots_policy':'skip_konsierge_public_by_user_2026_09_19','timeout_seconds':420})
p.write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Applied source-local recurring integration; shared transport unchanged.')
