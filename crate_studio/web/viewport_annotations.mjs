export function niceStep(value) {
  if(!Number.isFinite(value)||value<=0)return 1;
  const scale=10**Math.floor(Math.log10(value));
  return [1,2,5,10].find(v=>v*scale>=value)*scale;
}
export function gridSpec(unitsPerPixel) {
  const step=niceStep(unitsPerPixel*25);
  return {step,extent:step*80,divisions:80};
}
export function envelopeDimensions(bounds) {
  if(!bounds||bounds.length!==2)return [];
  const [lo,hi]=bounds, pad=Math.max(1,Math.min(12,Math.max(...hi.map((v,i)=>v-lo[i]))*.12));
  return [
    {axis:'X',value:hi[0]-lo[0],a:[lo[0],lo[1]-pad,lo[2]],b:[hi[0],lo[1]-pad,lo[2]],fromA:[lo[0],lo[1],lo[2]],fromB:[hi[0],lo[1],lo[2]]},
    {axis:'Y',value:hi[1]-lo[1],a:[hi[0]+pad,lo[1],lo[2]],b:[hi[0]+pad,hi[1],lo[2]],fromA:[hi[0],lo[1],lo[2]],fromB:[hi[0],hi[1],lo[2]]},
    {axis:'Z',value:hi[2]-lo[2],a:[hi[0]+pad,hi[1]+pad,lo[2]],b:[hi[0]+pad,hi[1]+pad,hi[2]],fromA:[hi[0],hi[1],lo[2]],fromB:[hi[0],hi[1],hi[2]]},
  ];
}
export function bodyDragAllowed({button=0,modified=false,mode='bodies',busy=false,dirty=false,preview=false,measure=false,pointAction=false,handle=false}) {
  return button===0&&!modified&&mode==='bodies'&&!busy&&!dirty&&!preview&&!measure&&!pointAction&&!handle;
}
