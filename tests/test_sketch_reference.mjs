import test from "node:test";
import assert from "node:assert/strict";
import {referenceSegments,savedSketchCount} from "../crate_studio/web/sketch_reference.mjs";

test("XY reference retains a mesh boundary without triangulation diagonals or fake editable sketches",()=>{
  const part={vertices:[0,0,0,10,0,0,10,20,0,0,20,0],triangles:[0,1,2,0,2,3]};
  const before=structuredClone(part),segments=referenceSegments([part]);
  assert.equal(segments.length,4);
  assert.ok(segments.every(([x1,y1,x2,y2])=>x1===x2||y1===y2));
  assert.deepEqual(part,before);
  assert.equal(savedSketchCount({features:[{type:"box"},{type:"sketch_extrude",suppressed:true}]}),0);
  assert.equal(savedSketchCount({features:[{type:"sketch_extrude"}]}),1);
});
