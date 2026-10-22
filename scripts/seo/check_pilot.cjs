const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const {performance}=require('node:perf_hooks');
const {chromium}=require('playwright');

(async()=>{
 const base=new URL(process.env.HTML_PILOT_BASE_URL||'http://127.0.0.1:18013');
 assert(['127.0.0.1','localhost','[::1]'].includes(base.hostname),'Only loopback');
 const runId=process.env.HTML_PILOT_RUN_ID;
 assert.match(runId||'',/^[0-9a-f]{32}$/);
 const out=process.env.HTML_PILOT_ARTIFACT_DIR||'/tmp/html-pilot-result';
 await fs.mkdir(out,{recursive:true});
 const get=(p,options={})=>fetch(new URL(p,base),{redirect:'manual',signal:AbortSignal.timeout(15000),...options});
 let status;
 for(let n=0;n<60;n++){
  try{status=await get('/__html_pilot__/status').then(r=>r.json());break;}
  catch(e){if(n===59)throw e; await new Promise(resolve=>setTimeout(resolve,500));}
 }
 assert.equal(status.run_id,runId);
 assert.equal(status.database,'humorpedia_html_pilot_'+runId);
 if(process.env.HTML_PILOT_COLD==='1'){
  const samples=[];
  for(const kind of ['people','articles'])for(const kib of [10,250]){
   const start=performance.now(),r=await get('/'+kind+'/perf-'+kind+'-'+kib+'k');
   assert.equal(r.status,200);
   const bytes=(await r.arrayBuffer()).byteLength;
   samples.push({kind,kib,ms:performance.now()-start,bytes});
  }
  const probe=await get('/__html_pilot__/measure').then(r=>r.json());
  await fs.writeFile(path.join(out,'cold.json'),JSON.stringify({samples,probe},null,2));
  console.log(JSON.stringify({cold:samples,startup:probe.fixture_lifespan_startup_ms,rss:probe.rss_kib}));
  return;
 }
 const browser=await chromium.launch({headless:true});
 const pages=[];
 try{
  const ctx=await browser.newContext({javaScriptEnabled:false});
  const unexpected=[];
  await ctx.route('**/*',route=>{
   if(new URL(route.request().url()).origin!==base.origin){unexpected.push(route.request().url());return route.abort();}
   return route.continue();
  });
  const page=await ctx.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  for(const [url,heading,needle] of [['/people/alpha','Альфа','Основной текст Альфы'],['/articles/story','История','Статья о'],['/articles/legacy','Старая статья','Legacy text']]){
   const response=await page.goto(new URL(url,base).href);
   assert.equal(response.status(),200);
   assert.equal(await page.locator('html').getAttribute('lang'),'ru');
   assert.equal(await page.locator('h1').textContent(),heading);
   assert((await page.locator('article').textContent()).includes(needle));
   assert.equal(await page.locator('head title').count(),1);
   assert.equal(await page.locator('link[rel=canonical]').count(),1);
   const canonical=await page.locator('link[rel=canonical]').getAttribute('href');
   assert.equal(canonical,'https://humorpedia.ru'+url);
   assert((await page.locator('meta[name=description]').getAttribute('content')).length>0);
   for(const key of ['title','description','type','url','image','image:alt','locale']){
    const tag=page.locator('meta[property="og:'+key+'"]');
    assert.equal(await tag.count(),1,key);
    assert((await tag.getAttribute('content')).length>0);
   }
   assert.equal(await page.locator('meta[property="og:url"]').getAttribute('content'),canonical);
   const image=new URL(await page.locator('meta[property="og:image"]').getAttribute('content'));
   assert.equal(image.origin,'https://humorpedia.ru');
   const imageResponse=await get(image.pathname);
   assert.equal(imageResponse.status,200);
   assert.match(imageResponse.headers.get('content-type'),/^image\/png/);
   assert.equal((await imageResponse.arrayBuffer()).byteLength>8,true);
   const html=await response.text();
   assert(!html.includes('HIDDEN_SECRET')&&!html.includes('SIDEBAR_SECRET')&&!html.includes('SCRIPT_SECRET'));
   assert.equal(await page.locator('script').count(),0);
   assert.equal(await page.locator('a[href^="javascript:"]').count(),0);
   assert.equal(response.headers()['cache-control'],'no-store');
   if(url!='/articles/legacy')assert((await page.locator('article').textContent()).includes('признан в РФ иностранным агентом'));
   pages.push({url,canonical,status:response.status(),jsDisabled:true});
  }
  for(const slug of ['draft','missing']){
   const r=await get('/people/'+slug);
   assert.equal(r.status,200);assert.match(r.headers.get('x-robots-tag'),/noindex/);
  }
  for(const url of ['/people/archived','/people/unknown','/old/archived.html','/people/private','/old/private.html','/people/private.html','/people/archived.html']){
   const r=await get(url,{headers:{Authorization:'Bearer staff',Cookie:'admin_token=staff'}});
   assert.equal(r.status,404);assert.match(r.headers.get('x-robots-tag'),/noindex/);
  }
  for(const url of ['/old/alpha.html','/people/alpha-old.html','/people/person-alpha']){
   const r=await get(url,{headers:{Host:'evil.invalid',Forwarded:'host=evil.invalid'}});
   assert.equal(r.status,301);assert.equal(r.headers.get('location'),'https://humorpedia.ru/people/alpha');
  }
  for(const [url,target] of [['/people/beta.html','/people/beta'],['/articles/story.html','/articles/story']]){
   const r=await get(url);
   assert.equal(r.status,301);assert.equal(r.headers.get('location'),'https://humorpedia.ru'+target);
  }
  await page.goto(new URL('/people/beta',base).href);
  assert.equal(await page.locator('h1').textContent(),'Бета*');
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
  await fs.writeFile(path.join(out,'browser.json'),JSON.stringify({pages,errors,unexpected,status},null,2));
  console.log('PASS: JS-off HTML, metadata, safe text/notices, image, anonymous 301/404/noindex');
 }finally{await browser.close();}
 if(process.env.HTML_PILOT_MEASURE==='1'){
  const probe=()=>get('/__html_pilot__/measure').then(r=>r.json());
  const metrics=[], before=await probe();
  for(const kind of ['people','articles'])for(const kib of [10,250]){
   const url='/'+kind+'/perf-'+kind+'-'+kib+'k';
   for(let series=0;series<5;series++){
    for(let n=0;n<30;n++){const r=await get(url);assert.equal(r.status,200);await r.arrayBuffer();}
    const a=await probe(),samples=[];let bytes=0;
    for(let n=0;n<100;n++){
     const start=performance.now(),r=await get(url);
     assert.equal(r.status,200);bytes=(await r.arrayBuffer()).byteLength;samples.push(performance.now()-start);
    }
    const b=await probe(),sorted=[...samples].sort((x,y)=>x-y);
    const counts={};
    for(const key of new Set([...Object.keys(a.commands),...Object.keys(b.commands)]))counts[key]=(b.commands[key]||0)-(a.commands[key]||0);
    metrics.push({kind,kib,series,samples,bytes,p50:sorted[49],p95:sorted[94],rss_kib:b.rss_kib,commands:counts});
    console.log(JSON.stringify({kind,kib,series,p95:sorted[94],rss_kib:b.rss_kib,commands:counts}));
   }
  }
  const after=await probe();
  await fs.writeFile(path.join(out,'metrics.json'),JSON.stringify({before,after,metrics},null,2));
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
