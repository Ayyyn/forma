"""Non-folding structure pilot contracts and independent mechanics checks."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from structure_lab.mechanics import solve_frame
from structure_lab.verification import verify
from structure_lab.design import task_cases,templates,bounds,validate_graph,geometry
from structure_lab.search import Laboratory,numerical_portfolio,BudgetExhausted
from structure_lab.agent import run_meta
from structure_lab.tool_protocol import normalize


class StructuralLabTests(unittest.TestCase):
    def test_reference_mechanics_and_independent_gradients(self):
        result=verify();self.assertTrue(result['passed'],result)

    def test_invalid_graph_and_cache_accounting(self):
        task=task_cases()[0];lab=Laboratory(task,budget=2);ids=templates()['straight_beam']
        r=lab.evaluate(ids,[1.,1.]);again=lab.evaluate(ids,[1.,1.]);self.assertIs(r,again)
        self.assertEqual(lab.physics_solves,1);self.assertEqual(len(lab.records),1)
        bad=lab.evaluate([0],[1.]);self.assertFalse(bad['valid']);self.assertEqual(len(lab.records),2)
        with self.assertRaises(BudgetExhausted):lab.evaluate(ids,[1.1,1.1])

    def test_clearance_counts_member_width(self):
        task=task_cases()[-1];ids=templates()['straight_beam']
        with self.assertRaisesRegex(ValueError,'channel'):validate_graph(task,ids,[.4,.4])
        validate_graph(task,templates()['dual_rail'],[.4]*6)

    def test_crossing_beams_not_silently_fused(self):
        nodes,edges=geometry();a=edges.index((0,4));b=edges.index((1,3))
        with self.assertRaisesRegex(ValueError,'Crossing'):validate_graph(task_cases()[0],[a,b],[.4,.4])

    def test_optimizer_internal_evaluations_are_charged(self):
        lab=Laboratory(task_cases()[0],budget=4)
        result=lab.optimize(template='upper_frame',allocation=4,fraction=.8)
        self.assertLessEqual(result['used_slots'],4);self.assertEqual(len(lab.records),result['used_slots'])
        self.assertGreater(lab.cache_hits,0)

    def test_optimizer_edge_permutation_preserves_derivative_mapping(self):
        task=task_cases()[0];ids=templates()['upper_frame'];a=Laboratory(task);b=Laboratory(task)
        a.optimize(edge_ids=ids,allocation=20,fraction=.8)
        b.optimize(edge_ids=ids[::-1],allocation=20,fraction=.8)
        self.assertEqual(a.best,b.best)
        self.assertEqual(len(a.records),len(b.records))

    def test_numerical_portfolio_validated_for_every_development_task(self):
        for task in task_cases():
            lab=Laboratory(task);numerical_portfolio(lab,101)
            self.assertLessEqual(len(lab.records),96);self.assertTrue(lab.best['feasible'],(task,lab.best))
            self.assertTrue(lab.final_verify()['passed'])

    def test_oracle_rejects_corrupted_model_output(self):
        lab=Laboratory(task_cases()[0]);ids=templates()['upper_frame'];lab.evaluate(ids,[1.9,1.9,1.])
        lab.best['compliance_mm_per_N'][0][0]+=1
        self.assertFalse(lab.final_verify()['passed'])

    def test_actual_tool_result_history_is_sent_back(self):
        responses=[({'role':'assistant','content':None,'tool_calls':[{'id':'test-opt','type':'function','function':{'name':'optimize_design','arguments':json.dumps({'template':'upper_frame','allocation':8,'start_fraction':1.})}}]},
                     {'transport':{'http_status':200},'response_id':'test-fixture-1'}),
                    ({'role':'assistant','content':None,'tool_calls':[{'id':'test-finish','type':'function','function':{'name':'finish_search','arguments':'{}'}}]},
                     {'transport':{'http_status':200},'response_id':'test-fixture-2'})]
        calls=[]
        def fixture(messages,*args):
            calls.append(json.loads(json.dumps(messages)));return responses[len(calls)-1]
        with patch('structure_lab.agent.model_request',side_effect=fixture):
            result=run_meta(Laboratory(task_cases()[0]),101,Path('unused-fixture-directory'))
        self.assertEqual(result['actual_api_calls'],2)
        self.assertTrue(any(m.get('role')=='tool' and m.get('tool_call_id')=='test-opt' for m in calls[1]))
        self.assertTrue(any(m.get('role')=='tool' and 'best_evaluated' in m['content'] for m in calls[1]))

    def test_provider_xml_and_json_plans_preserve_actual_arguments(self):
        args={'searches':[{'template':'upper_frame','allocation':8}]}
        xml='<atem:function_calls><atem:invoke name="plan_search"><atem:parameter name="searches">'+json.dumps(args['searches'])+'</atem:parameter></atem:invoke></atem:function_calls>'
        for text,kind in [(xml,'atem_xml'),('Plan:\n```json\n'+json.dumps(args)+'\n```','single_tool_json')]:
            out,encoding=normalize({'role':'assistant','content':text,'tool_calls':[]},{'plan_search'},'synthetic-test-receipt',single_tool='plan_search')
            self.assertEqual(encoding,kind);self.assertEqual(json.loads(out['tool_calls'][0]['function']['arguments']),args)

    def test_protocol_rejects_entities_unknown_tools_and_duplicate_fields(self):
        bad=['<atem:function_calls><atem:invoke name="python"/></atem:function_calls>',
             '<atem:function_calls><atem:invoke></atem:function_calls>',
             '<atem:function_calls><atem:invoke name="plan_search"><atem:parameter name="searches">&entity;</atem:parameter></atem:invoke></atem:function_calls>',
             '{"searches":[],"searches":[]}']
        for content in bad:
            with self.assertRaises(ValueError):normalize({'content':content,'tool_calls':[]},{'plan_search'},'fixture',single_tool='plan_search')

    def test_adaptive_protocol_does_not_guess_tool_from_arbitrary_json(self):
        public={'role':'assistant','content':'{"edge_ids":[1,4],"widths_mm":[1,1]}','tool_calls':[]}
        out,encoding=normalize(public,{'evaluate_design','optimize_design'},'fixture')
        self.assertEqual(encoding,'no_command');self.assertEqual(out,public)


if __name__=='__main__':unittest.main()
