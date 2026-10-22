const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const {setTimeout:pause}=require('node:timers/promises');
const base=new URL(process.env.HTML_REACT_PILOT_BASE_URL||'http://127.0.0.1');
const runId=process.env.HTML_GATEWAY_RUN_ID,mode=process.env.HTML_GATEWAY_MODE;
const out=process.env.HTML_REACT_PILOT_ARTIFACT_DIR;
const request=(p,options)=>fetch(new URL(p,base),{redirect:'manual',...options});
const control=async action=>{const r=await request('/api/__html_gateway__/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run_id:runId,action})});assert.equal(r.status,200);return r.json();};
async function main(){
 assert(['127.0.0.1','localhost','[::1]'].includes(base.hostname));assert.match(runId||'',/^[a-f0-9]{32}$/);
 await fs.mkdir(out,{recursive:true});
 let state;
 for(let i=0;i<120;i++){try{const r=await request('/api/__html_gateway__/measure');if(r.ok){state=await r.json();break;}}catch{}await pause(250);}
 assert.equal(state?.run_id,runId);assert.equal(state.database,'humorpedia_html_gateway_'+runId);
 if(process.env.HTML_GATEWAY_BROKEN_RELEASE==='1'){
  assert.equal((await request('/api/health')).status,200);
  for(const route of ['/people/alpha','/articles/anchors','/sitemap.xml']){
   const response=await request(route);assert.equal(response.status,503);assert.match(response.headers.get('x-robots-tag'),/noindex/);
  }
  const ready=await request('/api/ready');assert.equal(ready.status,503);assert.equal((await ready.json()).checks.public_html,'error');
  await fs.writeFile(path.join(out,'broken-release.json'),JSON.stringify({run_id:runId,passed:true}));
  return;
 }
 if(process.env.HTML_GATEWAY_INJECT_FAILURE==='1')throw new Error('Intentional browser failure for cleanup acceptance');
 if(process.env.HTML_GATEWAY_PERF){
  const {measureGateway}=require('./gateway_performance.cjs');
  await measureGateway({base,runId,out,cold:process.env.HTML_GATEWAY_PERF==='cold',kind:process.env.HTML_GATEWAY_PERF_KIND,kib:process.env.HTML_GATEWAY_PERF_KIB});
  return;
 }
 const checks=[];
 const code=async(p,status,options)=>{const r=await request(p,options);assert.equal(r.status,status,p);checks.push(p+':'+status);return r;};
 assert.equal((await code('/api/health',200)).headers.get('content-type').includes('json'),true);
 await code('/api/page-packages/preview',401,{method:'POST'});
 const user=await (await code('/api/auth/login',200,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'pilot@example.invalid',password:'Pilot-only-2026'})})).json();
 await code('/api/page-packages/preview',403,{method:'POST',headers:{Authorization:'Bearer '+user.access_token}});
 const admin=await (await code('/api/auth/login',200,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'gateway@example.invalid',password:'Gateway-only-2026'})})).json();
 await code('/api/competitions/seasons/gateway-season',409,{method:'PUT',headers:{Authorization:'Bearer '+admin.access_token,'Content-Type':'application/json'},body:'{"description":"missing version"}'});
 await code('/api/echo',413,{method:'POST',body:Buffer.alloc(21*1024*1024)});
 const form=new FormData();form.append('file',new Blob([Buffer.alloc(21*1024*1024)]),'gateway.zip');
 const oversized=await code('/api/page-packages/preview',422,{method:'POST',headers:{Authorization:'Bearer '+admin.access_token},body:form});
 assert(!((await oversized.text()).includes('413 Request')));
 const apiLimit=new FormData();apiLimit.append('file',new Blob([Buffer.alloc(51*1024*1024)]),'too-large.zip');
 const apiLimitResponse=await code('/api/page-packages/preview',422,{method:'POST',headers:{Authorization:'Bearer '+admin.access_token},body:apiLimit});
 assert.match(apiLimitResponse.headers.get('content-type'),/application\/json/); assert.match(await apiLimitResponse.text(),/ZIP больше 50 MiB/);
 await code('/api/page-packages/preview',413,{method:'POST',headers:{Authorization:'Bearer '+admin.access_token},body:Buffer.alloc(53*1024*1024)});

 const config=await code('/config.js',200);assert.match(config.headers.get('cache-control'),/no-store/);
 assert((await config.text()).includes('window.__PUBLIC_HTML_ENABLED__ = '+(mode!=='disabled')));
 await code('/_internal/public-html/state',404);
 if(mode==='disabled'){
  const r=await code('/people/unknown',200);assert(!(await r.text()).includes('html-pilot-fallback'));
 }else{
  const before=await control('flush');
  for(const p of ['/people/alpha','/people/draft','/people/missing','/articles/anchors']){const r=await code(p,200,{headers:{'X-Humorpedia-Release':'spoof'}});assert.match(r.headers.get('cache-control'),/no-store/);assert((await r.text()).includes('html-pilot-fallback'));}
  for(const p of ['/people/unknown','/people/archived','/people/private','/old/private'])await code(p,404);
  for(const p of ['/old/alpha.html','/old%26name?utm=x','/old/alpha?x=1','/people/alpha/']){const r=await code(p,301,{headers:{'X-Humorpedia-Original-URI':'/old/private'}});assert.equal(r.headers.get('location'),'https://humorpedia.ru/people/alpha');}
  for(const p of ['/unknown','/people','/articles','/teams/x','/admin','/preview/x'])await code(p,200);
  for(const [p,status] of [['/teams/x',200],['/people',200],['/unknown',200],['/old/alpha.html',301],['/people/alpha',200],['/people/archived',404]]){
   const r=await code(p,status,{method:'HEAD'});assert.equal(await r.text(),'');
  }

  for(const p of ['/assets/missing.js','/media/missing.png','/%5finternal/public-html/state','/_INTERNAL/public-html/state','/%61pi/no-such'])await code(p,404);
  const image=await code('/media/pilot-share.png',200);assert.match(image.headers.get('content-type'),/image\/png/);assert((await image.arrayBuffer()).byteLength>0);
  const {chromium}=require('playwright');const imageBrowser=await chromium.launch({headless:true});
  try{
   const imagePage=await imageBrowser.newPage();await imagePage.goto(base.href+'/healthz');
   assert(await imagePage.evaluate(()=>new Promise(resolve=>{const img=new Image();img.onload=()=>resolve(img.naturalWidth>0);img.onerror=()=>resolve(false);img.src='/media/pilot-share.png';})));
  }finally{await imageBrowser.close();}
  const robots=await code('/robots.txt',200);assert.match(robots.headers.get('content-type'),/text\/plain/);
  const sitemap=await code('/sitemap.xml',200);assert.match(sitemap.headers.get('content-type'),/application\/xml/);assert.match(sitemap.headers.get('cache-control'),/no-store/);
  const text=await sitemap.text();
  assert(text.includes('<url>')===(mode==='indexed'));
  if(mode==='closed')assert.match(await robots.text(),/Disallow: \//);
  else{
   assert.match(text,/https:\/\/humorpedia.ru\/people\/alpha/);assert(!/\/people\/(draft|missing|private|archived)</.test(text));
   await control('rename');const next=await (await code('/sitemap.xml',200)).text();assert(next.includes('/people/alpha-renamed<'));assert(!next.includes('/people/alpha<'));await control('restore');
   await control('archive');assert(!(await (await request('/sitemap.xml')).text()).includes('/people/alpha<'));await control('restore');
  }
  assert.deepEqual((await control('flush')).views,before.views);
  await control('mismatch');
  for(const p of ['/people/alpha','/sitemap.xml','/unknown']){const r=await code(p,503);assert.match(r.headers.get('x-robots-tag'),/noindex/);}
  await code('/api/health',200);const notReady=await code('/api/ready',200);assert.equal((await notReady.json()).checks.public_html,'ok'); // backend release valid, pair mismatch is gateway readiness
  await control('match');await code('/people/alpha',200);
  if(mode==='closed'){
   const child=spawnSync(process.execPath,['scripts/seo/check_react_pilot.cjs'],{stdio:'inherit',env:process.env});
   assert.equal(child.status,0,'R13d browser parity on native gateway');
  }
 }
 await fs.writeFile(path.join(out,'gateway.json'),JSON.stringify({mode,run_id:runId,checks},null,2));
 console.log('PASS gateway matrix',mode,checks.length);
}
main().catch(error=>{console.error(error);process.exitCode=1;});
