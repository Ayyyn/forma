export function selectedSketch(document, id) {
  return (document?.features || []).find(f=>f.id===id && f.type==="sketch_extrude") || null;
}

export function sketchKeyCommand(key, tab, sketch, editingText=false) {
  if (tab!=="sketch" || editingText) return null;
  if (key==="Escape") return "select";
  if ((key==="Delete" || key==="Backspace") && sketch) return "delete";
  return null;
}
