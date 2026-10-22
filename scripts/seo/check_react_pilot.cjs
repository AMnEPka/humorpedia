// Own UUID database + production build; no requests to the primary site.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {setTimeout: pause} = require('node:timers/promises');
const {chromium} = require('playwright');
const base = new URL(process.env.HTML_REACT_PILOT_BASE_URL || 'http://127.0.0.1:18014');
const runId = process.env.HTML_PILOT_RUN_ID;
const output = process.env.HTML_REACT_PILOT_ARTIFACT_DIR || '.cache/r13d/browser';
const passed = [], errors = [], external = [];
let browser;
const url = p => new URL(p, base);
async function json(p, options) {const response=await fetch(url(p),options);assert(response.ok,`${p}: ${response.status}`);return response.json();}
const control = action => json('/__html_react_pilot__/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run_id:runId,action})});
async function context(options={}) {
  const ctx=await browser.newContext({baseURL:base.href,...options});
  await ctx.route('**/*',route=>{
    if(new URL(route.request().url()).origin!==base.origin){external.push(route.request().url());return route.abort();}
    return route.continue();
  });
  ctx.on('page',page=>{page.setDefaultTimeout(15000);page.on('pageerror',error=>errors.push(error.message));});
  return ctx;
}
async function ready(page) {await page.waitForFunction(()=>!document.getElementById('html-pilot-fallback') && document.getElementById('root') && !document.getElementById('root').hidden && document.getElementById('root').dataset.htmlPilotReady===window.location.pathname);}
async function head(page) {return page.evaluate(()=>({title:document.title,canonical:document.querySelector('link[rel="canonical"]')?.href,description:document.querySelector('meta[name="description"]')?.content,robots:document.querySelector('meta[name="robots"]')?.content,og:document.querySelector('meta[property="og:title"]')?.content}));}
// Drive the real BrowserRouter through the browser history API; rich-text <a>
// links intentionally perform full document loads and cannot test a SPA race.
async function navigate(page, pathname) {
  await page.evaluate(pathname => {
    history.pushState({idx:(history.state?.idx || 0)+1,key:crypto.randomUUID()},'',pathname);
    dispatchEvent(new PopStateEvent('popstate',{state:history.state}));
  }, pathname);
}
async function test(name,fn){await fn();passed.push(name);console.log('PASS',name);}
async function main(){
  assert(['localhost','127.0.0.1','[::1]'].includes(base.hostname));assert.match(runId||'',/^[0-9a-f]{32}$/);
  let state;
  for(let i=0;i<60;i++){try{state=await json('/__html_react_pilot__/measure');break;}catch(e){if(i===59)throw e;await pause(250);}}
  assert.equal(state.run_id,runId);assert.equal(state.database,'humorpedia_html_pilot_'+runId);
  await fs.mkdir(output,{recursive:true});browser=await chromium.launch({headless:true});
  try {
    await test('JS off: metadata, text, anchors, notices, redirects, zero API/views',async()=>{
      const before=await control('flush');const ctx=await context({javaScriptEnabled:false});const page=await ctx.newPage();let api=0;page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/'))api++;});
      for(const [route,title,text,anchor] of [
        ['/people/alpha','Альфа — карточка | humorpedia.ru','Основной текст Альфы.','section-0'],
        ['/people/legacy-person','Legacy человек | humorpedia.ru','Legacy хронология','timeline-1'],
        ['/articles/anchors','Мета статьи | humorpedia.ru','Цель якоря','second'],
        ['/articles/legacy','Старая статья | humorpedia.ru','Legacy text',null],
        ['/articles/header-image','Статья с обложкой | humorpedia.ru','Текст под обложкой',null],
        ['/articles/hidden-only','Скрытые модули | humorpedia.ru','Скрытые модули',null],
        ['/people/draft','Черновик | humorpedia.ru','Черновик',null],
        ['/people/missing','Legacy без статуса | humorpedia.ru','Legacy без статуса',null]]){
        const response=await page.goto(route);assert.equal(response.status(),200);assert.equal(await page.title(),title);
        assert((await page.locator('#html-pilot-fallback').innerText()).includes(text));
        assert.equal(await page.locator('#root').getAttribute('hidden'),'');
        const metadata=await head(page);assert.equal(metadata.canonical,'https://humorpedia.ru'+route);assert.match(metadata.robots,/noindex/);assert.equal(metadata.og,title);
        if(anchor)assert.equal(await page.locator('#'+anchor).count(),1);
      }
      await page.goto('/articles/hidden-only');assert(!/HIDDEN_SECRET|FALLBACK_SECRET/.test(await page.locator('body').innerText()));
      await page.goto('/people/beta');assert.equal((await page.locator('body').innerText()).split('признан в РФ иностранным агентом').length-1,1);
      for(const route of ['/people/archived','/people/private','/unknown'])assert.equal((await page.goto(route)).status(),404);
      const redirect=await fetch(url('/old/alpha.html'),{redirect:'manual'});assert.equal(redirect.status,301);assert.equal(redirect.headers.get('location'),'https://humorpedia.ru/people/alpha');
      assert.equal((await fetch(url('/media/pilot-share.png'))).status,200);assert.equal(api,0);
      assert.deepEqual((await control('flush')).views,before.views);await ctx.close();
    });
    for(const width of [1280,390])await test('JS on '+width+': one GET/view, title stable, real widgets',async()=>{
      const before=await control('flush');const ctx=await context({viewport:{width,height:900}});const page=await ctx.newPage();let content=0;page.on('request',r=>{if(new URL(r.url()).pathname==='/api/content/people/alpha'){content++;assert.equal(new URL(r.url()).searchParams.get('include_page_metadata'),'1');}});
      await page.goto('/people/alpha');await ready(page);assert.equal(content,1);assert.equal(await page.title(),'Альфа — карточка | humorpedia.ru');assert.equal(await page.locator('h1').count(),1);
      await page.getByRole('button',{name:'Поставить оценку 8 из 10',exact:true}).click();await page.getByText('Ваша оценка: 8',{exact:true}).waitFor();
      await page.locator('#section-career-teams').getByRole('link',{name:'Команда пилота'}).waitFor();await page.getByText('Участник проекта «Шоу пилота»',{exact:true}).waitFor();
      const login=await json('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'pilot@example.invalid',password:'Pilot-only-2026'})});
      await page.evaluate(token=>localStorage.setItem('admin_token',token),login.access_token);
      if(width===1280){await page.getByRole('radio',{name:'Подходит',exact:true}).check();await page.getByRole('button',{name:'Проголосовать',exact:true}).click();await page.getByText('Всего голосов: 1',{exact:true}).waitFor();}
      await page.getByRole('button',{name:'Предложить исправление',exact:true}).click();if(width===390)await page.getByRole('button',{name:'Предложить исправление',exact:true}).click();
      await page.getByRole('combobox').click();await page.getByRole('option',{name:'Основная информация',exact:true}).click();await page.getByLabel('Предлагаемое исправление',{exact:true}).fill('Проверка пилота '+width);
      await page.getByRole('button',{name:/Отправить предложение/}).click();await page.getByText('Предложение отправлено',{exact:true}).waitFor();await page.getByRole('button',{name:'Закрыть',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});
      const after=await control('flush');assert.equal(after.views.people['person-alpha']-before.views.people['person-alpha'],1);
      await page.screenshot({path:path.join(output,'person-'+width+'.png'),fullPage:true});await ctx.close();
    });
    await test('React parity: legacy, anchors, notice; refresh and uncovered navigation',async()=>{
      const ctx=await context();const page=await ctx.newPage();
      for(const [route,text,id] of [['/people/legacy-person','Legacy хронология','timeline-1'],['/articles/anchors#second','Цель якоря','second'],['/articles/legacy','Legacy text',null],['/articles/header-image','Текст под обложкой',null],['/people/beta','признан в РФ иностранным агентом',null]]){
        await page.goto(route);await ready(page);assert((await page.locator('#root').innerText()).includes(text));if(id)assert.equal(await page.locator('#'+id).count(),1);assert.equal(await page.locator('h1').count(),1);
      }
      await page.goto('/articles/header-image');await ready(page);await page.waitForFunction(()=>[...document.querySelectorAll('#root article img')].some(img=>img.complete && img.naturalWidth>0));
      await page.goto('/articles/hidden-only');await ready(page);assert(!/HIDDEN_SECRET|FALLBACK_SECRET/.test(await page.locator('#root').innerText()));
      await page.goto('/articles/anchors#second');await ready(page);await page.locator('summary').filter({hasText:'Подробнее'}).click();assert((await page.locator('#root').innerText()).includes('Подробный текст'));assert(await page.locator('#second').evaluate(el=>Math.abs(el.getBoundingClientRect().top)<200));
      await page.reload();await ready(page);assert.equal(await page.title(),'Мета статьи | humorpedia.ru');
      await page.locator('nav').getByRole('link',{name:'Статьи',exact:true}).first().click();await page.waitForURL('**/articles');await page.waitForFunction(()=>!document.querySelector('link[rel="canonical"]'));assert.equal(await page.locator('meta[property="og:title"]').count(),0);
      await ctx.close();
    });
    for(const mode of ['slow-api','slow-chunk','js-failure','network'])await test(mode+' preserves initial content/head',async()=>{
      const ctx=await context();const page=await ctx.newPage();let release, entered=false;const gate=new Promise(r=>release=r);
      const pattern=mode==='slow-chunk'?/\/assets\/PersonDetailPage-[^/]+\.js/:mode==='js-failure'?/\/assets\/.*\.js/:/\/api\/content\/people\/alpha/;
      await page.route(pattern,async route=>{entered=true;if(['network','js-failure'].includes(mode))return route.abort();await gate;return route.continue();});
      await page.goto('/people/alpha',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>document.getElementById('html-pilot-fallback'));
      for(let i=0;!entered&&i<100;i++)await pause(20);assert(entered);
      assert.equal(await page.title(),'Альфа — карточка | humorpedia.ru');assert(await page.locator('#html-pilot-fallback').isVisible());
      if(mode==='network')await page.getByRole('status').waitFor();
      if(mode.startsWith('slow')){release();await ready(page);}else{release();assert.equal(await page.locator('#root').getAttribute('hidden'),'');}
      await ctx.close();
    });
    await test('archive between HTML and real API response removes stale fallback',async()=>{
      const ctx=await context();const page=await ctx.newPage();let release,entered=false;const gate=new Promise(r=>release=r);
      await page.route(/\/api\/content\/people\/alpha/,async route=>{entered=true;await gate;return route.continue();});
      try{await page.goto('/people/alpha',{waitUntil:'domcontentloaded'});for(let i=0;!entered&&i<100;i++)await pause(20);assert(entered);await control('archive');release();await ready(page);assert((await page.locator('#root').innerText()).includes('Человек не найден'));assert.match((await head(page)).robots,/noindex/);assert.equal((await head(page)).canonical,undefined);}finally{release();await control('restore');await ctx.close();}
    });
    await test('SPA API failure clears previous detail head',async()=>{
      const ctx=await context();const page=await ctx.newPage();
      await page.goto('/people/alpha');await ready(page);
      await page.route(/\/api\/content\/people\/beta/,route=>route.abort());
      await navigate(page,'/people/beta');await page.locator('#html-pilot-status').waitFor();
      assert.equal((await head(page)).canonical,undefined);assert.equal((await head(page)).og,undefined);
      assert.equal(await page.title(),'Humorpedia | humorpedia.ru');assert.equal(await page.locator('#root').getAttribute('hidden'),null);
      await ctx.close();
    });
    await test('stale response, Back/Forward and direct refresh',async()=>{
      const ctx=await context();const page=await ctx.newPage();let release,entered=false;const gate=new Promise(r=>release=r);
      await page.goto('/people/alpha');await ready(page);
      await page.route(/\/api\/content\/people\/beta/,async route=>{entered=true;await gate;return route.continue();});
      await navigate(page,'/people/beta');for(let i=0;!entered&&i<100;i++)await pause(20);assert(entered);
      await page.goBack();await ready(page);release();await pause(100);assert.equal(await page.title(),'Альфа — карточка | humorpedia.ru');assert.equal(await page.locator('h1').innerText(),'Альфа');
      await page.goForward();await ready(page);assert((await page.locator('h1').innerText()).includes('Бета'));await page.reload();await ready(page);assert.equal(await page.locator('h1').count(),1);await ctx.close();
    });
    const performance=[];
    if(process.env.HTML_REACT_PILOT_PERF==='1')await test('5 warm series x10 navigations, four type/size combinations',async()=>{
      const ctx=await context();const page=await ctx.newPage();
      for(const kind of ['people','articles'])for(const kib of [10,250]){
        const route='/'+kind+'/perf-'+kind+'-'+kib+'k';
        for(let i=0;i<3;i++){await page.goto(route);await ready(page);}
        for(let series=0;series<5;series++){
          const before=await json('/__html_react_pilot__/measure');const samples=[];
          for(let i=0;i<10;i++){
            const start=performanceNow();await page.goto(route);await ready(page);
            samples.push({ready_ms:performanceNow()-start,network:await page.evaluate(()=>({navigation:performance.getEntriesByType('navigation')[0]?.toJSON(),content:performance.getEntriesByType('resource').filter(e=>e.name.includes('/api/content/')).map(e=>e.toJSON())}))});
          }
          const after=await json('/__html_react_pilot__/measure');const commands=Object.fromEntries(Object.entries(after.commands).map(([k,v])=>[k,v-(before.commands[k]||0)]));
          performance.push({kind,kib,series,samples,commands,rss_kib:after.rss_kib});
        }
      }await ctx.close();
    });
    assert.deepEqual(external,[]);assert.deepEqual(errors,[]);
    await fs.writeFile(path.join(output,'result.json'),JSON.stringify({run_id:runId,database:state.database,passed,errors,external,performance},null,2));console.log(JSON.stringify({passed:passed.length,series:performance.length}));
  }catch(error){await fs.writeFile(path.join(output,'failure.json'),JSON.stringify({passed,errors,external,error:error.stack},null,2));throw error;}finally{await browser.close();}
}
const performanceNow=()=>Number(process.hrtime.bigint())/1e6;
main().catch(error=>{console.error(error);process.exitCode=1;});
