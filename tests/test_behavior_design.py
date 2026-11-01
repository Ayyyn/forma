import unittest
from copy import deepcopy
import numpy as np
from behavior_design import linkage
from behavior_design.model import design,predict,evaluate,bounds,ARCHITECTURES,independent_audit
from behavior_design.tasks import tasks,reference,audit_task,TEACHER,WITNESS
from behavior_design.laboratory import Laboratory,BudgetExhausted
from behavior_design.agent import dispatch

class BehaviorPhysicsTests(unittest.TestCase):
    def test_classical_two_spring_double_well(self):
        e,f,k,_=linkage.primitive(20.,20.,1.,0.,np.array([0.,20.,40.]),1,False)
        np.testing.assert_allclose(e,[0.,(20-20*np.sqrt(2))**2,0.],atol=1e-11);np.testing.assert_allclose(f,0.,atol=1e-11)
        self.assertGreater(k[0],0);self.assertLess(k[1],0);self.assertGreater(k[2],0)
    def test_geometry_change_moves_free_equilibrium(self):
        for H in [10.,20.]:
            e,f,k,_=linkage.primitive(20.,H,1.,0.,2*H,1,False);self.assertAlmostEqual(float(f),0.);self.assertGreater(k,0.)
    def test_analytic_force_and_tangent_are_energy_derivatives(self):
        for o in [-1,1]:
            for u in [0.,3.,7.,12.]:
                h=1e-4;E,F,K,_=linkage.primitive(19.,6.,2.8,.015,u,o);plus=linkage.primitive(19.,6.,2.8,.015,u+h,o);minus=linkage.primitive(19.,6.,2.8,.015,u-h,o)
                self.assertAlmostEqual(float((plus[0]-minus[0])/(2*h)),float(F),places=7);self.assertAlmostEqual(float((plus[1]-minus[1])/(2*h)),float(K),places=7)
    def test_convexification_margin_is_exact_global_tangent_floor(self):
        for a,H,k,b in [(12.,6.,3.,.01),(19.,6.,2.8,.015)]:
            self.assertAlmostEqual(float(linkage.primitive(a,H,k,b,H,1)[2]),b,places=12)
            self.assertGreaterEqual(min(linkage.primitive(a,H,k,b,np.linspace(0,20,101),1)[2]),b-1e-12)
    def test_series_equilibrium_force_balance_and_independent_work(self):
        p=predict(TEACHER,np.linspace(0,12,17));self.assertTrue(independent_audit(TEACHER,p)['passed'])
        for q in p:self.assertAlmostEqual(sum(q['stage_travels_mm']),q['travel_mm'],places=9);self.assertLess(q['force_balance_residual_N'],1e-7);self.assertGreater(q['internal_hessian_eigenvalues_N_mm'][0],0.)
    def test_parallel_spring_consolidation_is_algebraically_equivalent(self):
        p=predict(TEACHER,np.linspace(0,12,33));q=predict(WITNESS,np.linspace(0,12,33));np.testing.assert_allclose([v['force_N'] for v in p],[v['force_N'] for v in q],atol=1e-10)
    def test_packaging_revision_rejects_old_geometry_and_accepts_witness(self):
        initial,compact=tasks();self.assertTrue(evaluate(TEACHER,initial)['target_passed']);self.assertTrue(evaluate(WITNESS,compact)['target_passed'])
        with self.assertRaisesRegex(ValueError,'bounds'):evaluate(TEACHER,compact)
    def test_withheld_points_are_disjoint_and_reference_accepted(self):
        t=tasks()[1];ref=reference();self.assertFalse(set(t['fit_travel_mm'])&set(ref['heldout_travel_mm']));self.assertTrue(evaluate(WITNESS,audit_task(t,ref))['target_passed'])
    def test_kresling_torque_stationary_and_independent_vertex_agreement(self):
        d=design('kresling_parallel_1',[22.,1.3,.3,.4]);p=predict(d,[0.,2.,5.],True);self.assertTrue(independent_audit(d,p)['passed'])
        self.assertLess(max(q['torque_residual_N_mm'] for q in p),1e-6);self.assertTrue(all(q['internal_hessian_eigenvalues_N_mm'][0]>0 for q in p))
    def test_invalid_internal_travel_rejected(self):
        with self.assertRaises(ValueError):linkage.equilibrium(TEACHER['stages'],-1.)
    def test_query_budget_includes_every_fitter_callback_and_cache_free(self):
        lab=Laboratory(tasks()[0],budget=7);lab.fit('single_hardening',100);self.assertEqual(len(lab.records),7);old=lab.records[0];self.assertEqual(lab.evaluate(old['architecture'],old['parameters'])['id'],old['id'])
        with self.assertRaises(BudgetExhausted):lab.evaluate('single_hardening',[20.,5.,1.,.1])
    def test_plan_cannot_expand_budget_or_edit_requirements(self):
        lab=Laboratory(tasks()[0]);original=deepcopy(lab.task)
        with self.assertRaises(ValueError):dispatch(lab,'submit_plan',{'searches':[{'architecture':'single_hardening','maximum_evaluations':241}]})
        with self.assertRaises(ValueError):dispatch(lab,'relax_requirements',{'maximum_width_mm':1000})
        self.assertEqual(original,lab.task)

if __name__=='__main__':unittest.main()
