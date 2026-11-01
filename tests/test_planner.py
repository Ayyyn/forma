import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from continuum.geometry import Requirements
from continuum.planner import run_single_pass
from continuum.server import AgentRequest


class SinglePassContracts(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=patch('continuum.planner.ROOT',Path(self.temp.name));self.root.start();self.addCleanup(self.root.stop)
        self.keys=patch.dict('os.environ',{'BASETEN_API_KEY':'unit-test-not-a-real-key'});self.keys.start();self.addCleanup(self.keys.stop)

    def response(self,plan=None):
        plan=plan or {'family':'miura','gamma_min':82,'gamma_max':82,'columns_min':12,'columns_max':12,
            'rows_min':2,'rows_max':2,'packed_theta_min':88,'packed_theta_max':88,'expected_feasible':True,'rationale':'Test fixture only.'}
        return ({'http_status':200,'latency_ms':1,'usage':{'total_tokens':1}},
                {'id':'unit-test-response','model':'meta-models/muse-spark-open-1026','choices':[{'message':{'tool_calls':[{
                    'function':{'name':'search_designs','arguments':json.dumps(plan)}}]}}]})

    def test_default_is_single_pass(self):
        self.assertEqual(AgentRequest().mode,'single_pass')
        with patch('continuum.planner.run_single_pass',return_value={'test_only':True}) as one:
            from continuum.agent import run_agent
            self.assertEqual(run_agent(Requirements(),'A valid design brief')['test_only'],True)
            one.assert_called_once()

    def test_one_call_exact_budget_and_independent_verification(self):
        with patch('continuum.planner.request',return_value=self.response()) as transport:
            report=run_single_pass(Requirements(),'Prefer fewer creases, subject to the stated envelope.')
        self.assertEqual(transport.call_count,1)
        payload=transport.call_args.args[3]
        self.assertEqual(payload['tool_choice'],'auto')
        self.assertEqual(payload['reasoning_effort'],'medium')
        self.assertEqual(report['mode'],'single_pass')
        self.assertEqual(report['evaluations_used'],64)
        self.assertEqual(report['status'],'completed')
        self.assertTrue(report['selected']['feasible'])
        self.assertTrue(report['validation']['passed'])
        self.assertTrue(all(r['independent_audit']['passed'] for r in report['ledger'] if r['valid']))
        self.assertNotIn('reasoning_content',json.dumps(report))

    def test_failure_has_no_retry_or_silent_fallback(self):
        with patch('continuum.planner.request',return_value=({'http_status':403},None)) as transport:
            report=run_single_pass(Requirements(),'A valid design brief')
        self.assertEqual(transport.call_count,1)
        self.assertEqual(report['status'],'incomplete')
        self.assertIsNone(report['selected'])
        self.assertEqual(report['evaluations_used'],1)

    def test_impossible_requirements_cannot_be_overridden_by_model_claim(self):
        with patch('continuum.planner.request',return_value=self.response()):
            report=run_single_pass(Requirements(deployed_y_min_mm=220,blank_y_max_mm=190),'A valid design brief')
        self.assertEqual(report['evaluations_used'],64)
        self.assertIsNone(report['selected'])
        self.assertEqual(report['status'],'incomplete')

    def test_failed_final_geometry_check_blocks_selection(self):
        with patch('continuum.planner.request',return_value=self.response()),patch('continuum.planner.validate_geometry',return_value={'passed':False}):
            report=run_single_pass(Requirements(),'A valid design brief')
        self.assertIsNone(report['selected'])
        self.assertIn('verification',report['error']['message'])


if __name__=='__main__':unittest.main()
