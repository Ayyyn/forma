import unittest
from continuum.geometry import Design, dimensions
from continuum.measurements import compare_measurement


class PaperMeasurementContracts(unittest.TestCase):
    def setUp(self):
        self.design = Design()
        self.row = {'design_id': 'sample', 'state': 'partial', 'trial': '1', 'x_mm': '', 'y_mm': '', 'h_mm': ''}

    def test_blanks_never_become_observations(self):
        self.assertEqual(compare_measurement(self.design, 'sample', self.row)['status'], 'unmeasured')

    def test_inferred_height_is_not_scored_as_an_independent_prediction(self):
        # Synthetic fixture only. Actual measurement CSV remains blank.
        d = dimensions(self.design, 45)
        row = {**self.row, 'x_mm': str(d['x_mm'] + 2), 'y_mm': str(d['y_mm'] - 1), 'h_mm': str(d['z_mm'])}
        report = compare_measurement(self.design, 'sample', row)
        self.assertAlmostEqual(report['theta_deg'], 45)
        self.assertNotIn('z_mm', report['residuals'])
        self.assertAlmostEqual(report['residuals']['x_mm']['signed_residual_mm'], 2)
        row['theta_measured_deg'] = '45'
        self.assertIn('z_mm', compare_measurement(self.design, 'sample', row)['residuals'])

    def test_invalid_or_mismatched_readings_are_preserved_as_rejections(self):
        for changes in ({'design_id': 'other'}, {'x_mm': '200'},
                        {'x_mm': 'nan', 'y_mm': '100', 'h_mm': '15'},
                        {'x_mm': '200', 'y_mm': '100', 'h_mm': '50'},
                        {'x_mm': '200', 'y_mm': '100', 'h_mm': '15', 'theta_measured_deg': '90'}):
            with self.subTest(changes=changes):
                self.assertEqual(compare_measurement(self.design, 'sample', {**self.row, **changes})['status'], 'rejected')


if __name__ == '__main__':unittest.main()
