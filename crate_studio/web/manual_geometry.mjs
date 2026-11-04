export function rotateXYZ(point, angles) {
  let [x,y,z]=point;
  const [a,b,c]=angles.map(v=>v*Math.PI/180);
  [y,z]=[y*Math.cos(a)-z*Math.sin(a),y*Math.sin(a)+z*Math.cos(a)];
  [x,z]=[x*Math.cos(b)+z*Math.sin(b),-x*Math.sin(b)+z*Math.cos(b)];
  return [x*Math.cos(c)-y*Math.sin(c),x*Math.sin(c)+y*Math.cos(c),z];
}
export function pivotTranslation(pivot, shift, angles) {
  if (![...pivot,...shift,...angles].every(Number.isFinite)) throw new Error('Enter finite coordinates and angles.');
  const rotated=rotateXYZ(pivot,angles);
  return pivot.map((v,i)=>v+shift[i]-rotated[i]);
}
