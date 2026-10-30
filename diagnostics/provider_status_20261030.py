"""One-shot provider audit; no queue, publishing, account changes or paid fallback."""
from __future__ import annotations
import argparse, base64, hashlib, io, json, os, re, time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont
import deepseek_capacity_probe as common

ROUTES = {
 'orcarouter': ('https://api.orcarouter.ai/v1/chat/completions', ['deepseek/deepseek-v4.1-flash-free','z-ai/glm-5.3-flash-free','tencent/hy4-preview-free']),
 'tokenharbor': ('https://tokenharbor.ai/v1/chat/completions', ['deepseek-v4.1-flash:free','mimo-v2.6-flash:free']),
 'openrouter': ('https://openrouter.ai/api/v1/chat/completions', ['nvidia/nemotron-3.5-super-vl:free','google/gemma-4-31b-it:free','qwen/qwen3.8-27b:free','deepseek/deepseek-v4.1-flash:free']),
 'opencode': ('https://opencode.ai/inference/openai/v1/chat/completions', ['deepseek-v4.1-flash-free','glm-5.3-flash-free','mimo-v2.6-flash-free']),
 'gemini': ('https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent', ['gemini-3.8-flash']),
 'vercel': ('https://ai-gateway.vercel.sh/v1/chat/completions', ['deepseek/deepseek-v4.1-flash-1017','deepseek/deepseek-v4.1-flash','google/gemini-3.8-flash']),
 'experiential': ('https://api.experientiallabs.ai/v1/chat/completions', ['deepseek-v4.1-flash:free','deepseek-v4.1-flash-1017:free']),
 'kilo': ('https://ai-gateway.kilo.ai/api/v1/chat/completions', []),
 'cohere': ('https://api.cohere.ai/compatibility/v1/chat/completions', ['command-a-vision-07-2025']),
 'scaleway': ('https://api.scaleway.ai/v1/models', []),
 'nvidia': ('https://integrate.api.nvidia.com/v1/models', []),
 'nebius': ('https://api.tokenfactory.nebius.com/v1/models', []),
}
CATALOGS = {
 'orcarouter':'https://api.orcarouter.ai/v1/models',
 'tokenharbor':'https://tokenharbor.ai/v1/models',
 'openrouter':'https://openrouter.ai/api/v1/models',
 'kilo':'https://ai-gateway.kilo.ai/api/v1/models',
 'experiential':'https://api.experientiallabs.ai/api/v1/models',
 'vercel':'https://ai-gateway.vercel.sh/v1/models',
 'cohere':'https://api.cohere.ai/v1/models',
}
PRIVATE=[]
def clean(value):
 s=json.dumps(value,ensure_ascii=False,allow_nan=False)
 for secret in PRIVATE:
  if secret:
   for x in (secret,json.dumps(secret)[1:-1],base64.b64encode(secret.encode()).decode()):s=s.replace(x,'[REDACTED]')
 s=re.sub(r'\bxpl_[A-Za-z0-9_-]+','[REDACTED]',s)
 return json.loads(s)
def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2))
def smoke():
 im=Image.new('RGB',(340,110),'white')
 ImageDraw.Draw(im).text((20,15),'5837',fill='black',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',64))
 b=io.BytesIO();im.save(b,format='PNG')
 return {'id':'vision','system':'Read only the supplied image. Return only JSON.','text':'Return the four digits visible in the image. SCHEMA: '+json.dumps(common.SMOKE_SCHEMA),'images':[base64.b64encode(b.getvalue()).decode()],'schema':common.SMOKE_SCHEMA}
def model_rows(data):
 if not isinstance(data,dict):return []
 rows=data.get('data',data.get('models',[]))
 if isinstance(rows,dict):rows=[dict(v,id=k) for k,v in rows.items() if isinstance(v,dict)]
 return rows if isinstance(rows,list) else []
def zero_price(m):
 p=m.get('pricing',{})
 try:return isinstance(p,dict) and 'prompt' in p and 'completion' in p and Decimal(str(p['prompt']))==0 and Decimal(str(p['completion']))==0
 except Exception:return False
def request_payload(doc,provider,model):
 if model not in ROUTES[provider][1] and provider!='kilo':raise ValueError('unapproved_route')
 if provider=='kilo' and not model.endswith(':free'):raise ValueError('paid_route')
 if provider in ('orcarouter','tokenharbor','openrouter','opencode','experiential') and not model.endswith((':free','-free')):raise ValueError('paid_route')
 if provider=='gemini':
  return {'systemInstruction':{'parts':[{'text':doc['system']}]},'contents':[{'role':'user','parts':[{'text':doc['text']},*[{'inlineData':{'mimeType':'image/png','data':im}} for im in doc['images']]]}], 'generationConfig':{'maxOutputTokens':4096 if doc['id']=='vision' else 16384,'responseMimeType':'application/json'}}
 p=common.build_payload(doc,model);p['max_tokens']=4096 if doc['id']=='vision' else 16384
 if provider in ('orcarouter','openrouter'):p['reasoning']={'enabled':True,'effort':'high'}
 return p
class Audit:
 def __init__(self,provider,out):
  self.provider,self.out=provider,out;self.key=os.environ.pop('LLM_PROBE_KEY','').strip();PRIVATE.append(self.key)
  self.session=requests.Session();self.session.trust_env=False
  self.report={'provider':provider,'checked_at':datetime.now(timezone.utc).isoformat(),'credential_present':bool(self.key),'reads':[],'attempts':[],'generation_requests':0,'production_changed':False,'account_mutations':0}
 def read(self,label,url,auth=True):
  h={'Accept':'application/json'}
  if auth and self.key:h['Authorization']='Bearer '+self.key
  row={'label':label,'endpoint':url,'authenticated':auth};data={}
  try:
   r=self.session.get(url,headers=h,timeout=(15,45),allow_redirects=False);row['http_status']=r.status_code;data=r.json()
   row['response_sha256']=hashlib.sha256(r.content).hexdigest()
   if r.status_code!=200:row['error']=data
  except (requests.RequestException,ValueError) as e:row['error_type']=type(e).__name__
  self.report['reads'].append(row)
  return data,row
 def checkpoint(self):save(self.out/'summary.json',self.report)
 def generate(self,model,doc,index):
  p=request_payload(doc,self.provider,model);url=ROUTES[self.provider][0]
  headers={'Content-Type':'application/json'}
  if self.provider=='gemini':headers['x-goog-api-key']=self.key
  else:headers['Authorization']='Bearer '+self.key
  raw=json.dumps(p,ensure_ascii=False).encode();folder=self.out/f'route-{index}'/doc['id'];folder.mkdir(parents=True,exist_ok=True)
  row={'model':model,'case':doc['id'],'endpoint':url,'request_bytes':len(raw),'request_sha256':hashlib.sha256(raw).hexdigest(),'started_at':datetime.now(timezone.utc).isoformat()}
  self.report['generation_requests']+=1;self.report['attempts'].append(row);self.checkpoint();start=time.monotonic();data={}
  try:
   r=self.session.post(url,headers=headers,data=raw,timeout=(15,180),allow_redirects=False)
   row.update(http_status=r.status_code,seconds=round(time.monotonic()-start,3),headers={k:v for k,v in r.headers.items() if k.lower().startswith(('x-ratelimit-','x-gateway-cost','x-request-id')) or k.lower()=='retry-after'})
   try:data=r.json()
   except ValueError:data={'non_json_response':r.text[:500]}
   save(folder/'response.json',data)
   if r.status_code!=200:row['error']=data;row['status']='api_error'
   else:
    if self.provider=='gemini':
     c=data.get('candidates',[{}])[0];row['finish_reason']=c.get('finishReason');row['usage']=data.get('usageMetadata');row['returned_model']=data.get('modelVersion')
     if c.get('finishReason')!='STOP':raise ValueError('incomplete_generation')
     value=common.validate_content(''.join(x.get('text','') for x in c.get('content',{}).get('parts',[]) if not x.get('thought')),doc['schema'])
    else:
     row['returned_model']=data.get('model');row['usage']=data.get('usage');row['finish_reason']=(data.get('choices') or [{}])[0].get('finish_reason');value=common.validate_response(data,doc['schema'])
    row['status']='completed';row['schema_valid']=True
    if doc['id']=='vision':row['vision_correct']=value=={'code':'5837'}
    else:
     quotes=[q for offer in value.get('offers',[]) for q in offer.get('evidence',[])]
     source=' '.join(doc['text'].split('Полный текст:\n',1)[-1].split())
     row['quotes_found']=sum(' '.join(q.split()) in source for q in quotes);row['quotes_total']=len(quotes)
    save(folder/'extracted.json',value)
  except requests.RequestException as e:row.update(status='transport_error',error_type=type(e).__name__,unknown_execution_outcome=True,seconds=round(time.monotonic()-start,3))
  except Exception as e:row.update(status='response_not_complete_json',validation_error=type(e).__name__+': '+str(e)[:220])
  save(folder/'measurement.json',row);self.checkpoint();return row,data
 def run(self,inputs):
  if not self.key:self.report['status']='credential_missing';return
  models=list(ROUTES[self.provider][1]);catalog=[]
  if self.provider in CATALOGS:
   data,row=self.read('models',CATALOGS[self.provider]);catalog=model_rows(data)
   self.report['catalog']=[{k:m.get(k) for k in ('id','name','canonical_slug','pricing','architecture','supported_parameters','input_modalities')} for m in catalog if str(m.get('id','')).endswith((':free','-free')) or any(w in str(m.get('id',m.get('name',''))).lower() for w in ('deepseek','gemini-3.8','command-a-vision','nemotron','glm-5.3','mimo-v2.6','qwen3.8'))]
  if self.provider=='orcarouter':
   d,_=self.read('free_package','https://www.orcarouter.ai/api/free-package/public',False);self.report['published_quotas']=d
  if self.provider=='openrouter':
   d,_=self.read('key_limits','https://openrouter.ai/api/v1/key');v=d.get('data',{})
   self.report['key_limits']={k:v.get(k) for k in ('limit','limit_remaining','is_free_tier','usage','usage_daily','usage_weekly','usage_monthly')}
   if catalog:
    ids={m.get('id') for m in catalog};self.report['absent_free_models']=[m for m in models if m not in ids];models=[m for m in models if m in ids]
  if self.provider=='kilo':
   viable=[m for m in catalog if str(m.get('id','')).endswith(':free') and zero_price(m) and 'image' in m.get('architecture',{}).get('input_modalities',[])]
   def rank(m):
    s=m['id'].lower()
    return (0 if 'nemotron' in s else 1 if 'qwen3.8' in s else 2 if 'mimo' in s else 3 if 'kimi' in s else 4,s)
   models=[m['id'] for m in sorted(viable,key=rank)[:2]]
   if not models:self.report['status']='no_verified_zero_price_vision_route';return
  if self.provider=='experiential':
   for label,path in [('key','/api/v1/key'),('credits_before','/api/v1/credits')]:
    d,_=self.read(label,'https://api.experientiallabs.ai'+path);v=d.get('data',{})
    self.report[label]={k:v.get(k) for k in ('is_free_tier','usage','total_credits','total_usage') if k in v}
   self.report['promotions']={}
   for m in ['deepseek-v4.1-flash','deepseek-v4.1-flash-1017','glm-5.3-uncensored']:
    d,_=self.read('promotion:'+m,'https://api.experientiallabs.ai/api/models/'+m)
    self.report['promotions'][m]={k:d.get(k) for k in ('promotional_listed','promotions','retention')}
  if self.provider in ('scaleway','nvidia','nebius'):
   d,row=self.read('models',ROUTES[self.provider][0]);self.report['catalog_ids']=[m.get('id',m.get('name')) for m in model_rows(d)]
   self.report['status']='catalog_read_only_free_account_budget_unverified';return
  if self.provider=='vercel':
   d,row=self.read('credits_before','https://ai-gateway.vercel.sh/v1/credits');self.report['credits_before']=d
   v=common.credit_numbers(d)
   if row.get('http_status')!=200 or v is None or not (v==(Decimal(0),Decimal(0)) or Decimal('4.75')<=v[0]<=5 and Decimal('4.99')<=sum(v)<=Decimal('5.01')):
    self.report['status']='read_only_credit_provenance_unverified';return
  smoke_doc=smoke();docs=inputs.get('documents',[]) if isinstance(inputs,dict) else []
  chosen=next((d for d in docs if d.get('id')=='muzcomedy'),docs[0] if docs else None)
  for index,model in enumerate(models):
   if index:time.sleep(7)
   row,data=self.generate(model,smoke_doc,index)
   if self.provider=='vercel':
    d,_=self.read('credits_after','https://ai-gateway.vercel.sh/v1/credits');self.report['credits_after']=d;v=common.credit_numbers(d)
    if row.get('http_status')==200 and (v is None or not (Decimal('4.75')<=v[0]<=5 and Decimal('4.99')<=sum(v)<=Decimal('5.01'))):
     self.report['status']='free_credit_origin_not_confirmed';break
   elif common.existing.reported_cost_warning(data):self.report['status']='cost_anomaly';break
   if row.get('vision_correct') and chosen:
    time.sleep(7);r,d=self.generate(model,chosen,index)
    if self.provider=='vercel':
     cr,_=self.read('credits_after_document','https://ai-gateway.vercel.sh/v1/credits');self.report['credits_after']=cr
     break
    if common.existing.reported_cost_warning(d):self.report['status']='cost_anomaly';break
   err=data.get('error',{}) if isinstance(data,dict) else {}
   if isinstance(err,dict) and err.get('type')=='customer_verification_required':break
   if row.get('http_status') in (401,402):break
   if row.get('http_status')==429 and self.provider in ('tokenharbor','opencode'):break
   if row.get('http_status')==429 and self.provider=='openrouter' and (not isinstance(err,dict) or not err.get('metadata',{}).get('provider_name')):break
   if row.get('unknown_execution_outcome'):break
  if self.provider=='experiential':
   d,_=self.read('credits_after','https://api.experientiallabs.ai/api/v1/credits');self.report['credits_after']={k:v for k,v in d.get('data',{}).items() if k in ('total_credits','total_usage')}
  self.report.setdefault('status','audit_completed')

def main():
 p=argparse.ArgumentParser();p.add_argument('provider',choices=ROUTES);p.add_argument('--inputs',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();inputs={}
 if a.inputs and a.inputs.exists():
  d=json.loads(a.inputs.read_text());inputs={'documents':d} if isinstance(d,list) else d
 audit=Audit(a.provider,a.out)
 try:audit.run(inputs)
 finally:
  audit.checkpoint();print(json.dumps(clean(audit.report),ensure_ascii=False));audit.session.close()
if __name__=='__main__':main()
