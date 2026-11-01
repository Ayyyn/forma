import unittest
from copy import deepcopy
from problem_selection.cases import cases
from problem_selection.engine import check,validate_contract,validate_submission,equivalent


class RevisionEvidenceTests(unittest.TestCase):
    def setUp(self):self.rows={r["id"]:r for r in cases()}

    def test_expected_outcomes_include_positive_negative_ambiguous(self):
        expected={"R01":"geometry_and_records_pass","R02":"block","R03":"block","R04":"block","R05":"geometry_and_records_pass","R06":"clarify","R07":"geometry_and_records_pass","R08":"block","R09":"clarify","R10":"geometry_and_records_pass","R11":"block","R12":"geometry_and_records_pass","R13":"clarify"}
        for name,want in expected.items():
            r=self.rows[name]
            self.assertEqual(check(r["packet"],r["gold_contract"])["decision"],want,name)

    def test_interval_against_all_independent_corner_combinations(self):
        for name in ("R04","R05"):
            r=self.rows[name];m=r["packet"]["proposed_model"];w=m["width_mm"];t=m["thickness_mm"]
            # Independently enumerate width and BOTH independent side thicknesses.
            opening=min((w+dw)-(t+d1)-(t+d2) for dw in (-.5,.5) for d1 in (-.2,.2) for d2 in (-.2,.2))
            self.assertAlmostEqual(check(r["packet"],r["gold_contract"])["worst_case_opening_mm"],opening)

    def test_wrong_achieved_opening_can_silently_clear(self):
        r=self.rows["R03"];wrong=deepcopy(r["gold_contract"]);wrong["min_opening_mm"]=594
        self.assertEqual(check(r["packet"],wrong)["decision"],"geometry_and_records_pass")
        self.assertFalse(equivalent(wrong,r["gold_contract"]))
        # This demonstrates that geometry checks do NOT validate semantic intent.

    def test_quotes_must_exist_but_do_not_prove_interpretation(self):
        r=self.rows["R01"];s={"contract":r["gold_contract"],"evidence":[{"source_id":"message-1","quote":"Made up approval"}]}
        with self.assertRaises(ValueError):validate_submission(r["packet"],s)
        s["evidence"][0]["quote"]="Approve PETG";validate_submission(r["packet"],s)

    def test_numeric_and_unknown_field_rejection(self):
        for value in (True,float("nan"),float("inf"),-1,0):
            c=deepcopy(self.rows["R01"]["gold_contract"]);c["width_mm"]=value
            with self.assertRaises(ValueError):validate_contract(c)
        c=deepcopy(self.rows["R01"]["gold_contract"]);c["allow_ignore_drawing"]=True
        with self.assertRaises(ValueError):validate_contract(c)

    def test_drawing_and_bom_are_checked_even_when_requirements_pass(self):
        for name,prefix in (("R08","drawing:"),("R11","bom:")):
            r=self.rows[name];res=check(r["packet"],r["gold_contract"])
            self.assertTrue(any(x.startswith(prefix) for x in res["flags"]))


if __name__=="__main__":unittest.main()
