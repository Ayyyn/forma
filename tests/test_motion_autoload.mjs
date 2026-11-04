import test from "node:test";
import assert from "node:assert/strict";
import {motionAutoLoad, motionBinding} from "../crate_studio/web/motion_autoload.mjs";

const snapshot=()=>({geometry_signature:"geometry",geometry_version:"code",asset_identity:[["asset","bytes"]],
  native_study_state:{status:"current",passed:true},document:{metadata:{native_study_review:{source_identity:"check"},
    design_mechanism:{states:[{name:"start"},{name:"finish"}]},assembly_plan:{steps:[]}}}});

test("qualified Motion autoload is visible-only, coalesced, and attempted once",async()=>{
  let value=snapshot(), visible=false, busy=false, calls=0, resolve;
  const ensure=motionAutoLoad({getSnapshot:()=>value,isVisible:()=>visible,isBusy:()=>busy,hasStudy:()=>false,
    load:()=>{calls++;return new Promise(r=>resolve=r);}});
  ensure();assert.equal(calls,0);visible=true;busy=true;ensure();assert.equal(calls,0);busy=false;
  const first=ensure();ensure();await Promise.resolve();assert.equal(calls,1);resolve();await first;
  ensure();assert.equal(calls,1);
});

test("unverified or failed definitions never auto-run and present studies do not reload",()=>{
  let value=snapshot(),calls=0,hasStudy=false;
  const ensure=motionAutoLoad({getSnapshot:()=>value,isVisible:()=>true,isBusy:()=>false,hasStudy:()=>hasStudy,load:()=>calls++});
  value.native_study_state.status="stale";ensure();value.native_study_state={status:"current",passed:false};ensure();
  value=snapshot();hasStudy=true;ensure();assert.equal(calls,0);
});

test("asset bytes, tool version, mechanism and assembly changes invalidate the display binding",()=>{
  const base=snapshot(), key=motionBinding(base);
  for (const change of [v=>v.asset_identity[0][1]="replacement",v=>v.geometry_version="new-code",
    v=>v.document.metadata.design_mechanism.states.push({name:"another"}),v=>v.document.metadata.assembly_plan.steps.push({name:"new"}),
    v=>v.document.metadata.native_study_review.source_identity="new-check",v=>v.native_study_state.status="stale"]) {
    const next=structuredClone(base);change(next);assert.notEqual(motionBinding(next),key);
  }
  assert.equal(motionBinding({...base,id:"unchanged-copy"}),key);
});

test("a changed eligible source loads after an earlier pending source completes",async()=>{
  let value=snapshot(),calls=0;const resolvers=[];
  const ensure=motionAutoLoad({getSnapshot:()=>value,isVisible:()=>true,isBusy:()=>false,hasStudy:()=>false,
    load:()=>{calls++;return new Promise(r=>resolvers.push(r));}});
  const first=ensure();await Promise.resolve();value={...snapshot(),geometry_signature:"new-geometry"};ensure();
  resolvers[0]();await first;await Promise.resolve();assert.equal(calls,2);resolvers[1]();
});
