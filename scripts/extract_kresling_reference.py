"""Extract Figure 5A reference geometry from the author PDF, without importing our model.

Requires pypdf only for this one-time source extraction. Committed reference data
are sufficient to run the scientific proof later.
"""
import argparse
import hashlib
import json
from pathlib import Path
from pypdf import PdfReader
from pypdf.generic import ContentStream


def multiply(p, q):
    a,b,c,d,e,f=p; A,B,C,D,E,F=q
    return (a*A+c*B,b*A+d*B,a*C+c*D,b*C+d*D,a*E+c*F+e,b*E+d*F+f)


def filled_paths(pdf):
    reader=PdfReader(pdf)
    form=reader.pages[7]['/Resources']['/XObject']['/Im7'].get_object()
    matrix=(1,0,0,1,0,0); color=(0,0,0); stack=[]; paths=[]; points=[]; subpaths=[]
    def point(x,y):
        a,b,c,d,e,f=matrix
        return (a*x+c*y+e,b*x+d*y+f)
    for args,op in ContentStream(form,reader).operations:
        if op==b'q':stack.append((matrix,color))
        elif op==b'Q':matrix,color=stack.pop()
        elif op==b'cm':matrix=multiply(matrix,tuple(map(float,args)))
        elif op==b'rg':color=tuple(map(float,args))
        elif op==b'm':
            if points:subpaths.append(points)
            points=[point(*map(float,args))]
        elif op==b'l':points.append(point(*map(float,args)))
        elif op==b'c':
            # None of the selected line-chart curves use cubic segments.
            points.extend(point(float(args[j]),float(args[j+1])) for j in (0,2,4))
        elif op==b're':
            x,y,w,h=map(float,args)
            if points:subpaths.append(points)
            points=[point(x,y),point(x+w,y),point(x+w,y+h),point(x,y+h)]
        elif op in (b'f',b'f*',b'n',b'S'):
            if points:subpaths.append(points)
            all_points=[p for path in subpaths for p in path]
            if all_points:
                xs,ys=zip(*all_points)
                paths.append({'index':len(paths),'color':color,'bounds':[min(xs),max(xs),min(ys),max(ys)],'subpaths':subpaths})
            points=[];subpaths=[]
    return paths


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf',type=Path)
    parser.add_argument('--inspect',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    paths=filled_paths(args.pdf)
    if args.inspect:
        for path in paths:
            x0,x1,y0,y1=path['bounds']
            if 20<x0<35 and 108<x1<125 and 160<y0<180 and 250<y1<270:
                print({k:v for k,v in path.items() if k!='subpaths'})
        return
    # Filled dashed line of the k_r=0.005 trace, Figure 5A-left. The exact RGB
    # and panel coordinates refer to the frozen PDF hash below, not model output.
    selected=[]
    for path in paths:
        x0,x1,y0,y1=path['bounds']
        if path['color']==(0.70196,0.40392,0.6902) and 26<x0<117 and x1<117 and y0>168 and y1<215:
            selected.extend(path['subpaths'])
    # Axis calibration is from the PDF's gray gridline center coordinates.
    x_origin,x_end=26.385,115.95
    y_origin,y_end=168.7735,258.3385
    samples=[]
    for j in range(10,131,2):
        target=j/100
        x=x_origin+(x_end-x_origin)*target/1.4
        crossings=[]
        for polygon in selected:
            for a,b in zip(polygon,polygon[1:]+polygon[:1]):
                if min(a[0],b[0])<=x<max(a[0],b[0]) and b[0]!=a[0]:
                    crossings.append(a[1]+(x-a[0])*(b[1]-a[1])/(b[0]-a[0]))
        # Skip dash gaps, overlapping outlines and marker occlusion. Selection
        # depends only on the source drawing, never on a predicted curve.
        if len(crossings)>=2 and max(crossings)-min(crossings)<0.8:
            y=(max(crossings)+min(crossings))/2
            samples.append({'u_over_r':target,'U_over_ks_r':(y-y_origin)/(y_end-y_origin)*.014})
    if len(samples)<12:raise RuntimeError('Insufficient unambiguous source samples')
    record={'doi':'10.1016/j.jmps.2024.105630','page':8,'figure':'5A-left',
            'trace':'k_r=0.005','source_pdf_sha256':hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
            'extraction':'filled vector-ribbon centerlines; no model imported',
            'axis_pdf_points':{'x_origin':x_origin,'x_end':x_end,'y_origin':y_origin,'y_end':y_end},
            'plot_ranges':{'u_over_r':[0,1.4],'U_over_ks_r':[0,.014]},
            'estimated_reading_uncertainty_U_over_ks_r':0.00012,
            'acceptance_nrmse_full_vertical_range':0.02,
            'samples':samples}
    if not args.output:raise SystemExit('--output required')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('Frozen source points:',len(samples),'at',args.output)
    print(json.dumps(samples[::5]))


if __name__=='__main__':main()
