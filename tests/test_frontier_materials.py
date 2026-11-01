import json,unittest
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from threadpoolctl import threadpool_limits
from frontier_scout.data import Dataset,audit
from frontier_scout.policy import expand,validate_plan,domain_features,choose,expected_improvement
from frontier_scout.meta import Budget

class FrontierMaterialsTests(unittest.TestCase):
 def test_raw_replicates_are_grouped_before_reveal(self):
    data=Dataset('crossed_barrel');self.assertEqual(data.raw_rows,1800);self.assertEqual(len(data.X),600);self.assertTrue(all(data._counts==3));self.assertEqual(len(set(data.ids)),600)
 def test_current_tables_not_old_paper_table_sizes(self):
    rows=audit();self.assertEqual(rows['perovskite']['pool_design_groups'],94);self.assertEqual(rows['printing']['pool_design_groups'],100)
 def test_feature_language_cannot_execute_strings_or_reference_outcomes(self):
    base={'hypothesis':'Test only','features':[{'name':'x','op':'product','inputs':[0,100],'rationale':'invalid'}]}
    with self.assertRaises(ValueError):validate_plan(base,4)
    base['features'][0].update(op='__import__',inputs=[0])
    with self.assertRaises(ValueError):validate_plan(base,4)
    base['features'][0].update(op='square',inputs=['0'])
    with self.assertRaises(ValueError):validate_plan(base,4)
 def test_annular_feature_is_exact_area_and_shared_with_Meta(self):
    d=Dataset('crossed_barrel');features=domain_features(d.name);validate_plan({'hypothesis':'domain control','features':features},4);z=expand(d.X,features)
    area=np.pi*(d.X[:,2]**2-(d.X[:,2]-d.X[:,3])**2);expected=(area-area.min())/np.ptp(area);np.testing.assert_allclose(z[:,4],expected)
 def test_no_hidden_label_or_variance_enters_a_policy(self):
    with threadpool_limits(1):
        d=Dataset('printing');history=[d.observe(i) for i in [0,3,7,10,15,20,25,30]];a,pa=choose(d.X,history,1)
        d._means[:]=999.;d._variance[:]=1e8;b,pb=choose(d.X,history,1)
        self.assertEqual(a,b);self.assertEqual(pa,pb);self.assertNotIn(a,[h['index'] for h in history])
 def test_minimization_score_and_JSON_are_not_inverted(self):
    d=Dataset('perovskite');indices=np.argsort(d._means)[::-1][:32];history=[d.observe(int(i)) for i in indices];r=d.score(history)
    self.assertEqual(r['best_group_mean'],min(h['mean'] for h in history));self.assertTrue(all(a>=b for a,b in zip(r['normalized_regret'],r['normalized_regret'][1:])));json.dumps(r)
 def test_EI_is_nonnegative_and_prefers_a_good_prediction(self):
    a=expected_improvement(np.array([0.,2.]),np.array([.01,.01]),1.)
    self.assertTrue(np.all(a>=0));self.assertGreater(a[1],a[0])
 def test_budget_reservations_cannot_race_past_cap(self):
    b=Budget(cap=1.,maximum=20)
    with ThreadPoolExecutor(max_workers=8) as pool:result=list(pool.map(lambda _:b.reserve(.2),range(20)))
    self.assertLessEqual(sum(result),5);self.assertLessEqual(b.state()['pending_reserved_USD'],1.+1e-10)
 def test_ratio_guard_and_overflow_rejection(self):
    z=expand(np.array([[1.,0.],[2.,1.]]),[{'op':'ratio','inputs':[0,1]}]);self.assertTrue(np.isfinite(z).all())
    with self.assertRaises(ValueError):expand(np.array([[1e8],[2e8]]),[{'op':'square','inputs':[0]}])
 def test_transport_halt_blocks_new_dispatches(self):
    b=Budget();self.assertTrue(b.reserve(.1));b.halt('HTTP400 compatibility error');self.assertFalse(b.reserve(.1));b.settle(.1,0.);self.assertEqual(b.state()['request_count'],1)

if __name__=='__main__':unittest.main()
