import json
import unittest
from pydantic import ValidationError
from bugproof_pilot_v2.adapter import decode
from bugproof_pilot_v2.contracts import Assertion,check


class ContractAdapterTests(unittest.TestCase):
    def test_native_json_and_xml_agree(self):
        value={'status':'suite','evidence_quote':'fixture','tests':[{'action':'request','assertion':{'kind':'returns'}}]}
        native={'tool_calls':[{'function':{'name':'submit_suite','arguments':json.dumps(value)}}]}
        xml='<atem:function_calls><atem:invoke name="submit_suite"><atem:parameter name="status">suite</atem:parameter><atem:parameter name="evidence_quote">fixture</atem:parameter><atem:parameter name="tests">'+json.dumps(value['tests'])+'</atem:parameter></atem:invoke></atem:function_calls>'
        objects=[decode(m)[0].model_dump() for m in [native,{'content':json.dumps(value)},{'content':xml}]]
        self.assertEqual(objects[0],objects[1]);self.assertEqual(objects[1],objects[2])

    def test_unknown_invocation_extra_fields_and_entities_rejected(self):
        for text in ['<!DOCTYPE x><atem:function_calls/>','<atem:function_calls><atem:invoke name="exec"/></atem:function_calls>',json.dumps({'status':'suite','code':'print(1)'})]:
            with self.assertRaises((ValueError,ValidationError)):decode({'content':text})

    def test_missing_and_null_headers_never_equal_strings(self):
        a=Assertion(kind='header_equals',header='x-count',value='3')
        self.assertFalse(check({'headers':{}},a));self.assertFalse(check({'headers':{'X-Count':None}},a))
        self.assertTrue(check({'headers':{'X-Count':'3'}},a))


if __name__=='__main__':unittest.main()
