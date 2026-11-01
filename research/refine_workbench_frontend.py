"""Exact, checked source edits for the initial compact frontend."""
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'mechanical_workbench/web/app.js'
text=p.read_text(encoding='utf-8')
changes=[
("status('selection-status',row.kind==='observation'?'Virtual failure':row.accepted?'Verified model repair':r.passes_model_screen?'Model screen passed':'Model screen failed',row.kind==='observation'||!r.passes_model_screen?'bad':'good')", "const finalSelected=state.run?.final?.selected_revision===row.id;status('selection-status',row.kind==='observation'?'Virtual failure':finalSelected?(state.run.final.accepted?'Held-out load passed':'Withheld load failed'):row.accepted?'Calibrated model screen passed':r.passes_model_screen?'Model screen passed':'Model screen failed',row.kind==='observation'||!r.passes_model_screen||(finalSelected&&!state.run.final.accepted)?'bad':'good')"),
("state.run=null;$('study-title')", "state.run=null;state.caseIndex=project.reference.cases.reduce((best,c,i,a)=>c.maximum_displacement_mm>a[best].maximum_displacement_mm?i:best,0);$('study-title')"),
("['Physical validation','None']", "['Load-direction displacement envelope',r.directional_envelope?.performed?(r.directional_envelope.passed?'Passed · '+fmt(r.directional_envelope.modulus_uncertainty_bound_mm)+' mm bound':'Failed · '+fmt(r.directional_envelope.modulus_uncertainty_bound_mm)+' mm bound'):'Not available for this load basis'],['Physical validation','None']"),
("['Load cases',project.cases.length]", "['Load cases',project.cases.length],['Direction envelope',project.reference.directional_envelope?.performed?'All same-norm force directions: displacement only':'Explicit cases only']"),
("$('manual-E').value=state.selected.kind==='observation'?'1200':r.design.E_N_mm2", "$('manual-E').value=state.selected.kind==='observation'?'':r.design.E_N_mm2"),
("limit=state.project.requirements.maximum_displacement_mm,maxY=Math.max(reference,observation,selected/.95,limit)*1.18", "limit=state.project.requirements.maximum_displacement_mm,reserve=1-state.project.requirements.material_E_relative_uncertainty,maxY=Math.max(reference,observation,selected/reserve,limit)*1.18"),
("${y(selected/.95)}", "${y(selected/reserve)}"),
("await post('/api/runs',{policy})", "await post('/api/runs',{policy,project_spec:{design:state.project.design,load_cases:state.project.cases,requirements:state.project.requirements}})"),
("{E_N_mm2:Number($('manual-E').value),radius_mm:Number($('manual-radius').value)}", "{E_N_mm2:Number($('manual-E').value),radius_mm:Number($('manual-radius').value),design:state.selected.result.design,load_cases:state.selected.result.load_cases,requirements:state.selected.result.requirements,parent_id:state.selected.id}"),
]
for before,after in changes:
    # Earlier preparatory revisions could duplicate labels whose replacement
    # includes the original anchor. Collapse these exact repeated fields once.
    repeated=None
    if before.startswith("['Load cases'"):repeated=after[len(before)+1:]
    elif before=="['Physical validation','None']":repeated=after[:-(len(before)+1)]
    if repeated:
        while repeated+','+repeated in text:text=text.replace(repeated+','+repeated,repeated)
    if after in text:continue
    if before not in text:
        raise ValueError('Unexpected frontend: '+before)
    if text.count(before)!=1:raise ValueError('Ambiguous source edit')
    text=text.replace(before,after)
p.write_text(text,encoding='utf-8')
print('Checked frontend material assumptions, uncertainty and project context')
