import unittest
from unittest.mock import patch
from pydantic import ValidationError
from bugproof_pilot.contracts import Assertion,Contract,Proposal,check
from bugproof_pilot.runtime import verify
from bugproof_pilot.baseline import literal_suite


class RegressionProofContracts(unittest.TestCase):
    def test_no_code_or_unknown_actions(self):
        with self.assertRaises(ValidationError):Contract(action='exec',code='print(1)',assertion={'kind':'returns'})
        with self.assertRaises(ValidationError):Proposal(status='suite',tests=[{'action':'request','assertion':{'kind':'returns'}}]*5)

    def test_exception_is_not_silently_a_success(self):
        self.assertFalse(check({'exception':'UnicodeDecodeError'},Assertion(kind='returns')))
        self.assertFalse(check({'exception':'UnicodeDecodeError'},Assertion(kind='raises',value='InvalidURL')))
        self.assertTrue(check({'exception':'InvalidURL'},Assertion(kind='raises',value='InvalidURL')))

    def test_header_presence_is_case_insensitive_and_none_is_present(self):
        assertion=Assertion(kind='header_absent',value='Accept-Encoding')
        self.assertFalse(check({'headers':{'accept-encoding':None}},assertion))
        self.assertTrue(check({'headers':{}},assertion))

    def test_green_both_red_both_and_empty_never_verify(self):
        case={'instance_id':'synthetic-fixture','repo':'psf/requests'}
        contract={'action':'request','assertion':{'kind':'returns'}}
        for outcomes in [[{'passed':[True]},{'passed':[True]}],[{'passed':[False]},{'passed':[False]}]]:
            with patch('bugproof_pilot.runtime.execute',side_effect=outcomes):self.assertFalse(verify(case,[contract])['verified'])
        with patch('bugproof_pilot.runtime.execute',return_value={'passed':[]}):self.assertFalse(verify(case,[])['verified'])

    def test_runtime_import_failure_not_bug_reproduction(self):
        with patch('bugproof_pilot.runtime.execute',side_effect=[{'runtime_error':'import failed'},{'passed':[True]}]):
            self.assertFalse(verify({},[{'action':'request','assertion':{'kind':'returns'}}])['verified'])

    def test_rules_do_not_execute_embedded_report_code(self):
        issue='```python\n__import__("os").remove("anything")\n```'
        self.assertEqual(literal_suite(issue,'requests'),[])


if __name__=='__main__':unittest.main()
