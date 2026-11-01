import unittest
from copy import deepcopy
import numpy as np
from nonlinear_discovery.model import reference,mapping,jet,independent_energy,evaluate,audit,validate,mesh


class NonlinearDiscoveryTests(unittest.TestCase):
    def test_constraints_hold_for_all_internal_coordinates(self):
        d=reference();B,q0=mapping(d);q=B@np.arange(6)*.03+q0
        self.assertAlmostEqual(float(sum(q[::2])*30),55.)
        self.assertAlmostEqual(float(np.dot(q[1::2],d['handedness'])),0.)

    def test_independent_energy_and_constrained_derivatives(self):
        d=reference();x=np.array([.8,.8,.7,.7,.1,.1]);value,g,h=jet(d,x,'A');step=1e-5;eye=np.eye(6)*step
        fd=np.array([(independent_energy(d,x+e,'A')-independent_energy(d,x-e,'A'))/(2*step) for e in eye])
        self.assertAlmostEqual(value,independent_energy(d,x,'A'),places=11);self.assertTrue(np.allclose(g,fd,atol=1e-7))

    def test_common_reference_has_programmable_coexisting_minima(self):
        d=reference();result=evaluate(d,16);self.assertTrue(result['feasible'],result['details']);self.assertTrue(audit(d,result)['passed'])
        for setting in ['A','B']:
            detail=result['details'][setting];self.assertGreaterEqual(detail['minimum_count_found'],2);self.assertGreater(detail['energy_bias_N_mm'],.5)
            shape=mesh(d,detail['target']);self.assertEqual(len(shape['vertices_mm']),48);self.assertEqual(len(shape['triangles']),48)

    def test_torsional_ring_coupling_has_independent_energy(self):
        d=reference();d['springs'].append({'type':'torsion','rings':[1,3],'k':2.,'offset':.3});x=np.array([.8,.8,.7,.7,.1,.1])
        self.assertAlmostEqual(jet(d,x,'B')[0],independent_energy(d,x,'B'),places=11)

    def test_global_constraint_spring_and_wrong_schema_rejected(self):
        d=reference();d['springs'][0]['rings']=[0,4]
        with self.assertRaises(ValueError):validate(d)
        d=reference();d['springs'][0]['offset']=0
        with self.assertRaises(ValueError):validate(d)


if __name__=='__main__':unittest.main()
