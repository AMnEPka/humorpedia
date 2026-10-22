const {spawn}=require('node:child_process');
const {randomUUID}=require('node:crypto');
const fs=require('node:fs/promises');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
function ownedResources(runId){
 if(!/^[a-f0-9]{32}$/.test(runId||''))throw new Error('Expected UUID runId');
 const prefix='hp-r13e-'+runId;
 return {database:'humorpedia_html_gateway_'+runId,network:prefix+'-network',
  containers:{mongo:prefix+'-mongo',backend:prefix+'-backend',gateway:prefix+'-gateway',checker:prefix+'-checker'},
  images:{backend:prefix+'-backend:latest',gateway:prefix+'-gateway:latest'}};
}
function assertOwned(name,id,type){
 const r=ownedResources(id);
 const allowed=type==='container'?Object.values(r.containers):type==='network'?[r.network]:type==='image'?Object.values(r.images):[];
 if(!allowed.includes(name))throw new Error('Foreign '+type+' is forbidden');
}
function runDockerProcess(args,{cwd,timeout=180000,allowFailure=false,spawnProcess=spawn}={}){
 return new Promise((resolve,reject)=>{
  const child=spawnProcess('docker',args,{cwd,stdio:['ignore','pipe','pipe']});
  let output='',timedOut=false;
  child.stdout.on('data',data=>output+=data);
  child.stderr.on('data',data=>output+=data);
  const timer=setTimeout(()=>{timedOut=true;child.kill('SIGTERM');},timeout);
  child.on('error',error=>{clearTimeout(timer);reject(error);});
  child.on('close',(code,signal)=>{
   clearTimeout(timer);
   const result={code,signal,timedOut,output};
   if(timedOut || signal || code===null || (code!==0&&!allowFailure)){
    const error=new Error((timedOut?'Docker command timed out':signal?'Docker command terminated by signal '+signal:'Docker command exited '+code)+'\n'+output.slice(-5000));
    Object.assign(error,result);reject(error);
   }else resolve(result);
  });
 });
}
async function waitMongoReady(command,name,{timeout=60000,pause=ms=>new Promise(resolve=>setTimeout(resolve,ms))}={}){
 const deadline=Date.now()+timeout;
 while(Date.now()<deadline){
  const state=JSON.parse((await command(['inspect','--format','{{json .State}}',name])).output);
  if(!state.Running){
   const logs=await command(['logs','--tail','60',name],{allowFailure:true});
   throw new Error('Mongo exited before readiness (exit '+state.ExitCode+')\n'+logs.output);
  }
  const ping=await command(['exec','--user','mongodb','--env','HOME=/tmp',name,
   'mongosh','--norc','--quiet','mongodb://127.0.0.1:27017/?serverSelectionTimeoutMS=1000',
   '--eval','quit(db.adminCommand("ping").ok===1?0:1)'],{timeout:10000,allowFailure:true});
  if(ping.code===0)return;
  await pause(500);
 }
 const logs=await command(['logs','--tail','60',name],{allowFailure:true});
 throw new Error('Mongo did not become ready within '+timeout+'ms\n'+logs.output);
}
async function main(){
 const root=path.resolve(__dirname,'../..');
 const build=path.resolve(process.env.BROWSER_BUILD_DIR||'');
 if(!process.env.BROWSER_BUILD_DIR)throw new Error('BROWSER_BUILD_DIR is required');
 const manifest=JSON.parse(await fs.readFile(path.join(build,'public-html-release.json'),'utf8'));
 const runId=randomUUID().replaceAll('-',''),r=ownedResources(runId);
 const out=path.resolve(process.env.HTML_GATEWAY_ARTIFACT_DIR||path.join(root,'.cache/r13e'),runId);
 await fs.mkdir(out,{recursive:true});
 const {writeGatewayBundle}=await import(pathToFileURL(path.join(root,'frontend/tooling/public-html-gateway.mjs')).href);
 const bundle=path.join(out,'bundle');
 await writeGatewayBundle(build,bundle,{backendOrigin:'http://backend:8001'});
 const commands=[];
 async function command(args,{timeout=180000,allowFailure=false}={}){
  const record={argv:['docker',...args],start:new Date().toISOString()};
  commands.push(record);
  await fs.writeFile(path.join(out,'commands.json'),JSON.stringify(commands,null,2));
  try{
   const result=await runDockerProcess(args,{cwd:root,timeout,allowFailure});
   Object.assign(record,result);return result;
  }catch(error){
   Object.assign(record,{code:error.code??null,signal:error.signal,timedOut:error.timedOut,output:error.output||error.message});
   throw error;
  }finally{
   record.elapsed_ms=Date.now()-Date.parse(record.start);
   await fs.writeFile(path.join(out,'commands.json'),JSON.stringify(commands,null,2));
   await fs.appendFile(path.join(out,'docker.log'),'\n'+args.join(' ')+'\n'+(record.output||''));
   delete record.output;
  }
 }
 const created=new Set(),images=new Set();let network=false,backend=false,primaryError;
 async function ownedRemove(name){
  assertOwned(name,runId,'container');
  const inspection=await command(['inspect',name],{allowFailure:true});
  if(inspection.code!==0){
   if(/No such (object|container)/i.test(inspection.output)){created.delete(name);return;}
   throw new Error('Unable to verify container ownership: '+inspection.output);
  }
  const inspect=JSON.parse(inspection.output)[0];
  if(inspect.Config.Labels?.['humorpedia.r13e.run']!==runId)throw new Error('Container ownership lost');
  await command(['rm','-fv',name]);
  created.delete(name);
 }
 async function stopBackend(){
  if(!backend)return;
  await command(['stop','--time','30',r.containers.backend]);
  const logs=await command(['logs',r.containers.backend]);
  if(!logs.output.includes('Application shutdown complete.'))throw new Error('Native writers did not shut down cleanly\n'+logs.output.slice(-3000));
  await command(['run','--rm','--network',r.network,'--entrypoint','python',r.images.backend,'-c',
   "import asyncio; from pymongo import AsyncMongoClient\nasync def check():\n c=AsyncMongoClient('mongodb://mongo:27017'); assert '"+r.database+"' not in await c.list_database_names(), 'Owned DB cleanup failed'; await c.close()\nasyncio.run(check())"]);
  backend=false;await ownedRemove(r.containers.backend);
 }
 const label=['--label','humorpedia.r13e.run='+runId];
 try{
  for(const target of ['backend','gateway']){
   console.log('BUILD',target,runId);
   await command(['build','--file','Dockerfile.public-html','--target',target+'-release','--build-context','public_html_release='+bundle,...label,'-t',r.images[target],'.'],{timeout:600000});
   images.add(r.images[target]);
  }
  if((await command(['image','inspect','mcr.microsoft.com/playwright:v1.62.1-noble'],{allowFailure:true})).code!==0){
   await command(['pull','mcr.microsoft.com/playwright:v1.62.1-noble'],{timeout:600000});
  }
  await command(['network','create','--internal',...label,r.network]);network=true;
  await command(['run','-d','--name',r.containers.mongo,...label,'--network',r.network,'--network-alias','mongo','--security-opt','seccomp='+path.join(root,'scripts/vps-test/seccomp-mongodb.json'),'--tmpfs','/data/db:rw,size=768m','--tmpfs','/data/configdb:rw,size=16m','mongo:8.0.32']);created.add(r.containers.mongo);
  await waitMongoReady(command,r.containers.mongo);
  const candidates=[...(process.env.NODE_PATH||'').split(path.delimiter),path.join(root,'.cache/browser-tools/node_modules')].filter(Boolean);
  let tools;
  for(const candidate of candidates){try{await fs.access(path.join(candidate,'playwright/package.json'));tools=candidate;break;}catch{}}
  if(!tools)throw new Error('Separate Playwright1.62.1 tooling is required');
  for(const mode of (process.env.HTML_GATEWAY_MODES||'disabled,closed,indexed').split(',')){
   if(!['disabled','closed','indexed'].includes(mode))throw new Error('Invalid test mode');
   const serving=String(mode!=='disabled'),indexing=String(mode==='indexed');
   await command(['run','-d','--name',r.containers.backend,...label,'--network',r.network,'--network-alias','backend',
    '-e','MONGO_URL=mongodb://mongo:27017','-e','DB_NAME='+r.database,'-e','HTML_GATEWAY_RUN_ID='+runId,
    '-e','PUBLIC_HTML_ENABLED='+serving,'-e','SEARCH_INDEXING_ENABLED='+indexing,
    '-e','PUBLIC_HTML_DEFAULT_IMAGE_URL=/media/pilot-share.png',
    ...(process.env.HTML_GATEWAY_BROKEN_RELEASE==='1'?['-e','PUBLIC_HTML_BUILD_DIR=/missing-release']:[]),
    '--mount','type=bind,src='+path.join(root,'scripts/seo')+',dst=/harness/scripts/seo,readonly',
    '--mount','type=bind,src='+path.join(root,'backend/tests/fixtures')+',dst=/harness/backend/tests/fixtures,readonly',
    '--entrypoint','python',r.images.backend,'/harness/scripts/seo/gateway_server.py']);created.add(r.containers.backend);backend=true;
   await command(['run','-d','--name',r.containers.gateway,...label,'--network',r.network,
    '-e','PUBLIC_HTML_ENABLED='+serving,'-e','SEARCH_INDEXING_ENABLED='+indexing,r.images.gateway]);created.add(r.containers.gateway);
   console.log('CHECK',mode,runId);
   created.add(r.containers.checker);
   await command(['run','--rm','--name',r.containers.checker,...label,'--network','container:'+r.containers.gateway,
    '--ipc','host','--mount','type=bind,src='+root+',dst=/work',
    '--mount','type=bind,src='+tools+',dst=/tools/node_modules,readonly',
    '--mount','type=bind,src='+out+',dst=/artifacts','-w','/work',
    '-e','NODE_PATH=/tools/node_modules','-e','HTML_GATEWAY_RUN_ID='+runId,'-e','HTML_PILOT_RUN_ID='+runId,
    '-e','HTML_GATEWAY_MODE='+mode,'-e','HTML_GATEWAY_RELEASE='+manifest.release_id,
    '-e','HTML_REACT_PILOT_BASE_URL=http://127.0.0.1','-e','HTML_REACT_PILOT_ARTIFACT_DIR=/artifacts/'+mode,
    ...['HTML_GATEWAY_PERF','HTML_GATEWAY_PERF_KIND','HTML_GATEWAY_PERF_KIB','HTML_GATEWAY_INJECT_FAILURE','HTML_GATEWAY_BROKEN_RELEASE'].flatMap(key=>process.env[key]?['-e',key+'='+process.env[key]]:[]),
    'mcr.microsoft.com/playwright:v1.62.1-noble','node','scripts/seo/check_gateway.cjs'],{timeout:300000});
   created.delete(r.containers.checker);
   if(mode!=='disabled'&&!process.env.HTML_GATEWAY_PERF&&process.env.HTML_GATEWAY_BROKEN_RELEASE!=='1'){
    const action=action=>command(['exec',r.containers.backend,'python','-c',
     "import requests; r=requests.post('http://127.0.0.1:8001/api/__html_gateway__/control',json={'run_id':'"+runId+"','action':'"+action+"'});r.raise_for_status()"]);
    await action('mismatch');
    const mismatch=await command(['exec',r.containers.gateway,'/usr/local/bin/public-html-ready'],{allowFailure:true});
    if(mismatch.code===0)throw new Error('Mismatched pair was ready');
    await action('match');
   }
   const ready=await command(['exec',r.containers.gateway,'/usr/local/bin/public-html-ready'],{allowFailure:process.env.HTML_GATEWAY_BROKEN_RELEASE==='1'});
   if((ready.code===0)===(process.env.HTML_GATEWAY_BROKEN_RELEASE==='1'))throw new Error('Unexpected gateway readiness');

   await ownedRemove(r.containers.gateway);await stopBackend();
  }
  await fs.writeFile(path.join(out,'result.json'),JSON.stringify({run_id:runId,release_id:manifest.release_id,status:'passed'},null,2));
  console.log('PASS gateway',out);
 }catch(error){primaryError=error;throw error;}finally{
  let failure;
  try{await stopBackend();}catch(error){failure=error;}
  for(const name of [...created].reverse())try{await ownedRemove(name);}catch(error){failure||=error;}
  if(network){assertOwned(r.network,runId,'network');await command(['network','rm',r.network]);}
  for(const name of images){assertOwned(name,runId,'image');await command(['image','rm',name]);}
  await fs.writeFile(path.join(out,'cleanup.json'),JSON.stringify({containers:[...created],network_removed:network,images_removed:[...images],error:failure?.message||null},null,2));
  if(failure)throw primaryError?new AggregateError([primaryError,failure],'Gateway and cleanup failed'):failure;
 }
}
module.exports={ownedResources,assertOwned,runDockerProcess,waitMongoReady};
if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1;});