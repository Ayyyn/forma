"""Synthetic fixtures test policy fairness, inference and real-response accounting."""
import json
import os
import unittest
from unittest.mock import patch
import numpy as np
from kresling_bench.design import catalogue
from kresling_bench.inference import Laboratory,update,expected_information
from kresling_bench.policies import meta_choice,public_catalogue
from kresling_bench.summary import replay,cluster_interval


class SelectionBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=catalogue()

    def test_gaussian_bayes_update(self):
        logp=update(np.log([.5,.5]),np.array([[0.,0.],[2.,0.]]),[0.,0.],np.ones(2))
        self.assertAlmostEqual(np.exp(logp)[0],1/(1+np.exp(-2)),places=12)

    def test_information_targets_mechanics_not_calibration(self):
        prior=np.full(4,-np.log(4));noise=np.ones(2)*.2
        nuisance_only=np.array([[0,0],[2,0],[0,0],[2,0]])
        self.assertAlmostEqual(expected_information(prior,nuisance_only,noise,15,members=2),0,places=10)
        mechanical=np.array([[0,0],[0,0],[2,0],[2,0]])
        self.assertGreater(expected_information(prior,mechanical,noise,15,members=2),.69)

    def test_zero_information_identical_models(self):
        p=np.log([.2,.3,.5]);means=np.zeros((3,2))
        self.assertAlmostEqual(expected_information(p,means,np.ones(2),15),0,places=12)

    def test_budget_repeats_and_invalid_actions(self):
        lab=Laboratory(self.data,0,101)
        a=lab.measure('E01');b=lab.measure('E01');c=lab.measure('unknown');lab.measure('E02')
        self.assertNotEqual(a['observation_F_T'],b['observation_F_T'])
        self.assertFalse(c['valid']);self.assertEqual(lab.metrics()['charged_attempts'],4)
        with self.assertRaises(ValueError):lab.measure('E03')

    def test_common_potential_observation_independent_of_order(self):
        a=Laboratory(self.data,3,202,7);b=Laboratory(self.data,3,202,7)
        a.measure('E02');b.measure('E03')
        x=a.measure('E01');y=b.measure('E01')
        self.assertEqual(x['observation_F_T'],y['observation_F_T'])
        self.assertNotEqual(x['posterior'],y['posterior'])

    def test_public_state_excludes_hidden_truth_and_holdout(self):
        a=Laboratory(self.data,0,101,0);b=Laboratory(self.data,15,101,8)
        self.assertEqual(a.public_state(),b.public_state())
        public=public_catalogue(self.data)
        self.assertNotIn('heldout',public);self.assertNotIn('heldout_means',public)
        self.assertEqual(len(a.public_state()['mechanical_posterior']),16)

    def test_missing_rounds_keep_last_belief_no_fake_observation(self):
        lab=Laboratory(self.data,5,101,4);lab.measure('E03');m=lab.metrics()
        self.assertEqual(m['valid_measurements'],1)
        self.assertEqual(m['step_nll'],[m['step_nll'][0]]*4)

    def test_api_ledger_and_no_saved_private_reasoning(self):
        response={'id':'synthetic-test-fixture','model':'test-model','choices':[{'message':{
          'reasoning_content':'PRIVATE_FIXTURE','tool_calls':[{'function':{'name':'perform_experiment','arguments':json.dumps({'experiment_id':'E04','public_reason':'test fixture'})}}]}}]}
        transport={'http_status':200,'usage':{'completion_tokens':12}}
        with patch.dict(os.environ,{'BASETEN_API_KEY':'synthetic-fixture-key'}),patch('kresling_bench.policies.load_env'),patch('kresling_bench.policies.request',return_value=(transport,response)) as mocked:
            choice,event=meta_choice(Laboratory(self.data,0,101))
            self.assertEqual(mocked.call_count,1);self.assertEqual(choice,'E04')
            self.assertEqual(event['response_id'],'synthetic-test-fixture')
            self.assertNotIn('PRIVATE_FIXTURE',json.dumps(event));self.assertNotIn('synthetic-fixture-key',json.dumps(event))

    def test_replay_rejects_tampering(self):
        lab=Laboratory(self.data,1,202,4);out=lab.measure('E04')
        case={'truth_index':1,'noise_seed':202,'calibration_index':4}
        scores=[0.]*12;scores[3]=1.
        record={'method':'bayes_eig','status':'completed','trace':[{'outcome':out,'expected_information_nats':scores}],'metrics':lab.metrics()}
        self.assertEqual(replay(self.data,case,record)['valid'],1)
        record['metrics']['final_nll']+=.1
        with self.assertRaises(AssertionError):replay(self.data,case,record)

    def test_bootstrap_uses_mechanical_clusters(self):
        ci=cluster_interval([1,1,1,3,3,3],['a']*3+['b']*3)
        self.assertEqual(ci['clusters'],2);self.assertEqual(ci['estimate'],2)


if __name__=='__main__':unittest.main()
