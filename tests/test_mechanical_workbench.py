import json,unittest
from copy import deepcopy
import numpy as np
from mechanical_workbench.physics import evaluate,grid,segment_gap,validate,development_scenario
from mechanical_workbench.laboratory import Laboratory
from mechanical_workbench.agent import dispatch

REQ={'maximum_displacement_mm':.12,'maximum_nominal_normal_strain':.005,'maximum_nominal_shear_strain':.005,'maximum_section_rotation_rad':.03,'maximum_pinned_euler_ratio':.2,'material_E_relative_uncertainty':.05}
def small():
    d={'nodes_mm':[[0,0,0],[30,0,0]],'edges':[[0,1]],'radii_mm':[.6],'clamped_nodes':[0],'E_N_mm2':2000.,'nu':.3,'label':'reference cantilever'};cases=[{'id':'tip','loads':[{'node':1,'force_N':[0,0,.001]}]}]
    return {'title':'test fixture','design':d,'cases':cases,'requirements':deepcopy(REQ),'reference':evaluate(d,cases,REQ),'observation':{'source':'synthetic','load_case_peaks_mm':{}},'source':'test only'}

class WorkbenchPhysicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.scenario=development_scenario()
    def test_complex_graph_and_independent_multi_load_agreement(self):
        r=self.scenario['reference'];self.assertEqual((r['node_count'],r['member_count'],r['free_dofs']),(45,112,216));self.assertEqual(len(r['cases']),3);self.assertTrue(r['independent_check']['passed']);self.assertTrue(all(c['passes_model_screen'] for c in r['cases']));self.assertFalse(r['directional_envelope']['passed']);self.assertFalse(r['passes_model_screen']);self.assertFalse(self.scenario['observation']['requirement_passed'])
    def test_analytical_cantilever_is_preserved_by_general_adapter(self):
        s=small();r=s['reference'];I=np.pi*.6**4/4;expected=.001*30**3/(3*2000*I)
        self.assertAlmostEqual(r['cases'][0]['node_translations_mm'][1][2],expected,places=10);self.assertTrue(r['independent_check']['passed'])
    def test_uncertainty_scaling_matches_explicit_low_modulus_solve(self):
        s=small();d=deepcopy(s['design']);d['E_N_mm2']*=.95;requirements=deepcopy(REQ);requirements['material_E_relative_uncertainty']=0.;low=evaluate(d,s['cases'],requirements)
        self.assertAlmostEqual(low['maximum_displacement_mm'],s['reference']['cases'][0]['modulus_uncertainty_displacement_bound_mm'],places=10)
    def test_unjoined_crossing_members_are_rejected(self):
        d=small()['design'];d.update(nodes_mm=[[-10,0,0],[10,0,0],[0,-10,0],[0,10,0]],edges=[[0,1],[2,3]],radii_mm=[.2,.2],clamped_nodes=[0,2])
        with self.assertRaisesRegex(ValueError,'collision'):validate(d)
    def test_segment_distance_handles_skew_parallel_and_crossing(self):
        a=np.array([0.,0,0]);b=np.array([2.,0,0]);self.assertAlmostEqual(segment_gap(a,b,np.array([0.,1,0]),np.array([2.,1,0])),1.)
        self.assertAlmostEqual(segment_gap(a,b,np.array([1.,-1,1]),np.array([1.,1,1])),1.)
        self.assertAlmostEqual(segment_gap(a,b,np.array([1.,-1,0]),np.array([1.,1,0])),0.)
    def test_requirements_and_small_displacement_guards_cannot_silently_vanish(self):
        s=small();bad=dict(REQ);bad.pop('maximum_nominal_normal_strain')
        with self.assertRaises(ValueError):evaluate(s['design'],s['cases'],bad)
        d=deepcopy(s['design']);d['radii_mm']=[4.]
        with self.assertRaisesRegex(ValueError,'diameter'):validate(d)
    def test_more_than_previous_ten_node_catalogue_is_supported(self):
        d,_=grid(6,3,3);self.assertEqual(len(d['nodes_mm']),54);self.assertGreater(len(d['edges']),112)
    def test_direction_envelope_matches_explicit_worst_direction_solve(self):
        s=self.scenario;r=s['reference'];e=r['directional_envelope'];self.assertTrue(e['performed']);direction=np.array(e['critical_force_direction']);case={'id':'svd_worst','loads':[{'node':s['cases'][0]['loads'][0]['node'],'force_N':(direction*e['force_norm_N']).tolist()}]};direct=evaluate(s['design'],[case],s['requirements']);self.assertAlmostEqual(direct['maximum_displacement_mm'],e['maximum_displacement_mm'],places=9)
    def test_direction_envelope_bounds_combined_load_and_exact_E_scaling(self):
        s=self.scenario;e=s['reference']['directional_envelope'];d=deepcopy(s['design']);d['E_N_mm2']*=.95;direction=np.array([.3,.6,-.8]);direction/=np.linalg.norm(direction);case={'id':'mixed','loads':[{'node':s['cases'][0]['loads'][0]['node'],'force_N':(direction*e['force_norm_N']).tolist()}]};r=evaluate(d,[case],s['requirements']);self.assertLessEqual(r['maximum_displacement_mm'],e['modulus_uncertainty_bound_mm']+1e-10)

class WorkbenchInvestigationTests(unittest.TestCase):
    def test_virtual_coupon_has_explicit_source_and_identifies_one_parameter(self):
        lab=Laboratory(small());r=lab.virtual_test('coupon_cantilever');self.assertAlmostEqual(r['inferred_E_N_mm2'],1200.);self.assertIn('synthetic',r['source']);self.assertEqual(lab.ledger['virtual_test_queries'],1);lab.virtual_test('coupon_cantilever');self.assertEqual(lab.ledger['virtual_test_queries'],1)
    def test_assuming_stiffer_material_cannot_manufacture_acceptance(self):
        lab=Laboratory(small());lab.virtual_test('coupon_cantilever');r=lab.evaluate_design(lab.candidate(2000.,.6));self.assertTrue(r['result']['passes_model_screen']);self.assertFalse(r['accepted'])
    def test_revision_preserves_original_and_fixed_requirements(self):
        s=small();before=json.dumps(s,sort_keys=True);lab=Laboratory(s);lab.virtual_test('coupon_cantilever');r=lab.evaluate_design(lab.candidate(1200.,.6));self.assertTrue(r['accepted']);self.assertEqual(json.dumps(s,sort_keys=True),before)
        with self.assertRaises(ValueError):dispatch(lab,'evaluate_revision',{'E_N_mm2':1200,'radius_mm':.6,'maximum_displacement_mm':1000})
    def test_shared_optimizer_and_internal_work_obey_candidate_cap(self):
        lab=Laboratory(small(),candidate_limit=4);lab.virtual_test('coupon_cantilever');r=lab.size(maximum_evaluations=16);self.assertIsNotNone(r['best']);self.assertEqual(lab.ledger['candidate_queries'],4);self.assertEqual(lab.ledger['production_assemblies'],4);self.assertEqual(lab.ledger['independent_assemblies'],4)
    def test_calibration_updates_evidence_without_mutating_old_revision(self):
        lab=Laboratory(small());d=lab.candidate(1200.,.6);old=lab.evaluate_design(d);self.assertFalse(old['accepted']);lab.virtual_test('coupon_cantilever');new=lab.evaluate_design(d);self.assertTrue(new['accepted']);self.assertFalse(old['accepted']);self.assertNotEqual(new['id'],old['id']);self.assertEqual(lab.ledger['candidate_queries'],1)
    def test_heldout_is_separate_and_explicitly_not_hardware(self):
        lab=Laboratory(small());lab.virtual_test('coupon_cantilever');lab.evaluate_design(lab.candidate(1200.,.6));r=lab.finish();self.assertTrue(r['accepted']);self.assertEqual(r['heldout_result']['cases'][0]['id'],'withheld_oblique');self.assertEqual(lab.ledger['heldout_assemblies'],1);self.assertFalse(r['physical_validation'])

if __name__=='__main__':unittest.main()

class WorkbenchAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from mechanical_workbench.server import app
        cls.client=TestClient(app)
    def test_ui_and_pinned_renderer_are_served_without_credentials(self):
        self.assertEqual(self.client.get('/').status_code,200);self.assertEqual(self.client.get('/assets/vendor/THREE-LICENSE.txt').status_code,200);self.assertEqual(self.client.get('/.env').status_code,404)
    def test_unknown_run_and_path_traversal_cannot_export_private_files(self):
        self.assertEqual(self.client.get('/api/runs/no-such-run/export').status_code,404);self.assertEqual(self.client.get('/assets/../../.env').status_code,404)
    def test_unrequested_model_parameters_and_relaxed_limits_are_rejected(self):
        self.assertEqual(self.client.post('/api/runs',json={'policy':'meta','relax_requirements':True}).status_code,422);self.assertEqual(self.client.post('/api/explore',json={'E_N_mm2':2000,'radius_mm':10}).status_code,422)
    def test_coverage_distinguishes_nonlinear_and_fabrication_limits(self):
        r=self.client.get('/api/coverage').json();self.assertEqual(r['maximum_nodes'],90);self.assertEqual(r['maximum_members'],300);self.assertEqual(r['nonlinear_target_force_response'],'not integrated');self.assertEqual(r['physical_measurements'],0)
