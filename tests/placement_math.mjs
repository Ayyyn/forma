import test from 'node:test';
import assert from 'node:assert/strict';
import {modelToWorld,worldToModel,constrainedDelta,closestAxisParameter,placementParameters,outsideDimension,nativeBodyPivot} from '../crate_studio/web/placement_math.mjs';
import {rotateXYZ} from '../crate_studio/web/manual_geometry.mjs';

test('native XYZ and viewport coordinates round-trip without exchanging CAD Y and Z',()=>{
  assert.deepEqual(modelToWorld([4,7,9]),[4,9,-7]);assert.deepEqual(worldToModel([4,9,-7]),[4,7,9]);
});
test('rotation pivots use native double precision bounds, without display-mesh rounding',()=>{
  const rows=[{id:'body_002',bounds_mm:[[33.224210123456,-5.68987654321,-7.82412345],[45.224210123456,6.31012345679,4.17587655]]}];
  const p=nativeBodyPivot(rows,'body_002');p.forEach((v,i)=>assert.ok(Math.abs(v-[39.224210123456,.31012345679,-1.82412345][i])<1e-12));
  assert.equal(nativeBodyPivot(rows,'body_001'),null);
});
test('XY dragging locks depth and snaps without accumulating floating noise',()=>{
  assert.deepEqual(constrainedDelta([9.622955,-4.917737,-3.225065],'XY',1),[10,-5,0]);
  assert.deepEqual(constrainedDelta([1.125,4,9],'X',.25),[1.25,0,0]);
  assert.deepEqual(constrainedDelta([.125,4,-9],'YZ',0),[0,4,-9]);
});
test('axis dragging solves world distance from the viewing ray and rejects depth-parallel instability',()=>{
  assert.equal(closestAxisParameter([12,4,20],[0,0,-1],[2,4,0],[1,0,0]),10);
  assert.equal(closestAxisParameter([12,4,20],[0,0,-1],[2,4,0],[0,0,1]),null);
  const ray=[1,0,-1].map(v=>v/Math.sqrt(2));
  assert.ok(Math.abs(closestAxisParameter([0,0,10],ray,[0,0,0],[1,0,0])-10)<1e-8);
});
test('combined placement retains the component centre while native transform rotates at world origin',()=>{
  const pivot=[50,-18,6],shift=[10,0,-3],angles=[20,35,90],p=placementParameters(pivot,shift,angles),rotated=rotateXYZ(pivot,angles);
  rotated.forEach((v,i)=>assert.ok(Math.abs(v+p.translation[i]-pivot[i]-shift[i])<1e-8));
});
test('dimension rails sit outside the projected part and retain parallel, equal-length witness spans',()=>{
  const corners=[{x:50,y:50},{x:150,y:50},{x:50,y:150},{x:150,y:150}],a={x:50,y:150,visible:true},b={x:150,y:150,visible:true};
  const layout=outsideDimension(a,b,corners,25);assert.equal(layout.a.y,175);assert.equal(layout.b.y,175);assert.equal(layout.b.x-layout.a.x,100);
  assert.equal(outsideDimension({x:0,y:0},{x:0,y:3},corners),null);
});
