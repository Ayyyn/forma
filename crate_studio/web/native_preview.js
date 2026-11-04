import * as THREE from "three";
import {OrbitControls} from "/assets/vendor/OrbitControls.js";
import {drawingRequest} from "/assets/drawing_request.js";
const host=document.querySelector("#viewport"), scene=new THREE.Scene();
scene.background=new THREE.Color(0xf5f3ee);
const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));host.append(renderer.domElement);
const camera=new THREE.PerspectiveCamera(40,1,.05,100000);camera.up.set(0,0,1);
const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
scene.add(new THREE.HemisphereLight(0xffffff,0x657478,2.5));const light=new THREE.DirectionalLight(0xffffff,2);light.position.set(150,-200,350);scene.add(light);
let group=null,latest=null,view='model';
function clear(){latest=null;if(group){scene.remove(group);group.traverse(o=>{o.geometry?.dispose();if(o.material)[o.material].flat().forEach(m=>m.dispose());});group=null;}document.querySelector("#empty").hidden=false;document.querySelector("#drawing").replaceChildren();document.querySelector("#stage").textContent="Waiting for the next native draft…";}
const requestDrawing=drawingRequest({getSnapshot:()=>latest,isNeeded:()=>view==='drawing',
 api:async(path,body)=>{const response=await fetch('/api/studio'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const value=await response.json();if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:'Native drawing failed');return value;},
 onReady:snapshot=>{document.querySelector('#drawing').innerHTML=snapshot.drawing_svg;},
 onError:error=>{document.querySelector('#drawing').textContent=error.message;}});
function ensureDrawing(){if(latest?.drawing_pending&&!latest.drawing_svg)document.querySelector('#drawing').textContent='Generating native vector drawing…';requestDrawing();}
function fit(){if(!group)return;const bounds=new THREE.Box3().setFromObject(group),center=bounds.getCenter(new THREE.Vector3()),size=bounds.getSize(new THREE.Vector3()).length();controls.target.copy(center);camera.position.copy(center).addScaledVector(new THREE.Vector3(.8,-1,.8).normalize(),Math.max(size,1)*1.8);camera.near=Math.max(.01,size/10000);camera.far=Math.max(size*30,1000);camera.updateProjectionMatrix();controls.update();}
function resize(){if(!host.clientWidth||!host.clientHeight)return;renderer.setSize(host.clientWidth,host.clientHeight,false);camera.aspect=host.clientWidth/host.clientHeight;camera.updateProjectionMatrix();}
new ResizeObserver(resize).observe(host);renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera);});
function model(snapshot){
 clear();
 latest=snapshot;
 group=new THREE.Group();
 for(const [i,part] of (snapshot.geometry?.parts||[]).entries()){
  const geometry=new THREE.BufferGeometry();geometry.setAttribute("position",new THREE.Float32BufferAttribute(part.vertices,3));geometry.setIndex(part.triangles);geometry.computeVertexNormals();
  const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:[0xa5bac0,0xc2b299,0xa9bca4][i%3],roughness:.65}));
  mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry),new THREE.LineBasicMaterial({color:0x46565d,transparent:true,opacity:.35})));group.add(mesh);
 }
 scene.add(group);document.querySelector("#empty").hidden=true;
 document.querySelector("#drawing").innerHTML=snapshot.drawing_svg||"<p>No drawing available.</p>";
 if(view==='drawing')ensureDrawing();
 resize();fit();
}
window.addEventListener("message",event=>{if(event.source!==parent||event.origin!==location.origin)return;const data=event.data;if(data?.type==="forma-preview"){model(data.snapshot);document.querySelector("#stage").textContent=data.label||"Native candidate · not applied";}else if(data?.type==="forma-preview-reset")clear();else if(data?.type==="forma-preview-stage")document.querySelector("#stage").textContent=data.label;});
for(const [id,target] of [["model","model"],["drawing-button","drawing"]])document.getElementById(id).onclick=()=>{view=target;host.style.display=view==="model"?"block":"none";document.querySelector("#drawing").style.display=view==="drawing"?"block":"none";document.querySelector("#model").setAttribute("aria-pressed",String(view==="model"));document.querySelector("#drawing-button").setAttribute("aria-pressed",String(view==="drawing"));if(view==='drawing')ensureDrawing();resize();};
document.querySelector("#fit").onclick=fit;
parent.postMessage({type:"forma-preview-ready"},location.origin);
