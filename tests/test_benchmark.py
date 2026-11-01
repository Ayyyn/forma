import copy
import unittest
from continuum.benchmark import Ledger, Plan, propose, deterministic, rank
from continuum.geometry import Design, Requirements, evaluate
from continuum.audit import audit_record


class BenchmarkContracts(unittest.TestCase):
    def test_accordion_region_fields_canonicalized(self):
        physical=Plan(family='accordion',gamma_min=90,gamma_max=90,rows_min=1,rows_max=1)
        defaults=Plan(family='accordion')
        self.assertEqual(physical,defaults)
        self.assertEqual(defaults.rows_min,1)
        self.assertEqual(defaults.gamma_max,90)
        with self.assertRaises(ValueError):Plan(family='miura',gamma_min=90,gamma_max=90,rows_min=1)

    def test_charge_invalid_duplicate_and_block_overspend(self):
        ledger=Ledger(Requirements(),'creases',budget=3)
        ledger.evaluate(Design().model_dump(),'first')
        ledger.evaluate(Design().model_dump(),'duplicate')
        ledger.evaluate({'invalid':True},'invalid')
        self.assertEqual(len(ledger.records),3)
        self.assertTrue(ledger.records[1]['duplicate'])
        self.assertFalse(ledger.records[2]['valid'])
        with self.assertRaises(ValueError):ledger.evaluate(Design().model_dump(),'over-budget')
        self.assertEqual(len(ledger.records),3)

    def test_no_hidden_reference_and_reproducible_sampler(self):
        a=list(propose(Requirements(),Plan(),21,101))
        self.assertEqual(a,list(propose(Requirements(),Plan(),21,101)))
        self.assertNotIn(Design().model_dump(),a)
        self.assertEqual(len(a),21)

    def test_deterministic_method_exact_budget(self):
        ledger=Ledger(Requirements(),'creases')
        ledger.evaluate(Design().model_dump(),'common-start')
        deterministic(ledger,101)
        self.assertEqual(len(ledger.records),64)
        self.assertTrue(all(r['independent_audit']['passed'] for r in ledger.records if r['valid']))

    def test_objective_not_model_reported_score(self):
        a=evaluate(Design(),Requirements());b=copy.deepcopy(a)
        a['score']=-1000000;b['score']=1000000
        b['metrics']['crease_segments']=a['metrics']['crease_segments']-1
        self.assertLess(rank(b,'creases'),rank(a,'creases'))

    def test_oracle_catches_fabricated_success(self):
        r=Requirements(packed_long_max_mm=30)
        result=evaluate(Design(),r)
        self.assertFalse(result['feasible'])
        result['feasible']=True
        self.assertFalse(audit_record(result,r.model_dump())['passed'])


if __name__=='__main__':unittest.main()
