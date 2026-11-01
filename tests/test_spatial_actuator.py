"""Spatial mechanics and loaded-transmission acceptance regressions."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from spatial_actuator.mechanics import solve
from spatial_actuator.oracle import solve as oracle
from spatial_actuator.verification import verify
from spatial_actuator.design import geometry,catalogue,task,compute,validate,segment_distance
from spatial_actuator.laboratory import Lab,Exhausted
from spatial_actuator.agent import handle


class SpatialActuatorTests(unittest.TestCase):
    def test_analytical_and_independent_mechanics_gate(self):
        result=verify();self.assertTrue(result['passed'],result)

    def test_initial_member_envelopes_reject_crossing(self):
        nodes,edges=geometry();ids=sorted([edges.index((0,4)),edges.index((1,4)),edges.index((4,9)),edges.index((5,8)),edges.index((6,7))])
        with self.assertRaisesRegex(ValueError,'collide'):validate(task(),ids,[.8]*len(ids))

    def test_3d_segment_distance_skew_endpoint_and_parallel(self):
        self.assertAlmostEqual(segment_distance(np.array([0,0,0]),np.array([2,0,0]),np.array([1,-1,3]),np.array([1,1,3])),3.)
        self.assertAlmostEqual(segment_distance(np.array([0,0,0]),np.array([2,0,0]),np.array([0,2,0]),np.array([2,2,0])),2.)
        self.assertAlmostEqual(segment_distance(np.array([0,0,0]),np.array([1,0,0]),np.array([2,0,0]),np.array([3,0,0])),1.,places=5)

    def test_passivity_and_negative_stroke_does_not_pass(self):
        t=task();ids=catalogue()['anchor_pair_0_1'];result=compute(t,ids,[.5]*len(ids));m=result['metrics']
        self.assertLess(m['loaded_stroke_mm'],0);self.assertFalse(result['feasible'])
        self.assertAlmostEqual(m['beam_energy_N_mm']+m['output_spring_energy_N_mm'],m['input_ramp_work_N_mm'],places=14)
        self.assertGreaterEqual(m['spring_energy_fraction'],0);self.assertLessEqual(m['spring_energy_fraction'],1)

    def test_no_input_force_no_output_energy(self):
        t=dict(task(),input_force_N=0.);ids=catalogue()['fork_2_3'];result=compute(t,ids,[.4]*len(ids))
        self.assertEqual(result['metrics']['loaded_stroke_mm'],0);self.assertEqual(result['metrics']['output_spring_energy_N_mm'],0);self.assertFalse(result['feasible'])

    def test_unloaded_stroke_is_not_loaded_stroke(self):
        ids=catalogue()['fork_2_3'];rr=[.4]*len(ids);t=task()
        unloaded=compute(dict(t,output_spring_N_mm=0.),ids,rr)['metrics'];loaded=compute(t,ids,rr)['metrics']
        self.assertGreater(unloaded['loaded_stroke_mm'],loaded['loaded_stroke_mm']);self.assertEqual(unloaded['output_force_N'],0)
        self.assertGreater(loaded['output_force_N'],0)

    def test_full_material_and_spring_stiffness_scaling(self):
        t=task();ids=catalogue()['fork_2_3'];radii=[.4]*len(ids);first=compute(t,ids,radii)
        changed=compute(dict(t,E_N_mm2=t['E_N_mm2']*2,output_spring_N_mm=t['output_spring_N_mm']*2),ids,radii)
        self.assertTrue(np.allclose(changed['solved']['u'],first['solved']['u']/2,rtol=1e-10,atol=1e-12))

    def test_cache_invalid_and_optimizer_work_share_one_budget(self):
        ids=catalogue()['fork_2_3'];lab=Lab(task(),budget=5);first=lab.evaluate(ids,[.4]*len(ids));self.assertIs(first,lab.evaluate(ids,[.4]*len(ids)))
        self.assertEqual(lab.assemblies,1);result=lab.optimize(allocation=4,start_id=first['id']);self.assertLessEqual(result['charged_candidates'],4)
        self.assertEqual(len(lab.records),5)
        with self.assertRaises(Exhausted):lab.evaluate(ids,[.45]*len(ids))

    def test_optimizer_permutation_preserves_radius_mapping(self):
        ids=catalogue()['fork_2_3'];radii=np.linspace(.36,.5,len(ids));a=Lab(task(),48);b=Lab(task(),48)
        ra=a.evaluate(ids,radii);rb=b.evaluate(ids[::-1],radii[::-1]);self.assertEqual(ra['metrics'],rb['metrics'])
        a.optimize(allocation=30,start_id=ra['id']);b.optimize(allocation=30,start_id=rb['id']);self.assertEqual(a.best,b.best)

    def test_oracle_rejects_corrupt_saved_metric(self):
        ids=catalogue()['fork_2_3'];lab=Lab(task());r=lab.evaluate(ids,[.4]*len(ids));self.assertTrue(lab.verify()['passed'])
        r['metrics']['loaded_stroke_mm']+=.01;self.assertFalse(lab.verify()['passed'])

    def test_unsupported_component_and_bad_load_rejected(self):
        nodes=[[0,0,0],[20,0,0],[0,10,0],[20,10,0]];F=np.zeros(24)
        with self.assertRaisesRegex(ValueError,'Unsupported'):solve(nodes,[(0,1),(2,3)],[.4,.4],[0],F)
        F[18]=1
        with self.assertRaisesRegex(ValueError,'inactive'):solve(nodes,[(0,1)],[.4],[0],F)

    def test_model_tool_rejects_unknown_and_ambiguous_arguments(self):
        lab=Lab(task())
        with self.assertRaisesRegex(ValueError,'Unknown'):handle(lab,'execute_code',{},None)
        with self.assertRaisesRegex(ValueError,'Unexpected'):handle(lab,'evaluate',{'edge_ids':[],'radii_mm':[],'python':'x'},None)
        with self.assertRaisesRegex(ValueError,'exactly one'):handle(lab,'optimize',{'template':'fork_2_3','edge_ids':[0],'allocation':10},None)

    def test_valid_loaded_design_can_be_found_with_shared_optimizer(self):
        lab=Lab(task(),64);result=lab.optimize(template='fork_2_3',allocation=64,start_fraction=.25)
        self.assertTrue(lab.best['feasible'],result);self.assertTrue(lab.verify()['passed'])

    def test_inspection_reuses_solution_without_unmetered_assembly(self):
        lab=Lab(task());ids=catalogue()['fork_2_3'];lab.evaluate(ids,[.4]*len(ids));before=lab.assemblies
        with tempfile.TemporaryDirectory() as folder,patch('spatial_actuator.figures.compute',side_effect=AssertionError('Unexpected rendering physics solve')):
            result,image=handle(lab,'inspect',{},Path(folder))
            self.assertTrue(image.startswith('data:image/png;base64,'));self.assertEqual(lab.assemblies,before)


if __name__=='__main__':unittest.main()
