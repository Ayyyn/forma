import {gridSpec,niceStep,envelopeDimensions,bodyDragAllowed,dimensionLayout} from '/assets/viewport_annotations.mjs';

export function viewportTools({$,esc,state,get3D,setGrid,highlight,inspect,status,toast,addFeature,editDimension}) {
  let drag=null, lastKey='', lastGrid='', lastFrame=0,editing=null;
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
    if(!$('#drag-components').checked||!bodyDragAllowed({button:event.button,modified:event.ctrlKey||event.metaKey||event.shiftKey,mode:$('#selection-mode').value,busy:state.busy,dirty:state.pending||state.inspectorDirty||!!editing,preview:state.agentPreview,measure:state.measure,pointAction:g.pointAction,handle:!!g.gizmo?.axis}))return;
    const hit=ray(event).intersectObjects(g.meshes,false).find(h=>h.object.visible&&(!g.acceptHit||g.acceptHit(h.point)));if(!hit)return;
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
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&(drag||editing)){restore();closeEditor();status('Edit cancelled');event.preventDefault();event.stopImmediatePropagation();}},true);
  function closeEditor(){editing=null;$('#dimension-editor').classList.add('hidden');}
  function openEditor(id,x,y){
    if(state.busy||state.agentBusy||state.pending||state.inspectorDirty||state.agentPreview){toast('Save or discard pending edits first.',true);return;}
    const d=state.snapshot.feature_dimensions?.find(d=>d.id===id);if(!d)return;
    editing={dimension:d,revision:state.snapshot.id};get3D().gizmo?.detach();
    $('#dimension-editor-title').textContent=d.label+' · '+d.feature_name;
    $('#dimension-value').value=d.value_mm;$('#dimension-editor-source').textContent=`Edits ${d.key}${d.multiplier===2?' (diameter ÷ 2)':''}. Native CAD regenerates dependent views.`;
    $('#dimension-editor-error').textContent='';
    const box=$('#dimension-editor'),r=canvas.getBoundingClientRect();box.classList.remove('hidden');box.style.left=Math.max(8,Math.min(r.width-276,x))+'px';box.style.top=Math.max(52,Math.min(r.height-220,y))+'px';
    $('#dimension-value').focus();$('#dimension-value').select();
  }
  $('#model-annotations').addEventListener('click',event=>{const node=event.target.closest('[data-dimension]');if(node){event.stopPropagation();const r=canvas.getBoundingClientRect();openEditor(node.dataset.dimension,event.clientX-r.left,event.clientY-r.top);}});
  $('#model-annotations').addEventListener('keydown',event=>{const node=event.target.closest('[data-dimension]');if(node&&['Enter',' '].includes(event.key)){event.preventDefault();const r=node.getBoundingClientRect(),c=canvas.getBoundingClientRect();openEditor(node.dataset.dimension,r.left-c.left,r.top-c.top);}});
  $('#dimension-editor-cancel').onclick=closeEditor;
  $('#dimension-editor-form').onsubmit=async event=>{
    event.preventDefault();if(!editing||!$('#dimension-editor-form').reportValidity())return;
    const current=editing,value=Number($('#dimension-value').value);
    $('#dimension-editor-save').disabled=true;
    try{await editDimension(current.dimension,value,current.revision);closeEditor();selectBody(current.dimension.part_id);}
    catch(error){$('#dimension-editor-error').textContent=error.message;}
    finally{$('#dimension-editor-save').disabled=false;}
  };
  $('#body-select').onchange=()=>{if(state.inspectorDirty||state.busy){toast('Save or discard pending edits first.',true);return;}$('#selection-mode').value='bodies';$('#edit-target').value='selected';selectBody($('#body-select').value);};
  for(const id of ['dimension-display','show-edge-sizes','show-grid'])$('#'+id).addEventListener('change',()=>lastKey='');
  function sync() {
    if(editing&&editing.revision!==state.snapshot.id)closeEditor();
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
    function dimension(a,b,text,{binding=null,fromA=null,fromB=null,title='Native reference measurement',leader=false}={}){
      if(!a.visible||!b.visible)return;
      const color=binding?'#245db3':'#526479';
      const originalA=a,originalB=b,outside=leader||dimensionLayout(a,b).length<text.length*6+18;
      const lines=[];
      if(fromA&&fromB)lines.push(`<path d="M${fromA.x},${fromA.y} L${a.x},${a.y} M${fromB.x},${fromB.y} L${b.x},${b.y}" fill="none" stroke="${color}" stroke-width=".7" opacity=".7"/>`);
      if(leader||dimensionLayout(a,b).length<text.length*6+18){
        const start=b,elbow={x:b.x+20,y:b.y-24,visible:true};
        a=elbow;b={x:elbow.x+text.length*6+16,y:elbow.y,visible:true};
        if(!leader)lines.push(`<path d="M${originalA.x},${originalA.y} L${originalB.x},${originalB.y}" fill="none" stroke="${color}" marker-start="url(#dim-arrow)" marker-end="url(#dim-arrow)"/>`);
        lines.push(`<path d="M${start.x},${start.y} L${elbow.x},${elbow.y}" fill="none" stroke="${color}"/>`);
      }
      const layout=dimensionLayout(a,b);if(layout.length<8)return;
      const textWidth=text.length*6.4+10;
      if(labelled.some(q=>Math.abs(layout.x-q.x)<(textWidth+q.w)/2&&Math.abs(layout.y-q.y)<18))return;
      labelled.push({x:layout.x,y:layout.y,w:textWidth});
      svg.push(...lines,`<path d="M${a.x},${a.y} L${b.x},${b.y}" fill="none" stroke="${color}" stroke-width="1" ${outside?'':'marker-start="url(#dim-arrow)" marker-end="url(#dim-arrow)"'}/>`);
      const description=binding?`Edit ${binding.label} · ${binding.feature_name} · ${text}`:title+' · '+text;
      svg.push(`<g transform="translate(${layout.x},${layout.y}) rotate(${layout.angle})" ${binding?`class="editable-dimension" role="button" tabindex="0" data-dimension="${esc(binding.id)}" aria-label="${esc(description)}"`:''}><title>${esc(description)}</title><rect x="${-textWidth/2}" y="-8" width="${textWidth}" height="17" rx="2" fill="#fff"/><text x="0" y="4" text-anchor="middle" style="fill:${color};stroke-width:0">${esc(text)}</text></g>`);
    }
    const selected=state.selection.at(-1),id=selected?.part_id||selected?.id,mode=$('#dimension-display').value;
    const rows=state.snapshot.body_measurements||[], selectedRow=rows.find(row=>row.id===id);
    if(mode!=='off'&&!g.gizmoDragging){
      const driving=state.snapshot.feature_dimensions||[];
      for(const d of driving){
        const mesh=g.meshes.find(m=>m.userData.id===d.part_id);if(!mesh?.visible||(mode==='selected'&&d.part_id!==id))continue;
        const delta=drag&&(drag.id==='all'||drag.id===d.part_id)?model(drag.delta):[0,0,0];
        const p=v=>project(v.map((n,i)=>n+delta[i]));
        dimension(p(d.a),p(d.b),(d.symbol||'')+format(d.value_mm)+' mm',{binding:drag?null:d,fromA:p(d.fromA),fromB:p(d.fromB)});
      }
      for(const row of rows){
        const mesh=g.meshes.find(m=>m.userData.id===row.id);if(!mesh?.visible||(mode==='selected'&&row.id!==id))continue;
        const delta=drag&&(drag.id==='all'||drag.id===row.id)?model(drag.delta):[0,0,0];
        const bounds=row.bounds_mm.map(p=>p.map((v,i)=>v+delta[i]));
        for(const d of driving.some(d=>d.part_id===row.id)?[]:envelopeDimensions(bounds)){
          const a=project(d.a),b=project(d.b);if(!a.visible||!b.visible||Math.hypot(a.x-b.x,a.y-b.y)<9)continue;
          const fa=project(d.fromA),fb=project(d.fromB);
          dimension(a,b,format(d.value)+' mm',{fromA:fa,fromB:fb,title:'Global '+d.axis+' envelope · reference only'});
        }
        for(const circle of row.circles){
          if(driving.some(d=>d.part_id===row.id&&d.symbol==='Ø'&&Math.abs(d.value_mm-circle.diameter_mm)<1e-6))continue;
          const p=project((circle.edge_point_mm||circle.center_mm).map((v,i)=>v+delta[i]));
          dimension(p,p,'Ø'+format(circle.diameter_mm)+' mm',{leader:true,title:'Diameter · native circular edge · reference only'});
        }
      }
      if($('#show-edge-sizes').checked&&id){
        const edges=(state.snapshot.geometry.edge_meta||[]).filter(e=>e.part_id===id&&e.type==='LINE');
        for(const edge of edges.slice(0,64)){
          const delta=drag&&(drag.id==='all'||drag.id===id)?model(drag.delta):[0,0,0];
          dimension(project(edge.start.map((v,i)=>v+delta[i])),project(edge.end.map((v,i)=>v+delta[i])),format(edge.length_mm)+' mm',{title:'Edge length · reference only'});
        }
      }
    }
    $('#model-annotations').setAttribute('viewBox',`0 0 ${width} ${height}`);
    $('#model-annotations').innerHTML='<defs><marker id="dim-arrow" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M6,0 L0,3 L6,6" fill="none" stroke="#5b6b7c"/></marker></defs>'+svg.join('');
    const box=$('#body-measurements');box.classList.toggle('hidden',!selectedRow||mode==='off');
    if(selectedRow&&mode!=='off')box.innerHTML=`<strong>${esc(selectedRow.id)}</strong><br>Global X × Y × Z · mm<br>${selectedRow.size_mm.map(format).join(' × ')}<br>Volume ${format(selectedRow.volume_mm3)} mm³${selected?.kind==='edge'?'<br>Edge '+format(selected.length_mm)+' mm':''}${selected?.kind==='face'?'<br>Face '+format(selected.area_mm2)+' mm²':''}<br><small>Blue: click to edit · grey: reference<br>Ø means diameter${drag?' · position preview':''}${$('#show-edge-sizes').checked?' · up to 64 edge labels':''}</small>`;
  }
  function format(value){return Number(value.toFixed(3)).toLocaleString(undefined,{maximumFractionDigits:3});}
  return {sync,update,cancel:restore,selectBody,invalidate:()=>lastKey=''};
}
