"""Plane-wave duct with lumped, damped Helmholtz side branches (SI internally).

Pressure / normalized volume-flow transfer matrices. Established equations:
https://pmc.ncbi.nlm.nih.gov/articles/PMC5469634/ equations 1, 2, 5.
The resistance is an ASSUMED damping-ratio parameter, not a calibrated loss law.
Matched acoustic terminations, rigid walls, no mean airflow or nonlinear effects.
"""
from copy import deepcopy
import numpy as np

RHO = 1.204
C = 343.0


def validate(design):
    diameter = float(design['duct_diameter_mm'])
    if not np.isfinite(diameter) or not 10 <= diameter <= 100:
        raise ValueError('Duct diameter must be 10–100 mm')
    cells = design['cells']
    if not isinstance(cells, list) or not 1 <= len(cells) <= 6:
        raise ValueError('One to six resonators required')
    previous = -1.
    for c in cells:
        for key, lo, hi in [('position_mm', 0, 1000), ('neck_radius_mm', 1, 10),
                            ('neck_length_mm', 2, 60), ('volume_cm3', 1, 150),
                            ('end_correction_radii', 0, 3), ('loss_factor', 0, 1)]:
            v = float(c[key])
            if not np.isfinite(v) or not lo <= v <= hi:
                raise ValueError(f'{key} outside model domain')
        if c['position_mm'] <= previous:
            raise ValueError('Positions must strictly increase')
        previous = c['position_mm']
    return design


def impedance(cell, frequency):
    radius = cell['neck_radius_mm'] * .001
    length = cell['neck_length_mm'] * .001 + cell['end_correction_radii'] * radius
    area = np.pi * radius ** 2
    volume = cell['volume_cm3'] * 1e-6
    mass = RHO * length / area
    compliance = volume / (RHO * C ** 2)
    omega = 2 * np.pi * np.asarray(frequency)
    resistance = cell['loss_factor'] * np.sqrt(mass / compliance)
    return resistance + 1j * (omega * mass - 1 / (omega * compliance))


def resonance_hz(cell):
    r = cell['neck_radius_mm'] * .001
    length = cell['neck_length_mm'] * .001 + cell['end_correction_radii'] * r
    return float(C / (2 * np.pi) * np.sqrt(np.pi * r * r / (length * cell['volume_cm3'] * 1e-6)))


def response(design, frequency):
    validate(design)
    f = np.atleast_1d(np.asarray(frequency, dtype=float))
    if f.ndim != 1 or not len(f) or not np.all(np.isfinite(f)) or np.min(f) <= 0:
        raise ValueError('Positive finite frequency vector required')
    # Circular rigid-duct first transverse-mode cutoff, conservatively restricted.
    cutoff = 1.841 * C / (np.pi * design['duct_diameter_mm'] * .001)
    if np.max(f) >= .8 * cutoff:
        raise ValueError('Frequency outside conservative plane-wave domain')
    z0 = RHO * C / (np.pi * (design['duct_diameter_mm'] * .0005) ** 2)
    matrix = np.tile(np.eye(2, dtype=complex), (len(f), 1, 1))
    previous = design['cells'][0]['position_mm']
    for cell in design['cells']:
        distance = (cell['position_mm'] - previous) * .001
        phase = 2 * np.pi * f * distance / C
        propagation = np.zeros_like(matrix)
        propagation[:, 0, 0] = propagation[:, 1, 1] = np.cos(phase)
        propagation[:, 0, 1] = propagation[:, 1, 0] = 1j * np.sin(phase)
        matrix = matrix @ propagation
        z = impedance(cell, f)
        # Exact lossless resonance uses the limiting zero-transmission solution.
        z = np.where(np.abs(z) < 1e-14*z0, 1e-14*z0 + 0j, z)
        shunt = np.tile(np.eye(2, dtype=complex), (len(f), 1, 1))
        shunt[:, 1, 0] = z0 / z
        matrix = matrix @ shunt
        previous = cell['position_mm']
    a, b, c, d = matrix[:, 0, 0], matrix[:, 0, 1], matrix[:, 1, 0], matrix[:, 1, 1]
    denominator = a + b + c + d
    transmitted = 2 / denominator
    reflected = (a + b - c - d) / denominator
    power_t, power_r = abs(transmitted)**2, abs(reflected)**2
    return {'frequency_hz': f, 'amplitude_t': transmitted, 'amplitude_r': reflected,
            'power_t': power_t, 'power_r': power_r, 'power_absorbed': 1-power_t-power_r,
            'transmission_loss_db': -10*np.log10(np.maximum(power_t, 1e-30)),
            'cutoff_hz': cutoff}


def wave_oracle(design, frequency):
    """Independent global wave-balance solve; no transfer-matrix cascade.

Four amplitudes per junction: a(left incident), b(left outgoing),
 c(right outgoing), d(right incident). Rebuilds each branch impedance.
"""
    validate(design)
    diameter = design['duct_diameter_mm'] / 1000
    z0 = 4*1.204*343/(np.pi*diameter**2)
    n = len(design['cells'])
    ts, rs = [], []
    for f in frequency:
        matrix = np.zeros((4*n, 4*n), complex)
        rhs = np.zeros(4*n, complex)
        for i, cell in enumerate(design['cells']):
            r = cell['neck_radius_mm']/1000
            effective_l = (cell['neck_length_mm'] + cell['end_correction_radii']*cell['neck_radius_mm'])/1000
            inertance = 1.204*effective_l/(np.pi*r*r)
            stiffness = 1.204*343**2/(cell['volume_cm3']*1e-6)
            z = cell['loss_factor']*np.sqrt(inertance*stiffness) + 1j*(2*np.pi*f*inertance-stiffness/(2*np.pi*f))
            trans = 2*z/(2*z+z0)
            refl = -z0/(2*z+z0)
            k = 4*i
            matrix[k, k+1], matrix[k, k], matrix[k, k+3] = 1, -refl, -trans
            matrix[k+1, k+2], matrix[k+1, k], matrix[k+1, k+3] = 1, -trans, -refl
            matrix[k+2, k] = 1
            if i == 0:
                rhs[k+2] = 1
            else:
                gap = (cell['position_mm']-design['cells'][i-1]['position_mm'])/1000
                matrix[k+2, k-2] = -np.exp(-2j*np.pi*f*gap/343)
            matrix[k+3, k+3] = 1
            if i < n-1:
                gap = (design['cells'][i+1]['position_mm']-cell['position_mm'])/1000
                matrix[k+3, k+5] = -np.exp(-2j*np.pi*f*gap/343)
        x = np.linalg.solve(matrix, rhs)
        ts.append(x[-2]); rs.append(x[1])
    return np.array(ts), np.array(rs)


def uncertainty_cases(design):
    """Seven declared samples, not a continuous worst-case guarantee."""
    cases = [('nominal', 0, 0, 1, 1.7, .04),
             ('low_tuning', -.15, .3, 1.05, 2.0, .04),
             ('high_tuning', .15, -.3, .95, 1.4, .04),
             ('low_loss', 0, 0, 1, 1.7, .02),
             ('high_loss', 0, 0, 1, 1.7, .08),
             ('low_tuning_high_loss', -.15, .3, 1.05, 2.0, .08),
             ('high_tuning_high_loss', .15, -.3, .95, 1.4, .08)]
    for name, dr, dl, vm, end, loss in cases:
        d = deepcopy(design)
        for cell in d['cells']:
            cell['neck_radius_mm'] += dr
            cell['neck_length_mm'] += dl
            cell['volume_cm3'] *= vm
            cell['end_correction_radii'] = end
            cell['loss_factor'] = loss
        yield name, d
