import importlib.util,json,tempfile,unittest
from pathlib import Path
import numpy as np

@unittest.skipUnless(importlib.util.find_spec('cadquery') and importlib.util.find_spec('trimesh'),'Use the isolated CAD runtime')
class FabricationExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fabrication_export.panels import export_kit
        parent=Path(__file__).resolve().parents[1]/'output'/'cad-test-temp';parent.mkdir(parents=True,exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='cad-export-test-',dir=parent);cls.destination=Path(cls.temp.name)/'kit'
        cls.source={'kind':'triangular_panel_kit','vertices_mm':[[1,2,3],[4,6,3],[1,2,8],[0,0,0],[3,0,0],[0,4,0]],'triangles':[[0,1,2],[3,4,5]],'provenance':{'scope':'synthetic test triangles'}}
        cls.result=export_kit(cls.source,cls.destination,thickness=1.2,columns=2)
        from fabrication_export.display import export_display
        cls.static=export_display({'kind':'triangular_panel_kit','vertices_mm':[[0,0,0],[10,0,0],[0,10,0],[0,0,10]],'triangles':[[0,1,2],[0,3,1]],'provenance':{'scope':'synthetic joined-panel reference'},'source_state':{}},Path(cls.temp.name)/'display')
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_all_formats_round_trip_and_preserve_solid_count(self):
        r=self.result;self.assertTrue(r['geometry_checks_passed']);self.assertEqual(r['parts_count'],2)
        for format,check in r['assembly']['checks'].items():self.assertTrue(check['passed'],format)
        for format in ['stl','obj']:self.assertEqual(r['assembly']['checks'][format]['connected_components'],2)
    def test_independent_triangle_area_sets_exact_solid_volume(self):
        # Triangle1 has orthogonal legs 5,5; triangle2 has legs3,4.
        expected=(12.5+6)*1.2;self.assertAlmostEqual(self.result['assembly']['volume_mm3'],expected,places=8)
    def test_triangle_mapping_preserves_three_spatial_vertices(self):
        from fabrication_export.panels import flatten_triangle
        original=np.array(self.source['vertices_mm'][:3]);flat,transform,error=flatten_triangle(original,1.2)
        homogeneous=np.column_stack([flat,np.full(3,.6),np.ones(3)]);reconstructed=(transform@homogeneous.T).T[:,:3]
        np.testing.assert_allclose(reconstructed,original,atol=1e-10);self.assertLess(error,1e-10)
    def test_open_surface_is_rejected_as_print_solid(self):
        import trimesh
        from fabrication_export.panels import check_mesh
        mesh=trimesh.Trimesh(vertices=[[0,0,0],[1,0,0],[0,1,0]],faces=[[0,1,2]])
        with self.assertRaises(ValueError):check_mesh(mesh,np.array([[0,0,0],[1,1,0]]),1.,1)
    def test_degenerate_triangle_rejected(self):
        from fabrication_export.panels import flatten_triangle
        with self.assertRaises(ValueError):flatten_triangle([[0,0,0],[1,0,0],[2,0,0]],1.)
    def test_existing_export_is_preserved(self):
        from fabrication_export.panels import export_kit
        with self.assertRaises(ValueError):export_kit(self.source,self.destination)
    def test_fractional_face_index_is_not_silently_truncated(self):
        from fabrication_export.panels import export_kit
        bad={**self.source,'triangles':[[0,1.5,2]]}
        with self.assertRaisesRegex(ValueError,'integers'):export_kit(bad,Path(self.temp.name)/'invalid')
    def test_print_scope_remains_explicit(self):
        self.assertEqual(self.result['printer_profile'],'unconfirmed');self.assertIn('NOT a validated folding assembly',self.result['mechanical_status'])
        self.assertTrue((self.destination/'stl-bundle.zip').exists());self.assertTrue((self.destination/'step-bundle.zip').exists())
    def test_fused_display_is_one_valid_round_trip_solid(self):
        r=self.static;self.assertEqual(r['parts_count'],1);self.assertTrue(r['geometry_checks_passed'])
        self.assertGreater(r['overlap_volume_removed_mm3'],0.);self.assertAlmostEqual(r['assembly']['bounds_mm'][0][2],0.,places=8)
        self.assertIn('RIGID STATIC DISPLAY',r['mechanical_status'])
        for check in r['assembly']['checks'].values():self.assertTrue(check['passed'])
    def test_disconnected_panels_are_rejected_as_one_display(self):
        from fabrication_export.display import export_display
        source={'kind':'triangular_panel_kit','vertices_mm':[[0,0,0],[10,0,0],[0,10,0],[50,0,0],[60,0,0],[50,10,0]],'triangles':[[0,1,2],[3,4,5]],'source_state':{},'provenance':{}}
        with self.assertRaisesRegex(ValueError,'exactly one'):export_display(source,Path(self.temp.name)/'disconnected')

if __name__=='__main__':unittest.main()
