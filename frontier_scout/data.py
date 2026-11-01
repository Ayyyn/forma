"""A reveal-only interface to grouped historical experimental measurements."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
VENDOR=ROOT/'research/frontier_scout/vendor/pv-benchmark'
CASES={
 'crossed_barrel':{'file':'Crossed barrel_dataset.csv','direction':1,'units':'J','description':'Maximize mean measured compressive toughness of historically 3D-printed crossed barrels. Two circular platforms are joined by n hollow columns, outer radius r mm and wall thickness t mm, twisted by theta degrees. Toughness is integrated compression force-displacement energy; contact/buckling/print defects make simple stiffness formulas insufficient. No new specimens are printed here.','doi':'10.1126/sciadv.aaz1708'},
 'printing':{'file':'AutoAM_dataset.csv','direction':1,'units':'published shape score','description':'Maximize a published print-shape score by selecting prime delay, print speed, X/Y offset correction. The original dataset concerns autonomous additive-manufacturing calibration. Feature names have no additional verified units here. No new printing is performed.','doi':'10.1557/s43577-021-00051-1'},
 'perovskite':{'file':'Perovskite_dataset.csv','direction':-1,'units':'published instability index','description':'Minimize published instability index in a CsPbI/FAPbI/MAPbI composition mixture. The features are composition fractions. This is a fixed historical table, not a stability/lifetime prediction for a new composition or a chemistry synthesis system.','doi':'10.1016/j.matt.2021.01.008'}
}

class Dataset:
 def __init__(self,name):
    self.name=name;self.info=CASES[name];path=VENDOR/'datasets'/self.info['file'];df=pd.read_csv(path)
    if not all(pd.api.types.is_numeric_dtype(df[c]) for c in df) or not np.isfinite(df.to_numpy()).all():raise ValueError('Nonfinite/nonnumeric raw data')
    self.features=list(df.columns[:-1]);self.outcome=df.columns[-1];groups=df.groupby(self.features,sort=True,dropna=False)[self.outcome].agg(['mean','std','count']).reset_index()
    # Randomize pool order before policies see it; original row order is not a feature.
    order=np.random.default_rng(3010202601).permutation(len(groups));groups=groups.iloc[order].reset_index(drop=True)
    self.X=groups[self.features].to_numpy(float);self._means=groups['mean'].to_numpy(float);self._variance=groups['std'].fillna(0).to_numpy(float)**2;self._counts=groups['count'].to_numpy(int)
    self.ids=[hashlib.sha256(json.dumps(row.tolist()).encode()).hexdigest()[:12] for row in self.X];self.raw_rows=len(df);self.sha256=hashlib.sha256(path.read_bytes()).hexdigest()
    if len(set(self.ids))!=len(self.ids):raise ValueError('Repeated feature groups')
 def observe(self,index):
    return {'index':int(index),'id':self.ids[index],'x':self.X[index].tolist(),'mean':float(self._means[index]),'sample_variance':float(self._variance[index]),'historical_replicates':int(self._counts[index])}
 def public(self):
    return {'name':self.name,'description':self.info['description'],'features':self.features,'outcome':self.outcome,'direction':'maximize' if self.info['direction']==1 else 'minimize','units':self.info['units'],'pool_design_groups':len(self.X),'ranges':[[float(a),float(b)] for a,b in zip(self.X.min(0),self.X.max(0))],'replay_scope':'An observation reveals the historical group mean/variance/count. Equal design-group query budgets are not always equal historical replicate counts. No physical experiments are performed.'}
 def score(self,history):
    y=self.info['direction']*self._means;best=np.maximum.accumulate([self.info['direction']*h['mean'] for h in history]);span=max(float(np.ptp(y)),1e-12);regret=(y.max()-best)/span;top=np.quantile(y,.95)
    return {'normalized_regret':regret.tolist(),'post_initial_mean_regret':float(np.mean(regret[8:])),'best_group_mean':float(history[int(np.argmax([self.info['direction']*h['mean'] for h in history]))]['mean']),'top5_first_query':next((i+1 for i,b in enumerate(best) if b>=top),None),'top5_groups_found':int(sum(self.info['direction']*h['mean']>=top for h in history)),'revealed_design_groups':len(history),'revealed_historical_rows':sum(h['historical_replicates'] for h in history),'global_best_pool_group_mean':float(self.info['direction']*y.max())}

def audit():
    rows={}
    for name in CASES:
        d=Dataset(name);rows[name]={**d.public(),'raw_rows':d.raw_rows,'replicate_counts':{str(int(n)):int(sum(d._counts==n)) for n in np.unique(d._counts)},'sha256':d.sha256}
    return rows
