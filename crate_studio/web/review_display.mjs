// Advisory development notes retain their original candidate scope. This
// projection never changes native/design review results or the saved document.
export function displayChecks(snapshot) {
  const metadata = snapshot?.document?.metadata;
  const earlier = metadata?.assembly_development?.source_candidate;
  const current = metadata?.manufacturing_development?.source_candidate;
  return (snapshot?.checks || []).map(check => {
    if (check.id !== "practical_release" || !earlier || !current || earlier === current) return check;
    return {...check, status:"stale", label:"Development notes · earlier candidate",
      detail:`Recorded for ${earlier}. These inherited notes are not a fresh result for this revision. Current native checks and physical qualification remain separate. ${check.detail || ""}`};
  });
}
