import {modelToWorld,worldToModel,constrainedDelta,closestAxisParameter,placementParameters} from '/assets/placement_math.mjs';

export function modelPlacement({$,state,get3D,selectBody,toast,status,save}){
  let draft=null,gesture=null,lastKey='',locks=[];
  const canvas=get3D().renderer.domElement,svg=$('#move-draft-handles');
  const vector=p=>new (get3D().THREE.Vector3)(...modelToWorld(p));
  const blocked=()=>state.busy||state.agentBusy||state.pending||state.inspectorDirty||state.agentPreview||state.measure||get3D().pointAction;
  function lockControls(){
    if(!locks.length)locks=[...document.querySelectorAll('#new-document,#new-document-explorer,#import-document,#save-document,#component-library,#operation-tools button,#place-exact,#edit-dimensions,#hole-at-point,#component-at-point,#measure-toggle,#agent-send,#restore-configuration,#save-configuration,#edit-target,#selection-mode,#body-select,#dimension-feature-scope,#feature-tree button')].map(el=>[el,el.disabled]);
    locks.forEach(([el])=>el.disabled=true);
  }
  function objects(){const g=get3D();return [...g.meshes,...g.faces,...g.pickEdges].filter(m=>draft.id==='all'||(m.userData.part_id||m.userData.id)===draft.id);}
  function ray(event){const g=get3D(),r=canvas.getBoundingClientRect(),ray=new g.THREE.Raycaster();ray.setFromCamera(new g.THREE.Vector2((event.clientX-r.left)/r.width*2-1,-(event.clientY-r.top)/r.height*2+1),g.camera);return ray.ray;}
  function fields(){['x','y','z'].forEach((axis,i)=>{$('#move-draft-'+axis).value=Number(draft.shift[i].toFixed(6));$('#move-draft-r'+axis).value=Number(draft.rotation[i].toFixed(6));});}
  function preview(){
    if(!draft)return;lockControls();const g=get3D(),p=placementParameters(draft.pivot,draft.shift,draft.rotation);
    const q=new g.THREE.Quaternion().setFromEuler(new g.THREE.Euler(...p.rotation.map(v=>v*Math.PI/180),'ZYX'));
    const display=new g.THREE.Quaternion(q.x,q.z,-q.y,q.w);
    objects().forEach(m=>{m.position.copy(vector(p.translation));m.quaternion.copy(display);});
    $('#move-draft-centre').textContent='Centre: '+draft.pivot.map((v,i)=>Number((v+draft.shift[i]).toFixed(3))).join(' / ')+' mm';
    $('#move-draft-apply').disabled=![...draft.shift,...draft.rotation].some(v=>Math.abs(v)>1e-8);
    $('#document-state').textContent='Placement preview · Apply to save';lastKey='';
  }
  function configureGizmo(){
    const g=get3D();g.gizmo?.detach();if(!draft||draft.mode!=='rotate'||!g.gizmo)return;
    g.gizmo.setMode('rotate');g.gizmo.setSpace('local');
    const q=new g.THREE.Quaternion().setFromEuler(new g.THREE.Euler(...draft.rotation.map(v=>v*Math.PI/180),'ZYX'));
    const base=new g.THREE.Quaternion().setFromAxisAngle(new g.THREE.Vector3(1,0,0),-Math.PI/2);
    g.gizmoPivot.quaternion.set(q.x,q.z,-q.y,q.w).multiply(base);
    g.gizmoPivot.position.copy(vector(draft.pivot.map((v,i)=>v+draft.shift[i])));
    g.gizmo.showX=true;g.gizmo.showY=true;g.gizmo.showZ=true;g.gizmo.setRotationSnap($('#move-draft-snap').checked?Math.PI/180*Number($('#move-draft-angle-step').value):null);g.gizmo.attach(g.gizmoPivot);
  }
  function begin(mode,target){
    if(blocked()){toast('Finish the current edit first.',true);return;}
    if(!target){toast('Select a component first.',true);return;}
    $('#move-draft-panel').dataset.mode=mode;
    if(draft){draft.mode=mode;$('#move-draft-title').textContent=mode==='rotate'?'Rotate component':'Move component';configureGizmo();lastKey='';return;}
    draft={id:target.id,pivot:[...target.pivot],shift:[0,0,0],rotation:[0,0,0],revision:state.snapshot.id,mode,applying:false,savedStatus:$('#document-state').textContent};
    state.placementDraft=true;$('#move-draft-cancel').disabled=false;$('#move-draft-error').textContent='';$('#move-draft-title').textContent=mode==='rotate'?'Rotate component':'Move component';$('#move-draft-target').textContent=target.id==='all'?'Whole model':target.id;
    $('#move-draft-panel').classList.remove('hidden');$('.inspector').classList.add('move-draft-active');fields();preview();configureGizmo();
    status('Placement preview · drag an axis or the component on the chosen plane · Apply saves one revision');
  }
  function endGesture(){if(!gesture)return;try{gesture.element.releasePointerCapture(gesture.pointer);}catch{}gesture=null;get3D().controls.enabled=true;lastKey='';}
  function cancel(){
    if(!draft)return;const saved=draft.savedStatus;endGesture();objects().forEach(m=>{m.position.set(0,0,0);m.quaternion.identity();});const g=get3D();g.gizmo?.detach();if(g.gizmo)g.gizmo.dragging=false;g.controls.enabled=true;draft=null;state.placementDraft=false;locks.forEach(([el,disabled])=>el.disabled=disabled);locks=[];svg.innerHTML='';$('#move-draft-panel').classList.add('hidden');$('.inspector').classList.remove('move-draft-active');$('#document-state').textContent=saved;lastKey='';
  }
  function start(event,constraint,point,element){
    if(!draft||draft.mode!=='translate'||draft.applying||blocked())return;
    const g=get3D(),r=ray(event),pivot=vector(point),axis=constraint.length===1?vector('XYZ'.split('').map(a=>a===constraint?1:0)):null;
    const plane=axis?null:new g.THREE.Plane().setFromNormalAndCoplanarPoint(vector(constraint==='XY'?[0,0,1]:constraint==='XZ'?[0,1,0]:[1,0,0]),pivot);
    const hit=axis?closestAxisParameter(r.origin.toArray(),r.direction.toArray(),pivot.toArray(),axis.toArray()):Math.abs(r.direction.dot(plane.normal))<.08?null:r.intersectPlane(plane,new g.THREE.Vector3());
    if(hit===null){toast('This direction points into the view. Choose another view or enter a numeric offset.',true);return;}
    gesture={pointer:event.pointerId,element,constraint,pivot,axis,plane,start:hit,shift:[...draft.shift],xy:[event.clientX,event.clientY]};
    event.preventDefault();event.stopImmediatePropagation();g.controls.enabled=false;element.setPointerCapture(event.pointerId);
  }
  canvas.addEventListener('pointerdown',event=>{
    if(event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||state.measure||get3D().pointAction||$('#selection-mode').value!=='bodies'||get3D().gizmo?.axis)return;
    if(blocked())return;
    const g=get3D();
    const cast=new g.THREE.Raycaster();cast.ray.copy(ray(event));
    const picked=cast.intersectObjects(g.meshes,false).find(h=>h.object.visible&&(!g.acceptHit||g.acceptHit(h.point)));
    if(!picked)return;
    event.preventDefault();event.stopImmediatePropagation();
    if(!draft){selectBody(picked.object.userData.id,worldToModel(picked.point.toArray()));return;}
    if(draft.id!=='all'&&draft.id!==picked.object.userData.id){toast('Apply or cancel the current placement before selecting another component.',true);return;}
    start(event,$('#move-draft-constraint').value,worldToModel(picked.point.toArray()),canvas);
  },true);
  svg.addEventListener('pointerdown',event=>{const node=event.target.closest('[data-move-axis]');if(!node||!draft)return;$('#move-draft-constraint').value=node.dataset.moveAxis;start(event,node.dataset.moveAxis,draft.pivot.map((v,i)=>v+draft.shift[i]),svg);});
  document.addEventListener('pointermove',event=>{
    if(!gesture||event.pointerId!==gesture.pointer||!draft)return;
    event.preventDefault();event.stopImmediatePropagation();if(state.snapshot.id!==draft.revision){cancel();return;}
    if(Math.hypot(event.clientX-gesture.xy[0],event.clientY-gesture.xy[1])<3)return;
    const g=get3D(),r=ray(event);let delta;
    if(gesture.axis){const t=closestAxisParameter(r.origin.toArray(),r.direction.toArray(),gesture.pivot.toArray(),gesture.axis.toArray());if(t===null)return;delta=worldToModel(gesture.axis.clone().multiplyScalar(t-gesture.start).toArray());}
    else{if(Math.abs(r.direction.dot(gesture.plane.normal))<.08)return;const p=r.intersectPlane(gesture.plane,new g.THREE.Vector3());if(!p)return;delta=worldToModel(p.sub(gesture.start).toArray());}
    const step=$('#move-draft-snap').checked?Number($('#move-draft-step').value):0;
    const change=constrainedDelta(delta,gesture.constraint,step);draft.shift=gesture.shift.map((v,i)=>Number((v+change[i]).toFixed(8)));fields();preview();
  },true);
  document.addEventListener('pointerup',event=>{if(gesture&&event.pointerId===gesture.pointer){event.preventDefault();event.stopImmediatePropagation();endGesture();status('Placement preview · Apply to save, Cancel to restore');}},true);
  document.addEventListener('pointercancel',()=>{if(gesture){draft.shift=[...gesture.shift];endGesture();fields();preview();}},true);
  document.addEventListener('keydown',event=>{if(!draft||draft.applying)return;if(event.key==='Escape'||((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z')){event.preventDefault();event.stopImmediatePropagation();cancel();status('Placement cancelled · saved model unchanged');}},true);
  $('#move-draft-form').onsubmit=async event=>{
    event.preventDefault();if(!draft||draft.applying||blocked()||!$('#move-draft-form').reportValidity())return;
    if(draft.revision!==state.snapshot.id){cancel();toast('Source changed. Reopen Move.',true);return;}
    const current=draft;current.applying=true;$('#move-draft-apply').disabled=true;$('#move-draft-cancel').disabled=true;$('#move-draft-error').textContent='';$('#document-state').textContent='Verifying placement…';status('Validating placement with the native CAD engine…');
    try{await save(placementParameters(current.pivot,current.shift,current.rotation),current.id,current.revision);if(draft===current)cancel();if(current.id!=='all')selectBody(current.id);}
    catch(error){if(draft===current){current.applying=false;$('#move-draft-cancel').disabled=false;$('#move-draft-error').textContent=error.message;preview();}}
  };
  $('#move-draft-cancel').onclick=()=>{if(!draft?.applying)cancel();};
  for(const name of ['x','y','z','rx','ry','rz'])$('#move-draft-'+name).oninput=()=>{
    if(!draft||draft.applying||!$('#move-draft-form').checkValidity())return;
    draft.shift=['x','y','z'].map(a=>Number($('#move-draft-'+a).value));draft.rotation=['x','y','z'].map(a=>Number($('#move-draft-r'+a).value));preview();configureGizmo();
  };
  $('#move-draft-constraint').onchange=()=>lastKey='';$('#move-draft-snap').onchange=configureGizmo;$('#move-draft-angle-step').onchange=configureGizmo;
  function update(){
    if(!draft)return;if(draft.revision!==state.snapshot.id){cancel();return;}
    // Keep the captured handle nodes stable until release; replacing an active
    // pointer target can interrupt a drag in browsers and assistive tools.
    if(gesture)return;
    if(draft.mode!=='translate'){svg.innerHTML='';return;}
    const g=get3D(),rect=canvas.getBoundingClientRect(),key=[rect.width,rect.height,...g.camera.position.toArray(),...g.camera.quaternion.toArray(),...draft.shift,$('#move-draft-constraint').value].join('|');if(key===lastKey)return;lastKey=key;
    const centre=vector(draft.pivot.map((v,i)=>v+draft.shift[i])),units=2*g.camera.position.distanceTo(centre)*Math.tan(g.camera.fov*Math.PI/360)/rect.height;
    const p=v=>{const q=v.clone().project(g.camera);return [(q.x+1)*rect.width/2,(1-q.y)*rect.height/2];},[x,y]=p(centre),paths=[];
    for(const [i,axis] of [...'XYZ'].entries()){
      const direction=vector([0,0,0].map((v,j)=>j===i?1:0));if(Math.abs(direction.dot(g.camera.getWorldDirection(new g.THREE.Vector3())))>.97)continue;
      const [a,b]=p(centre.clone().addScaledVector(direction,units*85)),colour=['#bd443f','#318449','#2f6abe'][i],angle=Math.atan2(b-y,a-x),tip=[a-10*Math.cos(angle-.4),b-10*Math.sin(angle-.4),a-10*Math.cos(angle+.4),b-10*Math.sin(angle+.4)];
      paths.push(`<g role="button" tabindex="0" aria-label="Drag along ${axis}" data-move-axis="${axis}" style="pointer-events:all;cursor:grab"><path d="M${x},${y} L${a},${b}" stroke="transparent" stroke-width="18"/><path d="M${x},${y} L${a},${b}" stroke="${colour}" stroke-width="3"/><path d="M${a},${b} L${tip[0]},${tip[1]} L${tip[2]},${tip[3]} Z" fill="${colour}"/><text x="${a+8}" y="${b-8}" fill="${colour}">${axis}</text></g>`);
    }
    svg.setAttribute('viewBox',`0 0 ${rect.width} ${rect.height}`);svg.innerHTML=paths.join('');
  }
  function gizmoChange(){
    if(!draft||draft.mode!=='rotate')return;const g=get3D(),base=new g.THREE.Quaternion().setFromAxisAngle(new g.THREE.Vector3(1,0,0),Math.PI/2),q=g.gizmoPivot.quaternion.clone().multiply(base);
    const e=new g.THREE.Euler().setFromQuaternion(new g.THREE.Quaternion(q.x,-q.z,q.y,q.w),'ZYX');draft.rotation=[e.x,e.y,e.z].map(v=>Number((v*180/Math.PI).toFixed(6)));fields();preview();
  }
  return {begin,cancel,update,gizmoChange,active:()=>!!draft,applying:()=>!!draft?.applying,previewing:()=>!!draft};
}
