'use strict';
const $ = id => document.getElementById(id);
const state = {requirements:null, candidates:[], selected:null, inspection:null, frame:0, mode:'3d', yaw:-.55, elevation:.70, zoom:1, playing:false, pareto:[], inspectTicket:0};
const fmt = (n, digits=1) => Number(n).toLocaleString('en', {maximumFractionDigits:digits, minimumFractionDigits:digits});
const escapeHTML = value => String(value).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function status(text, kind=''){ $('status').textContent=text; $('status').className='status '+kind; }
async function api(path, body){
  const response = await fetch(path, body===undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!response.ok){
    const error=await response.json().catch(()=>({detail:response.statusText}));
    throw new Error(Array.isArray(error.detail)?error.detail.map(e=>e.msg).join('; '):error.detail||`HTTP ${response.status}`);
  }
  return response.json();
}
function requirements(){
  return Object.fromEntries(Object.keys(state.requirements).map(k=>[k,Number($(k).value)]));
}
function busy(button, value){ button.disabled=value; }
async function explore(event){
  if(event)event.preventDefault();
  if(!$('requirements-form').reportValidity())return;
  state.requirements=requirements();
  busy($('explore-btn'),true);status('Evaluating both fold families against your constraints…','busy');
  try{
    const result=await api('/api/search',{requirements:state.requirements,count:384,seed:27});
    state.candidates=result.candidates;state.baseline=result.baseline;state.pareto=result.pareto_ids;
    $('search-count').textContent=`${result.evaluated_count} evaluated · ${result.feasible_count} feasible`;
    renderCandidates();renderPareto();
    if(await selectCandidate(state.candidates[0]))status(`${result.feasible_count} of ${result.evaluated_count} candidates meet all constraints. Seed 27 · deterministic search.`);
  }catch(error){status(error.message,'error');}finally{busy($('explore-btn'),false);}
}
async function selectCandidate(candidate){
  if(!candidate)return;
  const ticket=++state.inspectTicket;
  state.playing=false;$('play').textContent='▶';$('play').setAttribute('aria-label','Play folding motion');
  try{
    const inspection=await api('/api/inspect',{design:candidate.design,requirements:state.requirements});
    if(ticket!==state.inspectTicket)return;
    state.inspection=inspection;state.selected=inspection.candidate;state.frame=0;$('fold-slider').value=0;
    renderEvidence();renderCandidates();updateFrame();return true;
  }catch(error){status(error.message,'error');return false;}
}
function renderEvidence(){
  const c=state.selected, d=c.design, m=c.metrics, v=state.inspection.validation;
  $('candidate-title').textContent=d.family==='miura'?'Miura panel':'Accordion panel';
  $('candidate-id').textContent=`PATTERN ${c.id.toUpperCase()} · ${m.facet_count} FACETS`;
  $('feasibility').textContent=c.feasible?'Feasible':'Rejected';$('feasibility').className='pill'+(c.feasible?'':' fail');
  $('model-label').textContent=`${d.family.toUpperCase()} / IDEAL RIGID FOLDING`;
  for(const key of ['columns','rows','a_mm','b_mm','gamma_deg','packed_theta_deg'])$('param-'+key).value=d[key];
  $('coverage').innerHTML=fmt(m.projected_coverage_mm2/100,0)+'<small> cm²</small>';
  $('expansion').innerHTML=fmt(m.footprint_expansion_ratio)+'<small> ×</small>';
  $('creases').textContent=m.crease_segments;
  $('check-count').textContent=`${c.constraints.filter(t=>t.passed).length} / ${c.constraints.length}`;
  $('constraints').innerHTML=c.constraints.map(t=>`<div class="constraint${t.passed?'':' fail'}"><span class="constraint-icon">${t.passed?'✓':'×'}</span><div><span class="constraint-name">${escapeHTML(t.name)}</span><span class="constraint-values">${fmt(t.value,t.unit==='segments'?0:1)} ${escapeHTML(t.comparator)} ${fmt(t.limit,0)} ${escapeHTML(t.unit)}</span></div></div>`).join('');
  $('validation-result').textContent=`${v.passed?'PASS':'FAIL'} · ${v.sample_count} motion samples\nMax distance drift ${v.max_distance_relative_error.toExponential(1)}\nMax planarity error ${v.max_planarity_error_mm.toExponential(1)} mm`;
  $('validation-result').style.whiteSpace='pre-line';
}
function renderCandidates(){
  const gallery=$('candidate-gallery');gallery.replaceChildren();
  const shown=state.candidates.slice(0,8);
  if(state.selected&&!shown.some(c=>c.id===state.selected.id)&&state.selected.id!==state.baseline?.id)shown.unshift(state.selected);
  if(state.baseline&&!shown.some(c=>c.id===state.baseline.id))shown.push(state.baseline);
  for(const candidate of shown){
    const d=candidate.design,m=candidate.metrics, button=document.createElement('button');
    button.className='candidate-card'+(state.selected?.id===candidate.id?' selected':'');
    button.setAttribute('aria-label',`${d.family}, ${m.crease_segments} crease segments, ${candidate.feasible?'feasible':'rejected'}`);
    button.innerHTML=`<span class="card-badge${candidate.feasible?'':' reject'}">${!candidate.feasible?'REJECTED':state.pareto.includes(candidate.id)?'PARETO CANDIDATE':'VERIFIED SELECTION'}</span><canvas aria-hidden="true"></canvas><h4>${d.family==='miura'?'Miura':'Accordion'} / ${d.columns} × ${d.rows}</h4><div class="card-metrics">${m.crease_segments} crease segments<br>${fmt(m.material_area_mm2/100,0)} cm² material</div>`;
    button.addEventListener('click',()=>selectCandidate(candidate));gallery.append(button);
    const preview=candidate.preview||(candidate.id===state.selected?.id?state.inspection?.mesh:null);
    if(preview)drawMesh(button.querySelector('canvas'),preview.vertices,preview.faces,{yaw:-.55,elevation:.70,zoom:1},true);
  }
}
function renderPareto(){
  const svg=$('pareto'), w=600,h=190,pad=42;
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
  const feasible=state.candidates.filter(c=>c.feasible);
  if(!feasible.length){svg.innerHTML='<text x="42" y="80" font-size="12" fill="#8b7767">No feasible candidates in this bounded search.</text>';return;}
  const areas=feasible.map(c=>c.metrics.material_area_mm2/100),folds=feasible.map(c=>c.metrics.crease_segments);
  const amin=Math.min(...areas)-5,amax=Math.max(...areas)+5,fmin=Math.min(...folds)-5,fmax=Math.max(...folds)+5;
  const x=v=>pad+(v-amin)/(amax-amin)*(w-2*pad),y=v=>h-pad-(v-fmin)/(fmax-fmin)*(h-2*pad);
  svg.innerHTML=`<path d="M${pad} 15V${h-pad}H${w-pad}" fill="none" stroke="#c5cdb9"/><text x="${w/2}" y="185" text-anchor="middle" font-size="9" fill="#7a866d">Material area · cm² →</text><text x="4" y="14" font-size="9" fill="#7a866d">Crease segments ↑</text><text x="${pad}" y="${h-pad+15}" font-size="8" fill="#8d967f">${fmt(amin,0)}</text><text x="${w-pad}" y="${h-pad+15}" font-size="8" text-anchor="end" fill="#8d967f">${fmt(amax,0)}</text>`;
  for(const c of feasible){
    const dot=document.createElementNS('http://www.w3.org/2000/svg','circle');
    dot.setAttribute('cx',x(c.metrics.material_area_mm2/100));dot.setAttribute('cy',y(c.metrics.crease_segments));
    dot.setAttribute('r',state.pareto.includes(c.id)?6:4);dot.setAttribute('fill',c.design.family==='miura'?'#879c74':'#b7a383');
    dot.setAttribute('stroke',state.pareto.includes(c.id)?'#485c3b':'transparent');dot.setAttribute('stroke-width','2');dot.setAttribute('tabindex','0');dot.setAttribute('role','button');
    const title=document.createElementNS('http://www.w3.org/2000/svg','title');title.textContent=`${c.design.family}: ${fmt(c.metrics.material_area_mm2/100)} cm², ${c.metrics.crease_segments} crease segments`;dot.append(title);
    dot.setAttribute('aria-label',title.textContent);dot.addEventListener('click',()=>selectCandidate(c));dot.addEventListener('keydown',e=>{if(e.key==='Enter')selectCandidate(c);});svg.append(dot);
  }
}
function updateFrame(){
  if(!state.inspection)return;
  const frame=state.inspection.frames[state.frame], flat=state.mode==='flat';
  const dims=flat?state.selected.metrics.flat:frame.dimensions;
  $('current-dims').textContent=`${fmt(dims.x_mm)} × ${fmt(dims.y_mm)} × ${fmt(dims.z_mm)} mm`;
  $('fold-state').textContent=flat?'Flat fabrication pattern':`Folded ${Math.round(state.frame/80*100)}%`;
  $('angle').textContent=`θ ${fmt(flat?0:frame.theta_deg)}°`;
  const data=flat?state.inspection.flat_mesh:state.inspection.mesh;
  drawMesh($('scene'),flat?data.vertices:frame.vertices,data.faces,state,false,state.selected.metrics.flat);
}
function drawMesh(canvas,vertices,faces,view,mini=false,flatDims=null){
  const rect=canvas.getBoundingClientRect(), ratio=Math.min(window.devicePixelRatio||1,2);
  if(!rect.width||!rect.height)return;
  canvas.width=Math.round(rect.width*ratio);canvas.height=Math.round(rect.height*ratio);
  const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);const w=rect.width,h=rect.height;
  const mins=[0,1,2].map(i=>Math.min(...vertices.map(p=>p[i]))),maxs=[0,1,2].map(i=>Math.max(...vertices.map(p=>p[i])));
  const center=mins.map((v,i)=>(v+maxs[i])/2), ext=maxs.map((v,i)=>v-mins[i]);
  const flat=!mini&&state.mode==='flat';const yaw=flat?0:view.yaw,elev=flat?Math.PI/2:view.elevation;
  const ca=Math.cos(yaw),sa=Math.sin(yaw),ce=Math.cos(elev),se=Math.sin(elev);
  const bound=flatDims?Math.max(flatDims.x_mm,flatDims.y_mm):Math.max(ext[0],ext[1]);
  const scale=Math.min(w/(bound*1.12),h/(bound*.80))*view.zoom*(mini?.85:.89);
  const project=p=>{const x=p[0]-center[0],y=p[1]-center[1],z=p[2]-center[2],rx=x*ca-y*sa,ry=x*sa+y*ca;return [w/2+rx*scale,h*(mini?.48:.47)+(se*ry-ce*z)*scale,-ce*ry+se*z];};
  if(!mini&&!flat){
    ctx.save();ctx.filter='blur(14px)';ctx.fillStyle='#7e8b6a20';ctx.beginPath();
    [[mins[0],mins[1],-4],[maxs[0],mins[1],-4],[maxs[0],maxs[1],-4],[mins[0],maxs[1],-4]].map(project).forEach((p,i)=>i?ctx.lineTo(p[0],p[1]+14):ctx.moveTo(p[0],p[1]+14));ctx.closePath();ctx.fill();ctx.restore();
  }
  const projected=vertices.map(project);
  const ordered=faces.map((face,i)=>({face,i,depth:face.reduce((v,id)=>v+projected[id][2],0)/face.length})).sort((a,b)=>a.depth-b.depth);
  for(const {face,i} of ordered){
    const p=face.map(id=>vertices[id]), u=p[1].map((v,j)=>v-p[0][j]),v=p[3].map((x,j)=>x-p[0][j]);
    const normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],len=Math.hypot(...normal);
    const illumination=(normal[0]*-.4+normal[1]*-.3+normal[2]*.85)/len;
    const light=Math.max(54,Math.min(88,72+illumination*12));
    ctx.beginPath();face.forEach((id,j)=>j?ctx.lineTo(...projected[id].slice(0,2)):ctx.moveTo(...projected[id].slice(0,2)));ctx.closePath();
    ctx.fillStyle=flat?(i%2?'#e0e6d4':'#e9ecdf'):`hsl(${i%2?76:65} 19% ${light+(i%2?0:5)}%)`;ctx.fill();
    ctx.strokeStyle=flat?'#8c9a7b':'#647457';ctx.lineWidth=mini?.45:.65;ctx.stroke();
  }
  if(!mini){
    ctx.font='9px monospace';ctx.fillStyle='#8d987d';
    const corner=project([mins[0],maxs[1],0]);ctx.fillText(flat?'FLAT / mm':'XY / mm',Math.max(15,corner[0]-22),Math.min(h-83,corner[1]+27));
  }
}
async function applyParameters(){
  if(!state.selected)return;
  const design={...state.selected.design};
  for(const key of ['columns','rows','a_mm','b_mm','gamma_deg','packed_theta_deg'])design[key]=Number($('param-'+key).value);
  status('Recomputing the edited mechanism…','busy');
  if(await selectCandidate({design}))status('Edited geometry recomputed and independently checked. Constraints reflect your current brief.');
  else renderEvidence();
}
async function exportDesign(format){
  if(!state.selected)return;
  try{
    const response=await fetch('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({design:state.selected.design,format})});
    if(!response.ok)throw new Error('Export failed. Recompute a valid candidate and try again.');
    const blob=await response.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`continuum-${state.selected.design.family}-${format}.${format==='svg'?'svg':'fold'}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    status('Exported from the selected geometry. Print the SVG at 100%; physical measurements are still pending.');
  }catch(error){status(error.message,'error');}
}
function renderRun(run){
  const target=$('trace');target.replaceChildren();
  const summary=document.createElement('div');summary.className='run-summary';
  const title=document.createElement('strong');title.textContent=run.status==='completed'?'A verified candidate, selected through real tools.':'Experiment incomplete — no verified final selection.';summary.append(title);
  const explanation=document.createElement('p');explanation.textContent=run.rationale||run.error?.message||'No selection returned.';summary.append(explanation);
  const note=document.createElement('small');note.textContent=`${run.model} · ${run.mode==='single_pass'?'single-pass plan · '+run.model_calls+' model request · '+run.evaluations_used+'/64 candidate attempts':run.tool_calls+' feedback tool calls'} · ${fmt(run.latency_ms/1000)} s · saved ${run.run_id}. All dimensions are computed predictions; physical measurements are pending.`;summary.append(note);
  if(run.selected){const choose=document.createElement('button');choose.className='button secondary';choose.textContent='Inspect the verified selection ↗';choose.addEventListener('click',()=>selectCandidate(run.selected));summary.append(choose);}
  target.append(summary);
  for(const event of run.trace){
    const row=document.createElement('div');row.className='trace-event';
    const label=document.createElement('div');label.className='eyebrow';
    const text=document.createElement('p');
    if(event.kind==='model_request'){
      label.textContent=`MODEL TURN ${event.turn}`;
      text.textContent=`${event.model} · HTTP ${event.http_status} · ${fmt(event.latency_ms/1000)} s · ${event.usage?.total_tokens??'unreported'} tokens`;
    }else if(event.kind==='public_model_output'){
      label.textContent='PUBLIC MODEL COMMENTARY / COMPUTED DIMENSIONS';text.textContent=event.text;
    }else if(event.kind==='verification'){
      label.textContent='DETERMINISTIC VERIFICATION';text.textContent=event.text;
    }else{
      label.textContent=`TOOL / ${event.tool}`;
      const r=event.result;
      text.textContent=r.error?`Rejected: ${r.error}`:event.tool==='search_designs'?`${r.evaluated_count} candidates computed; ${r.feasible_count} feasible. Family: ${r.search_space.family}.`:`Candidate ${r.id}: ${r.feasible?'all constraints satisfied':r.violations.map(v=>v.name).join(', ')+' failed'}.`;
      let args;try{args=JSON.parse(event.arguments);}catch{args=event.arguments;}
      const detail=document.createElement('details'),heading=document.createElement('summary'),pre=document.createElement('pre');heading.textContent='Inspect tool arguments and computed results';pre.textContent=JSON.stringify({arguments:args,result:r},null,2);detail.append(heading,pre);row.append(detail);
    }
    row.prepend(label,text);target.append(row);
  }
}
async function runAgent(){
  const button=$('agent-btn');busy(button,true);status('Meta is making one search plan. Numerical selection and verification follow; allow up to a few minutes…','busy');
  try{
    if(!$('requirements-form').reportValidity())return;
    state.requirements=requirements();
    const run=await api('/api/agent',{brief:$('brief').value,requirements:state.requirements,provider:$('provider').value,mode:'single_pass',objective:$('objective').value});
    renderRun(run);
    if(run.selected)await selectCandidate(run.selected);
    status(run.status==='completed'?'Single-pass plan complete. The numerically selected design passed independent geometry checks.':run.error?.message||'The planning request ended without a verified selection.',run.status==='completed'?'':'error');
    $('trace').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'nearest'});
  }catch(error){status(error.message,'error');}finally{busy(button,false);}
}
async function loadLatest(){
  try{const runs=await api('/api/runs');if(!runs.length){status('No saved model run yet. Use Plan & verify to run one.');return;}const run=await api('/api/runs/'+runs[0].run_id);renderRun(run);status('Loaded a recorded real API run; no new model call was made.');}catch(error){status(error.message,'error');}
}
let drag=null;
$('scene').addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY};$('scene').setPointerCapture(e.pointerId);});
$('scene').addEventListener('pointermove',e=>{if(!drag||state.mode==='flat')return;state.yaw+=(e.clientX-drag.x)*.008;state.elevation=Math.max(.12,Math.min(1.5,state.elevation+(e.clientY-drag.y)*.008));drag={x:e.clientX,y:e.clientY};updateFrame();});
for(const type of ['pointerup','pointercancel'])$('scene').addEventListener(type,()=>{drag=null;});
$('scene').addEventListener('wheel',e=>{e.preventDefault();state.zoom=Math.max(.4,Math.min(2.8,state.zoom*Math.exp(-e.deltaY*.001)));updateFrame();},{passive:false});
$('scene').addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-','='].includes(e.key))return;e.preventDefault();if(e.key==='ArrowLeft')state.yaw-=.1;if(e.key==='ArrowRight')state.yaw+=.1;if(e.key==='ArrowUp')state.elevation=Math.min(1.5,state.elevation+.1);if(e.key==='ArrowDown')state.elevation=Math.max(.12,state.elevation-.1);if(e.key==='+'||e.key==='=')state.zoom=Math.min(2.8,state.zoom+.1);if(e.key==='-')state.zoom=Math.max(.4,state.zoom-.1);updateFrame();});
$('requirements-form').addEventListener('submit',explore);
$('baseline-btn').addEventListener('click',()=>selectCandidate(state.baseline));
$('apply-params').addEventListener('click',applyParameters);
$('agent-btn').addEventListener('click',runAgent);$('load-run').addEventListener('click',loadLatest);
$('fold-slider').addEventListener('input',e=>{state.frame=Number(e.target.value);state.playing=false;$('play').textContent='▶';updateFrame();});
$('reset-view').addEventListener('click',()=>{state.yaw=-.55;state.elevation=.70;state.zoom=1;updateFrame();});
for(const [id,mode]of [['view-3d','3d'],['view-flat','flat']])$(id).addEventListener('click',()=>{state.mode=mode;for(const b of ['view-3d','view-flat']){$(b).classList.toggle('selected',b===id);$(b).setAttribute('aria-pressed',String(b===id));}updateFrame();});
$('play').addEventListener('click',()=>{state.playing=!state.playing;$('play').textContent=state.playing?'Ⅱ':'▶';$('play').setAttribute('aria-label',state.playing?'Pause folding motion':'Play folding motion');if(state.playing&&state.frame===80)state.frame=0;});
let last=0;function tick(time){if(state.playing&&time-last>45){state.frame=(state.frame+1)%81;$('fold-slider').value=state.frame;updateFrame();last=time;}requestAnimationFrame(tick);}requestAnimationFrame(tick);
for(const [id,format]of [['export-svg','svg'],['export-fold','fold'],['export-folded','folded']])$(id).addEventListener('click',()=>exportDesign(format));
new ResizeObserver(()=>{updateFrame();renderCandidates();}).observe($('scene'));
async function init(){
  try{
    const [defaults,health]=await Promise.all([api('/api/defaults'),api('/api/health')]);state.requirements=defaults.requirements;
    for(const [key,value]of Object.entries(state.requirements))$(key).value=value;
    for(const option of $('provider').options)option.disabled=!health.providers[option.value];
    if(!health.providers.baseten&&health.providers.meta)$('provider').value='meta';
    if(!health.providers.baseten&&!health.providers.meta){$('agent-btn').disabled=true;$('agent-btn').title='Configure a provider key in the local .env file';}
    await explore();
  }catch(error){status('Unable to connect to the geometry engine: '+error.message,'error');}
}
init();
