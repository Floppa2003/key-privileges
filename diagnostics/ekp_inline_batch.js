// Ordinary source-owned detail links only. No login, coupon, form or API replay.
const deadline=Date.now()+42000, result={details:[],actions:[],initialCards:[],fullCatalogue:false};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const cardURL=value=>{const u=new URL(value,location.href);const q=[...u.searchParams];
 if(u.origin!=='https://ekp.spb.ru'||!/^\/capabilities\/loyalty\/tiles\/\d+\/?$/.test(u.pathname)||u.hash||
    q.length>1||(q.length===1&&(q[0][0]!=='region'||!/^\d+$/.test(q[0][1]))))return null;
 return u.href;};
function cards(){const found=new Map();for(const a of document.querySelectorAll('main a[href]')){
 const url=cardURL(a.href),box=a.closest('.v-card'),title=box?.querySelector('.v-card-title')?.innerText.trim();
 if(url&&box&&title&&a.innerText.trim()==='Подробнее')found.set(url,{url,title,loginNotice:box.innerText.includes('Требуется авторизация')});}
 return [...found.values()];}
function resources(){const found=new Map();for(const r of performance.getEntriesByType('resource')){
 const u=new URL(r.name);if(u.origin!==location.origin||!u.pathname.startsWith('/api/portal/')||
 /auth|user|profile|cabinet|session|token|metrics/i.test(u.pathname))continue;
 const q=[...u.searchParams];const safe=q.every(([k,v])=>/^(region|regionId|page|pageSize|size|limit|offset|count|categoryId|skip|take)$/i.test(k)&&/^\d{1,8}$/.test(v));
 const value={path:u.pathname,queryKeys:q.map(x=>x[0]),url:safe?u.href:null};found.set(JSON.stringify(value),value);
 }return [...found.values()].slice(0,100);}
function restricted(){return /access denied|captcha|проверка безопасности|доступ к сайту временно ограничен/i.test(document.title+' '+document.body.innerText.slice(0,800));}
function owner(entry){const id=new URL(entry.url).pathname.match(/\/(\d+)\/?$/)[1];return document.getElementById('partner.'+id);}
function ready(entry){const n=owner(entry);if(!n||cardURL(location.href)!==entry.url)return false;
 const t=n.innerText;return t.includes('Программа лояльности')||t.includes('Для просмотра подробной информации о программе лояльности авторизуйтесь');}
function clean(node){const copy=node.cloneNode(true);for(const n of copy.querySelectorAll('script,style,noscript,svg,img,form,input,textarea,iframe,button,[hidden],[aria-hidden="true"]'))n.remove();
 for(const n of [copy,...copy.querySelectorAll('*')]){for(const a of [...n.attributes])if(!['id','class','href','role','title'].includes(a.name))n.removeAttribute(a.name);
  if(n.hasAttribute('href')){const u=new URL(n.getAttribute('href'),location.href);if(!['https:','http:'].includes(u.protocol)||u.username||u.password)n.removeAttribute('href');
   else{const card=cardURL(u.href);u.search='';u.hash='';n.setAttribute('href',card||u.href);}}}
 if(copy.outerHTML.length>150000)throw Error('detail_size_limit');return copy.outerHTML;}
try{
 while(!cards().length&&Date.now()<deadline-32000&&!restricted())await sleep(300);
 if(restricted())throw Error('restriction_document');
 result.initialResources=resources();result.initialCards=cards();if(!result.initialCards.length)throw Error('cards_missing');
 const publicCards=result.initialCards.filter(x=>!x.loginNotice),locked=result.initialCards.filter(x=>x.loginNotice);
 const selected=[...publicCards.slice(0,1),...locked.slice(0,1),...publicCards.slice(1,8)];result.selected=selected;
 for(const entry of selected){
  if(Date.now()>deadline-5500){result.stopReason='time_budget';break;}
  if(restricted())throw Error('restriction_document');
  const links=[...document.querySelectorAll('main a[href]')].filter(a=>cardURL(a.href)===entry.url&&a.innerText.trim()==='Подробнее');
  if(links.length!==1){result.actions.push({url:entry.url,error:'detail_link_not_unique'});break;}
  links[0].scrollIntoView({block:'center'});await sleep(1100);links[0].click();
  const until=Math.min(deadline-1000,Date.now()+5000);
  while(!ready(entry)&&Date.now()<until&&!restricted())await sleep(250);
  if(restricted())throw Error('restriction_document');
  if(!ready(entry)){result.actions.push({url:entry.url,error:'detail_not_ready',finalPath:location.pathname});break;}
  const n=owner(entry),title=n.querySelector('.v-card-title')?.innerText.trim();
  if(title!==entry.title)throw Error('detail_title_mismatch');
  result.details.push({...entry,observedAt:new Date().toISOString(),finalUrl:location.href,html:clean(n)});
  result.actions.push({url:entry.url,action:'source_detail_opened'});
  const close=[...n.querySelectorAll('.v-card > button.v-btn--absolute')].filter(x=>!x.disabled);
  if(close.length!==1){result.stopReason='close_control_not_unique';break;}
  await sleep(1100);close[0].click();await sleep(200);
 }
 result.stopReason=result.stopReason||'selected_batch_finished';
}catch(e){result.error=/^[a-z_]+$/.test(e.message)?e.message:e.name;}
result.finalResources=resources();result.finishedAt=new Date().toISOString();result.finalPath=location.pathname;
const pre=document.createElement('pre');pre.id='loyalty-inline-evidence';pre.textContent=JSON.stringify(result);document.body.replaceChildren(pre);
