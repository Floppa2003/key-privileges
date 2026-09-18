"""One-time review helper, excluded from the final release tree."""
from pathlib import Path
import hashlib

root=Path('.')
changed=[]
def blob(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def edit(path,expected,changes):
    p=root/path;raw=p.read_bytes()
    assert blob(raw)==expected,('unexpected baseline',path)
    s=raw.decode()
    for old,new in changes:
        assert s.count(old)==1,(path,old[:90],s.count(old))
        s=s.replace(old,new)
    if path.endswith('.py'):compile(s,path,'exec')
    p.write_text(s);changed.append(path)

edit('loyalty/sheets_normalized.py','c509bd9a7e2ac1ad0b476ecd3304a62e53c624c6',[
    ('from sheets_sync import Sheets','from sheets_sync import Sheets\nfrom practical_scope import publication_rows'),
    ('    rows=prepare(json.loads(path.read_text()))',"    bundle=json.loads(path.read_text())\n    rows=publication_rows(prepare(bundle),{r['id']:r['source_id'] for r in bundle['records']})")])
edit('loyalty/unified_publish.py','3ec22b08cb2dd5d7eadf0d0d2dee4baa3f4d2f4b',[
    ('from unified_views import SCHEMAS,prepare_views,retire_missing','from unified_views import SCHEMAS,prepare_views,retire_missing\nfrom practical_scope import select_inputs,VERSION as SCOPE_VERSION'),
    ('    result=normalize_inputs(inputs,as_of=as_of)',"    practical,excluded=select_inputs(inputs)\n    result=normalize_inputs(practical,as_of=as_of)\n    result['audit'].update(publication_scope=SCOPE_VERSION,excluded_bulk_records=excluded,\n        input_records_before_scope=len(inputs),source_snapshot_sha256=digest(inputs))")])
edit('loyalty/coral_linked_rules.py','500a06ce713e5c83be59905cf29af9d5926d3137',[
    ('from normalized import make_offer,text','from normalized import make_offer,text\nfrom practical_scope import follow_document_link'),
    ('if not is_rule_url(url):continue',"if not is_rule_url(url) or not follow_document_link(url,link['label']):continue")])
edit('.github/workflows/coral-import.yml','caa66c8318ae9c14c85f01fe654e64871813d0b8',[
    ("      - name: Download source-linked public PDFs with the existing free key\n        env:\n          SCRAPINGANT_API_KEY: ${{ secrets.SCRAPINGANT_API_KEY }}\n        run: python loyalty/coral_pdf_collect.py\n",''),
    ('from coral_pdf_collect import validate_bundle','from coral_import import validate_bundle'),
    ('--input coral-source-evidence/combined.json\n','--input coral-source-evidence/normalized.json\n'),
    ('--input coral-source-evidence/combined.json --publish','--input coral-source-evidence/normalized.json --publish')])
edit('loyalty/rzd_external.py','14465613ce03da493c294a928931a9139ccb0ea9',[
    ('def collect(reader,run_id,observed):','def collect(reader,run_id,observed,*,include_bank_documents=True):'),
    ("        if not entries:d['errors'].append({'url':BANK,'reason':'re_no_reward_rules_links'})", "        if not include_bank_documents:\n            d['excluded']=[{'url':e['url'],'reason':'out_of_scope_general_contract'} for e in entries]\n            d['targets']=[];entries=[]\n        if not entries and include_bank_documents:d['errors'].append({'url':BANK,'reason':'re_no_reward_rules_links'})"),
    ("'status':'partial' if errors and rows else 'failed' if errors else 'ok','discovered':", "'status':'out_of_scope' if sid=='rzd_unicredit_rules' and not include_bank_documents else 'partial' if errors and rows else 'failed' if errors else 'ok','discovered':"),
    ("bundle=collect(replay,run_id,audit['observed_at'])", "bundle=collect(replay,run_id,audit['observed_at'],include_bank_documents=audit.get('include_bank_documents',True))"),
    ('bundle=collect(reader,run_id,observed)','bundle=collect(reader,run_id,observed,include_bank_documents=False)'),
    ("'finished_at':now(),'receipts':reader.receipts}","'finished_at':now(),'receipts':reader.receipts,'include_bank_documents':False}")])
edit('loyalty/ekp_linked_rules.py','b33ef5789a650980f0fae70d761c5c322804c727',[
    ('def discover(base,clock):','def discover(base,clock,*,practical_only=False):'),
    ("                if not (urlsplit(original).path.lower().endswith('.pdf') or RULE_LABEL.search(label)):continue", "                if practical_only and urlsplit(original).path.lower().endswith('.pdf'):\n                    entry['classification']='out_of_scope_bulk_appendix';continue\n                if not (urlsplit(original).path.lower().endswith('.pdf') or RULE_LABEL.search(label)):continue"),
    ("entries,inventory=discover(base,instant(audit['started_at']))", "entries,inventory=discover(base,instant(audit['started_at']),practical_only=audit.get('practical_only',False))"),
    ("started=now();entries,inventory=discover(base,instant(started))", "started=now();entries,inventory=discover(base,instant(started),practical_only=True)"),
    ("'started_at':started,'inventory':inventory,'results':[]", "'started_at':started,'practical_only':True,'inventory':inventory,'results':[]")])
edit('loyalty/recovered_sources.py','49e28c663050df233cc9c7b32ea451f5584f8f67',[
    ('def _collect(cfg, report, now, limit):','def _collect(cfg, report, now, limit, *, include_documents=True):'),
    ("        links=parent['details']['linked_documents'];reader.bind_document_links(links)", "        links=parent['details']['linked_documents']\n        if not include_documents:\n            parent['details']['linked_documents_policy']='references_only_practical_scope'\n            parent['content_sha256']=content_hash(parent)\n            report['discovered']=1\n            report['coverage']=json.dumps({'kind':'practical_parent_page','attachments':'references_only','attached_documents_are_not_missing_offers':True},ensure_ascii=False)\n            return records\n        reader.bind_document_links(links)"),
    ('return await asyncio.to_thread(_collect,cfg,report,now,limit)', 'return await asyncio.to_thread(_collect,cfg,report,now,limit,include_documents=False)')])
edit('loyalty/utair_documents.py','15df4e10b4009bebfc1206916ee3facbf59984d8',[
    ('from read_budget import within_source_budget','from read_budget import within_source_budget\nfrom practical_scope import follow_document_link'),
    ("    entries=discover_documents(raw);parent_sha=hashlib.sha256(raw.encode()).hexdigest()", "    discovered=discover_documents(raw)\n    entries=[e for e in discovered if follow_document_link(e['url'],'; '.join(e['labels']+e['contexts']))]\n    omitted=[{'url':e['url'],'labels':e['labels'],'reason':'out_of_scope_general_programme_rules'} for e in discovered if e not in entries]\n    parent_sha=hashlib.sha256(raw.encode()).hexdigest()"),
    ("'discovered_links':len(entries),'links_attempted':attempted", "'discovered_links':len(entries),'out_of_scope_references':omitted,'links_attempted':attempted")])
edit('loyalty/tests/test_coral_pdf_collect.py','2db914273d32a26dd2a34de554c3ed6f5f6d618f',[
    ("    def test_pdf_only_safe_step_has_no_google_credential(self):\n        path=Path(__file__).parents[2]/'.github/workflows/coral-import.yml'\n        text=path.read_text();step=text.split('- name: Download source-linked public PDFs')[1].split('- uses:')[0]\n        self.assertIn('SCRAPINGANT_API_KEY',step);self.assertNotIn('GOOGLE_ACCESS_TOKEN',step)\n        self.assertIn('from coral_pdf_collect import validate_bundle',text);self.assertIn('combined.json --publish',text)\n",'')])
p=root/'.github/workflows/aeroflot-linked-rules.yml'
assert blob(p.read_bytes())=='d44a13fe365d76b5c8d296ed0de4d714cce77b43'
p.write_text('''name: Aeroflot linked public rules (retired bulk scope)
on:
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: loyalty-catalog-'''+ '$' +'''{{ github.ref }}
  cancel-in-progress: false
  queue: max
jobs:
  scope:
    runs-on: ubuntu-24.04
    steps:
      - run: echo "Bulk parking manuals and exhaustive exclusion lists are out of practical-offer scope. Main Aeroflot offer collection is unchanged. No source fetch or publication."
''')
changed.append(str(p))
changed += ['loyalty/practical_scope.py','loyalty/practical_migrate.py','loyalty/tests/test_practical_scope.py','loyalty/tests/test_practical_migrate.py','loyalty/tests/test_practical_collection.py']
import json
Path('practical-verification/changed-paths.json').write_text(json.dumps(changed))
