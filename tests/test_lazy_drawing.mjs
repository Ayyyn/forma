import test from 'node:test';
import assert from 'node:assert/strict';
import {drawingRequest} from '../crate_studio/web/drawing_request.js';

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
