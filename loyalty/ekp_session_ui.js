// Known anonymous catalogue POST only; no account, coupon or arbitrary endpoint.
const API='https://ekp.spb.ru/api/portal/loyalty/partners', deadline=Date.now()+43000;
const result={pages:[],errors:[],startedAt:new Date().toISOString(),initialUrl:location.href,complete:false};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function sourceURL(){const u=new URL(location.href);if(u.origin!=='https://ekp.spb.ru'||!['/capabilities/loyalty/','/capabilities/loyalty/tiles','/capabilities/loyalty/tiles/'].includes(u.pathname))throw Error('root_identity_changed');}
function projection(row){
 if(!row||typeof row.id!=='string'||!/^\d{1,12}$/.test(row.id)||typeof row.name!=='string'||!row.name.trim()||
 typeof row.active!=='boolean'||typeof row.description_authorized!=='boolean')throw Error('partner_schema_changed');
 const out={id:row.id,name:row.name,active:row.active,description_authorized:row.description_authorized,categories:row.categories,text:row.text};
 if(!row.description_authorized){out.loyaltyDescription=row.loyaltyDescription;out.discountScheme=row.discountScheme;}
 return out;
}
try{
 sourceURL();
 if(/captcha|access denied|проверка безопасности|доступ к сайту временно ограничен/i.test(document.title+' '+document.body.textContent.slice(0,1000)))throw Error('restriction_document');
 let total=null,offset=0,seen=new Set(),bytes=0;
 for(let i=0;i<11;i++){
  if(Date.now()>deadline-6000)throw Error('source_time_bound');
  const request={pagination:{limit:120,offset},filters:{categories:[],name:'',qrDiscount:false,region:'98'}};
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),5000);
  let response,raw;
  try{
   response=await fetch(API,{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(request),credentials:'omit',redirect:'error',cache:'no-store',signal:controller.signal});
   if(response.status!==200||response.url!==API||response.headers.has('Retry-After'))throw Error('source_http_refusal');
   raw=await response.text();if(raw.length>6000000)throw Error('source_size_bound');
  }finally{clearTimeout(timer);}
  const data=JSON.parse(raw);
  if(!Number.isInteger(data.total)||data.total<0||data.total>5000||data.offset!==offset||!Array.isArray(data.partners)||
   data.partners.length!==Math.min(120,data.total-offset))throw Error('page_schema_changed');
  if(total===null)total=data.total;if(total!==data.total)throw Error('catalogue_changed');
  const partners=data.partners.map(projection),pageIDs=new Set(partners.map(x=>x.id));
  if(pageIDs.size!==partners.length||[...pageIDs].some(x=>seen.has(x)))throw Error('repeated_partner_ids');
  const sourceSha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(raw)))].map(x=>x.toString(16).padStart(2,'0')).join('');
  const item={request,total,offset,partners,status:200,url:response.url,sourceSha,completedAt:new Date().toISOString()};
  bytes+=JSON.stringify(item).length;if(bytes>3000000)throw Error('public_output_bound');
  result.pages.push(item);pageIDs.forEach(id=>seen.add(id));offset+=partners.length;
  if(offset===total){result.complete=seen.size===total;break;}
  await sleep(1100);
 }
 result.total=total;result.observed=seen.size;
 if(!result.complete)result.errors.push('page_count_bound');
}catch(e){result.errors.push(/^[a-z_]+$/.test(e.message)?e.message:e.name);}
result.finishedAt=new Date().toISOString();result.finalUrl=location.href;
const pre=document.createElement('pre');pre.id='loyalty-session-api';pre.textContent=JSON.stringify(result);document.body.replaceChildren(pre);
