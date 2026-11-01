"""Reference mechanics tests. All inputs are published or explicitly synthetic."""
from dataclasses import replace
import math
import unittest
import numpy as np
from kresling_proof.model import Cell,AxialSpring,features,coefficients,energy_components,energy,jet,scaled_jet
from kresling_proof.oracle import vertex_features,vertex_energy,high_precision_jet
from kresling_proof.statics import equilibria,state_record,relax_phi,branch_barrier
from kresling_proof.verification import reference_checks,convergence_checks


class KreslingMechanicalProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cell=Cell()
        cls.solved=equilibria(cls.cell)

    def test_published_checkpoints_and_frozen_curve(self):
        report=reference_checks(self.cell,self.solved)
        self.assertTrue(report['passed'],report['checks'])
        self.assertEqual(len(report['curve_comparison']),30)

    def test_independent_vertices_for_different_geometries(self):
        rng=np.random.default_rng(9834)
        for cell in [self.cell,Cell(n=8,r_mm=17,h0_mm=26,theta0_deg=20),Cell(n=5,r_mm=23,h0_mm=31,theta0_deg=24)]:
            for _ in range(12):
                u=rng.uniform(-.05,.9)*cell.h0_mm;p=rng.uniform(0,.95)*cell.phi_max
                np.testing.assert_allclose(features(cell,u,p),vertex_features(cell.to_dict(),u,p),rtol=1e-12,atol=1e-12)
                self.assertAlmostEqual(float(energy(cell,u,p)),vertex_energy(cell.to_dict(),u,p),places=10)

    def test_full_hessian_rejects_the_published_intermediate_saddle(self):
        kinds=[s['classification'] for s in self.solved['states']]
        self.assertEqual(kinds,['minimum','saddle','minimum'])
        saddle=self.solved['states'][1]
        self.assertLess(saddle['hessian_eigenvalues'][0],0)
        self.assertGreater(saddle['hessian_eigenvalues'][1],0)
        self.assertEqual(state_record(self.cell,[10/30,.5])['classification'],'not_equilibrium')

    def test_hessian_and_gradient_against_seventy_digit_source(self):
        for spring in [AxialSpring(),AxialSpring(True,.01,2.)]:
            q=[.4,.55]
            v,g,h=scaled_jet(self.cell,q,spring)
            ov,og,oh=high_precision_jet(self.cell.to_dict(),q,spring.to_dict())
            self.assertAlmostEqual(v,ov,places=12)
            np.testing.assert_allclose(g,og,atol=1e-11)
            np.testing.assert_allclose(h,oh,atol=1e-10)

    def test_energy_nonnegative_and_rest_is_zero(self):
        self.assertEqual(float(energy(self.cell,0,0)),0.)
        terms=energy_components(self.cell,np.linspace(0,35,20),np.linspace(0,.9,20),AxialSpring(True,.01,2))
        self.assertTrue(np.all(terms>=0))
        self.assertEqual(terms.shape,(6,20))
        # Both end polygons contribute n edges to the hinge term.
        self.assertAlmostEqual(coefficients(self.cell)[2],2*6*.005*30)

    def test_geometric_folded_limit_is_not_declared_an_interior_minimum(self):
        h=30*math.sqrt(2*(math.cos(math.radians(30))-math.cos(math.radians(90))))
        truss=replace(self.cell,h0_mm=h,kr_per_length=0)
        self.assertLess(float(energy(truss,h,truss.phi_max)),1e-20)
        with self.assertRaisesRegex(ValueError,'boundary'):
            jet(truss,h,truss.phi_max)

    def test_disabled_spring_and_zero_offset_are_different(self):
        u,p=12.,.55
        bare=float(energy(self.cell,u,p))
        self.assertEqual(float(energy(self.cell,u,p,AxialSpring(False,.02,3))),bare)
        active=float(energy(self.cell,u,p,AxialSpring(True,.02,0)))
        self.assertAlmostEqual(active-bare,.5*.02*u*u)

    def test_axial_spring_exact_force_and_torque_identities(self):
        spring=AxialSpring(True,.02,3)
        v,g,h=jet(self.cell,10,.5)
        sv,sg,sh=jet(self.cell,10,.5,spring)
        self.assertAlmostEqual(sv-v,.5*.02*(3-10)**2)
        np.testing.assert_allclose(sg-g,[.02*(10-3),0],atol=1e-12)
        np.testing.assert_allclose(sh-h,[[.02,0],[0,0]],atol=1e-12)
        self.assertAlmostEqual(relax_phi(self.cell,10,spring)['phi_rad'],relax_phi(self.cell,10)['phi_rad'],places=11)

    def test_geometric_scaling_preserves_normalized_energy(self):
        base=self.cell;q=[.4,.55]
        scaled=replace(base,r_mm=base.r_mm/1000,h0_mm=base.h0_mm/1000)
        v,g,h=scaled_jet(base,q);sv,sg,sh=scaled_jet(scaled,q)
        self.assertAlmostEqual(v,sv,places=12)
        np.testing.assert_allclose(g,sg,atol=1e-11)
        np.testing.assert_allclose(h,sh,atol=1e-10)

    def test_branch_barrier_is_directional_and_protocol_labeled(self):
        result=branch_barrier(self.cell,self.solved['states'])
        self.assertEqual(result['status'],'resolved_on_declared_branch')
        self.assertGreater(result['forward_N_mm'],result['reverse_N_mm'])
        self.assertGreater(result['reverse_N_mm'],0)
        self.assertIn('not a globally',result['scope'])
        self.assertEqual(branch_barrier(self.cell,[])['status'],'unresolved')

    def test_search_and_angular_resolution_converge(self):
        self.assertTrue(convergence_checks(self.cell)['passed'])

    def test_free_rotation_resolves_a_well_between_boundary_and_first_sample(self):
        # This small compression has a true minimum inside the first angular
        # grid interval. A sampled-energy-only minimum incorrectly clamps phi=0.
        fine=relax_phi(self.cell,.0136,samples=257)
        coarse=relax_phi(self.cell,.0136,samples=65)
        self.assertGreater(fine['phi_rad'],0)
        self.assertLess(abs(fine['torque_N_mm']),1e-8)
        self.assertAlmostEqual(fine['phi_rad'],coarse['phi_rad'],places=10)

    def test_preloaded_two_well_barrier_is_not_lost_by_angular_clamping(self):
        spring=AxialSpring(True,.002*self.cell.ks_N/self.cell.r_mm,.1*self.cell.h0_mm)
        solved=equilibria(self.cell,spring,grid=7)
        result=branch_barrier(self.cell,solved['states'],spring)
        self.assertEqual(result['status'],'resolved_on_declared_branch',result)

    def test_relaxed_energy_derivative_matches_axial_reaction(self):
        for u in [1.,10.,20.,37.8]:
            step=1e-4
            a=relax_phi(self.cell,u-step);b=relax_phi(self.cell,u+step)
            center=relax_phi(self.cell,u)
            self.assertAlmostEqual((b['energy_N_mm']-a['energy_N_mm'])/(2*step),center['force_N'],places=7)

    def test_invalid_parameters_units_and_singular_states_rejected(self):
        for kwargs in [{'n':True},{'n':6.0},{'r_mm':-1},{'ks_N':0},{'kr_per_length':-1},
                       {'theta0_deg':80},{'h0_mm':float('nan')}]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):Cell(**kwargs)
        for spring in [{'enabled':'false'},{'stiffness_N_per_mm':-1},{'offset_mm':float('inf')}]:
            with self.subTest(spring=spring),self.assertRaises(ValueError):AxialSpring(**spring)
        for u,p in [(40.,.5),(2.,55.),(float('nan'),.5)]:
            with self.subTest(u=u,p=p),self.assertRaises(ValueError):features(self.cell,u,p)


if __name__=='__main__':unittest.main()
