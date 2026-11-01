"""Small checked corrections for saved-run and arbitrary-import UI semantics."""
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'mechanical_workbench/web/app.js';text=p.read_text(encoding='utf-8')
edits=[
("state.run=null;state.caseIndex", "state.run=null;status('run-status','Idle');$('budget').textContent='';$('export-study').hidden=true;$('run-history').value='';$('timeline').replaceChildren();state.caseIndex"),
("function renderRun(run){state.run=run;", "function renderRun(run){state.run=run;$('run-history').value=run.id;"),
("subtitle:'Virtual test · original design fails'", "subtitle:project.observation.requirement_passed?'Virtual test · original design passes':'Virtual test · original design fails'"),
("row.kind==='observation'?'Virtual failure':finalSelected", "row.kind==='observation'?(r.passes_model_screen?'Virtual screen passed':'Virtual failure'):finalSelected"),
("row.kind==='observation'||!r.passes_model_screen||(finalSelected&&!state.run.final.accepted)?'bad':'good'", "!r.passes_model_screen||(finalSelected&&!state.run.final.accepted)?'bad':'good'"),
("parent_id:state.selected.id", "parent_id:(state.run?.id||'project')+':'+state.selected.id"),
("if(state.run?.external_audit)lines.push(", "if(state.run?.final?.selected_revision===state.selected.id&&state.run.final.heldout_result)lines.push(['Withheld oblique displacement',fmt(state.run.final.heldout_result.maximum_displacement_mm)+' mm / '+r.requirements.maximum_displacement_mm+' mm limit']);if(state.run?.external_audit)lines.push("),
]
for before,after in edits:
    if after in text:continue
    if text.count(before)!=1:raise ValueError('Unexpected UI source for '+before)
    text=text.replace(before,after)
p.write_text(text,encoding='utf-8');print('Saved-run and import evidence labels checked')
