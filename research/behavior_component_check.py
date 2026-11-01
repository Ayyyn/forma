"""Independent nonlinear corotational-truss check; same ideal axial law, no FEA shell claim."""
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research.spatial_external_check import runtime
from behavior_design.linkage import primitive

def check(a,H,k,orientation,travel):
    ops=runtime();ops.wipe();ops.model('basic','-ndm',2,'-ndf',2)
    for n,x,y in [(1,-a,0.),(2,a,0.),(3,0.,orientation*H)]:ops.node(n,x,y)
    ops.fix(1,1,1);ops.fix(2,1,1);ops.fix(3,1,0);E=1000.;A=k*np.hypot(a,H)/E
    ops.uniaxialMaterial('Elastic',1,E)
    ops.element('corotTruss',1,1,3,float(A),1);ops.element('corotTruss',2,2,3,float(A),1)
    ops.timeSeries('Linear',1);ops.pattern('Plain',1,1);ops.load(3,0.,-1.)
    ops.constraints('Plain');ops.numberer('RCM');ops.system('BandGeneral');ops.test('NormUnbalance',1e-10,40);ops.algorithm('Newton');ops.integrator('DisplacementControl',3,2,-travel/100);ops.analysis('Static')
    status=ops.analyze(100)
    if status!=0:raise RuntimeError(f'OpenSees displacement-control failure: {status}')
    actual=float(ops.getLoadFactor(1));expected=float(primitive(a,H,k,0.,travel,orientation,False)[1]);links=[float(ops.eleResponse(n,'axialForce')[0]) for n in (1,2)];error=abs(actual-expected)
    return {'a_mm':a,'H_mm':H,'k_N_mm':k,'orientation':orientation,'travel_mm':travel,'opensees_force_N':actual,'analytic_force_N':expected,'error_N':error,'link_forces_N':links,'passed':error<1e-8}

def main():
    checks=[check(a,H,k,o,u) for a,H,k,o,us in [(20.,20.,1.,1,[5.,15.,20.,25.,35.,40.]),(19.,6.,2.8,-1,[1.,6.,12.]),(22.8,3.6,5.04,-1,[1.,5.,9.])] for u in us]
    report={'passed':all(c['passed'] for c in checks),'solver':'OpenSees corotTruss + Elastic, 100 displacement-control steps/case','version':runtime().version(),'maximum_force_error_N':max(c['error_N'] for c in checks),'checks':checks,'scope':'Independent code implementation of ideal bilateral axial springs, guided apex. Negative-slope points are imposed configurations, not freely stable states. Not physical validation. Linear return spring is verified separately by energy derivatives.','sources':['https://openseespydoc.readthedocs.io/en/latest/src/corotTruss.html','https://github.com/OpenSees/OpenSees/blob/master/SRC/element/truss/CorotTruss.cpp']}
    out=ROOT/'output/behavior-design';out.mkdir(parents=True,exist_ok=True);(out/'component-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='checks'}))
if __name__=='__main__':main()
