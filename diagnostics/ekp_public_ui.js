const started = Date.now(), limit = started + 42000;
const result = {snapshots:[], actions:[], publicResponses:[], fullCatalogue:false, detailChecked:false};
const sleep = ms => new Promise(r=>setTimeout(r,ms));
const visible = n => n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden';
const isCard = u => u.origin==='https://ekp.spb.ru' && /^\/capabilities\/loyalty\/tiles\/[0-9]+\/?$/.test(u.pathname);
function publicUrl(value){
 const u=new URL(value,location.href);
 if(u.protocol!=='https:'||u.username||u.password)return null;
 const region=u.searchParams.get('region'); u.search='';u.hash='';
 if(region&&/^\d+$/.test(region))u.searchParams.set('region',region);
 return u.href;
}
function cards(){
 const found=new Map();
 for(const a of document.querySelectorAll('main a[href]')){
  const u=new URL(a.href), box=a.closest('.v-card');
  if(isCard(u)&&box)found.set(u.pathname,{url:publicUrl(a.href),title:box.querySelector('.v-card-title')?.innerText||'',login:box.innerText.includes('Требуется авторизация')});
 }
 return [...found.values()];
}
function snapshot(label){
 const main=document.querySelector('main');if(!main)return;
 const copy=main.cloneNode(true);
 for(const n of copy.querySelectorAll('script,style,noscript,form,input,textarea,iframe,[hidden],[aria-hidden="true"]'))n.remove();
 for(const n of copy.querySelectorAll('*')){
  for(const a of [...n.attributes])if(!['id','class','href','title','role'].includes(a.name))n.removeAttribute(a.name);
  if(n.hasAttribute('href')){const url=publicUrl(n.getAttribute('href'));if(url)n.setAttribute('href',url);else n.removeAttribute('href');}
 }
 if(copy.outerHTML.length>2500000)throw new Error('snapshot_limit');
 const snap={label,url:publicUrl(location.href),observedAt:new Date().toISOString(),cards:cards(),html:copy.outerHTML};
 const old=result.snapshots.findIndex(x=>x.label===label);
 if(old<0)result.snapshots.push(snap);else result.snapshots[old]=snap;
}
function restricted(){return /access denied|captcha|доступ к сайту временно ограничен|проверка безопасности/i.test(document.title+' '+document.body.innerText.slice(0,1000));}
const original=XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open=function(method,url,...args){
 const u=new URL(url,location.href);
 if(method.toUpperCase()==='GET'&&u.origin===location.origin&&/^\/api\/portal\/loyalty\/partners(?:\/\d+)?\/?$/.test(u.pathname)){
  this.addEventListener('load',()=>{
   if(result.publicResponses.length>=4)return;
   try{
    const body=this.responseType==='json'?this.response:JSON.parse(this.responseText);
    const encoded=JSON.stringify(body);
    if(encoded.length>2200000){result.responseError='public_response_size_limit';return;}
    result.publicResponses.push({path:u.pathname,status:this.status,observedAt:new Date().toISOString(),body});
   }catch{result.responseError='public_response_not_json';}
  },{once:true});
 }
 return original.call(this,method,url,...args);
};
try{
 const ready=Math.min(limit,Date.now()+8000);
 while(!cards().length&&Date.now()<ready&&!restricted())await sleep(300);
 if(restricted())throw new Error('restriction_document');
 if(!cards().length)throw new Error('cards_not_ready');
 snapshot('initial');
 const size=[...document.querySelectorAll('main button')].filter(n=>visible(n)&&!n.disabled&&n.innerText.trim()==='120');
 if(size.length===1){
  const before=cards().length;size[0].click();await sleep(1100);
  const until=Math.min(limit-9000,Date.now()+8000);
  while(cards().length<=before&&Date.now()<until&&!restricted())await sleep(300);
  result.actions.push({action:'page_size_120',before,after:cards().length});
  snapshot('expanded');
 }
 const more=[...document.querySelectorAll('main button')].filter(n=>visible(n)&&!n.disabled&&n.innerText.trim()==='Показать еще');
 if(more.length===1&&Date.now()<limit-15000){
  await sleep(1100);const before=cards().length;more[0].click();await sleep(1100);
  const until=Math.min(limit-10000,Date.now()+8000);
  while(cards().length<=before&&Date.now()<until&&!restricted())await sleep(300);
  result.actions.push({action:'load_more_once',before,after:cards().length});snapshot('expanded');
 }
 if(restricted())throw new Error('restriction_document');
 result.selected=cards().find(x=>!x.login&&x.title)||null;
 result.detailNotOpened='separate_navigation_kept_out_of_in_page_capture';
}catch(e){result.error=['snapshot_limit','restriction_document','cards_not_ready'].includes(e.message)?e.message:e.name;}
finally{XMLHttpRequest.prototype.open=original;}
result.finishedAt=new Date().toISOString();result.finalUrl=publicUrl(location.href);
const pre=document.createElement('pre');pre.id='loyalty-public-ui-evidence';pre.textContent=JSON.stringify(result);document.body.replaceChildren(pre);
