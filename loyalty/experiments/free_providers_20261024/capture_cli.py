"""Fresh public captures and official OpenCode CLI, isolated from production."""
from __future__ import annotations
import argparse, ast, base64, hashlib, io, json, os, signal, subprocess, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image
import routes

HERE=Path(__file__).resolve().parent

def tiles(raw:bytes)->list[bytes]:
    im=Image.open(io.BytesIO(raw));im.load()
    if im.width>1024 or im.height>50000:raise ValueError('capture_exceeds_bound_not_truncated')
    result=[]
    for y in range(0,im.height,1024):
        b=io.BytesIO();im.crop((0,y,im.width,min(y+1024,im.height))).save(b,format='PNG');result.append(b.getvalue())
    return result

def cli_config(model:str,system:str)->dict:
    if not model.startswith('opencode/')or not model.endswith('-free'):raise ValueError('nonfree_cli_model')
    return {'$schema':'https://opencode.ai/config.json','model':model,'small_model':model,
      'enabled_providers':['opencode'],'share':'disabled','autoupdate':False,
      'permission':{'*':'deny'},'compaction':{'auto':False},
      'provider':{'opencode':{'options':{'apiKey':'{env:OPENCODE_API_KEY}'}}},
      'agent':{'extract':{'description':'Extract supplied public evidence only','mode':'primary',
          'model':model,'prompt':system,'steps':1,'temperature':1,'permission':{'*':'deny'}},
        'title':{'disable':True},'summary':{'disable':True}}}

def cli_answer(raw:str)->str:
    events=[]
    for line in raw.splitlines():
        if not line.strip():continue
        try:events.append(json.loads(line))
        except ValueError:continue
    if any(e.get('type')in('error','tool_use')for e in events):raise ValueError('cli_error_or_tool')
    endings=[e for e in events if e.get('type')=='step_finish']
    if len(endings)!=1 or endings[0].get('part',{}).get('reason')!='stop':raise ValueError('cli_not_one_completed_step')
    text=''.join(e.get('part',{}).get('text','')for e in events if e.get('type')=='text')
    if not text.strip():raise ValueError('cli_empty_final')
    return text

def baseline_contract():
    code=ast.parse((HERE.parent/'direct_think_json/direct_sampling.py').read_text())
    system=next(ast.literal_eval(n.value)for n in code.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='SYSTEM'for t in n.targets))
    schema=json.loads((HERE.parent/'prompt_ab/practical_schema.json').read_text());offer=schema['properties']['offers']['items']
    f=offer['properties'].pop('redemption');f['description']='Что пользователь должен или может сделать, чтобы получить эту выгоду. Не на что потом потратить баллы.'
    offer['properties']['how_to_get']=f;offer['required']=['how_to_get'if x=='redemption'else x for x in offer['required']]
    return system,schema

def capture(out:Path):
    from playwright.sync_api import sync_playwright
    out.mkdir(parents=True,exist_ok=False);system,schema=baseline_contract()
    targets=json.loads((HERE.parent/'visual/targets-20260927.json').read_text())
    targets=[x for x in targets if x['id']in ('muzcomedy','nevsky','rzd_museum','lavka')]
    documents=[];reports=[];date=datetime.now(timezone.utc).date().isoformat()
    with sync_playwright()as pw:
        browser=pw.chromium.launch(headless=True)
        for target in targets:
            folder=out/target['id'];folder.mkdir();report={'id':target['id'],'url':target['url'],'status':'failed'}
            page=browser.new_page(viewport={'width':1024,'height':1024},locale='ru-RU')
            try:
                response=page.goto(target['url'],wait_until='domcontentloaded',timeout=60000)
                report['http_status']=response.status if response else None;report['final_url']=page.url
                if response is None or response.status>=400:raise ValueError('target_http_error')
                page.wait_for_timeout(2500)
                text=page.locator('body').inner_text(timeout=15000)
                if len(text.strip())<100:raise ValueError('empty_target')
                (folder/'source.html').write_text(page.content());(folder/'visible-text.txt').write_text(text)
                raw=page.screenshot(full_page=True,timeout=30000);(folder/'full.png').write_bytes(raw)
                images=tiles(raw)
                for i,b in enumerate(images,1):(folder/f'page-{i}.png').write_bytes(b)
                t={'partner':target['merchant'],'program':'Единая карта петербуржца'if target['program']=='ЕКП'else target['program'],'as_of':date}
                message='TARGET: '+json.dumps(t,ensure_ascii=False)+'\nSCHEMA: '+json.dumps(schema,ensure_ascii=False)+'\nВсе изображения идут по порядку страниц. Полный текст:\n'+text
                documents.append({'id':target['id'],'system':system,'text':message,'schema':schema,
                  'images':[base64.b64encode(b).decode()for b in images]})
                report.update(status='captured',text_chars=len(text),images=len(images),
                  image_sha256=[hashlib.sha256(b).hexdigest()for b in images],text_sha256=hashlib.sha256(text.encode()).hexdigest())
            except Exception as exc:report.update(error_type=type(exc).__name__,error=str(exc)[:500])
            finally:page.close()
            reports.append(report);print(json.dumps(report,ensure_ascii=False),flush=True)
        browser.close()
    routes.save(out/'inputs.json',documents)
    routes.save(out/'capture-summary.json',{'observed_at':datetime.now(timezone.utc).isoformat(),'historical_frozen_inputs':False,
                'publication_allowed':False,'sources':reports})

def run_cli(model:str,out:Path,inputs:Path|None):
    out.mkdir(parents=True,exist_ok=False);key=os.environ.get('OPENCODE_API_KEY','');keys=[key]
    summary={'model':model,'credential_present':bool(key.strip()),'publication_allowed':False,'client':'official_opencode_cli','cases':[]}
    routes.save(out/'summary.json',summary)
    if not key.strip():return
    docs=json.loads(inputs.read_text())if inputs else [{'id':'vision_smoke','system':'Read the attached image. Return only JSON matching the supplied schema.',
      'text':'Return the four digits shown in the image in the field code. SCHEMA: '+json.dumps(routes.SMOKE_SCHEMA),
      'schema':routes.SMOKE_SCHEMA,'images':[base64.b64encode(routes.smoke_image()).decode()]}]
    for doc in docs:
        folder=out/doc['id'];folder.mkdir();row={'case':doc['id'],'status':'failed'}
        with tempfile.TemporaryDirectory(prefix='opencode-eval-')as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();home=root/'home';home.mkdir()
            conf=cli_config(model,doc['system']);routes.save(folder/'config-without-secrets.json',conf)
            env={'PATH':os.environ['PATH'],'HOME':str(home),'LANG':'C.UTF-8','CI':'true','OPENCODE_API_KEY':key,
              'XDG_CONFIG_HOME':str(home/'.config'),'XDG_DATA_HOME':str(home/'.local/share'),
              'XDG_CACHE_HOME':str(home/'.cache'),'OPENCODE_CONFIG_CONTENT':json.dumps(conf),
              'OPENCODE_DISABLE_AUTOUPDATE':'true','OPENCODE_DISABLE_PROJECT_CONFIG':'true','OPENCODE_DISABLE_EXTERNAL_SKILLS':'true'}
            cmd=['opencode','run',doc['text'],'--model',model,'--agent','extract','--title','Public extraction evaluation','--format','json']
            for i,b in enumerate(doc['images'],1):
                path=work/f'page-{i}.png';path.write_bytes(base64.b64decode(b,validate=True));cmd.extend(['--file',str(path)])
            started=time.monotonic();proc=subprocess.Popen(cmd,cwd=work,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            try:stdout,stderr=proc.communicate(timeout=240)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGTERM);stdout,stderr=proc.communicate(timeout=15);row['error']='cli_timeout'
            row.update(seconds=round(time.monotonic()-started,3),returncode=proc.returncode)
            raw=routes.scrub(stdout.decode(errors='replace'),keys)
            (folder/'events.jsonl').write_text(raw);(folder/'stderr.txt').write_text(routes.scrub(stderr.decode(errors='replace'),keys))
            try:
                if proc.returncode!=0:raise ValueError('cli_nonzero_exit')
                text=cli_answer(raw);(folder/'answer.txt').write_text(text)
                value=routes.validate(text,doc['schema']);routes.save(folder/'extracted.json',value,keys)
                row.update(status='completed',schema_valid=True)
                if not inputs:row['vision_correct']=value=={'code':'7429'}
            except ValueError as exc:row['error']=str(exc)
            summary['cases'].append(row);routes.save(out/'summary.json',summary,keys);print(json.dumps(row),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['capture','cli']);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--model');p.add_argument('--inputs',type=Path);a=p.parse_args()
    if a.command=='capture':capture(a.out)
    else:run_cli(a.model,a.out,a.inputs)
if __name__=='__main__':main()
