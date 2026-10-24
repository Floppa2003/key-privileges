"""Bounded, review-only free endpoint comparison. No publication or paid fallback."""
from __future__ import annotations
import argparse, base64, hashlib, io, json, os, re, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
import requests
import jsonschema
from PIL import Image, ImageDraw, ImageFont

ROUTES = {
 'orca': {'base':'https://api.orcarouter.ai/v1','models':['z-ai/glm-5.3-flash-free','deepseek/deepseek-v4.1-flash-free']},
 'harbor': {'base':'https://tokenharbor.ai/v1','models':['mimo-v2.6-flash:free','deepseek-v4.1-flash:free']},
 'opencode': {'base':'https://opencode.ai/zen/v1','models':['glm-5.3-flash-free','deepseek-v4.1-flash-free','mimo-v2.6-flash-free']},
 'openrouter': {'base':'https://openrouter.ai/api/v1','models':['qwen/qwen3.8-27b:free','google/gemma-4-31b-it:free']},
 'vercel': {'base':'https://ai-gateway.vercel.sh/v1','models':['minimax/minimax-m3.1-flash','minimax/minimax-m3']},
 'gemini': {'base':'https://generativelanguage.googleapis.com/v1beta','models':['gemini-3.8-flash']},
}
SMOKE_SCHEMA={'type':'object','properties':{'code':{'type':'string'}},'required':['code'],'additionalProperties':False}

def scrub(text,keys):
    for key in keys:
        if key:text=text.replace(key,'[REDACTED]')
    return text

def save(path,value,keys=()):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(scrub(json.dumps(value,ensure_ascii=False,indent=2),keys),encoding='utf-8')

def payload(provider,model,system,text,images,schema):
    # Schema is visible in text. No server-side schema capability preflight.
    if provider=='gemini':
        return {'systemInstruction':{'parts':[{'text':system}]},
          'contents':[{'role':'user','parts':[{'text':text},*[
            {'inlineData':{'mimeType':'image/png','data':b}}for b in images]]}],
          'generationConfig':{'temperature':1,'maxOutputTokens':8192,
            'thinkingConfig':{'thinkingLevel':'HIGH','includeThoughts':False},
            'responseMimeType':'application/json','responseJsonSchema':schema}}
    result={'model':model,'stream':False,'max_tokens':8192,'temperature':1,
      'messages':[{'role':'system','content':system},
        {'role':'user','content':[{'type':'text','text':text},*[
          {'type':'image_url','image_url':{'url':'data:image/png;base64,'+b}}for b in images]]}]}
    if provider in ('orca','openrouter'):
        result['reasoning']={'enabled':True,'effort':'high'}
    return result

def final_text(provider,data):
    if provider=='gemini':
        choices=data.get('candidates',[])
        if len(choices)!=1 or choices[0].get('finishReason')!='STOP':raise ValueError('unfinished_generation')
        parts=choices[0].get('content',{}).get('parts',[])
        if any('functionCall'in p for p in parts):raise ValueError('unexpected_tool_call')
        content=''.join(p.get('text','')for p in parts if not p.get('thought'))
    else:
        choices=data.get('choices',[])
        if len(choices)!=1 or choices[0].get('finish_reason')!='stop':raise ValueError('unfinished_generation')
        message=choices[0].get('message',{})
        if message.get('tool_calls') or message.get('refusal'):raise ValueError('unexpected_tool_or_refusal')
        content=message.get('content')
    if not isinstance(content,str)or not content.strip():raise ValueError('empty_final')
    return content

def validate(text,schema):
    # A single Markdown envelope is transport formatting, not a content error.
    # Preserve raw responses; never repair JSON or select a block from prose.
    text=text.strip()
    envelope=re.fullmatch(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n```",text,flags=re.DOTALL|re.IGNORECASE)
    if envelope:text=envelope.group(1)
    try:
        value=json.loads(text);jsonschema.validate(value,schema)
    except (json.JSONDecodeError,jsonschema.ValidationError)as exc:raise ValueError('invalid_final_json')from exc
    if isinstance(value,dict)and 'has_offer'in value and value['has_offer']!=bool(value.get('offers')):
        raise ValueError('offer_state_mismatch')
    return value

def is_zero_priced(model):
    p=model.get('pricing',{})
    pair=('input','output')if 'input'in p else ('prompt','completion')
    try:return all(k in p and Decimal(str(p[k]))==0 for k in pair)
    except (InvalidOperation,TypeError):return False

def http(session,method,url,headers,body,keys):
    started=time.monotonic()
    try:
        r=session.request(method,url,headers=headers,json=body,timeout=(10,180),allow_redirects=False)
        raw=scrub(r.content.decode('utf-8',errors='replace'),keys)
        try:data=json.loads(raw)
        except ValueError:data={'non_json_response':raw[:1200]}
        return {'http_status':r.status_code,'seconds':round(time.monotonic()-started,3),'body':data}
    except requests.RequestException as exc:
        return {'http_status':None,'seconds':round(time.monotonic()-started,3),'error_type':type(exc).__name__}

def smoke_image():
    image=Image.new('RGB',(512,160),'white');draw=ImageDraw.Draw(image)
    draw.text((35,50),'7429',font=ImageFont.load_default(size=64),fill='black')
    buf=io.BytesIO();image.save(buf,format='PNG');return buf.getvalue()

def main():
    p=argparse.ArgumentParser();p.add_argument('--provider',choices=ROUTES,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--inputs',type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    key=os.environ.get('LLM_PROVIDER_KEY','');keys=[key];route=ROUTES[a.provider]
    summary={'provider':a.provider,'credential_present':bool(key.strip()),'publication_allowed':False,'attempts':[],
             'phase':'frozen_benchmark'if a.inputs else 'synthetic_vision_smoke','paid_fallback':False}
    save(a.out/'summary.json',summary)
    if not key.strip():return 0
    session=requests.Session();session.trust_env=False
    headers={'Content-Type':'application/json'}
    headers.update({'x-goog-api-key':key}if a.provider=='gemini'else{'Authorization':'Bearer '+key})
    catalog=http(session,'GET',route['base']+'/models',headers,None,keys)
    body=catalog.pop('body',{});summary['catalog']=catalog
    models=body.get('data',body.get('models',[]))if isinstance(body,dict)else []
    # Keep only requested public model metadata, not private account information.
    selected=[m for m in models if isinstance(m,dict)and m.get('id',m.get('name','').removeprefix('models/'))in route['models']]
    save(a.out/'catalog-selected.json',selected,keys)
    if a.inputs:
        documents=json.loads(a.inputs.read_text())
    else:
        raw=smoke_image();(a.out/'smoke.png').write_bytes(raw)
        documents=[{'id':'vision_smoke','system':'Read the attached image. Return only JSON matching the supplied schema.',
         'text':'Return the four digits shown in the image in the field code. SCHEMA: '+json.dumps(SMOKE_SCHEMA),
         'images':[base64.b64encode(raw).decode()],'schema':SMOKE_SCHEMA}]
    for model in route['models']:
        if a.provider=='vercel':
            match=[m for m in selected if m.get('id')==model]
            if len(match)!=1 or not is_zero_priced(match[0]):
                summary['attempts'].append({'model':model,'status':'not_called','reason':'no_confirmed_zero_price_route','inference_attempts':0});continue
        for doc in documents:
            folder=a.out/model.replace('/','__').replace(':','_')/doc['id'];folder.mkdir(parents=True)
            row={'requested_model':model,'case':doc['id'],'status':'failed','schema_valid':False,'inference_attempts':1}
            request=payload(a.provider,model,doc['system'],doc['text'],doc['images'],doc['schema'])
            request_hash=hashlib.sha256(json.dumps(request,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            row['request_sha256']=request_hash
            save(folder/'input-manifest.json',{'system':doc['system'],'text':doc['text'],'schema':doc['schema'],
              'images':[hashlib.sha256(base64.b64decode(b,validate=True)).hexdigest()for b in doc['images']],
              'request_sha256':request_hash},keys)
            url=route['base']+('/models/'+model+':generateContent'if a.provider=='gemini'else'/chat/completions')
            result=http(session,'POST',url,headers,request,keys)
            data=result.pop('body',{});row.update(result)
            save(folder/'response.json',data,keys)
            if result.get('http_status')==200:
                try:
                    text=final_text(a.provider,data);(folder/'answer.txt').write_text(scrub(text,keys))
                    obj=validate(text,doc['schema']);save(folder/'extracted.json',obj,keys)
                    row.update(status='completed',schema_valid=True,output_wrapper='markdown_fence'if text.strip().startswith('```')else'none',returned_model=data.get('model',data.get('modelVersion')),
                               usage=data.get('usage',data.get('usageMetadata')))
                    if not a.inputs:row['vision_correct']=obj=={'code':'7429'}
                except ValueError as exc:row['error']=str(exc)
            elif isinstance(data,dict):
                err=data.get('error',{})
                row['api_error']=scrub(str(err)[:600],keys)
            save(folder/'measurement.json',row,keys);summary['attempts'].append(row)
            save(a.out/'summary.json',summary,keys)
            print(json.dumps({k:v for k,v in row.items()if k not in ('usage','api_error')},ensure_ascii=False),flush=True)
    save(a.out/'summary.json',summary,keys)
    return 0 # A diagnostic run finishing is not the same as endpoints succeeding.

if __name__=='__main__':raise SystemExit(main())
