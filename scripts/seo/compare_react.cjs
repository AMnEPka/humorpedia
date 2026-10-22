const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const http=require('node:http');
const {chromium}=require('playwright');

(async()=>{
 const root=path.resolve(__dirname,'../..'),build=path.join(root,'frontend/build');
 const payloads=JSON.parse(await fs.readFile(path.join(root,'.cache/r13b/reference/payloads.json'),'utf8'));
 const server=http.createServer(async(req,res)=>{
  try{
   const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
   const candidate=path.resolve(build,'.'+name);
   assert(candidate.startsWith(build+path.sep));
   const stat=await fs.stat(candidate).catch(()=>null);
   const file=stat?.isFile()?candidate:path.join(build,'index.html');
   const ext=path.extname(file);
   res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml'})[ext]||'application/octet-stream');
   res.end(await fs.readFile(file));
  }catch(e){res.statusCode=404;res.end();}
 });
 await new Promise(resolve=>server.listen(18014,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true});
 const results=[],blocked=[];
 try{
  const context=await browser.newContext();
  await context.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.origin!=='http://127.0.0.1:18014'){blocked.push(url.href);return route.abort();}
   if(url.pathname==='/config.js')return route.fulfill({contentType:'text/javascript',body:"window.__BACKEND_URL__='http://127.0.0.1:18014';"});
   if(url.pathname.startsWith('/api/')){
    const key=url.pathname.slice(4).replace(/^\/content/,''),item=payloads[key];
    const body=item?.document||((key.includes('ratings'))?{average:0,count:0}:[]);
    return route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
   }
   return route.continue();
  });
  const page=await context.newPage();
  for(const [url,item] of Object.entries(payloads)){
   await page.goto('http://127.0.0.1:18014'+url);
   await page.locator('h1').filter({hasText:item.heading}).waitFor();
   const text=await page.locator('main').evaluate(node=>{
    const copy=node.cloneNode(true);
    copy.querySelectorAll('script,style,iframe,object,svg,template,math').forEach(n=>n.remove());
    return copy.textContent.replace(/\s+/g,' ').trim();
   });
   const normalize=s=>s.replace(/\s+/g,'');
   const comparable=normalize(text);
   for(const block of item.blocks){
    for(const expected of [block.heading,block.text].filter(Boolean)){
     assert(comparable.includes(normalize(expected)),url+': missing '+expected);
    }
   }
   for(const notice of item.notices)assert(comparable.includes(normalize(notice)),url+': notice');
   for(const [label,href] of item.links){
    const candidates=page.locator('a').filter({hasText:label});
    assert(await candidates.count()>0,url+': link '+label);
    assert((await candidates.evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')))).includes(href),url+': href '+href);
   }
   assert(!text.includes('HIDDEN_SECRET')&&!text.includes('FALLBACK_SECRET')&&!text.includes('SIDEBAR_SECRET'));
   results.push({url,matchedBlocks:item.blocks.length,matchedLinks:item.links.length,unsupported:item.unsupported});
  }
  assert.deepEqual(blocked,[]);
  await fs.writeFile(path.join(root,'.cache/r13b/reference/react.json'),JSON.stringify({results,blocked},null,2));
  console.log('PASS: existing React build contains all selected pilot headings, text, links and notices on shared fixtures');
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1;});
