import test from 'node:test';
import assert from 'node:assert/strict';
import {drawingRequest} from '../crate_studio/web/drawing_request.js';

test('rapid history changes retain one in-flight request and fetch only the latest revision next',async()=>{
  const make=id=>({id,document:{name:id},geometry_signature:id,drawing_pending:true});
  let snapshot=make('a'),ready=0;const requests=[];
  const ensure=drawingRequest({getSnapshot:()=>snapshot,api:(path,body)=>new Promise(resolve=>requests.push({body,resolve})),onReady:()=>ready++,onError:e=>{throw e;}});
  ensure();snapshot=make('b');ensure();snapshot=make('c');ensure();ensure();
  assert.equal(requests.length,1);
  requests[0].resolve({geometry_signature:'a',svg:'old'});await new Promise(r=>setImmediate(r));
  assert.equal(ready,0);assert.equal(requests.length,2);assert.equal(requests[1].body.revision_id,'c');
  requests[1].resolve({geometry_signature:'c',svg:'latest'});await new Promise(r=>setImmediate(r));
  assert.equal(ready,1);assert.equal(snapshot.drawing_svg,'latest');
});

test('a queued revision does not start projection after leaving the drawing view',async()=>{
  let visible=true,snapshot={id:'a',document:{},geometry_signature:'a',drawing_pending:true};const requests=[];
  const ensure=drawingRequest({getSnapshot:()=>snapshot,isNeeded:()=>visible,api:()=>new Promise(resolve=>requests.push(resolve)),onReady:()=>{},onError:e=>{throw e;}});
  ensure();snapshot={id:'b',document:{},geometry_signature:'b',drawing_pending:true};ensure();visible=false;
  requests[0]({geometry_signature:'a',svg:'old'});await new Promise(r=>setImmediate(r));
  assert.equal(requests.length,1);visible=true;ensure();assert.equal(requests.length,2);
  requests[1]({geometry_signature:'b',svg:'new'});await new Promise(r=>setImmediate(r));
  assert.equal(snapshot.drawing_svg,'new');
});

test('one deferred request per snapshot, exact response becomes available',async()=>{
  let snapshot={id:'a',document:{},geometry_signature:'g',drawing_pending:true};
  let resolve,calls=0,ready=0;
  const ensure=drawingRequest({getSnapshot:()=>snapshot,api:()=>{calls++;return new Promise(r=>resolve=r);},onReady:()=>ready++,onError:e=>{throw e;}});
  ensure();ensure();assert.equal(calls,1);
  resolve({geometry_signature:'g',svg:'<svg/>'});await new Promise(r=>setImmediate(r));
  assert.equal(ready,1);assert.equal(snapshot.drawing_svg,'<svg/>');assert.equal(snapshot.drawing_pending,false);
  ensure();assert.equal(calls,1);
});

test('changed snapshots and wrong geometry cannot receive stale vectors',async()=>{
  let snapshot={id:'a',document:{},geometry_signature:'a',drawing_pending:true};
  const first=snapshot;let resolve,ready=0,errors=0;
  const ensure=drawingRequest({getSnapshot:()=>snapshot,api:()=>new Promise(r=>resolve=r),onReady:()=>ready++,onError:()=>errors++});
  ensure();snapshot={id:'b',document:{},geometry_signature:'b',drawing_pending:true};
  resolve({geometry_signature:'a',svg:'old'});await new Promise(r=>setImmediate(r));
  assert.equal(ready,0);assert.equal(first.drawing_svg,undefined);assert.equal(snapshot.drawing_svg,undefined);
  ensure();resolve({geometry_signature:'wrong',svg:'wrong'});await new Promise(r=>setImmediate(r));
  assert.equal(errors,1);assert.equal(snapshot.drawing_svg,undefined);
  snapshot.asset_identity=[['same-id','old-hash']];
  ensure();resolve({geometry_signature:'b',asset_identity:[['same-id','new-hash']],svg:'changed asset'});await new Promise(r=>setImmediate(r));
  assert.equal(errors,2);assert.equal(snapshot.drawing_svg,undefined);
});
