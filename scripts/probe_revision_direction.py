"""Small synthetic capability probe for the proposed pivot; not a benchmark or CAD product."""
import json, math, os, sys
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from api_preflight import load_env, request


class Revision(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    case_id: str
    action: Literal['propose','needs_input']
    material_family: str | None
    thickness_mm: float | None=Field(ge=0,default=None)
    outer_width_mm: float | None=Field(ge=0,default=None)
    questions: list[str]
    evidence_quotes: list[str]


class Batch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revisions: list[Revision]


CASES=[
 {'id':'A','request':'The customer wants plastic instead of steel due to budget. Keep the current outside size and usable opening. No grade, stock thickness or prices were provided.'},
 {'id':'B','request':'The designer has approved synthetic fixture material Polymer-X sheet at 6 mm thickness. Replace the steel panels. Outside width must stay 600 mm; clear opening must remain at least 594 mm. Propose the change so the geometry checker can inspect it.'},
 {'id':'C','request':'Designer-approved Polymer-X sheet is 6 mm thick. The customer explicitly allows outside width to become 606 mm, with the clear opening still at least 594 mm. Update the panel material, thickness and outside width.'},
 {'id':'D','request':'Use designer-approved Polymer-X stock, thickness 0.23622047244 inches. The customer explicitly permits 606 mm outside width. Keep clear opening at least 594 mm. Work in millimeters.'},
 {'id':'E','request':'Please make it cheaper somehow. Keep every current dimensional requirement. There are no supplier quotes, material grades, stock thickness options or process costs available.'},
]


def check_geometry(thickness, width, minimum_opening=594):
    # Independent of the model: two parallel panels inset within a fixed envelope.
    opening=width-2*thickness
    return {'opening_mm':opening,'minimum_opening_mm':minimum_opening,
            'passed':opening>=minimum_opening-1e-8,
            'required_outer_width_mm':minimum_opening+2*thickness,
            'scope':'nominal geometry only; material suitability, joints and price unverified'}


def main():
    load_env();key=os.environ.get('BASETEN_API_KEY')
    if not key:raise SystemExit('BASETEN_API_KEY not configured')
    fixture={'kind':'synthetic non-load-bearing display cladding; no real customer data',
             'baseline':{'material_family':'steel','thickness_mm':1.2,'outer_width_mm':600,'minimum_clear_opening_mm':594},
             'geometry':'Two parallel side panels inset in the outside width; opening = outside width - 2*thickness.',
             'cases':CASES}
    payload={'model':'meta-models/muse-spark-open-1026','temperature':.2,'max_tokens':12000,
      'reasoning_effort':'medium','tool_choice':'auto','messages':[
        {'role':'system','content':'Convert each isolated client revision into a proposed typed edit. Each case starts from the SAME baseline, not the previous case. Use propose only when requested edits are specified enough; otherwise needs_input with precise questions. Copy only specified changes; null means unchanged/unspecified. Convert explicit units to mm. Do not invent a grade, stock thickness, cost saving or strength. Preserve the explicit opening requirement. A fully specified but geometrically conflicting change may still be proposed; deterministic checks, not you, decide acceptance. Quote exact source phrases supporting each proposal. Return exactly one propose_revisions tool call for all cases. Do not generate CAD code or certify manufacturing.'},
        {'role':'user','content':json.dumps(fixture)}],
      'tools':[{'type':'function','function':{'name':'propose_revisions','description':'Extract evidence-linked material revision proposals. Geometry validation is external.','parameters':Batch.model_json_schema()}}]}
    transport,response=request('https://inference.baseten.co/v1',key,'/chat/completions',payload,timeout=180)
    out=ROOT/'research';out.mkdir(exist_ok=True)
    report={'purpose':'five synthetic cases in ONE request; feasibility probe, not independent product validation or a comparative benchmark',
            'input':fixture,'transport':transport,'model':payload['model'],'model_calls':1,'physical_validation':'not performed'}
    if response:
        report.update(response_id=response.get('id'),response_model=response.get('model'))
        calls=response['choices'][0]['message'].get('tool_calls',[])
        if len(calls)!=1 or calls[0]['function']['name']!='propose_revisions':raise RuntimeError('Expected one structured proposal batch')
        batch=Batch.model_validate_json(calls[0]['function']['arguments'])
        decisions={r.case_id:r for r in batch.revisions}
        if set(decisions)!=set(c['id'] for c in CASES) or len(batch.revisions)!=5:raise RuntimeError('Incorrect case coverage')
        results=[]
        for case in CASES:
            r=decisions[case['id']];item={'proposal':r.model_dump()}
            item['quotes_are_source_substrings']=all(q in case['request'] for q in r.evidence_quotes)
            if r.action=='propose':
                t=r.thickness_mm if r.thickness_mm is not None else 1.2
                w=r.outer_width_mm if r.outer_width_mm is not None else 600
                item['nominal_geometry']=check_geometry(t,w)
            results.append(item)
        report['results']=results
        report['observed_checks']={
            'A_requests_missing_inputs':decisions['A'].action=='needs_input' and decisions['A'].thickness_mm is None,
            'B_specified_change_rejected_by_geometry':decisions['B'].action=='propose' and decisions['B'].thickness_mm==6 and (decisions['B'].outer_width_mm in (None,600)) and not check_geometry(6,600)['passed'],
            'C_authorized_change_geometry_passes':decisions['C'].action=='propose' and decisions['C'].thickness_mm==6 and decisions['C'].outer_width_mm==606 and check_geometry(6,606)['passed'],
            'D_explicit_units_converted':decisions['D'].action=='propose' and decisions['D'].thickness_mm is not None and math.isclose(decisions['D'].thickness_mm,6,abs_tol=1e-7) and decisions['D'].outer_width_mm==606,
            'E_no_fabricated_cost_optimization':decisions['E'].action=='needs_input' and decisions['E'].thickness_mm is None,
            'all_evidence_quotes_literal':all(i['quotes_are_source_substrings'] for i in results)}
        report['review_findings']=[{
            'case_id':'A','kind':'possible_intent_loss_despite_structural_checks',
            'detail':'The existing opening is 597.6 mm, whereas the original minimum is 594 mm. The request says keep the current usable opening. The model correctly requests input but its question restates only the old minimum. A production contract must distinguish preserving current geometry from satisfying a minimum and ask when ambiguous. Literal evidence quotes alone do not prove semantic correctness.'},
            {'case_id':'C/D','kind':'nominal_only',
             'detail':'606 - 2*6 = 594 has zero nominal margin. No manufacturing tolerances, attachment design or material suitability were supplied. Nominal geometry passing cannot authorize manufacturing.'}]
    path=out/'revision-direction-probe.json';path.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'report':str(path),'transport_status':transport.get('status'),'observed_checks':report.get('observed_checks')},indent=2))
    return 0 if response and all(report['observed_checks'].values()) else 1


if __name__=='__main__':raise SystemExit(main())
