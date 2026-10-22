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

test('Mongo startup fails with diagnostics before browser work when the container exited',async()=>{
 const {waitMongoReady}=require('./run_gateway.cjs');
 const calls=[];
 await assert.rejects(waitMongoReady(async args=>{
  calls.push(args);
  return args[0]==='inspect'?{code:0,output:'{"Running":false,"ExitCode":14}'}:{code:0,output:'rseq startup failure'};
 },'owned-mongo'),/rseq startup failure/);
 assert.deepEqual(calls.map(args=>args[0]),['inspect','logs']);
});
test('Mongo startup waits for ping, using a non-data HOME for mongosh',async()=>{
 const {waitMongoReady}=require('./run_gateway.cjs');
 const calls=[];let probes=0;
 await waitMongoReady(async args=>{
  calls.push(args);
  return args[0]==='inspect'?{code:0,output:'{"Running":true}'}:{code:++probes===1?1:0,output:''};
 },'owned-mongo',{pause:async()=>{}});
 assert.equal(probes,2);
 const probe=calls.find(args=>args[0]==='exec');
 assert(probe.includes('HOME=/tmp'));assert(probe.includes('mongodb'));
});