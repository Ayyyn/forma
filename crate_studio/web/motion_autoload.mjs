// Exact display binding, including imported bytes and retained checker identity.
export function motionBinding(snapshot) {
  const meta = snapshot?.document?.metadata || {};
  return JSON.stringify([snapshot?.geometry_signature, snapshot?.geometry_version,
    snapshot?.asset_identity, meta.design_mechanism || null, meta.assembly_plan || null,
    snapshot?.native_study_state?.status, meta.native_study_review?.source_identity]);
}

// Opening Motion may load an already-qualified definition. Failed/unverified
// designs still require an explicit check; merely opening another tab does none.
export function motionAutoLoad({getSnapshot, isVisible, isBusy, hasStudy, load}) {
  let attempted = null, pending = false;
  return function ensure() {
    const snapshot = getSnapshot();
    if (!isVisible() || isBusy() || pending || hasStudy() ||
        snapshot?.native_study_state?.status !== "current" ||
        snapshot?.native_study_state?.passed !== true ||
        !snapshot?.document?.metadata?.design_mechanism?.states?.length) return;
    const key = motionBinding(snapshot);
    if (key === attempted) return;
    attempted = key;
    pending = true;
    return Promise.resolve().then(load).finally(() => {
      pending = false;
      if (motionBinding(getSnapshot()) !== key) ensure();
    });
  };
}
