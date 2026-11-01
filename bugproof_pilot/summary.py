"""Offline report: all cells, executed evidence, no model-judged success."""
from collections import Counter
import csv
import hashlib
import json
import numpy as np
from .__main__ import DIRECTORY,load,payload,dump
from .runtime import verify


def summarize():
    manifest=load();rows=[];totals={};usage=Counter();price=0.;replayed=0;ids=[]
    for method in manifest['methods']:
        rr=[]
        for case in manifest['cases']:
            for seed in manifest['seeds']:
                p=DIRECTORY/'runs'/f"{method}-{case['instance_id']}-{seed}.json"
                r=json.loads(p.read_text(encoding='utf-8'))
                if method=='meta':
                    expected=hashlib.sha256(json.dumps(payload(case,seed),sort_keys=True).encode()).hexdigest()
                    if r['request_sha256']!=expected:raise AssertionError('Public request drift')
                    if r.get('response_id'):ids.append(r['response_id'])
                    u=r['transport'].get('usage') or {};inp=u.get('prompt_tokens',0) or 0;out=u.get('completion_tokens',0) or 0
                    cached=(u.get('prompt_tokens_details') or {}).get('cached_tokens',0) or 0
                    reasoning=(u.get('completion_tokens_details') or {}).get('reasoning_tokens',0) or 0
                    usage.update(input_tokens=inp,output_tokens=out,cached_input_tokens=cached,reasoning_tokens=reasoning,
                                 requests=1,responses_with_usage=int(bool(u)),responses_with_reasoning=int(reasoning>0))
                    price+=((inp-cached)*1.25+cached*.15+out*4.25)/1e6
                if r.get('execution'):
                    rerun=verify(case,r['proposal']['tests']);saved=r['execution']
                    if rerun!=saved:raise AssertionError('Executed proof failed to replay: '+str(p))
                    replayed+=1
                if r['verified'] and not r.get('execution',{}).get('verified'):raise AssertionError('Unexecuted success claim')
                rr.append(r)
                rows.append({'method':method,'case':case['instance_id'],'seed':seed,'kind':case['kind'],
                             'verified':r['verified'],'control_correct':r.get('control_correct',False),
                             'seconds':r['elapsed_seconds'],'status':r.get('proposal',{}).get('status','invalid_output')})
        bugs=[r for r in rr if r['kind']=='real_bug'];controls=[r for r in rr if r['kind']=='missing_information']
        totals[method]={'real_issue_cells':len(bugs),'verified_cells':sum(r['verified'] for r in bugs),
            'distinct_issues_verified':len({r['case_id'] for r in bugs if r['verified']}),
            'control_cells':len(controls),'controls_correct':sum(r.get('control_correct',False) for r in controls),
            'median_seconds_per_cell':float(np.median([r['elapsed_seconds'] for r in rr])),
            'transport_received':sum(r.get('transport',{}).get('http_status')==200 for r in rr) if method=='meta' else None,
            'invalid_outputs':sum('proposal' not in r for r in rr)}
    a=totals['meta'];b=totals['literal_extraction']
    gates={'verified_at_least_12_of_16':a['verified_cells']>=12,'at_least_six_distinct_real_issues':a['distinct_issues_verified']>=6,
           'all_four_missing_information_controls_correct':a['controls_correct']==4,
           'at_least_four_more_verified_cells_than_literal':a['verified_cells']-b['verified_cells']>=4,
           'every_saved_execution_replayed':True}
    result={'capability_gate_passed':all(gates.values()),'gates':gates,'totals':totals,'usage':dict(usage),
            'estimated_reported_usage_usd':price,'provider_response_ids':ids,'distinct_provider_response_ids':len(set(ids)),
            'execution_cells_replayed':replayed,'manifest_sha256':hashlib.sha256((DIRECTORY/'manifest.json').read_bytes()).hexdigest(),
            'scope':'Small assisted capability pilot, not a competitive leaderboard or demonstrated commercial novelty. Historical public issues may be memorized; all upstream fixes/gold tests were hidden from model requests.'}
    (DIRECTORY/'summary.json').write_text(dump(result),encoding='utf-8')
    with (DIRECTORY/'cells.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(9,3.6),layout='constrained');names=['literal_extraction','meta']
    axes[0].bar(['Literal report rules','Meta'],[totals[n]['verified_cells'] for n in names],color=['#8c958e','#2b6c60'])
    axes[0].set(ylim=(0,16.8),ylabel='Executed red-before / green-after suites',title='8 historical issues × 2 seeds')
    axes[1].bar(['Literal report rules','Meta'],[totals[n]['controls_correct'] for n in names],color=['#8c958e','#2b6c60'])
    axes[1].set(ylim=(0,4.2),ylabel='Correct requests for missing information',title='2 underspecified reports × 2 seeds')
    fig.suptitle('Assisted unit-test generation pilot • limited baseline, not state of the art',fontsize=10)
    fig.savefig(DIRECTORY/'pilot.png',dpi=180);fig.savefig(DIRECTORY/'pilot.svg');plt.close(fig)
    print(dump({k:v for k,v in result.items() if k!='provider_response_ids'}))
