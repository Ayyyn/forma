export function viewportInspection({$,get3D,state,invalidate}) {
  let plane=null, last='';
  const style=()=>$('#model-display-style').value;
  function accepts(point){return !plane||plane.distanceToPoint(point)>=-1e-7;}
  function update(force=false) {
    const g=get3D();if(!state.snapshot||!g.renderer)return;
    const selected=new Set(state.selection.map(s=>s.part_id||s.id));
    const key=[state.snapshot.id,style(),[...selected].join(','),$('#section-enabled').checked,$('#section-cut-axis').value,$('#section-position').value,$('#section-flip').checked,$('#show-edges').checked].join('|');
    if(!force&&key===last)return;last=key;
    const {THREE}=g,enabled=$('#section-enabled').checked,axis=$('#section-cut-axis').value,idx={X:0,Y:1,Z:2}[axis],bounds=state.snapshot.metrics.bounds_mm||[[0,0,0],[1,1,1]],fraction=Number($('#section-position').value)/100,offset=bounds[0][idx]+fraction*(bounds[1][idx]-bounds[0][idx]);
    const sign=$('#section-flip').checked?-1:1, normal={X:[1,0,0],Y:[0,0,-1],Z:[0,1,0]}[axis];
    plane=enabled?new THREE.Plane(new THREE.Vector3(...normal).multiplyScalar(sign),-offset*sign):null;
    g.renderer.localClippingEnabled=true;
    $('#section-offset-label').textContent=`${axis} = ${Number(offset.toFixed(3))} mm`;
    $('#section-controls').classList.toggle('hidden',!enabled);
    const mode=style(),isTransparent=id=>mode==='transparent'||mode==='transparent-selected'&&selected.has(id),wire=mode==='wireframe';
    for(const mesh of g.meshes){
      const transparent=isTransparent(mesh.userData.id);
      const m=mesh.material;m.visible=!wire;m.wireframe=false;m.transparent=transparent;m.opacity=transparent ? .22 : 1;m.depthWrite=!transparent;m.side=(transparent||enabled)?THREE.DoubleSide:THREE.FrontSide;m.clippingPlanes=plane?[plane]:[];m.needsUpdate=true;
      for(const edge of [...mesh.children]){
        if(edge.userData.inspectionHidden){mesh.remove(edge);edge.material.dispose();continue;}
        edge.visible=$('#show-edges').checked||wire;
        edge.material.depthTest=!(wire||transparent);edge.material.opacity=wire?1:.65;edge.material.clippingPlanes=plane?[plane]:[];edge.material.needsUpdate=true;
        if(mode==='hidden'){
          const material=new THREE.LineDashedMaterial({color:0x485e78,dashSize:2,gapSize:1.2,transparent:true,opacity:.6,depthFunc:THREE.GreaterDepth,depthWrite:false,clippingPlanes:plane?[plane]:[]});
          const hidden=new THREE.LineSegments(edge.geometry,material);hidden.computeLineDistances();hidden.userData.inspectionHidden=true;hidden.visible=$('#show-edges').checked;hidden.renderOrder=4;mesh.add(hidden);
        }
      }
    }
    for(const face of g.faces){face.material.visible=!wire&&!isTransparent(face.userData.part_id);face.material.clippingPlanes=plane?[plane]:[];face.material.needsUpdate=true;}
    for(const edge of g.pickEdges){edge.material.clippingPlanes=plane?[plane]:[];edge.material.needsUpdate=true;}
    invalidate();
  }
  for(const id of ['model-display-style','section-enabled','section-cut-axis','section-position','section-flip','show-edges'])$('#'+id).addEventListener(id==='section-position'?'input':'change',()=>update(true));
  return {sync:()=>update(true),update,accepts};
}
