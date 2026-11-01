"""Compare observed paper dimensions with ideal geometry, without inventing observations."""
import math
from .geometry import Design, dimensions


def compare_measurement(design: Design, design_id: str, row: dict):
    result = {'state': row.get('state'), 'trial': row.get('trial'), 'status': 'unmeasured'}
    if row.get('design_id') != design_id:
        return {**result, 'status': 'rejected', 'reason': 'Design ID does not match the print manifest'}
    raw = [str(row.get(key, '')).strip() for key in ('x_mm', 'y_mm', 'h_mm')]
    if not any(raw):
        return result
    try:
        observed = dict(zip(('x_mm', 'y_mm', 'z_mm'), map(float, raw)))
        if not all(math.isfinite(v) and v >= 0 for v in observed.values()):
            raise ValueError('Dimensions must be finite and nonnegative')
        if not observed['x_mm'] or not observed['y_mm']:
            raise ValueError('Outside X and Y extents must be positive')
        angle_text = str(row.get('theta_measured_deg', '')).strip()
        if angle_text:
            theta = float(angle_text)
            mode = 'independently_measured_angle'
            compared_axes = ('x_mm', 'y_mm', 'z_mm')
        else:
            limit = design.a_mm * math.sin(math.radians(design.gamma_deg))
            if observed['z_mm'] >= limit:
                raise ValueError('Observed H exceeds the supported ideal-height range; retain the reading and inspect thickness, orientation and distortion')
            theta = math.degrees(math.asin(observed['z_mm'] / limit))
            mode = 'angle_inferred_from_H_conditional_XY_only'
            compared_axes = ('x_mm', 'y_mm')
        predicted = dimensions(design, theta)
        residuals = {axis: {'observed_mm': observed[axis], 'predicted_mm': predicted[axis],
                            'signed_residual_mm': observed[axis] - predicted[axis],
                            'relative_residual': (observed[axis] - predicted[axis]) / predicted[axis]
                            if predicted[axis] else None} for axis in compared_axes}
        return {**result, 'status': 'compared', 'comparison_mode': mode, 'theta_deg': theta,
                'observed': observed, 'ideal_prediction': predicted, 'residuals': residuals,
                'physical_validation': 'No automatic pass/fail; assess recorded measurement uncertainty and model limitations'}
    except (TypeError, ValueError) as exc:
        return {**result, 'status': 'rejected', 'reason': str(exc)}
