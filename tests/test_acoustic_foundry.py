import unittest
from copy import deepcopy
import numpy as np
from acoustic_foundry.model import response, wave_oracle, resonance_hz, impedance


def fixture():
    return {'duct_diameter_mm':40.,'cells':[{'position_mm':0.,'neck_radius_mm':4.,
        'neck_length_mm':10.,'volume_cm3':25.,'end_correction_radii':1.7,'loss_factor':.04}]}


class AcousticModelTests(unittest.TestCase):
    def test_single_branch_published_formula(self):
        d=fixture();f=np.linspace(100,1800,97)
        z0=1.204*343/(np.pi*.02**2)
        expected=20*np.log10(abs(1+z0/(2*impedance(d['cells'][0],f))))
        np.testing.assert_allclose(response(d,f)['transmission_loss_db'],expected,atol=1e-11)

    def test_global_wave_equations(self):
        rng=np.random.default_rng(20261101)
        for count in [1,2,4,6]:
            d=fixture();d['cells']=[]
            for i in range(count):
                c=fixture()['cells'][0];c.update(position_mm=i*47.,neck_radius_mm=float(rng.uniform(2,6)),
                    neck_length_mm=float(rng.uniform(5,22)),volume_cm3=float(rng.uniform(10,45)))
                d['cells'].append(c)
            f=np.linspace(150,1700,37);out=response(d,f);t,r=wave_oracle(d,f)
            np.testing.assert_allclose(out['amplitude_t'],t,atol=1e-11)
            np.testing.assert_allclose(out['amplitude_r'],r,atol=1e-11)

    def test_passivity(self):
        d=fixture();d['cells'] += [dict(d['cells'][0],position_mm=43,volume_cm3=34)]
        out=response(d,np.linspace(50,2500,2000))
        self.assertGreaterEqual(float(min(out['power_absorbed'])),-1e-12)
        self.assertLessEqual(float(max(out['power_t']+out['power_r'])),1+1e-12)

    def test_lossless_energy_and_resonance(self):
        d=fixture();d['cells'][0]['loss_factor']=0
        out=response(d,np.linspace(50,1800,300))
        np.testing.assert_allclose(out['power_t']+out['power_r'],1,atol=1e-12)
        self.assertLess(response(d,[resonance_hz(d['cells'][0])])['power_t'][0],1e-20)

    def test_reciprocity_reversed_array(self):
        d=fixture();d['cells'] += [dict(d['cells'][0],position_mm=47,volume_cm3=36)]
        rev=deepcopy(d);rev['cells']=list(reversed(rev['cells']))
        for c in rev['cells']:c['position_mm']=47-c['position_mm']
        f=np.linspace(200,1600,100)
        np.testing.assert_allclose(response(d,f)['amplitude_t'],response(rev,f)['amplitude_t'],atol=1e-12)

    def test_scale_frequency_similarity(self):
        d=fixture();d['cells'][0]['volume_cm3']=15.;scaled=deepcopy(d)
        scaled['duct_diameter_mm']*=2
        for c in scaled['cells']:
            for k in ['position_mm','neck_radius_mm','neck_length_mm']:c[k]*=2
            c['volume_cm3']*=8
        f=np.linspace(200,1500,50)
        np.testing.assert_allclose(response(d,f)['power_t'],response(scaled,f/2)['power_t'],atol=1e-12)

    def test_invalid_domain(self):
        for f in [[0],[float('nan')],[10000]]:
            with self.assertRaises(ValueError):response(fixture(),f)
        d=fixture();d['cells'][0]['loss_factor']=-.1
        with self.assertRaises(ValueError):response(d,[500])


if __name__=='__main__':unittest.main()
