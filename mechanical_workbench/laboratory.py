"""Immutable revisions, charged solver work, virtual tests and held-out audit."""
from copy import deepcopy
import hashlib,json,time
import numpy as np
from .physics import evaluate,grid

class Laboratory:
    def __init__(self,scenario,emit=None,candidate_limit=32,test_limit=3):
        self.scenario=deepcopy(scenario);self.records=[];self.cache={};self.events=[];self.tests=[];self.calibrated_E=None;self.candidate_limit=candidate_limit;self.test_limit=test_limit;self.emit=emit or (lambda event:None)
        self.ledger={'candidate_queries':0,'production_assemblies':0,'independent_assemblies':0,'virtual_test_queries':0,'cache_hits':0,'heldout_assemblies':0}
        self._actual_E=scenario.get('_actual_E_N_mm2',1200.) # Withheld development fixture, not an unseen benchmark.
    def count(self,kind):self.ledger[kind]+=1
    def event(self,kind,title,data):
        event={'index':len(self.events),'kind':kind,'title':title,'data':data,'timestamp_unix':time.time()};self.events.append(event);self.emit(event);return event
    def context(self):
        s=self.scenario
        return {'brief':s['title'],'design':s['design'],'load_cases':s['cases'],'requirements':s['requirements'],'reference_prediction':{k:s['reference'][k] for k in ['maximum_displacement_mm','volume_proxy_mm3','node_count','member_count','free_dofs','directional_envelope'] if k in s['reference']},'new_material_virtual_observation':{k:v for k,v in s['observation'].items() if k!='cases'},'limits':{'candidate_queries':self.candidate_limit,'virtual_tests':self.test_limit,'nodes':90,'members':300},'known_scenario_scope':s['source'],'assumptions':s['reference']['assumptions']}
    def virtual_test(self,kind):
        existing=next((r for r in self.tests if r['test']==kind),None)
        if existing:self.ledger['cache_hits']+=1;return existing
        if self.ledger['virtual_test_queries']>=self.test_limit:raise ValueError('Virtual test budget exhausted')
        self.ledger['virtual_test_queries']+=1
        if kind=='coupon_cantilever':
            length=30.;radius=1.;force=.01;I=np.pi*radius**4/4;deflection=force*length**3/(3*self._actual_E*I);inferred=force*length**3/(3*I*deflection);self.calibrated_E=float(inferred)
            result={'test':kind,'source':'synthetic virtual coupon, closed-form linear cantilever; no hardware','length_mm':length,'radius_mm':radius,'force_N':force,'tip_displacement_mm':deflection,'inferred_E_N_mm2':inferred,'inference':'E=F*L^3/(3*I*delta), I=pi*r^4/4','identifiability_scope':'One elastic modulus in this known ideal law; no joint/material-law mismatch or observation noise.'}
        elif kind=='fixture_motion':result={'test':kind,'source':'synthetic virtual fixture','maximum_clamp_displacement_mm':0.,'scope':'The development fixture has exactly rigid clamps; this does not validate physical clamps.'}
        elif kind=='repeat_assembly':result={'test':kind,'source':'repeat of cached deterministic synthetic observation','load_case_peaks_mm':self.scenario['observation']['load_case_peaks_mm'],'scope':'No new excitation or information in this noiseless linear fixture.'}
        else:raise ValueError('Unknown virtual test')
        self.tests.append(result);self.event('experiment','Virtual test: '+kind,result);return result
    def candidate(self,E,radius,remove_ids=(),add_members=(),parent_id='reference'):
        if parent_id=='reference':design=deepcopy(self.scenario['design'])
        else:design=deepcopy(next(r['design'] for r in self.records if r['id']==parent_id))
        if len(remove_ids)>8 or len(set(remove_ids))!=len(remove_ids) or any(type(i) is not int or not 0<=i<len(design['edges']) for i in remove_ids):raise ValueError('At most eight distinct valid member IDs may be removed')
        if len(add_members)>8:raise ValueError('At most eight members added per revision')
        design['edges']=[e for i,e in enumerate(design['edges']) if i not in remove_ids]+[list(e) for e in add_members];design['radii_mm']=[float(radius)]*len(design['edges']);design['E_N_mm2']=float(E);design['label']='Revision of '+parent_id
        return design
    def evaluate_design(self,design,parent_id='reference'):
        # Labels do not change the physical cache key.
        key=json.dumps({k:v for k,v in design.items() if k!='label'},sort_keys=True)
        if key in self.cache:
            self.ledger['cache_hits']+=1;old=self.cache[key]
            consistent=bool(self.calibrated_E is not None and abs(design['E_N_mm2']/self.calibrated_E-1)<.02)
            if old.get('valid') and consistent!=old['calibration_consistent']:
                # Keep earlier belief-state immutable; reuse the numerical result.
                revised=deepcopy(old);revised.update(id=f'v{len(self.records)+1:03d}',parent_id=old['id'],physics_reused_from=old['id'],calibration_consistent=consistent,accepted=bool(consistent and old['result']['passes_model_screen'] and old['result']['independent_check']['passed']));self.records.append(revised);self.cache[key]=revised;self.event('verification','Cached physics rechecked after calibration',self.compact(revised));return revised
            return old
        if self.ledger['candidate_queries']>=self.candidate_limit:raise ValueError('Candidate budget exhausted')
        self.ledger['candidate_queries']+=1;record={'id':f'v{len(self.records)+1:03d}','parent_id':parent_id,'design':deepcopy(design),'immutable':True};self.records.append(record);self.cache[key]=record
        try:
            r=evaluate(design,self.scenario['cases'],self.scenario['requirements'],on_assembly=self.count)
            calibration_ok=self.calibrated_E is not None and abs(design['E_N_mm2']/self.calibrated_E-1)<.02
            record.update(valid=True,result=r,calibration_consistent=bool(calibration_ok),accepted=bool(calibration_ok and r['passes_model_screen'] and r['independent_check']['passed']))
        except (ValueError,TypeError,KeyError,np.linalg.LinAlgError) as error:record.update(valid=False,accepted=False,error=str(error))
        self.event('revision','Evaluated '+record['id'],self.compact(record));return record
    def compact(self,r):
        if not r['valid']:return {k:v for k,v in r.items() if k!='design'}
        result=r['result'];return {'id':r['id'],'parent_id':r['parent_id'],'valid':True,'accepted':r['accepted'],'calibration_consistent':r['calibration_consistent'],'E_N_mm2':r['design']['E_N_mm2'],'radius_range_mm':[min(r['design']['radii_mm']),max(r['design']['radii_mm'])],'members':result['member_count'],'maximum_displacement_mm':result['maximum_displacement_mm'],'modulus_uncertainty_displacement_bound_mm':max(c['modulus_uncertainty_displacement_bound_mm'] for c in result['cases']),'volume_proxy_mm3':result['volume_proxy_mm3'],'directional_envelope':result.get('directional_envelope'),'independent_check':result['independent_check'],'cases':[{k:c[k] for k in ['id','maximum_displacement_mm','margins','passes_model_screen']} for c in result['cases']]}
    def size(self,parent_id='reference',maximum_evaluations=12):
        if self.calibrated_E is None:raise ValueError('Material is uncalibrated. Run an informative test before sizing a repair.')
        if type(maximum_evaluations) is not int or not 2<=maximum_evaluations<=16:raise ValueError('Sizing budget must be 2–16 candidate evaluations')
        base=self.candidate(self.calibrated_E,.45,parent_id=parent_id);nodes=np.array(base['nodes_mm']);upper=min(.8,min(.05*np.linalg.norm(nodes[b]-nodes[a]) for a,b in base['edges']));lower=.15;used=0;trace=[]
        def trial(radius):
            nonlocal used
            if self.ledger['candidate_queries']>=self.candidate_limit:return None
            d=deepcopy(base);d['radii_mm']=[float(radius)]*len(d['edges']);r=self.evaluate_design(d,parent_id);used+=1;trace.append(self.compact(r));return r
        high=trial(upper)
        if high is None or not high['accepted']:return {'sizing':'no accepted upper bracket','trace':trace,'best':None}
        low=trial(lower);best=high
        if low and low['accepted']:best=low
        else:
            while used<maximum_evaluations:
                radius=(lower+upper)/2;r=trial(radius)
                if r is None:break
                if r['accepted']:best=r;upper=radius
                else:lower=radius
        result={'best':self.compact(best),'trace':trace,'candidate_evaluations_requested':maximum_evaluations,'candidate_queries_charged_so_far':self.ledger['candidate_queries'],'scope':'Shared deterministic uniform-radius bracket search. Every new candidate is charged. No global topology/shape optimum or mathematical monotonicity certificate.'}
        self.event('optimizer','Shared numerical sizing completed',{'best':result['best'],'evaluations':len(trace)});return result
    @property
    def best(self):return min((r for r in self.records if r['accepted']),key=lambda r:r['result']['volume_proxy_mm3'],default=None)
    def finish(self):
        best=self.best
        if best is None:return {'accepted':False,'reason':'No independently checked, calibration-consistent repair','ledger':self.ledger}
        case=deepcopy(self.scenario['cases'][0]);force=np.linalg.norm(case['loads'][0]['force_N']);direction=np.array([.25,.60,-.76]);direction/=np.linalg.norm(direction);case['id']='withheld_oblique';case['loads'][0]['force_N']=(force*direction).tolist()
        check=evaluate(best['design'],[case],self.scenario['requirements'],on_assembly=self.count);self.ledger['heldout_assemblies']+=1
        accepted=bool(best['accepted'] and check['passes_model_screen'] and check['independent_check']['passed']);result={'accepted':accepted,'selected_revision':best['id'],'selected':self.compact(best),'heldout_result':check,'ledger':deepcopy(self.ledger),'physical_validation':False,'efficacy_claim':'None: one intentionally constructed known-law development scenario, not a fair multi-task benchmark.'}
        self.event('verification','Withheld load-case audit',{'accepted':accepted,'maximum_displacement_mm':check['maximum_displacement_mm'],'independent_check':check['independent_check']});return result
