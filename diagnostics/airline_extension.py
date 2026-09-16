"""One-time branch patch; exact old/new contents are verified before any commit.
This staging helper is removed in the same branch commit. No network or secrets.
"""
from pathlib import Path
import hashlib
import json

ROOT=Path('.')

def replace(path,old,new):
    p=ROOT/path;s=p.read_text()
    if s.count(old)!=1:raise ValueError('patch context count: '+path)
    p.write_text(s.replace(old,new))

replace('loyalty/aeroflot_import_catalog.py',
"    raise ValueError('af_url_scope')\n\n\ndef formula",
"    if kind in ('airline_catalog','airline_detail'):\n        from aeroflot_airlines import CATALOG as AIRLINES,DETAIL as AIRLINE_DETAIL,detail_url as airline_url\n        if kind=='airline_catalog' and url==AIRLINES:return url\n        if kind=='airline_detail' and u.path==urlsplit(AIRLINE_DETAIL).path:\n            pairs=parse_qsl(u.query,keep_blank_values=True);q=dict(pairs)\n            if (len(pairs)==3 and set(q)=={'lang','id','returnFullParentInfo'} and q['lang']=='ru'\n                and q['returnFullParentInfo']=='1' and re.fullmatch('[1-9][0-9]{0,11}',q['id'])\n                and url==airline_url(int(q['id']))):return url\n    raise ValueError('af_url_scope')\n\n\ndef formula")
replace('loyalty/aeroflot_import_catalog.py',"elif obs['kind']=='detail':", "elif obs['kind'] in ('detail','airline_catalog','airline_detail'):")
replace('loyalty/normalized.py',"    if r['source_id']=='aeroflot':\n        from aeroflot_import_catalog import validate_record\n        validate_record(r)","    if r['source_id']=='aeroflot':\n        if r['native_id'].startswith('airline:'):\n            from aeroflot_airlines import validate_record\n        else:\n            from aeroflot_import_catalog import validate_record\n        validate_record(r)")

p=ROOT/'loyalty/aeroflot_import_collect.py';s=p.read_text()
s=s.replace('import aeroflot_import_catalog as m','import aeroflot_import_catalog as m\nimport aeroflot_airlines as airlines')
s=s.replace('MAX_READS=263','MAX_READS=324').replace('def discovery(obs):',"def discovery(obs,scope='companies'):")
s=s.replace("    return True\n\n\ndef report", "    if scope in ('airlines','all') and not any(u.scheme=='https' and u.netloc in allowed and u.path.rstrip('/')=='/partners/airlines' for u in links):\n        raise ValueError('af_airline_catalogue_link_not_observed')\n    return True\n\n\ndef report")
s=s.replace('def report(observed_at,rows,partners,errors,pol=None):',"def report(observed_at,rows,partners,errors,pol=None,*,scope='companies',air_partners=None,air_roots=None):")
s=s.replace("    return {'source_id':'aeroflot','name':'Аэрофлот Бонус — компании-партнёры','root':m.ROOT,", "    name='Аэрофлот Бонус — компании-партнёры'\n    if scope!='companies':\n        air_partners=air_partners or {};air_roots=air_roots or set()\n        air_count=sum(r['native_id'].startswith('airline:') for r in rows)\n        company_count=len(rows)-air_count\n        coverage.update(scope=scope,discovered_company_partners=len(partners),accepted_company_details=company_count,\n            all_category_partners_read=bool(partners) and company_count==len(partners),\n            airline_catalogue_read=bool(air_roots),airline_catalogue_api=airlines.CATALOG,\n            discovered_root_airlines=len(air_roots),discovered_airlines_including_children=len(air_partners),\n            accepted_airline_details=air_count,all_discovered_airlines_read=bool(air_roots) and air_count==len(air_partners),\n            airline_table_coefficients_are_not_cash_discounts=True)\n        count=len(partners)+len(air_partners);name='Аэрофлот Бонус — '+('авиакомпании' if scope=='airlines' else 'компании и авиакомпании')\n    return {'source_id':'aeroflot','name':name,'root':m.ROOT,")
s=s.replace("def walk(reader,run_id,observed_at,*,checkpoint=lambda:None):\n    records=[];errors=[];partners={};pol=None", "def walk(reader,run_id,observed_at,*,checkpoint=lambda:None,scope='companies'):\n    if scope not in ('companies','airlines','all'):raise ValueError('af_scope_invalid')\n    records=[];errors=[];partners={};pol=None;root_seen=False;air_partners={};air_roots=set()")
a=s.index("        discovery(reader.read(m.ROOT,'discovery'));checkpoint()")
b=s.index("    except Exception as exc:errors.append({'phase':'discovery','reason':reason(exc)})",a)
body=s[a:b].replace("        discovery(reader.read(m.ROOT,'discovery'));checkpoint()", "        root_seen=discovery(reader.read(m.ROOT,'discovery'),scope);checkpoint()")
parts=body.split("        partners=m.catalog",1)
body=parts[0]+"        if scope in ('companies','all'):\n"+'\n'.join('    '+line if line else line for line in ("        partners=m.catalog"+parts[1]).split('\n'))
s=s[:a]+body+s[b:]
a=s.index("    return {'schema_version':2",s.index('def walk('))
s=s[:a]+'''    if root_seen and scope in ('airlines','all') and getattr(reader,'cleanup_verified',True):
        try:
            air_partners=airlines.catalog(reader.read(airlines.CATALOG,'airline_catalog'));air_roots=set(air_partners);checkpoint()
            pending=list(air_partners);attempted=set();consecutive=0
            while pending and len(attempted)<airlines.MAX_AIRLINES:
                pid=pending.pop(0)
                if pid in attempted:continue
                attempted.add(pid)
                try:
                    obs=reader.read(airlines.detail_url(pid),'airline_detail');checkpoint()
                    row=airlines.detail(obs,air_partners[pid],observed_at)
                    airlines.add_children(air_partners,row['details']['public_airline'])
                    records.append(row);consecutive=0
                    pending.extend(i for i in air_partners if i not in attempted and i not in pending)
                except Exception as exc:
                    errors.append({'phase':'airline_detail','url':airlines.detail_url(pid),'reason':reason(exc)});consecutive+=1
                    if not getattr(reader,'cleanup_verified',True) or consecutive>=3 or reason(exc)=='af_collection_bound':
                        errors.append({'phase':'airline_details','reason':'af_consecutive_failure_or_budget_stop'});break
            if pending and len(attempted)>=airlines.MAX_AIRLINES:errors.append({'phase':'airline_details','reason':'af_airline_detail_bound'})
        except Exception as exc:errors.append({'phase':'airline_catalogue','reason':reason(exc)})
''' +s[a:]
s=s.replace("'sources':[report(observed_at,records,partners,errors,pol)]}","'sources':[report(observed_at,records,partners,errors,pol,scope=scope,air_partners=air_partners,air_roots=air_roots)]}")
s=s.replace("    partners={};expected=[];pol=None;root_seen=False;last=start;seen=set()", "    scope=audit.get('scope','companies')\n    if scope not in ('companies','airlines','all'):raise ValueError('af_scope_invalid')\n    partners={};air_partners={};air_roots=set();expected=[];pol=None;root_seen=False;last=start;seen=set()")
s=s.replace("        if kind=='discovery':root_seen=discovery(obs)","        if kind=='discovery':root_seen=discovery(obs,scope)")
s=s.replace("            if not root_seen:raise ValueError('af_bundle_catalogue_not_discovered')", "            if not root_seen or scope=='airlines':raise ValueError('af_bundle_catalogue_not_discovered')")
s=s.replace("            except ValueError:continue\n    if expected!=bundle['records']", "            except ValueError:continue\n        elif kind=='airline_catalog':\n            if not root_seen or scope=='companies':raise ValueError('af_bundle_airlines_not_discovered')\n            try:air_partners=airlines.catalog(obs);air_roots=set(air_partners)\n            except ValueError:continue\n        elif kind=='airline_detail':\n            pid=int(dict(parse_qsl(urlsplit(obs['url']).query))['id'])\n            if pid not in air_partners:raise ValueError('af_bundle_undiscovered_airline')\n            try:\n                row=airlines.detail(obs,air_partners[pid],bundle['observed_at'])\n                airlines.add_children(air_partners,row['details']['public_airline']);expected.append(row)\n            except ValueError:continue\n    if expected!=bundle['records']")
s=s.replace("report(bundle['observed_at'],expected,partners,supplied['errors'],pol)","report(bundle['observed_at'],expected,partners,supplied['errors'],pol,scope=scope,air_partners=air_partners,air_roots=air_roots)")
s=s.replace("    if len(expected)>MAX_DETAILS:raise ValueError('af_bundle_detail_bound')", "    if sum(r['native_id'].startswith('partner:') for r in expected)>MAX_DETAILS or sum(r['native_id'].startswith('airline:') for r in expected)>airlines.MAX_AIRLINES:raise ValueError('af_bundle_detail_bound')")
s=s.replace("parser.add_argument('--out',default=str(OUT));args=parser.parse_args()", "parser.add_argument('--out',default=str(OUT));parser.add_argument('--scope',choices=('companies','airlines','all'),default='companies');args=parser.parse_args()")
s=s.replace("'origin_response_and_cache_age_not_exposed':True}","'origin_response_and_cache_age_not_exposed':True,'scope':args.scope}")
s=s.replace("bundle=walk(reader,run_id,started,checkpoint=checkpoint)","bundle=walk(reader,run_id,started,checkpoint=checkpoint,scope=args.scope)")
p.write_text(s)
replace('loyalty/unified_normalization.py',"    structured_evidence=set()",'''    structured_evidence=set()
    airline_rules=d.get('retrieval_method')=='aeroflot_airline_api_google_import_v1'
    if airline_rules:
        # These source coefficients use distance, not the ticket price. A fare
        # exclusion mentioning a discount must not become a discount offer.
        p=d['public_airline']
        for i,row in enumerate(p['miles_table']):
            benefit('earn_miles',f'/details/public_airline/miles_table/{i}',value=row['percent'],unit='percent_of_distance',
                basis_value=100,basis_unit='distance_miles',reward_unit='miles',qualifier='source_table',
                scope={'airline_id':p['id'],'iata':p['iata'],'cabin':row['cabin'],'tariff':row['tariff'],'codes':row['codes'],
                       'qualifying_miles':True,'remaining_exclusions_require_review':True})
        for i,row in enumerate(p['elite_coefficients']):
            benefit('earn_miles',f'/details/public_airline/elite_coefficients/{i}',value=row['percent'],unit='percent_of_distance',
                basis_value=100,basis_unit='distance_miles',reward_unit='miles',qualifier='source_table',
                scope={'airline_id':p['id'],'tier':row['tier'],'qualifying_miles':False})
        condition('airline_source_rules','/conditions',scope={'airline_id':p['id'],'table_exceptions_require_review':True})
        condition('minimum_mileage_source','/details/public_airline/miles_minimum',value=p['miles_minimum'],unit='miles',
            scope={'source_limitation_code':p['miles_limitation'],'applicability_not_inferred':True})
        if p['parent']:condition('parent_airline_reference','/details/public_airline/parent',scope={'not_applied_as_child_table':True})
''')
replace('loyalty/unified_normalization.py',"    for path,clause in _clauses(raw):", "    for path,clause in (() if airline_rules else _clauses(raw)):")
replace('.github/workflows/aeroflot-import.yml',"branches: [main, 'loyalty/aeroflot-google-import-20260916']","branches: [main, 'loyalty/aeroflot-google-import-20260916', 'loyalty/airline-coverage-20260916']")
replace('.github/workflows/aeroflot-import.yml','loyalty/aeroflot_import_catalog.py,','loyalty/aeroflot_import_catalog.py, loyalty/aeroflot_airlines.py, loyalty/tests/test_aeroflot_airlines.py, loyalty/unified_normalization.py,')
replace('.github/workflows/aeroflot-import.yml','  workflow_dispatch:\n',"  workflow_dispatch:\n    inputs:\n      scope:\n        description: Catalogue scope (all includes companies and airlines)\n        type: choice\n        options: [all, companies, airlines]\n        default: all\n")
replace('.github/workflows/aeroflot-import.yml',"          GOOGLE_ACCESS_TOKEN: ${{ steps.google.outputs.access_token }}\n        run: python loyalty/aeroflot_import_collect.py", "          GOOGLE_ACCESS_TOKEN: ${{ steps.google.outputs.access_token }}\n          CATALOG_SCOPE: ${{ github.event_name == 'push' && 'airlines' || inputs.scope || 'all' }}\n        run: python loyalty/aeroflot_import_collect.py --scope \"$CATALOG_SCOPE\"")
EXPECTED={'.github/workflows/aeroflot-import.yml':'fae936d2b793dd405adf3b2889c05380e1bf3dfe9e9a69ecb67b46eb68052285','loyalty/aeroflot_import_catalog.py':'9b66be0f19f8c08f88f64cb7c07e1a5b7e95d02326a4c6472bc7543741245682','loyalty/aeroflot_import_collect.py':'4fddf36b4491bac6063ccfa1d1fc4dc0c6db7c103bbbfe865c04a75c4e09b8ce','loyalty/aeroflot_airlines.py':'1db80eceda7bab466fe7611178127efe924802764c22e6eb9174911b9a01f0e2','loyalty/tests/test_aeroflot_airlines.py':'5094b28bbf676459512670446ab5f650c5a7144f911c677211623a27f3d08dd6','loyalty/normalized.py':'2202de30b248d2fe0e6de6246bad018fb18e9980d694668be2de4570a2a37c61','loyalty/unified_normalization.py':'ca433b27bb755040f9bb4f2ac1675b15c8bc2022cb69e282f364c3ddbcd501fb'}
for path,expected in EXPECTED.items():
    if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=expected:raise ValueError('patch digest mismatch: '+path)
print('All seven reviewed output file digests match.')
