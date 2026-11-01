"""Export actual nonlinear/linear study evidence into a standalone inspection board.

No model calls; optional older beam views recompute saved known candidates offline.
"""
import argparse
import json
from pathlib import Path
import sys
import hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def robust_rows():
    path=ROOT/'benchmarks/robust-discovery-v1/summary.json'
    if not path.exists():return []
    import numpy as np
    from nonlinear_discovery.model import mesh,independent_energy
    rows=[];data=json.loads(path.read_text())
    for method,group in data['methods'].items():
        candidate=next((r for r in group['audited'] if r['id']==group['best_accepted_id']),group['audited'][0])
        result=candidate['result'];s=result['summary'];t=result.get('tolerance',{});views=[];profiles=[]
        for setting in ['A','B']:
            for state in result['settings'][setting]['states']:
                views.append({'label':setting+' | '+state['classification']+' | P='+format(state['polarization'],'.2f')+' | '+format(state['energy_N_mm'],'.2f')+' mJ','setting':setting,'state':state,'mesh':mesh(candidate['design'],state)})
            detail=s['details'][setting]
            if detail.get('target_and_counter_found'):
                a,b=np.array(detail['target']['x']),np.array(detail['counter']['x']);points=[]
                for fraction in np.linspace(0,1,61):
                    try:points.append([float(fraction),independent_energy(candidate['design'],a*(1-fraction)+b*fraction,setting)*1500])
                    except (ValueError,FloatingPointError):pass
                profiles.append({'setting':setting,'points':points})
        low=min((v['minimum_sampled_escape_path_height_N_mm'] for v in s['details'].values() if v.get('minimum_sampled_escape_path_height_N_mm') is not None),default=None)
        rows.append({'id':'robust-'+method+'-'+candidate['id'],'family':'robust','method':method,'label':method+' '+candidate['id']+' | '+('screen + 8/8 samples passed' if candidate['accepted'] else 'failed/unresolved'),
                     'accepted':candidate['accepted'],'design':candidate['design'],'views':views,'profiles':profiles,
                     'result':{'worst_bias_N_mm':s['worst_bias_N_mm'],'feasible':candidate['accepted'],'minimum_selected_hessian_eigenvalue':s['min_hessian_eigenvalue'],'maximum_selected_holding_force_N':s['max_axial_force_N']},
                     'robustness':{'passed_trials':t.get('passed_trials',0),'total_trials':t.get('total_trials',0),'minimum_sampled_path_height_N_mm':low},
                     'audit':{'independent_checks':candidate['independent_audit'],'sampled_tolerance_scope':t.get('scope'),'sampled_trials':[{'trial':r['trial'],'passed':r['passed']} for r in t.get('trials',[])],'global_retention':'unresolved; sampled path height is not a certified barrier'},
                     'provenance':'New robustness study | '+method+' | 128 starts/setting plus saddle-directed minimization, independent vertex-energy/Hessian checks and 8 fixed local tolerance samples. No physical validation.'})
    return rows

def attach_exports(rows):
    count=0
    for path in sorted((ROOT/'output/discovery-board/exports').glob('*/manifest.json')):
        manifest=json.loads(path.read_text())
        if not manifest['geometry_checks_passed']:continue
        source=manifest['source'];prefix='robust-' if source['study']=='robust-discovery-v1' else '';candidate=next((r for r in rows if r['id']==prefix+source['method']+'-'+source['candidate']),None)
        if not candidate:continue
        state=manifest['source_state'];view=next((v for v in candidate['views'] if v['setting']==source['setting'] and max(abs(a-b) for a,b in zip(v['state']['x'],state['x']))<1e-6),None)
        if not view:continue
        if manifest['kind']=='single fixed-pose solid display':
            obj=path.parent/manifest['assembly']['files']['obj']['name']
            if hashlib.sha256(obj.read_bytes()).hexdigest()!=manifest['assembly']['files']['obj']['sha256']:raise ValueError('Display OBJ hash mismatch')
            vertices=[];faces=[]
            for line in obj.read_text().splitlines():
                if line.startswith('v '):vertices.append([float(v) for v in line.split()[1:4]])
                elif line.startswith('f '):faces.append([int(v.split('/')[0])-1 for v in line.split()[1:]])
            view['display_mesh']={'vertices_mm':vertices,'triangles':faces,'face_cells':[0]*len(faces)}
            view['display_export']={'formats':{f:'exports/'+path.parent.name+'/'+f+'-bundle.zip' for f in ['step','stl','obj']},'thickness_mm':manifest['panel_thickness_mm'],'bounds_mm':manifest['assembly']['bounds_mm']}
            count+=1;continue
        vertices=[];faces=[];cells=[]
        for part in manifest['parts']:
            obj=path.parent/'parts'/part['files']['obj']['name']
            if hashlib.sha256(obj.read_bytes()).hexdigest()!=part['files']['obj']['sha256']:raise ValueError('Export OBJ hash mismatch')
            offset=len(vertices);translation=part['layout_translation_mm']
            for line in obj.read_text().splitlines():
                if line.startswith('v '):vertices.append([float(v)+translation[i] for i,v in enumerate(line.split()[1:4])])
                elif line.startswith('f '):faces.append([offset+int(v.split('/')[0])-1 for v in line.split()[1:]]);cells.append(part['source_face_index']//12)
        view['print_mesh']={'vertices_mm':vertices,'triangles':faces,'face_cells':cells}
        view['print_export']={'formats':{f:'exports/'+path.parent.name+'/'+f+'-bundle.zip' for f in ['step','stl','obj']},'parts':manifest['parts_count'],'thickness_mm':manifest['panel_thickness_mm'],'scope':manifest['mechanical_status'],'bounds_mm':manifest['assembly']['bounds_mm']};count+=1
    return count


def build(directory,destination):
    data=json.loads((directory/'board-data.json').read_text());rows=[]
    dense_file=ROOT/'research/nonlinear-dense-check.json'
    dense=json.loads(dense_file.read_text())['checks'] if dense_file.exists() else []
    for item in data['candidates']:
        latest=next((c for c in dense if item['id']==c['method']+'-'+c['id']),None)
        if latest:
            from nonlinear_discovery.model import mesh
            item['result']=latest['result'];item['audit']=latest['independent_audit'];item['accepted']=latest['accepted'];item['views']=[]
            for setting in ['A','B']:
                for state in latest['result']['settings'][setting]['states']:item['views'].append({'setting':setting,'state':state,'mesh':mesh(item['design'],state)})
        item['family']='nonlinear';item['label']=item['method']+' '+item['id']+' · '+('accepted' if item['accepted'] else 'unresolved/failed')
        item['provenance']='Nonlinear pilot · '+item['method']+' · '+('256' if latest else '64')+' stationary starts per setting, independent vertex-energy/Hessian audit. Found states are not exhaustive.'
        if item['id']=='meta-n022':item['provenance']+=' Later robustness follow-up failed: 30 Nmm clamp torque; removing common offsets leaves shallow sampled paths and only 2/8 local tolerance samples passing.'
        for i,v in enumerate(item['views']):
            s=v['state'];v['label']=v['setting']+' · '+s['classification']+' · P='+format(s['polarization'],'.2f')+' · '+format(s['energy_N_mm'],'.2f')+' mJ'
        item['result']={k:item['result'][k] for k in ['worst_bias_N_mm','feasible','minimum_selected_hessian_eigenvalue','maximum_selected_holding_force_N']}
        rows.append(item)
    rows.extend(robust_rows())
    previous=ROOT/'benchmarks/spatial-revision-v1';offline_assemblies=0
    if (previous/'summary.json').exists():
        from spatial_revision.problem import compute
        from spatial_actuator.figures import deformed_member
        manifest=json.loads((previous/'manifest.json').read_text());summary=json.loads((previous/'summary.json').read_text())
        for task in manifest['cases']:
            for method in manifest['methods']:
                saved=json.loads((previous/'runs'/task['id']/method/'result.json').read_text());best=saved['state']['best_evaluated']
                if not best:continue
                result=compute(task,best['edge_ids'],best['radii_mm']);offline_assemblies+=1;initial=[];deformed=[]
                for edge,part in zip(result['edges'],result['solved']['parts']):
                    a,b=deformed_member(result['nodes'],edge,part,result['solved']['u'][:,0],60);initial.append(a[[0,-1]].tolist());deformed.append(b[::3].tolist())
                check=next(a for a in summary['audits'] if a['case_id']==task['id'] and a['method']==method)
                rows.append({'id':'linear-'+task['id']+'-'+method,'family':'linear','method':method,'label':task['revision_kind']+' · '+method+' · '+('feasible' if best['feasible'] else 'failed'),
                             'accepted':best['feasible'],'design':{'task':task,'edge_ids':best['edge_ids'],'radii_mm':best['radii_mm']},'metrics':best['metrics'],'margins':best['margins'],'audit':check,
                             'provenance':'Frozen eight-revision study · '+method+' · independently energy-checked; selected result compared with external OpenSees. View recomputation is offline, not search work.',
                             'views':[{'label':'Loaded linear response; deformation ×60','setting':'load','state':{'classification':'linear_loaded_response'},'mesh':{'vertices_mm':result['nodes'].tolist(),'initial_lines':initial,'deformed_lines':deformed}}],'profiles':[]})
    exports=attach_exports(rows)
    # Display coordinates only: source states/designs and CAD files retain full
    # precision. Rounding at 1e-8 mm keeps the offline viewer below its size cap.
    def coordinates(value):
        if isinstance(value,list):return [coordinates(v) for v in value]
        return round(value,8) if isinstance(value,float) else value
    for row in rows:
        for view in row['views']:
            for name in ['mesh','print_mesh','display_mesh']:
                if name not in view:continue
                for field in ['vertices_mm','initial_lines','deformed_lines']:
                    if field in view[name]:view[name][field]=coordinates(view[name][field])
    comparison=''
    report_path=ROOT/'output/robust-discovery/evidence.json'
    if report_path.exists():
        evidence=json.loads(report_path.read_text());comparison='Worst found-state bias: frozen numerical '+format(evidence['frozen_numerical']['bias_N_mm'],'.2f')+' mJ; Meta '+format(evidence['Meta']['bias_N_mm'],'.2f')+' mJ; additional post-hoc numerical pattern search '+format(evidence['posthoc_coordinate']['bias_N_mm'],'.2f')+' mJ. All three passed 8/8 local samples. Single development task: general AI advantage and physical performance remain unproven.'
    payload={'candidates':rows,'viewer_export_offline_frame_assemblies':offline_assemblies,'source':str(directory),'checked_export_configurations':exports,'comparison_note':comparison,'viewer_coordinate_rounding_mm':1e-8,'source_states_designs_and_CAD_files':'full precision'}
    template=(ROOT/'discovery_board/fragment.html').read_text(encoding='utf-8');fragment=template.replace('__DISCOVERY_DATA__',json.dumps(payload,separators=(',',':')).replace('</',r'<\/'))
    library=(ROOT/'discovery_board/vendor/d3.v7.9.0.min.js').read_text(encoding='utf-8');fragment=fragment.replace('__D3_LIBRARY__',library.replace('</script',r'<\/script'))
    if len(fragment.encode())>1000000:raise ValueError('Board exceeds inline size limit')
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(fragment,encoding='utf-8')
    (ROOT/'output/discovery-board').mkdir(parents=True,exist_ok=True)
    (ROOT/'output/discovery-board/export-provenance.json').write_text(json.dumps({'candidates':len(rows),'offline_assemblies':offline_assemblies,'model_calls':0,'source':str(directory),'checked_export_configurations':exports},indent=2))
    print(json.dumps({'fragment':str(destination),'bytes':len(fragment.encode()),'candidates':len(rows),'offline_view_assemblies':offline_assemblies}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=ROOT/'benchmarks/nonlinear-discovery-v1');p.add_argument('--destination',type=Path,required=True);a=p.parse_args();build(a.directory.resolve(),a.destination.resolve())
