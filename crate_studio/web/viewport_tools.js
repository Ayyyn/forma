import {outsideDimension} from '/assets/placement_math.mjs';
import {gridSpec,niceStep,envelopeDimensions,dimensionLayout} from '/assets/viewport_annotations.mjs';

export function viewportTools({$,esc,state,get3D,setGrid,highlight,inspect,status,toast,addFeature,editDimension}) {
  let lastKey='', lastGrid='', lastFrame=0,editing=null,dimensionFeature=null;
  const canvas=get3D().renderer.domElement;
  const world=p=>{const {THREE}=get3D();return new THREE.Vector3(p[0],p[2],-p[1]);};
  function selectBody(id,point,preferred=null) {
    if(state.placementDraft){toast('Apply or cancel placement first.',true);return;}
    const mesh=get3D().meshes.find(m=>m.userData.id===id);if(!mesh)return;
    get3D().gizmo?.detach();
    state.selection=[{id,part_id:id,kind:'body',name:mesh.userData.name,point:point||[0,0,0]}];
    $('#body-select').value=id;syncScope(id,preferred);state.feature=dimensionFeature;highlight();inspect();lastKey='';
    $('#edit-pick-status').textContent=`${id} selected · Move to place · select a feature to dimension`;
    $('#selection-message').textContent=mesh.userData.name+' · '+id;
  }
  function restore(){closeEditor();}
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&editing){closeEditor();event.preventDefault();event.stopImmediatePropagation();}},true);
  function closeEditor(){editing=null;$('#dimension-editor').classList.add('hidden');}
  function openEditor(id,x,y){
    if(state.placementDraft||state.busy||state.agentBusy||state.pending||state.inspectorDirty||state.agentPreview){toast('Save or discard pending edits first.',true);return;}
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
    try{await editDimension(current.dimension,value,current.revision);closeEditor();selectBody(current.dimension.part_id,null,current.dimension.feature_id);}
    catch(error){$('#dimension-editor-error').textContent=error.message;}
    finally{$('#dimension-editor-save').disabled=false;}
  };
  $('#body-select').onchange=()=>{if(state.placementDraft||state.inspectorDirty||state.busy){toast('Save or discard pending edits first.',true);return;}$('#selection-mode').value='bodies';$('#edit-target').value='selected';selectBody($('#body-select').value);};
  for(const id of ['dimension-display','show-edge-sizes','show-grid'])$('#'+id).addEventListener('change',()=>lastKey='');
  function syncScope(id,preferred=null){
    const choices=[...new Map((state.snapshot.feature_dimensions||[]).filter(d=>d.part_id===id).map(d=>[d.feature_id,d])).values()];
    dimensionFeature=choices.find(d=>d.feature_id===(preferred||dimensionFeature))?.feature_id||choices[0]?.feature_id||null;
    $('#dimension-feature-scope').innerHTML=choices.length?choices.map(d=>`<option value="${esc(d.feature_id)}">${esc(d.feature_name)}</option>`).join(''):'<option value="">No driving dimensions</option>';
    $('#dimension-feature-scope').value=dimensionFeature||'';$('#dimension-feature-scope').disabled=!choices.length;
  }
  $('#dimension-feature-scope').onchange=()=>{if(state.inspectorDirty||state.placementDraft){toast('Finish the current edit first.',true);return;}dimensionFeature=$('#dimension-feature-scope').value;state.feature=dimensionFeature;inspect();lastKey='';};
  $('#viewport-options-toggle').onclick=()=>$('#viewport-options-more').classList.toggle('hidden');
  function focusFeature(feature){const d=state.snapshot.feature_dimensions?.find(d=>d.feature_id===feature);if(d&&!state.placementDraft)selectBody(d.part_id,null,feature);}
  function sync() {
    if(editing&&editing.revision!==state.snapshot.id)closeEditor();
    $('#body-select').innerHTML='<option value="">Select component…</option>'+get3D().meshes.map(m=>`<option value="${esc(m.userData.id)}">${esc(m.userData.name)} · ${esc(m.userData.id)}</option>`).join('');syncScope(state.selection.at(-1)?.part_id);lastKey='';
  }
  function update() {
    const now=performance.now();if(now-lastFrame<65||!state.snapshot)return;lastFrame=now;
    const g=get3D(),r=canvas.getBoundingClientRect(),width=r.width,height=r.height;if(!height||!width)return;
    const units=2*g.camera.position.distanceTo(g.controls.target)*Math.tan(g.camera.fov*Math.PI/360)/height;
    const spec=gridSpec(units), floor=Math.min(0,state.snapshot.metrics?.bounds_mm?.[0]?.[2]||0)-.02;
    const key=[state.snapshot.id,width,height,...g.camera.position.toArray(),...g.camera.quaternion.toArray(),...g.controls.target.toArray(),state.selection.map(s=>s.id).join(','),$('#dimension-display').value,dimensionFeature,state.feature,!!state.placementDraft,$('#show-edge-sizes').checked,$('#show-grid').checked,g.gizmoDragging].join('|');
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
    function dimension(a,b,text,{binding=null,fromA=null,fromB=null,title='Native reference measurement',leader=false,arrows=true}={}){
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
      svg.push(...lines,`<path d="M${a.x},${a.y} L${b.x},${b.y}" fill="none" stroke="${color}" stroke-width="1" ${outside||!arrows?'':'marker-start="url(#dim-arrow)" marker-end="url(#dim-arrow)"'}/>`);
      const description=binding?`Edit ${binding.label} · ${binding.feature_name} · ${text}`:title+' · '+text;
      svg.push(`<g transform="translate(${layout.x},${layout.y}) rotate(${layout.angle})" ${binding?`class="editable-dimension" role="button" tabindex="0" data-dimension="${esc(binding.id)}" aria-label="${esc(description)}"`:''}><title>${esc(description)}</title><rect x="${-textWidth/2}" y="-8" width="${textWidth}" height="17" rx="2" fill="#fff"/><text x="0" y="4" text-anchor="middle" style="fill:${color};stroke-width:0">${esc(text)}</text></g>`);
    }
    const selected=state.selection.at(-1),id=selected?.part_id||selected?.id,mode=$('#dimension-display').value;
    const rows=state.snapshot.body_measurements||[];
    const bodyCorners=row=>row?[...Array(8)].map((_,i)=>project([row.bounds_mm[(i>>0)&1][0],row.bounds_mm[(i>>1)&1][1],row.bounds_mm[(i>>2)&1][2]])):[];
    if(mode!=='off'&&!g.gizmoDragging&&!state.placementDraft){
      const driving=state.snapshot.feature_dimensions||[];
      for(const d of driving){
        const mesh=g.meshes.find(m=>m.userData.id===d.part_id);if(!mesh?.visible||mode==='bounds'||d.part_id!==id||d.feature_id!==dimensionFeature)continue;
        const row=rows.find(row=>row.id===d.part_id),points=bodyCorners(row),text=(d.symbol||'')+format(d.value_mm)+' mm';
        if(d.symbol==='Ø'){
          const centre=d.fromA.map((v,i)=>(v+d.fromB[i])/2),circles=(row?.circles||[]).filter(c=>Math.abs(c.diameter_mm-d.value_mm)<1e-6).sort((a,b)=>Math.hypot(...a.center_mm.map((v,i)=>v-centre[i]))-Math.hypot(...b.center_mm.map((v,i)=>v-centre[i])));
          const start=project(circles[0]?.edge_point_mm||d.fromB),right=Math.max(...points.map(p=>p.x))+26,labelWidth=text.length*6.4+28,side=right+labelWidth<width-15?1:-1,x=side===1?right:Math.min(...points.map(p=>p.x))-26-labelWidth,y=Math.max(85,Math.min(height-85,start.y-24));
          const elbow=side===1?x:x+labelWidth;
          svg.push(`<path d="M${start.x},${start.y} L${elbow},${y}" fill="none" stroke="#245db3" marker-start="url(#dim-arrow)"/>`);
          dimension({x,y,visible:true},{x:x+labelWidth,y,visible:true},text,{binding:d,arrows:false});
        }else{
          const a=project(d.fromA),b=project(d.fromB),outside=outsideDimension(a,b,points.length?points:[a,b]);
          if(outside)dimension(outside.a,outside.b,text,{binding:d,fromA:a,fromB:b});
        }
      }
      for(const row of rows){
        const mesh=g.meshes.find(m=>m.userData.id===row.id);if(!mesh?.visible||row.id!==id||mode!=='bounds')continue;
        const delta=[0,0,0];
        const bounds=row.bounds_mm.map(p=>p.map((v,i)=>v+delta[i]));
        for(const d of envelopeDimensions(bounds)){
          const a=project(d.a),b=project(d.b);if(!a.visible||!b.visible||Math.hypot(a.x-b.x,a.y-b.y)<9)continue;
          const fa=project(d.fromA),fb=project(d.fromB);
          const outside=outsideDimension(fa,fb,bodyCorners(row));
          if(outside)dimension(outside.a,outside.b,format(d.value)+' mm',{fromA:fa,fromB:fb,title:'Global '+d.axis+' envelope · reference only'});
        }

      }
      if($('#show-edge-sizes').checked&&id){
        const edges=(state.snapshot.geometry.edge_meta||[]).filter(e=>e.id===selected?.id&&e.type==='LINE');
        for(const edge of edges.slice(0,64)){
          const delta=[0,0,0];
          dimension(project(edge.start.map((v,i)=>v+delta[i])),project(edge.end.map((v,i)=>v+delta[i])),format(edge.length_mm)+' mm',{title:'Edge length · reference only'});
        }
      }
    }
    $('#model-annotations').setAttribute('viewBox',`0 0 ${width} ${height}`);
    $('#model-annotations').innerHTML='<defs><marker id="dim-arrow" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M6,0 L0,3 L6,6" fill="none" stroke="#5b6b7c"/></marker></defs>'+svg.join('');
    $('#body-measurements').classList.add('hidden');
  }
  function format(value){return Number(value.toFixed(3)).toLocaleString(undefined,{maximumFractionDigits:3});}
  return {sync,update,cancel:restore,selectBody,focusFeature,invalidate:()=>lastKey=''};
}
