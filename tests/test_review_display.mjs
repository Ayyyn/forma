import test from "node:test";
import assert from "node:assert/strict";
import {displayChecks} from "../crate_studio/web/review_display.mjs";

test("inherited findings are historical without modifying current checks or evidence", () => {
  const snapshot={document:{metadata:{assembly_development:{source_candidate:"earlier"},manufacturing_development:{source_candidate:"current"}}},checks:[
    {id:"practical_release",status:"fail",detail:"Original failed handling path"},
    {id:"native_study",status:"fail",detail:"New collision"},
    {id:"design_review",status:"stale"},
  ]};
  const before=structuredClone(snapshot), result=displayChecks(snapshot);
  assert.equal(result[0].status,"stale");
  assert.match(result[0].detail,/Original failed handling path/);
  assert.match(result[0].detail,/not a fresh result/);
  assert.equal(result[1].status,"fail");
  assert.equal(result[2].status,"stale");
  assert.deepEqual(snapshot,before);
});

test("same-candidate or unscoped failures stay failed", () => {
  for(const current of ["earlier",undefined]) {
    const snapshot={document:{metadata:{assembly_development:{source_candidate:"earlier"},manufacturing_development:{source_candidate:current}}},checks:[{id:"practical_release",status:"fail"}]};
    assert.equal(displayChecks(snapshot)[0].status,"fail");
  }
});
