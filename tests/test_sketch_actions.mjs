import test from "node:test";
import assert from "node:assert/strict";
import {selectedSketch,sketchKeyCommand} from "../crate_studio/web/sketch_actions.mjs";

test("sketch deletion only targets an explicitly selected editable sketch, not the model reference",()=>{
  const document={features:[{id:"box",type:"box"},{id:"circle",type:"sketch_extrude"},{id:"fold",type:"folding_assembly"}]};
  assert.equal(selectedSketch(document,"box"),null);
  assert.equal(selectedSketch(document,"fold"),null);
  assert.equal(selectedSketch(document,null),null);
  assert.equal(selectedSketch(document,"deleted-id"),null);
  assert.equal(selectedSketch(document,"circle").id,"circle");
  assert.equal(sketchKeyCommand("Delete","sketch",selectedSketch(document,"box")),null);
});

test("Escape exits drawing; Delete and Backspace act on a selected sketch without hijacking text editing",()=>{
  const sketch={id:"circle",type:"sketch_extrude"};
  assert.equal(sketchKeyCommand("Escape","sketch",null),"select");
  for(const key of ["Delete","Backspace"]) {
    assert.equal(sketchKeyCommand(key,"sketch",sketch),"delete");
    assert.equal(sketchKeyCommand(key,"sketch",null),null);
    assert.equal(sketchKeyCommand(key,"sketch",sketch,true),null);
    assert.equal(sketchKeyCommand(key,"model",sketch),null);
  }
});
