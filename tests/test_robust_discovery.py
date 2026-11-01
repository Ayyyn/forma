import json,unittest
from copy import deepcopy
from pathlib import Path
import numpy as np
from nonlinear_discovery import model
from robust_discovery.engine import descend,summarize,tolerance_check

ROOT=Path(__file__).resolve().parents[1]

class RobustDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads((ROOT/'research/nonlinear-robustness-corrected.json').read_text())['result']
    def test_common_offset_only_adds_constant_and_clamp_torque(self):
        d=deepcopy(self.fixture['design']);original=deepcopy(d)
        for s in original['springs'][1:]:
            if s['type']=='torsion':s['offset']=1.
        for setting in ['A','B']:
            x=np.array(self.fixture['summary']['details'][setting]['target']['x'])
            a,g,h=model.jet(original,x,setting);b,g0,h0=model.jet(d,x,setting)
            self.assertAlmostEqual((a-b)*1500,30.,places=9)
            np.testing.assert_allclose(g,g0,atol=1e-12);np.testing.assert_allclose(h,h0,atol=1e-12)
            r=model.record(original,x,setting);s=model.record(d,x,setting)
            self.assertAlmostEqual(r['holding_torque_N_mm']-s['holding_torque_N_mm'],-30.,places=7)
    def test_saddle_descent_ends_at_nearby_true_minimum(self):
        d=self.fixture['design'];states=self.fixture['settings']['B']['states'];s=next(s for s in states if s['classification']!='minimum')
        x=np.array(s['x']);_,_,h=model.jet(d,x,'B');_,v=np.linalg.eigh(h)
        r=descend(d,x+.005*v[:,0],'B');self.assertTrue(r['converged'])
        np.testing.assert_allclose(r['path'][-1]['x'],r['minimum']['x'],atol=1e-10)
        self.assertLess(r['minimum']['gradient_residual_normalized'],1e-7)
        self.assertTrue(all(b['energy_N_mm']<=a['energy_N_mm']+1e-8 for a,b in zip(r['path'],r['path'][1:])))
    def test_missing_paths_are_unresolved_screen_failure(self):
        d=self.fixture['design'];settings=deepcopy(self.fixture['settings'])
        for r in settings.values():r['connections']=[]
        result=summarize(d,settings);self.assertFalse(result['passes_nominal_screen'])
        self.assertTrue(all(not v['selected_modes_have_constructed_paths'] for v in result['details'].values()))
    def test_shallow_state_rejected_even_with_large_energy_bias(self):
        s=self.fixture['summary'];self.assertGreater(s['worst_bias_N_mm'],40.)
        self.assertLess(s['details']['B']['minimum_sampled_escape_path_height_N_mm'],.03)
        self.assertFalse(s['passes_nominal_screen'])
    def test_tolerance_samples_are_repeatable_and_explicitly_local(self):
        a=tolerance_check(self.fixture['design'],self.fixture['summary'],1);b=tolerance_check(self.fixture['design'],self.fixture['summary'],1)
        self.assertEqual(a,b);self.assertIn('local continuation',a['scope']);self.assertEqual(len(a['trials'][0]['modes']),4)

if __name__=='__main__':unittest.main()
