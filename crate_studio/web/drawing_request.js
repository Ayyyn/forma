// Fetch exact vector drawings only when a visible view needs them.
export function drawingRequest({getSnapshot,api,onReady,onError,isNeeded=()=>true}) {
  let pending=null;
  return function ensureDrawing() {
    const snapshot=getSnapshot();
    if(!isNeeded()||!snapshot?.drawing_pending||snapshot.drawing_svg||pending)return;
    pending=snapshot;
    api('/drawing/overview',{document:snapshot.document,revision_id:snapshot.id},600000).then(result=>{
      if(getSnapshot()!==snapshot)return;
      if(result.geometry_signature!==snapshot.geometry_signature||result.geometry_version!==snapshot.geometry_version||JSON.stringify(result.asset_identity)!==JSON.stringify(snapshot.asset_identity))throw new Error('Drawing source or imported geometry changed. Reload the current revision.');
      snapshot.drawing_svg=result.svg;snapshot.drawing_pending=false;onReady(snapshot);
    }).catch(error=>{if(getSnapshot()===snapshot)onError(error);}).finally(()=>{
      if(pending===snapshot)pending=null;
      // Keep one request in flight. Rapid saves/history changes collapse to the
      // latest source instead of filling the browser's connection pool with
      // obsolete native projections and delaying ordinary edits.
      if(getSnapshot()!==snapshot&&isNeeded())ensureDrawing();
    });
  };
}
