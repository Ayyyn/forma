"""Pre-study adapter checks; generated scored cases are not evaluated here."""
import unittest
import numpy as np
from spatial_revision.problem import development_task,geometry,catalogue,broad_catalogue,compute,bounds,generate_cases
from spatial_revision.laboratory import Lab,eligible_catalogue
from spatial_actuator.design import compute as previous


class SpatialRevisionTests(unittest.TestCase):
    def test_identity_adapter_matches_previous_implementation(self):
        t=development_task();ids=catalogue()['fork_2_3'];rr=[.4]*len(ids)
        a=compute(t,ids,rr,True);b=previous(t,ids,rr,True)
        self.assertEqual(a['metrics'],b['metrics']);self.assertEqual(a['margins'],b['margins'])
        self.assertTrue(np.array_equal(a['solved']['du_dr'],b['solved']['du_dr']))

    def test_coordinate_scaling_and_offsets_are_explicit(self):
        t=development_task();old,_=geometry(t);t['geometry_matrix']=np.diag([1.1,.9,1.2]).tolist();t['node_offsets_mm'][9]=[1,2,3]
        new,_=geometry(t);self.assertTrue(np.allclose(new[9],old[9]*[1.1,.9,1.2]+[1,2,3]))

    def test_reverse_output_sign_changes_acceptance_not_physics(self):
        t=development_task();ids=catalogue()['fork_2_3'];radii=[.4]*len(ids)
        a=compute(t,ids,radii);b=compute(dict(t,output_sign=-1),ids,radii)
        self.assertEqual(a['metrics']['loaded_stroke_mm'],-b['metrics']['loaded_stroke_mm']);self.assertTrue(np.array_equal(a['solved']['u'],b['solved']['u']))

    def test_signed_optimizer_derivative(self):
        for sign in [1,-1]:
            t=dict(development_task(),output_sign=sign,geometry_matrix=np.diag([1.,1.,float(sign)]).tolist())
            lab=Lab(t);lab.optimize(template='fork_2_3',allocation=80,start_fraction=.25)
            self.assertTrue(lab.best['feasible'],lab.best);self.assertTrue(lab.verify()['passed'])

    def test_broad_catalogue_is_larger_and_no_duplicate_graphs(self):
        broad=broad_catalogue();self.assertGreater(len(broad),100)
        self.assertEqual(len(broad),len({tuple(e) for e in broad.values()}));self.assertTrue(set(catalogue())<=set(broad))

    def test_generator_reproducible_without_solver_or_label_filtering(self):
        from unittest.mock import patch
        with patch('spatial_revision.problem.compute',side_effect=AssertionError('No label generation allowed')):
            self.assertEqual(generate_cases(31415),generate_cases(31415));self.assertEqual(len(generate_cases(31415)),8)

    def test_collision_eligibility_is_geometric_only(self):
        from unittest.mock import patch
        with patch('spatial_revision.problem.solve',side_effect=AssertionError('No physics screening allowed')):
            eligible=eligible_catalogue(development_task());self.assertGreater(len(eligible),30)


if __name__=='__main__':unittest.main()
