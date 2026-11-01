import unittest
import numpy as np
from coating_proof.model import index,recursive_rt,matrix_rt,evaluate_stack

class CoatingProofTests(unittest.TestCase):
 def test_fresnel_interface_known_four_percent(self):
    r=recursive_rt([1.,1.5],[],[550.]);self.assertAlmostEqual(r['R'][0],.04,places=13);self.assertAlmostEqual(r['T'][0],.96,places=13)
 def test_Brewster_polarization(self):
    angle=np.rad2deg(np.arctan(1.5));r=recursive_rt([1.,1.5],[],[550.],angle,'p');self.assertLess(r['R'][0],1e-25)
 def test_total_internal_reflection(self):
    r=recursive_rt([1.5,1.],[],[550.],60.,'s');self.assertAlmostEqual(r['R'][0],1.,places=12);self.assertAlmostEqual(r['T'][0],0.,places=12)
 def test_quarterwave_closed_form(self):
    pairs=4;high,low,substrate=2.4,1.45,1.5;wave=550.;ns=[1.]+[v for _ in range(pairs) for v in [high,low]]+[substrate];d=[wave/(4*v) for _ in range(pairs) for v in [high,low]];expected=((1-substrate*(high/low)**(2*pairs))/(1+substrate*(high/low)**(2*pairs)))**2
    r=recursive_rt(ns,d,[wave]);self.assertAlmostEqual(r['R'][0],expected,places=12)
 def test_lossless_energy_and_two_formulations(self):
    wave=np.linspace(400,1400,51);ns=[1.,2.4,1.45,2.1,1.5];d=[100.,120.,160.]
    for polarization in ['s','p']:
        a=recursive_rt(ns,d,wave,53.,polarization);b=matrix_rt(ns,d,wave,53.,polarization);np.testing.assert_allclose(a['R']+a['T'],1.,atol=1e-12);np.testing.assert_allclose(a['R'],b['R'],atol=1e-12);np.testing.assert_allclose(a['T'],b['T'],atol=1e-12)
 def test_passive_absorption_and_reciprocity(self):
    a=recursive_rt([1.,2.+.1j,1.5],[100.],[500.]);b=recursive_rt([1.5,2.+.1j,1.],[100.],[500.]);self.assertGreater(a['A'][0],0.);self.assertAlmostEqual(a['T'][0],b['T'][0],places=12)
 def test_zero_thickness_layer_disappears(self):
    a=recursive_rt([1.,2.4,1.5],[0.],[550.],35.,'p');b=recursive_rt([1.,1.5],[],[550.],35.,'p');np.testing.assert_allclose(a['R'],b['R'],atol=1e-13)
 def test_measured_material_units_and_no_extrapolation(self):
    silica=index('SiO2',[550.])[0];self.assertGreater(silica.real,1.45);self.assertLess(silica.real,1.47);self.assertGreater(index('TiO2',[550.])[0].real,2.)
    with self.assertRaises(ValueError):index('SiO2',[100.])
    with self.assertRaises(ValueError):index('unknown',[550.])
 def test_invalid_or_active_stack_rejected(self):
    with self.assertRaises(ValueError):recursive_rt([1.,2.-.1j,1.5],[100.],[550.])
    with self.assertRaises(ValueError):evaluate_stack([{'material':'TiO2','thickness_nm':-1}],[550.])

if __name__=='__main__':unittest.main()
