"""Adversarial audit: source-equation oracle, nonlinear constraints, polygon union, mutations."""
import copy
import json
import math
from pathlib import Path
import random
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import mpmath as mp
import numpy as np
from scipy.optimize import least_squares
from shapely.geometry import Polygon
from shapely.ops import unary_union
from continuum.geometry import Design, Requirements, evaluate, mesh, cell
from continuum.audit import audit_record


def main():
    rng=random.Random(20261027)
    mp.mp.dps=70
    high_precision_error=0.; constraint_residual=0.; max_overlap=0.; checked=0
    for index in range(40):
        gamma=rng.uniform(25,85); theta=rng.uniform(5,88)
        design=Design(columns=rng.randint(2,10),rows=rng.randint(2,6),a_mm=rng.uniform(5,80),b_mm=rng.uniform(5,160),gamma_deg=gamma)
        q=design.model_dump(); a,b=design.a_mm,design.b_mm
        g,t=mp.radians(mp.mpf(str(gamma))),mp.radians(mp.mpf(str(theta))); tangent=mp.cos(t)*mp.tan(g)
        ref=[mp.mpf(str(a))*mp.sqrt(1-mp.sin(t)**2*mp.sin(g)**2),mp.mpf(str(b))*tangent/mp.sqrt(1+tangent**2),
             mp.mpf(str(b))/mp.sqrt(1+tangent**2),mp.mpf(str(a))*mp.sin(t)*mp.sin(g)]
        actual=cell(design,theta)
        high_precision_error=max(high_precision_error,max(abs(float(v)-w)/max(1,abs(float(v))) for v,w in zip(ref,actual)))
        # Independently solve four distance/dot/projected-area constraints, without calling cell().
        c,s,ct=math.cos(math.radians(gamma)),math.sin(math.radians(gamma)),math.cos(math.radians(theta))
        def residual(x):
            l,h,v,spacing=x
            return [l*l+h*h-1,v*v+spacing*spacing-1,l*v-c,l*spacing-s*ct]
        solution=least_squares(residual,[.8,.5,.4,.8],bounds=(0,1.000001),xtol=1e-13,ftol=1e-13,gtol=1e-13,max_nfev=3000)
        err=max(abs(v) for v in residual(solution.x));constraint_residual=max(constraint_residual,err)
        if err>1e-9: raise AssertionError('Independent nonlinear constraint solver did not converge')
        independent=np.array([a*solution.x[0],b*solution.x[3],b*solution.x[2],a*solution.x[1]])
        np.testing.assert_allclose(independent,actual,rtol=1e-7,atol=1e-7)
        data=mesh(design,theta); points=np.array(data['vertices'])
        polygons=[Polygon(points[f,:2]) for f in data['faces']]
        overlap=sum(p.area for p in polygons)-unary_union(polygons).area
        max_overlap=max(max_overlap,abs(overlap))
        if abs(overlap)>1e-7: raise AssertionError('Projected facet interiors overlap')
        assert audit_record(evaluate(design,Requirements()),Requirements().model_dump())['passed']
        checked+=1
    base=evaluate(Design(),Requirements()); r=Requirements().model_dump()
    mutated=[]
    for label,edit in [
        ('missing_chevron_overhang',lambda x:x['metrics']['packed'].__setitem__('x_mm',x['metrics']['packed']['x_mm']-20)),
        ('unit_scale_error',lambda x:x['metrics']['deployed'].__setitem__('y_mm',x['metrics']['deployed']['y_mm']*10)),
        ('invented_material_area',lambda x:x['metrics'].__setitem__('material_area_mm2',100)),
        ('false_feasibility',lambda x:x.__setitem__('feasible',False)),
        ('wrong_crease_count',lambda x:x['metrics'].__setitem__('crease_segments',1)),
        ('wrong_constraint_flag',lambda x:x['constraints'][0].__setitem__('passed',False))]:
        bad=copy.deepcopy(base);edit(bad);detected=not audit_record(bad,r)['passed'];assert detected,label
        mutated.append({'mutation':label,'detected':detected})
    example=json.loads(Path('examples/verified-agent-run.json').read_text())
    example_audit=audit_record(example['selected'],example['requirements']);assert example_audit['passed']
    report={'status':'passed','random_designs_checked':checked,'seed':20261027,'mpmath_decimal_digits':70,
            'max_source_equation_relative_error':high_precision_error,'max_nonlinear_constraint_residual':constraint_residual,
            'max_projected_overlap_area_mm2':max_overlap,'mutation_checks':mutated,'original_demo_independent_audit':example_audit,
            'limits':['No physical specimen','No finite-thickness clearance, load or stability validation','Finite randomized numerical coverage supports but does not replace the domain proof'],
            'source':'https://doi.org/10.1073/pnas.1217998110'}
    out=Path('benchmarks/audit-geometry.json');out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
