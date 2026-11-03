// UI binds through a small host interface; the server owns component generation.
export function componentLibrary({$,esc,state,api,toast,useSnapshot,refreshHistory,renderTree,renderInspector,setBusy,importFile,onMesh}) {
  let rows=[],chosen=null,editing=null,baseId=null;
  function choose(row,record=null) {
    chosen=row;
    $("#component-name").textContent=row.name;
    $("#component-fields").innerHTML=Object.entries(row.parameters).map(([key,spec])=>{
      const value=record?.parameters?.[key]??spec.default;
      return `<label class="field-label">${esc(key[0].toUpperCase()+key.slice(1))}${spec.unit ? ` · ${esc(spec.unit)}` : ""}${spec.type==="choice"?`<select data-component-param="${esc(key)}">${spec.choices.map(v=>`<option ${v===value?"selected":""}>${esc(v)}</option>`).join("")}</select>`:`<input data-component-param="${esc(key)}" type="number" min="${spec.min}" max="${spec.max}" step="any" value="${value}">`}</label>`;
    }).join("");
    const feature=editing?state.document.features.find(f=>f.id===editing):null;
    $("#component-placement").innerHTML=["translation","rotation"].map(key=>`<div class="field-label">${key==="translation"?"Position · mm":"Rotation · deg"}<span class="field-row three">${["X","Y","Z"].map((axis,i)=>`<label>${axis}<input data-component-pose="${key}" data-index="${i}" aria-label="Component ${key} ${axis}" type="number" step="any" value="${feature?.params?.[key]?.[i]??0}"></label>`).join("")}</span></div>`).join("");
    $("#component-scope").textContent=row.scope;
    const source=$("#component-source");source.replaceChildren();
    const link=document.createElement("a");link.href=row.source;link.target="_blank";link.rel="noopener";link.textContent="Source";
    source.append(link,document.createTextNode(` · ${row.license} · ${row.revision.slice(0,10)}`));
    $("#component-insert").disabled=false;
    renderList();
  }
  function renderList() {
    const query=$("#component-search").value.toLowerCase();
    const shown=rows.filter(r=>(!editing||r.id===chosen?.id)&&`${r.name} ${r.category}`.toLowerCase().includes(query));
    $("#component-list").innerHTML=shown.map(row=>`<button class="component-row ${row.id===chosen?.id?"active":""}" data-component-id="${row.id}"><small>${esc(row.category)}</small>${esc(row.name)}</button>`).join("") || '<p class="parameter-note">No matching components</p>';
    $("#component-list").querySelectorAll("button").forEach(button=>button.onclick=()=>choose(rows.find(r=>r.id===button.dataset.componentId)));
  }
  async function open(featureId=null) {
    if(state.busy)return;
    if(state.inspectorDirty || state.agentPreview) {toast("Save or discard the current edits before adding components.",true);return;}
    if(!rows.length)rows=(await api("/components")).components;
    editing=featureId;baseId=state.snapshot.id;chosen=null;
    $("#component-title").textContent=editing?"Edit library component":"Insert component";
    $("#component-insert").textContent=editing?"Update component":"Insert component";
    $("#component-file").hidden=!!editing;
    $("#component-search").value="";
    if(editing){const record=state.document.metadata.component_instances[editing];choose(rows.find(r=>r.id===record.catalog_id),record);}
    else choose(rows[0]);
    $("#component-dialog").showModal();
  }
  $("#component-search").oninput=renderList;
  $("#component-close").onclick=()=>$("#component-dialog").close();
  $("#component-insert").onclick=async()=>{
    if(state.busy||!chosen)return;
    if(baseId!==state.snapshot.id){toast("The design changed. Reopen the component library.",true);return;}
    const parameters={};
    for(const input of $("#component-fields").querySelectorAll("[data-component-param]")) {
      if(!input.reportValidity())return;
      parameters[input.dataset.componentParam]=input.type==="number"?Number(input.value):input.value;
    }
    const pose={translation:[0,0,0],rotation:[0,0,0]};
    for(const input of $("#component-placement").querySelectorAll("input")) {
      if(input.value===""||!input.reportValidity())return;
      pose[input.dataset.componentPose][Number(input.dataset.index)]=Number(input.value);
    }
    setBusy(true);$("#component-insert").disabled=true;
    try {
      const result=await api("/components/insert",{document:state.document,parent_id:baseId,catalog_id:chosen.id,parameters,...pose,feature_id:editing});
      useSnapshot(result);state.feature=result.selected_feature_id;renderTree();renderInspector();await refreshHistory();
      $("#component-dialog").close();toast(editing?"Component updated":"Component inserted · check placement and interference");
    }catch(e){toast(e.message,true);}finally{setBusy(false);$("#component-insert").disabled=false;}
  };
  $("#component-file").onclick=()=>$("#component-file-input").click();
  $("#component-file-input").onchange=event=>{
    const file=event.target.files[0];event.target.value="";
    if(!file)return;
    $("#component-dialog").close();
    if(/\.(stl|obj)$/i.test(file.name))onMesh(file);else importFile(file,undefined,true);
  };
  return open;
}
