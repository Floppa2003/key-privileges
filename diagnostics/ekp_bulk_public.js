// Anonymous, ordinary UI only. Catalogue and inline modals are separate evidence.
const cfg=__EKP_CONFIG__, deadline=Date.now()+43000;
const result={inventory:[],details:[],actions:[],errors:[],catalogueComplete:false,selectedComplete:false,config:cfg};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const frame=()=>new Promise(r=>requestAnimationFrame(r));
const visible=n=>n.getClientRects().length&&getComputedStyle(n).visibility!=='hidden';
function cardURL(value){const u=new URL(value,location.href),q=[...u.searchParams];
 if(u.origin!=='https://ekp.spb.ru'||!/^\/capabilities\/loyalty\/tiles\/\d+\/?$/.test(u.pathname)||u.hash||q.length>1||
 (q.length&&(q[0][0]!=='region'||!/^\d+$/.test(q[0][1]))))return null;return u.href;}
function cards(){const out=new Map();for(const a of document.querySelectorAll('main a[href]')){
 const url=cardURL(a.href),n=a.closest('.v-card'),title=n?.querySelector('.v-card-title')?.innerText.trim();
 if(!url||!n||!title||a.innerText.trim()!=='Подробнее')continue;
 const v={url,title,loginNotice:n.innerText.includes('Требуется авторизация'),preview:n.innerText.trim()};
 if(out.has(url)&&JSON.stringify(out.get(url))!==JSON.stringify(v))throw Error('conflicting_catalogue_card');out.set(url,v);
 }return [...out.values()];}
function more(){return [...document.querySelectorAll('main button')].filter(n=>visible(n)&&!n.disabled&&n.innerText.trim()==='Показать еще');}
function apiCount(){return performance.getEntriesByType('resource').filter(r=>{try{const u=new URL(r.name);return u.origin==='https://ekp.spb.ru'&&u.pathname.startsWith('/api/portal/loyalty/');}catch{return false;}}).length;}
function restricted(){return /access denied|captcha|проверка безопасности|доступ к сайту временно ограничен/i.test(document.title+' '+document.body.innerText.slice(0,800));}
function clean(node){const copy=node.cloneNode(true);for(const n of copy.querySelectorAll('script,style,noscript,svg,img,form,input,textarea,iframe,button,[hidden],[aria-hidden="true"]'))n.remove();
 for(const n of [copy,...copy.querySelectorAll('*')]){for(const a of [...n.attributes])if(!['id','class','href','role','title'].includes(a.name))n.removeAttribute(a.name);
 if(n.hasAttribute('href')){const u=new URL(n.getAttribute('href'),location.href);if(!['https:','http:'].includes(u.protocol)||u.username||u.password)n.removeAttribute('href');
 else{const card=cardURL(u.href);u.search='';u.hash='';n.setAttribute('href',card||u.href);}}}
 if(copy.outerHTML.length>60000)throw Error('detail_size_limit');return copy.outerHTML;}
async function grow(button,label){const before=cards().length;button.click();await frame();
 const end=Math.min(deadline-15000,Date.now()+2500);while(cards().length<=before&&Date.now()<end&&!restricted())await sleep(50);
 const after=cards().length;result.actions.push({action:label,before,after});if(after<=before)throw Error('catalogue_no_growth');}
try{
 const ready=Date.now()+7000;while(!cards().length&&Date.now()<ready&&!restricted())await sleep(150);
 if(restricted())throw Error('restriction_document');if(!cards().length)throw Error('catalogue_not_ready');
 const sizes=[...document.querySelectorAll('main button')].filter(n=>visible(n)&&!n.disabled&&n.innerText.trim()==='120');
 if(sizes.length!==1)throw Error('page_size_not_unique');await grow(sizes[0],'page_size_120');
 for(let i=0;i<15&&Date.now()<deadline-18000;i++){
  const buttons=more();if(!buttons.length){result.catalogueComplete=true;break;}
  if(buttons.length!==1)throw Error('load_more_not_unique');await grow(buttons[0],'load_more');
 }
 result.inventory=cards();result.catalogueComplete=result.catalogueComplete||more().length===0;
 result.catalogueUrl=location.href;result.catalogueObservedAt=new Date().toISOString();
 result.paginationText=document.querySelector('main .v-pagination')?.innerText||null;
 result.filterText=[...document.querySelectorAll('main .v-select__selection-text')].map(n=>n.innerText.trim());
 result.apiBeforeDetails=apiCount();
 const sorted=[...result.inventory].sort((a,b)=>Number(new URL(a.url).pathname.match(/(\d+)\/?$/)[1])-Number(new URL(b.url).pathname.match(/(\d+)\/?$/)[1]));
 const selected=sorted.filter((_,i)=>i%cfg.shards===cfg.shard);result.selectedURLs=selected.map(x=>x.url);
 let chars=JSON.stringify(result).length;
 for(const entry of selected){
  if(Date.now()>deadline-1800||result.details.length>=cfg.maxDetails){result.stopReason='detail_time_or_count_bound';break;}
  if(restricted())throw Error('restriction_document');
  const a=[...document.querySelectorAll('main a[href]')].filter(n=>cardURL(n.href)===entry.url&&n.innerText.trim()==='Подробнее');
  if(a.length!==1)throw Error('detail_link_not_unique');a[0].click();await frame();
  const id=new URL(entry.url).pathname.match(/(\d+)\/?$/)[1];let n;
  const until=Math.min(deadline-1000,Date.now()+900);
  while(Date.now()<until){n=document.getElementById('partner.'+id);if(n&&cardURL(location.href)===entry.url&&
    (n.innerText.includes('Программа лояльности')||n.innerText.includes('Для просмотра подробной информации о программе лояльности авторизуйтесь')))break;await sleep(20);}
  if(!n||cardURL(location.href)!==entry.url){result.errors.push({url:entry.url,reason:'detail_not_ready'});break;}
  const title=n.querySelector('.v-card-title')?.innerText.trim();if(title!==entry.title)throw Error('detail_title_changed');
  let html;try{html=clean(n);}catch(e){result.errors.push({url:entry.url,reason:e.message});}
  if(html){const item={url:entry.url,title,finalUrl:location.href,observedAt:new Date().toISOString(),html};
   chars+=JSON.stringify(item).length;if(chars>2200000){result.stopReason='output_size_bound';break;}result.details.push(item);}
  const close=[...n.querySelectorAll('.v-card > button.v-btn--absolute')].filter(x=>!x.disabled);
  if(close.length!==1){result.stopReason='close_control_not_unique';break;}close[0].click();await frame();
  if(apiCount()>result.apiBeforeDetails){result.stopReason='detail_network_request_observed';break;}
 }
 result.apiAfterDetails=apiCount();result.selectedComplete=result.details.length===selected.length&&!result.errors.length;
 result.stopReason=result.stopReason||'selected_details_finished';
}catch(e){result.error=/^[a-z_]+$/.test(e.message)?e.message:e.name;}
result.finishedAt=new Date().toISOString();result.finalPath=location.pathname;
const pre=document.createElement('pre');pre.id='loyalty-bulk-evidence';pre.textContent=JSON.stringify(result);document.body.replaceChildren(pre);
