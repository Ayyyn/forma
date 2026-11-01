"""Render a three-page, actual-size A4 paper trial pack from the computed manifest."""
import json,math
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor,Color
from reportlab.lib.utils import simpleSplit
from reportlab.lib.units import mm

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'output/paper/paper-model.json').read_text(encoding='utf-8'))
out=ROOT/'output/pdf/paper-model-print-pack.pdf';out.parent.mkdir(parents=True,exist_ok=True)
c=canvas.Canvas(str(out),pagesize=(297*mm,210*mm))
c.setTitle('Design Continuum - Paper trial '+data['design_id'])
c.setAuthor('Design Continuum')
INK=HexColor('#29352c');M=HexColor('#a23f29');V=HexColor('#246885');GREEN=HexColor('#536849');MUTED=HexColor('#6b7467')
W,H=297*mm,210*mm

def text(x,y,value,size=9,color=INK,font='Helvetica'):
    c.setFillColor(color);c.setFont(font,size);c.drawString(x*mm,y*mm,value)

def paragraph(x,y,value,width=82,size=9,leading=4.3):
    for line in simpleSplit(value,'Helvetica',size,width*mm):
        text(x,y,line,size);y-=leading
    return y

def header(number,title,subtitle):
    text(14,196,'DESIGN CONTINUUM / PAPER TRIAL',8,MUTED,'Helvetica-Bold')
    text(14,185,title,20,INK,'Helvetica-Bold')
    text(14,177,subtitle,9,MUTED)
    text(232,196,f'{number} / 3   ID {data["design_id"]}',8,MUTED)

def footer(number):
    text(14,7,'Computed geometry; physical folding and measurements pending. Keep this design ID with every measurement.',7,MUTED)
    text(272,7,f'{number} / 3',7,MUTED)

def pose(x,y,width,height,item,label):
    points=item['mesh']['vertices'];faces=item['mesh']['faces']
    mins=[min(p[i] for p in points) for i in range(3)];maxs=[max(p[i] for p in points) for i in range(3)]
    center=[(a+b)/2 for a,b in zip(mins,maxs)]
    yaw,elev=-.55,.72;ca,sa=math.cos(yaw),math.sin(yaw);ce,se=math.cos(elev),math.sin(elev)
    projected=[]
    for p in points:
        a,b,z=[p[i]-center[i] for i in range(3)];rx=a*ca-b*sa;ry=a*sa+b*ca
        projected.append([rx,se*ry-ce*z,-ce*ry+se*z])
    sx=max(p[0] for p in projected)-min(p[0] for p in projected)
    sy=max(p[1] for p in projected)-min(p[1] for p in projected)
    scale=min(width/max(sx,1),height/max(sy,1))*.90*mm
    for index,face in sorted(enumerate(faces),key=lambda pair:sum(projected[i][2] for i in pair[1])/4):
        path=c.beginPath()
        for k,i in enumerate(face):
            px=(x+width/2)*mm+projected[i][0]*scale;py=(y+height/2)*mm-projected[i][1]*scale
            path.moveTo(px,py) if not k else path.lineTo(px,py)
        path.close();c.setFillColor(HexColor('#e2e8d7') if index%2 else HexColor('#f1f3e9'));c.setStrokeColor(GREEN);c.setLineWidth(.35);c.setDash();c.drawPath(path,fill=1,stroke=1)
    text(x,y-3,label,9,INK,'Helvetica-Bold')
    d=item['dimensions'];text(x,y-8,f'{d["x_mm"]:.1f} x {d["y_mm"]:.1f} x {d["z_mm"]:.1f} mm',8,MUTED)

# Page 1: exact-size vector crease pattern. No fit-to-page transform.
text(14,197,'PRINT / 001',17,INK,'Helvetica-Bold')
text(69,198,f'PATTERN {data["design_id"].upper()}   |   {data["design"]["columns"]} columns x {data["design"]["rows"]} rows',9,MUTED)
text(14,189,'A4 LANDSCAPE - Actual size / 100% - Print this page only to make the model.',9,INK,'Helvetica-Bold')
text(14,183,'BLACK solid = cut border only. RED dash-dot / M = mountain. BLUE dashed / V = valley. Printed side faces you.',8,MUTED)
flat=data['metrics']['flat'];ox=(297-flat['x_mm'])/2;oy=27
if flat['x_mm']>269 or flat['y_mm']>151.9:raise ValueError('This fixed A4 layout needs a larger-page layout for the selected pattern')
for edge,assignment in zip(data['flat_mesh']['edges'],data['assignments']):
    p,q=[data['flat_mesh']['vertices'][i] for i in edge['vertices']]
    c.setStrokeColor({'B':INK,'M':M,'V':V,'F':MUTED}[assignment]);c.setLineWidth((.30 if assignment=='B' else .18)*mm)
    c.setDash([4*mm,1.1*mm,.6*mm,1.1*mm] if assignment=='M' else [2*mm,1.3*mm] if assignment=='V' else [])
    c.line((ox+p[0])*mm,(oy+p[1])*mm,(ox+q[0])*mm,(oy+q[1])*mm)
    if assignment in ('M','V'):
        dx,dy=q[0]-p[0],q[1]-p[1];length=math.hypot(dx,dy)
        x=ox+(p[0]+q[0])/2-dy/length*1.15;y=oy+(p[1]+q[1])/2+dx/length*1.15
        text(x,y,assignment,5.8,{'M':M,'V':V}[assignment],'Helvetica-Bold')
c.setDash()
for j in range(data['design']['rows']):
    text(ox-8,oy+(j+.5)*flat['y_mm']/data['design']['rows'],chr(65+j),7,MUTED,'Helvetica-Bold')
for i in range(data['design']['columns']):text(ox+(i+.5)*data['design']['a_mm']-1,oy-4,str(i+1),6,MUTED)
text(ox,oy+flat['y_mm']+1.5,'Y up  /  X right  /  CUT OUT THE ENTIRE CONNECTED SHEET',6.5,MUTED)
c.setStrokeColor(INK);c.setLineWidth(.6);c.line(16*mm,16*mm,116*mm,16*mm)
for x in (16,116):c.line(x*mm,14*mm,x*mm,18*mm)
text(43,19,'100 mm horizontal scale',8,INK,'Helvetica-Bold')
c.line(284*mm,70*mm,284*mm,120*mm)
for y in (70,120):c.line(282*mm,y*mm,286*mm,y*mm)
c.saveState();c.translate(289*mm,78*mm);c.rotate(90);c.setFillColor(INK);c.setFont('Helvetica-Bold',8);c.drawString(0,0,'50 mm vertical scale');c.restoreState()
text(130,17,'Check both bars with a ruler BEFORE cutting.',8,INK,'Helvetica-Bold')
text(130,12,'Suggested print gate: 100 mm bar within 1 mm; otherwise reprint at actual size.',7,MUTED)
footer(1);c.showPage()

# Page 2: original computed illustrations and practical first-trial instructions.
header(2,'FOLD / guide the creases together','Use ordinary thin printer paper for the first trial. Record the actual paper you use; the model assigns no material properties.')
steps=[('1  CUT + ORIENT',
 'Check the scale bars, then cut only the black outside border. Keep the sheet connected. Do not cut any interior line. Lay the printed face upwards. X runs along the numbered columns; Y runs from row A towards the last row.'),
 ('2  PRECREASE EACH SEGMENT',
 'Red M is a raised ridge viewed from the printed face. Blue V is a depressed trough. Use a ruler and fingers to make a shallow crease along each straight segment, then reopen it. Stop at each junction: a kinked zigzag is not one straight fold. Work a band at a time.'),
 ('3  GATHER, DO NOT FORCE',
 'Bring the left and right edges slowly closer together, nudging marked ridges up and troughs down. Let the top and bottom edges move too. Several creases must move together. If a corner jams, reopen slightly and inspect its M/V signs. Avoid forcing one corner fully flat while the rest stays open.')]
for x,(title,body) in zip((14,106,198),steps):
    text(x,162,title,10,INK,'Helvetica-Bold');paragraph(x,154,body,84,9,4.5)
text(14,102,'WHAT THE MOTION SHOULD LOOK LIKE',8,MUTED,'Helvetica-Bold')
for x,item,label in zip((14,106,198),data['poses'],('Deployed reference / 8 deg','Practice partial fold / 45 deg',f'Packed reference / {data["design"]["packed_theta_deg"]:.1f} deg')):
    pose(x,39,84,55,item,label)
paragraph(14,19,'These are computed views, not photographs. This exact paper folding sequence has not been physically tested here. Start with a comfortable partial fold; a failed first attempt is useful evidence.',268,8,4)
footer(2);c.showPage()

# Page 3: instructions + deliberately empty observation cells.
header(3,'MEASURE / record the real paper','Begin at a stable partial fold. Repeat readings without changing the pose, then try the packed state gently.')
text(14,163,'Sample ID: '+data['design_id']+'    Paper / gsm: __________________    Date: ______________    Ruler resolution: ______ mm',9)
text(14,155,'Print calibration observed: horizontal bar ______ mm (target 100); vertical bar ______ mm (target 50).',9)
paragraph(14,144,'Measure the entire outside X extent, including zigzag overhangs, then the outside Y extent. From the side, measure H from the table to the highest crest while the lowest troughs rest on the table. Record actual readings, not the prediction. H includes paper thickness, which this ideal model does not account for.',132,9,4.4)
paragraph(154,144,'An angle measurement is optional. If you know facet inclination, compare all three dimensions at that angle. Otherwise, the comparison script infers an ideal angle from H and checks X/Y conditionally. H is then an input, not an independent successful prediction.',129,9,4.4)
table_top=108;xs=[14,44,62,90,121,152,184,283]
headers=['State','Trial','X (mm)','Y (mm)','H (mm)','Angle, if known','Notes / uncertainty']
c.setStrokeColor(HexColor('#bbc5b3'));c.setLineWidth(.5)
for x in xs:c.line(x*mm,48*mm,x*mm,table_top*mm)
for y in [108,99,90.5,82,73.5,65,56.5,48]:c.line(14*mm,y*mm,283*mm,y*mm)
for x,label in zip(xs,headers):text(x+2,102,label,8,INK,'Helvetica-Bold')
for index,(state,trial) in enumerate([(s,t) for s in ['partial','packed'] for t in range(1,4)]):
    y=93-index*8.5;text(16,y,state,8);text(47,y,str(trial),8)
text(14,40,'COMPUTED REFERENCE ONLY - compare at the same angle; do not copy these into observation cells.',8,INK,'Helvetica-Bold')
for x,item,label in zip((14,106,198),data['poses'],('Deployed','Partial','Packed')):
    dim=item['dimensions'];text(x,33,f'{label} {item["angle"]:.2f} deg:',8,GREEN,'Helvetica-Bold')
    text(x,28,f'X {dim["x_mm"]:.2f} / Y {dim["y_mm"]:.2f} / H {dim["z_mm"]:.2f} mm',8)
paragraph(14,19,'Keep unsuccessful trials, wrinkles and springback in your notes. Photograph the sample from above and from the side with a ruler. Physical agreement, strength and reliable packing are still unverified.',268,8,4)
footer(3);c.save()
print(out)
