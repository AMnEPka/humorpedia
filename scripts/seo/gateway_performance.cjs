const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const {chromium}=require('playwright');
async function measureGateway({base,runId,out,cold,kind,kib}){
 const measure=async()=>{const r=await fetch(new URL('/api/__html_gateway__/measure',base));assert(r.ok);const data=await r.json();assert.equal(data.run_id,runId);return data;};
 const browser=await chromium.launch({headless:true});
 const series=[];
 try{
  const ctx=await browser.newContext({baseURL:base.href,viewport:{width:1280,height:900}});
  await ctx.route('**/*',route=>new URL(route.request().url()).origin===base.origin?route.continue():route.abort());
  const page=await ctx.newPage();
  const ready=()=>page.waitForFunction(()=>document.getElementById('root')?.dataset.htmlPilotReady===location.pathname&&!document.getElementById('root').hidden&&!document.getElementById('html-pilot-fallback'));
  const combos=cold?[[kind,Number(kib)]]:[['people',10],['people',250],['articles',10],['articles',250]];
  for(const [type,size] of combos){
   assert(['people','articles'].includes(type));assert([10,250].includes(size));
   const route='/'+type+'/perf-'+type+'-'+size+'k';
   if(!cold)for(let n=0;n<3;n++){await page.goto(route);await ready();await page.waitForLoadState('networkidle');}
   for(let batch=0;batch<(cold?1:5);batch++){
    const before=await measure(),samples=[];
    for(let n=0;n<(cold?1:10);n++){
     await page.goto(route);await ready();
     const core=await page.evaluate(()=>performance.now());
     // Waiting ensures all native widgets completed; duration is resource.responseEnd,
     // not the added 500ms quiet period used to know that the set has closed.
     await page.waitForLoadState('networkidle');
     const network=await page.evaluate(()=>{
      const navigation=performance.getEntriesByType('navigation')[0].toJSON();
      const api=performance.getEntriesByType('resource').filter(e=>new URL(e.name).pathname.startsWith('/api/')).map(e=>e.toJSON());
      return {navigation,api};
     });
     samples.push({core_ready_ms:core,required_widgets_ms:Math.max(core,...network.api.map(e=>e.responseEnd)),network});
    }
    const after=await measure();
    series.push({kind:type,kib:size,cold,series:batch,samples,rss_kib:after.rss_kib,
     commands:Object.fromEntries(Object.entries(after.commands).map(([k,v])=>[k,v-(before.commands[k]||0)]))});
   }
  }
  await ctx.close();
 }finally{await browser.close();}
 await fs.writeFile(path.join(out,'performance.json'),JSON.stringify({run_id:runId,series},null,2));
 console.log('PASS gateway performance',cold?'cold':'warm',series.length);
}
module.exports={measureGateway};
