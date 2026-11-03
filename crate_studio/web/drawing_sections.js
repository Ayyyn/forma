export function drawingSections({$,esc,state,api,toast,clone,commitDocument,renderDrawing}) {
  let selected=-1,editing=null,baseId=null,lastKey=null,lastSvg=null,ticket=0;
  const specs=()=>state.document?.metadata?.drawing_sections||[];
  function render() {
    const rows=specs();if(selected>=rows.length)selected=-1;
    $('#drawing-page').innerHTML='<option value="-1">Overview</option>'+rows.map((row,i)=>`<option value="${i}">Section ${String.fromCharCode(65+i)}-${String.fromCharCode(65+i)} · ${esc(row.name)}</option>`).join('');
    $('#drawing-page').value=String(selected);
    $('#edit-section').textContent=selected<0?'Section…':'Edit section…';
    $('#add-annotation').disabled=selected>=0;
    if(selected<0)return false;
    const key=JSON.stringify([state.snapshot?.id,state.document.features,rows,selected]);
    if(key===lastKey){if(lastSvg)$('#drawing-sheet').innerHTML=lastSvg;return true;}
    lastKey=key;lastSvg=null;const current=++ticket;
    $('#drawing-sheet').textContent='Computing native section…';
    api('/drawing/section',{document:state.document,section_index:selected,revision_id:state.snapshot?.id}).then(result=>{
      if(current!==ticket||selected<0)return;
      lastSvg=result.svg;$('#drawing-sheet').innerHTML=result.svg;
    }).catch(error=>{if(current!==ticket)return;$('#drawing-sheet').textContent=error.message;toast(error.message,true);});
    return true;
  }
  function open(){
    if(state.busy||state.inspectorDirty||state.agentPreview){toast('Save or discard pending edits before editing section planes.',true);return;}
    const parts=state.snapshot?.geometry?.parts||[];
    if(!parts.length){toast('Create valid solid geometry first.',true);return;}
    editing=selected>=0?selected:null;baseId=state.snapshot.id;
    if(editing===null&&specs().length>=6){toast('This drawing supports up to six section planes.',true);return;}
    const row=editing===null?{name:`Section ${specs().length+1}`,axis:'Z',offset_mm:(state.snapshot.metrics.bounds_mm[0][2]+state.snapshot.metrics.bounds_mm[1][2])/2}:specs()[editing];
    $('#section-name').value=row.name;$('#section-axis').value=row.axis;$('#section-offset').value=row.offset_mm;
    $('#section-body').innerHTML='<option value="">All bodies</option>'+parts.map(p=>`<option value="${esc(p.id)}">${esc(p.id)} · ${esc(p.name)}</option>`).join('')+(row.part_ids?.length>1?'<option value="__multi">Existing selected body set</option>':'');
    $('#section-body').value=row.part_ids?.length===1?row.part_ids[0]:row.part_ids?.length>1?'__multi':'';
    $('#section-remove').hidden=editing===null;
    $('#section-save').textContent=editing===null?'Add section':'Update section';
    $('#section-dialog').showModal();
  }
  $('#drawing-page').onchange=event=>{selected=Number(event.target.value);++ticket;lastKey=null;renderDrawing();};
  $('#section-form').onsubmit=event=>event.preventDefault();
  $('#edit-section').onclick=open;
  $('#section-close').onclick=()=>$('#section-dialog').close();
  $('#section-save').onclick=async()=>{
    if(state.busy)return;
    if(baseId!==state.snapshot.id){toast('The design changed. Reopen the section editor.',true);return;}
    if(!$('#section-form').reportValidity())return;
    const body=$('#section-body').value;
    const row={name:$('#section-name').value.trim(),axis:$('#section-axis').value,offset_mm:Number($('#section-offset').value),part_ids:body==='__multi'?specs()[editing].part_ids:body?[body]:null};
    const doc=clone(state.document);doc.metadata ||= {};const rows=doc.metadata.drawing_sections ||= [];
    const index=editing===null?rows.length:editing;if(editing===null)rows.push(row);else rows[index]=row;
    $('#section-save').disabled=true;
    try {
      await api('/drawing/section',{document:doc,section_index:index});
      if(baseId!==state.snapshot.id)throw new Error('Design changed during section validation. Reopen the editor.');
      state.document=doc;selected=index;lastKey=null;
      if(await commitDocument(editing===null?'Add native section':'Edit native section'))$('#section-dialog').close();
    }catch(error){toast(error.message,true);}finally{$('#section-save').disabled=false;}
  };
  $('#section-remove').onclick=async()=>{
    if(state.busy||editing===null||baseId!==state.snapshot.id)return;
    state.document.metadata.drawing_sections.splice(editing,1);selected=-1;lastKey=null;
    if(await commitDocument('Remove section plane'))$('#section-dialog').close();
  };
  return {render,active:()=>selected>=0};
}
