import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from continuum.geometry import Design, Requirements
from continuum.server import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_search_inspect_export_workflow(self):
        result = self.client.post('/api/search', json={'requirements': Requirements().model_dump(), 'count': 128})
        self.assertEqual(result.status_code, 200)
        data = result.json()
        candidates = [c for c in data['candidates'] if c['feasible']]
        self.assertTrue(candidates)
        self.assertIn('preview', candidates[0])
        chosen = candidates[0]['design']
        inspected = self.client.post('/api/inspect', json={'design': chosen}).json()
        self.assertTrue(inspected['validation']['passed'])
        self.assertEqual(len(inspected['frames']), 81)
        self.assertEqual(inspected['candidate']['design'], chosen)
        exported = self.client.post('/api/export', json={'design': chosen, 'format':'fold'}).json()
        self.assertEqual(exported['vertices_coords'], inspected['flat_mesh']['vertices'])

    def test_invalid_api_design_rejected(self):
        design = Design().model_dump()
        design['packed_theta_deg'] = 90
        self.assertEqual(self.client.post('/api/inspect',json={'design':design}).status_code,422)

    def test_api_defaults_to_single_pass(self):
        with patch('continuum.server.run_agent',return_value={'status':'test_only'}) as run:
            result=self.client.post('/api/agent',json={})
        self.assertEqual(result.status_code,200)
        self.assertEqual(run.call_args.args[3],'single_pass')
        self.assertEqual(self.client.get('/api/defaults').json()['planning_mode'],'single_pass')

    def test_frontend_and_secrets_not_served(self):
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/.env').status_code,404)
        self.assertEqual(self.client.get('/api/runs/not-a-run').status_code,404)
        health = self.client.get('/api/health').json()
        self.assertTrue(all(type(v) is bool for v in health['providers'].values()))


if __name__ == '__main__':
    unittest.main()
