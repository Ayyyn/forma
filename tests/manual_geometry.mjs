import test from 'node:test';
import assert from 'node:assert/strict';
import {pivotTranslation,rotateXYZ} from '../crate_studio/web/manual_geometry.mjs';
test('pivot rotation keeps the centre fixed and applies requested displacement',()=>{
  const pivot=[23,-12,8],shift=[4,7,-2],angles=[33,-21,72];
  const t=pivotTranslation(pivot,shift,angles),rp=rotateXYZ(pivot,angles);
  rp.forEach((v,i)=>assert.ok(Math.abs(v+t[i]-pivot[i]-shift[i])<1e-10));
  const point=[25,-7,13], moved=rotateXYZ(point,angles).map((v,i)=>v+t[i]);
  const local=rotateXYZ(point.map((v,i)=>v-pivot[i]),angles).map((v,i)=>v+pivot[i]+shift[i]);
  moved.forEach((v,i)=>assert.ok(Math.abs(v-local[i])<1e-10));
  assert.throws(()=>pivotTranslation([NaN,0,0],[0,0,0],[0,0,0]));
});
