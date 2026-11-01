import unittest
import numpy as np
from threadpoolctl import threadpool_limits
from frontier_scout.data import Dataset
from frontier_portfolio.engine import update_weights,reset_meta_weight,predictions,select

class FrontierPortfolioTests(unittest.TestCase):
 def test_prior_and_abstention_do_not_replace_base_experts(self):
    w=np.array([.6,.2,.2,0.]);a=reset_meta_weight(w,True);np.testing.assert_allclose(a,[.54,.18,.18,.1]);saved=a.copy();b=reset_meta_weight(a,False);np.testing.assert_allclose(b,w);np.testing.assert_array_equal(a,saved)
 def test_prequential_evidence_rewards_the_correct_prediction(self):
    w,loss=update_weights([1/3,1/3,1/3,0.],[0.,1.,3.,0.],[.2,.2,.2,1.],1.,[True,True,True,False]);self.assertGreater(w[1],w[0]);self.assertGreater(w[1],w[2]);self.assertEqual(w[3],0.);self.assertAlmostEqual(w.sum(),1.)
 def test_floors_avoid_nan_in_overconfident_experts(self):
    w,loss=update_weights([.3,.3,.3,.1],[0.,0.,0.,100.],[0.,0.,0.,0.],1.,[True]*4);self.assertTrue(np.isfinite(w).all());self.assertTrue((w>0).all());self.assertTrue((loss<=20.).all())
 def test_unrevealed_table_values_cannot_change_forecast_or_selection(self):
    with threadpool_limits(1):
        d=Dataset('printing');h=[d.observe(i) for i in range(8)];a=predictions(d,h,[],False);i=select(a,h,[1/3]*3);d._means[:]=1e12;d._variance[:]=1e12;b=predictions(d,h,[],False);j=select(b,h,[1/3]*3)
        self.assertEqual(i,j)
        for x,y in zip(a,b):np.testing.assert_allclose(x[0],y[0]);np.testing.assert_allclose(x[1],y[1])

if __name__=='__main__':unittest.main()
