const test=require('node:test');
const assert=require('node:assert/strict');
const {ownedResources,assertOwned}=require('./run_gateway.cjs');
test('only exact UUID resources are accepted',()=>{
 const id='a'.repeat(32), resource=ownedResources(id);
 assert.equal(resource.database,'humorpedia_html_gateway_'+id);
 for(const name of Object.values(resource.containers)) assertOwned(name,id,'container');
 assert.throws(()=>ownedResources('main'));
 for(const name of ['humorpedia-backend','hp-r13e-'+id+'-foreign','hp-r13e-'+'b'.repeat(32)+'-mongo']) assert.throws(()=>assertOwned(name,id,'container'));
 assert.throws(()=>assertOwned('mongo_data',id,'volume'));
});
test('timeout or signal is failure, never a successful Docker command',async()=>{
 const {runDockerProcess}=require('./run_gateway.cjs');
 const {EventEmitter}=require('node:events');
 const fake=()=>{
  const child=new EventEmitter();child.stdout=new EventEmitter();child.stderr=new EventEmitter();
  child.kill=()=>queueMicrotask(()=>child.emit('close',null,'SIGTERM'));
  return child;
 };
 await assert.rejects(runDockerProcess(['run'],{timeout:1,spawnProcess:fake}),/timed out/);
 const signalled=()=>{
  const child=fake();queueMicrotask(()=>child.emit('close',null,'SIGKILL'));return child;
 };
 await assert.rejects(runDockerProcess(['run'],{timeout:100,spawnProcess:signalled}),/signal/);
});
