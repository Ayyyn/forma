import {pivotTranslation} from './manual_geometry.mjs';
export const modelToWorld=p=>[p[0],p[2],-p[1]];
export const worldToModel=p=>[p[0],-p[2],p[1]];
export function nativeBodyPivot(rows,id){
  const row=rows?.find(r=>r.id===id);
  return row?row.bounds_mm[0].map((v,i)=>(v+row.bounds_mm[1][i])/2):null;
}
export function constrainedDelta(delta,constraint,step=0){
  return delta.map((value,i)=>{
    if(!Number.isFinite(value))throw new Error('Enter finite coordinates.');
    if(!constraint.includes('XYZ'[i]))return 0;
    return Number((step>0?Math.round(value/step)*step:value).toFixed(8))||0;
  });
}
export function closestAxisParameter(origin,direction,pivot,axis){
  const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),w=origin.map((v,i)=>v-pivot[i]),ad=dot(axis,direction),den=1-ad*ad;
  if(den<.025)return null;
  return (dot(w,axis)-dot(w,direction)*ad)/den;
}
export function placementParameters(pivot,shift,rotation){
  if(![...pivot,...shift,...rotation].every(Number.isFinite))throw new Error('Enter finite coordinates and angles.');
  return {translation:pivotTranslation(pivot,shift,rotation),rotation:[...rotation]};
}
export function outsideDimension(a,b,corners,gap=26){
  const dx=b.x-a.x,dy=b.y-a.y,length=Math.hypot(dx,dy);if(length<8)return null;
  const centre={x:corners.reduce((s,p)=>s+p.x,0)/corners.length,y:corners.reduce((s,p)=>s+p.y,0)/corners.length};
  let nx=-dy/length,ny=dx/length;
  const mid={x:(a.x+b.x)/2,y:(a.y+b.y)/2};
  if((mid.x-centre.x)*nx+(mid.y-centre.y)*ny<0){nx=-nx;ny=-ny;}
  const distance=Math.max(0,...corners.map(p=>(p.x-mid.x)*nx+(p.y-mid.y)*ny))+gap;
  return {a:{x:a.x+nx*distance,y:a.y+ny*distance,visible:a.visible},b:{x:b.x+nx*distance,y:b.y+ny*distance,visible:b.visible}};
}
