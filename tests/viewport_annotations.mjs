import test from 'node:test';
import assert from 'node:assert/strict';
import {niceStep,gridSpec,envelopeDimensions,bodyDragAllowed} from '../crate_studio/web/viewport_annotations.mjs';
test('grid uses readable physical intervals and changes with zoom',()=>{
  assert.equal(niceStep(.13),.2);assert.equal(niceStep(12),20);
  const a=gridSpec(.1),b=gridSpec(1);assert.equal(a.step,5);assert.equal(b.step,50);
  assert.equal(a.extent/a.divisions,a.step);
});
test('dimension values use native bounds including translated or negative geometry',()=>{
  const b=[[-12,4,-3],[23,54,9]],d=envelopeDimensions(b);
  assert.deepEqual(d.map(r=>r.value),[35,50,12]);
  d.forEach((r,i)=>assert.equal(r.b[i]-r.a[i],r.value));
  assert.deepEqual(b,[[-12,4,-3],[23,54,9]]);
});
test('part dragging cannot consume camera, topology, pending-edit or gizmo gestures',()=>{
  assert.equal(bodyDragAllowed({}),true);
  for(const p of [{button:2},{modified:true},{mode:'faces'},{busy:true},{dirty:true},{preview:true},{measure:true},{pointAction:true},{handle:true}])assert.equal(bodyDragAllowed(p),false);
});
