import test from "node:test";
import assert from "node:assert/strict";
import { profileContains } from "../crate_studio/web/sketch_hit.mjs";

const outline = {shape:"polyline", points:[[0,0],[40,0],[40,10],[15,10],[15,30],[0,30]]};
test("concave profile selects material and rejects the empty notch", () => {
  assert.equal(profileContains(outline,5,25),true);
  assert.equal(profileContains(outline,35,5),true);
  assert.equal(profileContains(outline,25,25),false);
  assert.equal(profileContains(outline,-1,5),false);
});
test("outline edges, vertices and reversed winding remain selectable", () => {
  for (const points of [outline.points,[...outline.points].reverse()]) {
    assert.equal(profileContains({...outline,points},15,20),true);
    assert.equal(profileContains({...outline,points},40,0),true);
    assert.equal(profileContains({...outline,points},15.01,20),false);
  }
});
test("translated sketch uses local coordinates", () => {
  assert.equal(profileContains({...outline,cx:-100,cy:70},-95,95),true);
  assert.equal(profileContains({...outline,cx:-100,cy:70},-75,95),false);
});
test("rectangle and circle behaviour is retained", () => {
  assert.equal(profileContains({shape:"rectangle",width:20,depth:10,cx:30},39,4),true);
  assert.equal(profileContains({shape:"rectangle",width:20,depth:10,cx:30},41,4),false);
  assert.equal(profileContains({shape:"circle",radius:5,cy:10},3,14),true);
  assert.equal(profileContains({shape:"circle",radius:5,cy:10},4,14),false);
});
test("missing or incomplete polyline cannot be selected", () => {
  assert.equal(profileContains({shape:"polyline"},0,0),false);
  assert.equal(profileContains({shape:"polyline",points:[[0,0],[1,1]]},0,0),false);
});
