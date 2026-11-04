import {gridSpec,niceStep,envelopeDimensions,bodyDragAllowed} from '/assets/viewport_annotations.mjs';

export function viewportTools({$,esc,state,get3D,setGrid,highlight,inspect,status,toast,addFeature}) {
  let drag=null, lastKey='', lastGrid='', lastFrame=0;
  const canvas=get3D().renderer.domElement;
  const model=v=>[v.x,-v.z,v.y];
  const world=p=>{const {THREE}=get3D();return new THREE.Vector3(p[0],p[2],-p[1]);};
  function ray(event) {
    const {THREE,camera}=get3D(), r=canvas.getBoundingClientRect(), ray=new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2((event.clientX-r.left)/r.width*2-1,-(event.clientY-r.top)/r.height*2+1),camera);return ray;
  }
  function selectBody(id,point) {
    const mesh=get3D().meshes.find(m=>m.userData.id===id);if(!mesh)return;
    get3D().gizmo?.detach();
    state.selection=[{id,part_id:id,kind:'body',name:mesh.userData.name,point:point||[0,0,0]}];
    $('#body-select').value=id;highlight();inspect();lastKey='';
    $('#edit-pick-status').textContent=`${id} selected · drag the component or use an axis handle`;
    $('#selection-message').textContent=mesh.userData.name+' · '+id;
  }
  function restore() {
    if(!drag)return;
    drag.objects.forEach(m=>m.position.set(0,0,0));
    try{canvas.releasePointerCapture(drag.pointer);}catch{}
    get3D().controls.enabled=true;drag=null;lastKey='';
  }
  canvas.addEventListener('pointerdown',event=>{
    const g=get3D();
    if(!$('#drag-components').checked||!bodyDragAllowed({button:event.button,modified:event.ctrlKey||event.metaKey||event.shiftKey,mode:$('#selection-mode').value,busy:state.busy,dirty:state.pending||state.inspectorDirty,preview:state.agentPreview,measure:state.measure,pointAction:g.pointAction,handle:!!g.gizmo?.axis}))return;
    const hit=ray(event).intersectObjects(g.meshes,false).find(h=>h.object.visible);if(!hit)return;
    event.preventDefault();event.stopImmediatePropagation();
    const id=hit.object.userData.id, scope=$('#edit-target').value==='all'?'all':id;
    selectBody(id,model(hit.point));
    const plane=$('#drag-plane').value, normal=plane==='XY'?new g.THREE.Vector3(0,1,0):plane==='XZ'?new g.THREE.Vector3(0,0,1):plane==='YZ'?new g.THREE.Vector3(1,0,0):g.camera.getWorldDirection(new g.THREE.Vector3());
    drag={id:scope,pointer:event.pointerId,revision:state.snapshot.id,start:hit.point.clone(),plane:new g.THREE.Plane().setFromNormalAndCoplanarPoint(normal,hit.point),xy:[event.clientX,event.clientY],delta:new g.THREE.Vector3(),moved:false,objects:[...g.meshes,...g.faces,...g.pickEdges].filter(m=>scope==='all'||(m.userData.part_id||m.userData.id)===scope)};
    g.gizmo?.detach();g.controls.enabled=false;canvas.setPointerCapture(event.pointerId);
  },true);
  canvas.addEventListener('pointermove',event=>{
    if(!drag||event.pointerId!==drag.pointer)return;
    event.preventDefault();event.stopImmediatePropagation();
    if(state.snapshot.id!==drag.revision){restore();return;}
    if(!drag.moved&&Math.hypot(event.clientX-drag.xy[0],event.clientY-drag.xy[1])<4)return;
    const point=ray(event).ray.intersectPlane(drag.plane,new (get3D().THREE.Vector3)());if(!point)return;
    drag.moved=true;drag.delta.copy(point).sub(drag.start);drag.objects.forEach(m=>m.position.copy(drag.delta));
    status('Move '+drag.id+' · Δ '+model(drag.delta).map(v=>v.toFixed(2)).join(', ')+' mm · release to save · Esc cancels');lastKey='';
  },true);
  canvas.addEventListener('pointerup',async event=>{
    if(!drag||event.pointerId!==drag.pointer)return;
    event.preventDefault();event.stopImmediatePropagation();
    const completed=drag,delta=model(drag.delta);restore();
    if(completed.moved&&delta.some(v=>Math.abs(v)>1e-6)&&state.snapshot.id===completed.revision){
      await addFeature('transform',{translation:delta,rotation:[0,0,0],...(completed.id==='all'?{}:{target_part_id:completed.id})});
      if(!state.pending&&completed.id!=='all')selectBody(completed.id);
    }
  },true);
  canvas.addEventListener('pointercancel',restore,true);
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&drag){restore();status('Component move cancelled');event.preventDefault();event.stopImmediatePropagation();}},true);
  $('#body-select').onchange=()=>{if(state.inspectorDirty||state.busy){toast('Save or discard pending edits first.',true);return;}$('#selection-mode').value='bodies';$('#edit-target').value='selected';selectBody($('#body-select').value);};
  for(const id of ['dimension-display','show-edge-sizes','show-grid'])$('#'+id).addEventListener('change',()=>lastKey='');
  function sync() {
    $('#body-select').innerHTML='<option value="">Select component…</option>'+get3D().meshes.map(m=>`<option value="${esc(m.userData.id)}">${esc(m.userData.name)} · ${esc(m.userData.id)}</option>`).join('');lastKey='';
  }
  function update() {
    const now=performance.now();if(now-lastFrame<65||!state.snapshot)return;lastFrame=now;
    const g=get3D(),r=canvas.getBoundingClientRect(),width=r.width,height=r.height;if(!height||!width)return;
    const units=2*g.camera.position.distanceTo(g.controls.target)*Math.tan(g.camera.fov*Math.PI/360)/height;
    const spec=gridSpec(units), floor=Math.min(0,state.snapshot.metrics?.bounds_mm?.[0]?.[2]||0)-.02;
    const key=[state.snapshot.id,width,height,...g.camera.position.toArray(),...g.camera.quaternion.toArray(),...g.controls.target.toArray(),state.selection.map(s=>s.id).join(','),$('#dimension-display').value,$('#show-edge-sizes').checked,$('#show-grid').checked,drag?.delta.toArray().join(','),g.gizmoDragging].join('|');
    if(key===lastKey)return;lastKey=key;
    const gridKey=spec.step+'|'+floor;
    if(lastGrid!==gridKey||!g.grid){
      if(g.grid){g.scene.remove(g.grid);g.grid.geometry.dispose();g.grid.material.dispose();}
      const grid=new g.THREE.GridHelper(spec.extent,spec.divisions,0x92a6b9,0xc1ccd7);grid.position.y=floor;g.scene.add(grid);setGrid(grid);lastGrid=gridKey;
    }
    const grid=get3D().grid;grid.visible=$('#show-grid').checked;
    grid.position.x=Math.round(g.controls.target.x/spec.step)*spec.step;grid.position.z=Math.round(g.controls.target.z/spec.step)*spec.step;
    $('#grid-scale-label').textContent=grid.visible?'Grid '+format(spec.step)+' mm':'Grid hidden';
    const scale=niceStep(units*75);$('#screen-scale-bar').style.width=scale/units+'px';$('#screen-scale-label').textContent=format(scale)+' mm at view centre';
    const project=p=>{const v=world(p).project(g.camera);return {x:(v.x+1)*width/2,y:(1-v.y)*height/2,visible:v.z>=-1&&v.z<=1&&Math.abs(v.x)<1.5&&Math.abs(v.y)<1.5};};
    const svg=[],labelled=[];
    function label(p,text,color='#3b5064',offset=0){if(!p.visible)return;const x=p.x,y=p.y+offset;if(labelled.some(q=>Math.abs(x-q.x)<Math.max(text.length*3,20)&&Math.abs(y-q.y)<13))return;labelled.push({x,y});svg.push(`<text x="${x}" y="${y}" text-anchor="middle" style="fill:${color}">${esc(text)}</text>`);}
    if(grid.visible){
      const x=grid.position.x,y=-grid.position.z;
      for(let i=-2;i<=2;i++){
        label(project([x+i*spec.step,y-3*spec.step,floor]),'X '+format(x+i*spec.step),'#8a5150');
        label(project([x-3*spec.step,y+i*spec.step,floor]),'Y '+format(y+i*spec.step),'#416d53');
      }
    }
    const selected=state.selection.at(-1),id=selected?.part_id||selected?.id,mode=$('#dimension-display').value;
    const rows=state.snapshot.body_measurements||[], selectedRow=rows.find(row=>row.id===id);
    if(mode!=='off'&&!g.gizmoDragging){
      for(const row of rows){
        const mesh=g.meshes.find(m=>m.userData.id===row.id);if(!mesh?.visible||(mode==='selected'&&row.id!==id))continue;
        const delta=drag&&(drag.id==='all'||drag.id===row.id)?model(drag.delta):[0,0,0];
        const bounds=row.bounds_mm.map(p=>p.map((v,i)=>v+delta[i]));
        for(const d of envelopeDimensions(bounds)){
          const a=project(d.a),b=project(d.b);if(!a.visible||!b.visible||Math.hypot(a.x-b.x,a.y-b.y)<9)continue;
          const color={X:'#a74f46',Y:'#39774f',Z:'#3567aa'}[d.axis];
          const fa=project(d.fromA),fb=project(d.fromB);
          svg.push(`<path d="M${fa.x},${fa.y} L${a.x},${a.y} M${fb.x},${fb.y} L${b.x},${b.y}" fill="none" stroke="${color}" stroke-width=".65" opacity=".65"/>`);
          svg.push(`<path d="M${a.x},${a.y} L${b.x},${b.y}" stroke="${color}" stroke-width="1" marker-start="url(#dim-arrow)" marker-end="url(#dim-arrow)"/>`);
          label({x:(a.x+b.x)/2,y:(a.y+b.y)/2,visible:true},d.axis+' '+format(d.value)+' mm',color,-5);
        }
        for(const circle of row.circles)label(project(circle.center_mm.map((v,i)=>v+delta[i])),'Ø'+format(circle.diameter_mm)+' mm','#5a457c',-8);
      }
      if($('#show-edge-sizes').checked&&id){
        const edges=(state.snapshot.geometry.edge_meta||[]).filter(e=>e.part_id===id&&e.type==='LINE');
        for(const edge of edges.slice(0,64)){
          const delta=drag&&(drag.id==='all'||drag.id===id)?model(drag.delta):[0,0,0];
          label(project(edge.center.map((v,i)=>v+delta[i])),format(edge.length_mm)+' mm','#705027',10);
        }
      }
    }
    $('#model-annotations').setAttribute('viewBox',`0 0 ${width} ${height}`);
    $('#model-annotations').innerHTML='<defs><marker id="dim-arrow" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M6,0 L0,3 L6,6" fill="none" stroke="#5b6b7c"/></marker></defs>'+svg.join('');
    const box=$('#body-measurements');box.classList.toggle('hidden',!selectedRow||mode==='off');
    if(selectedRow&&mode!=='off')box.innerHTML=`<strong>${esc(selectedRow.id)}</strong><br>Global X × Y × Z · mm<br>${selectedRow.size_mm.map(format).join(' × ')}<br>Volume ${format(selectedRow.volume_mm3)} mm³${selected?.kind==='edge'?'<br>Edge '+format(selected.length_mm)+' mm':''}${selected?.kind==='face'?'<br>Face '+format(selected.area_mm2)+' mm²':''}<br><small>Native reference dimensions${drag?' · position preview':''}${$('#show-edge-sizes').checked?' · up to 64 edge labels':''}</small>`;
  }
  function format(value){return Number(value.toFixed(3)).toLocaleString(undefined,{maximumFractionDigits:3});}
  return {sync,update,cancel:restore,selectBody,invalidate:()=>lastKey=''};
}
