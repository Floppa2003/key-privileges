// Read the public UI, then return its evidence. No fetch/API replay or sign-in.
const deadline=Date.now()+40000,result={cards:[],details:[],actions:[]};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function url(x){const u=new URL(x,location.href);return u.origin==='https://ekp.spb.ru'&&/^\/capabilities\/loyalty\/tiles\/\d+\/?$/.test(u.pathname)&&[...u.searchParams].every(([k,v])=>k==='region'&&/^\d+$/.test(v))?u.href:null;}
function cards(){const rows=[];for(const a of document.querySelectorAll('main a[href]')){const u=url(a.href),n=a.closest('.v-card');if(u&&n&&a.textContent.trim()==='Подробнее')rows.push({url:u,title:n.querySelector('.v-card-title').textContent.trim(),locked:n.textContent.includes('Требуется авторизация')});}return rows;}
function clean(n){const x=n.cloneNode(true);for(const e of x.querySelectorAll('script,style,noscript,svg,img,form,input,textarea,iframe,button,[hidden],[aria-hidden="true"]'))e.remove();for(const e of [x,...x.querySelectorAll('*')]){for(const a of [...e.attributes])if(!['id','class','href','title','role'].includes(a.name))e.removeAttribute(a.name);if(e.hasAttribute('href')){try{const u=new URL(e.getAttribute('href'),location.href);if(!['http:','https:'].includes(u.protocol)||u.username||u.password)e.removeAttribute('href');else{u.search='';u.hash='';e.setAttribute('href',u.href);}}catch{e.removeAttribute('href');}}}return x.outerHTML;}
try{
 while(!cards().length&&Date.now()<deadline-30000)await sleep(100);
 const b=[...document.querySelectorAll('main button')].filter(n=>!n.disabled&&n.textContent.trim()==='120');
 if(b.length!==1)throw Error('size_control_not_unique');const before=cards().length;b[0].click();
 while(cards().length<=before&&Date.now()<deadline-18000)await sleep(150);
 result.cards=cards();result.catalogueUrl=location.href;result.actions.push({action:'visible_page_size_120',before,after:result.cards.length});
 const samples=[...result.cards.filter(x=>!x.locked).slice(0,3),...result.cards.filter(x=>x.locked).slice(0,1)];
 for(const c of samples){if(Date.now()>deadline-4000)break;
  const a=[...document.querySelectorAll('main a[href]')].find(x=>url(x.href)===c.url&&x.textContent.trim()==='Подробнее');if(!a)throw Error('card_link_missing');a.click();
  const id=new URL(c.url).pathname.match(/(\d+)\/?$/)[1],until=Date.now()+2500;let n;
  do{await sleep(100);n=document.getElementById('partner.'+id);}while((!n||url(location.href)!==c.url)&&Date.now()<until);
  if(!n||url(location.href)!==c.url)throw Error('detail_not_ready');
  result.details.push({...c,observedAt:new Date().toISOString(),html:clean(n)});
  const close=n.querySelector('.v-card > button.v-btn--absolute');if(!close)throw Error('close_missing');close.click();await sleep(300);
 }
}catch(e){result.error=/^[a-z_]+$/.test(e.message)?e.message:e.name;}
result.finishedAt=new Date().toISOString();result.finalUrl=location.href;
const pre=document.createElement('pre');pre.id='loyalty-api-bridge';pre.textContent=JSON.stringify(result);document.body.replaceChildren(pre);
