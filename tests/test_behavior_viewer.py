import json,unittest
from pathlib import Path
from fastapi.testclient import TestClient
from behavior_design.server import app

class BehaviorViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.client=TestClient(app)
    def test_study_includes_real_receipts_and_preserves_failed_policy(self):
        report=self.client.get('/api/study').json();self.assertEqual(len(report['runs']),6);self.assertEqual(report['verification']['actual_Meta_calls'],8);self.assertTrue(report['verification']['archived_source_hashes_match']);failed=next(r for r in report['runs'] if r['id']=='compact_revision-single_pass');self.assertIsNone(failed['audit']);self.assertEqual(failed['candidate_queries'],0);self.assertEqual(failed['receipt']['actual_API_calls'],1)
    def test_raw_and_derived_denominator_correction_are_explicit(self):
        report=self.client.get('/api/study').json();ref=report['reference'];M=ref['points'][-1]['force_N']
        for r in report['runs']:
            if not r['audit']:continue
            a=r['audit']['heldout'];self.assertIn('raw_RMS_normalized_by_heldout_maximum',a);self.assertGreaterEqual(a['raw_RMS_normalized_by_heldout_maximum'],a['normalized_RMS_error']);raw=self.client.get('/api/raw/'+r['id']).json();self.assertEqual(raw['audit']['heldout']['normalized_RMS_error'],a['raw_RMS_normalized_by_heldout_maximum'])
    def test_manual_edits_preserve_bounds_and_independently_check_response(self):
        response=self.client.post('/api/evaluate',json={'task_id':'compact_revision','architecture':'consolidated_graded_series','parameters':[19.,6.,2.8,.015]});self.assertEqual(response.status_code,200);r=response.json();self.assertTrue(r['independent']['passed']);self.assertTrue(r['result']['target_passed']);self.assertFalse(r['result']['physical_validation']);self.assertIn('interpolation',r['source']);self.assertTrue((Path('output/behavior-design/explorations')/(r['id']+'.json')).exists())
        bad=self.client.post('/api/evaluate',json={'task_id':'compact_revision','architecture':'graded_series_parallel','parameters':[19.,6.,2.8,.015]});self.assertEqual(bad.status_code,422)
    def test_credential_and_unrecognized_paths_are_not_served(self):
        for url in ['/assets/../.env','/vendor/.env','/plot/.env','/api/raw/not-a-run','/api/candidate/initial-numerical/bad']:
            self.assertEqual(self.client.get(url).status_code,404)
    def test_manual_schema_cannot_relax_frozen_requirements(self):
        response=self.client.post('/api/evaluate',json={'task_id':'compact_revision','architecture':'single_hardening','parameters':[20.,5.,2.,.02],'maximum_width_mm':1000});self.assertEqual(response.status_code,422)
