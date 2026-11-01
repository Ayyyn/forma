"""Constructed development brief, deliberately not an unseen efficacy task."""
from copy import deepcopy
import numpy as np
from .model import design,predict,evaluate

TEACHER=design('graded_series_parallel',[19.,6.,2.8,.015])
WITNESS=design('consolidated_graded_series',[19.,6.,2.8,.015])

def tasks():
    grid=np.linspace(0,12,17);truth=predict(TEACHER,grid)
    base={'id':'initial','title':'Soft start, progressive resistance','stroke_mm':12.,'maximum_width_mm':100.,'maximum_height_mm':75.,'minimum_tangent_N_mm':.005,'maximum_link_travel_mm':8.,'maximum_link_force_N':20.,'maximum_normalized_RMS_error':.05,'maximum_normalized_max_error':.10,'fit_travel_mm':grid.tolist(),'target_travel_mm':grid.tolist(),'target_force_N':[p['force_N'] for p in truth],'source':'Constructed, known-feasible development target from ideal linkage mechanics. Not experimental data or an unseen efficacy benchmark. Target generator is withheld from controller context, not from reproducibility artifacts.','application':'Generic passive resistance cartridge; no medical or safety-critical qualification.'}
    revision=deepcopy(base);revision.update(id='compact_revision',title='Same resistance, half the packaging width',maximum_width_mm=50.,maximum_height_mm=30.)
    return [base,revision]

def reference():
    initial,revision=tasks();assert evaluate(TEACHER,initial)['target_passed'];assert evaluate(WITNESS,revision)['target_passed']
    grid=(np.arange(96)+.5)*12/96
    return {'target_generator':TEACHER,'compact_feasibility_witness':WITNESS,'heldout_travel_mm':grid.tolist(),'heldout_target_force_N':[p['force_N'] for p in predict(TEACHER,grid)],'scope':'Known constructed target and algebraically equivalent parallel-spring consolidation. Established mechanics, not AI-invented topology. No claim of broad search coverage.'}

def audit_task(task,ref):
    t=deepcopy(task);t['fit_travel_mm']=ref['heldout_travel_mm'];t['target_travel_mm']=ref['heldout_travel_mm'];t['target_force_N']=ref['heldout_target_force_N'];return t
