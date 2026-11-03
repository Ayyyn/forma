// Local, cancellable recording of actual checked poses. No generated video or model call.
export function motionSettingsCurrent(study, maxAngle, samples) {
  if (study?.family === "general_mechanism")
    return study.spec?.samples_per_segment === Number(samples);
  return !!study && study.config.max_angle_deg === Number(maxAngle)
    && study.config.samples === Number(samples);
}

export function videoFramePlan(count) {
  if (!Number.isInteger(count) || count < 2 || count > 721)
    throw new Error("A checked motion path with 2–721 poses is required.");
  return [...Array.from({length: count}, (_, i) => i),
    ...Array.from({length: count - 1}, (_, i) => count - 2 - i)];
}

export async function recordCanvasVideo(canvas, draw, plan, {signal, onProgress = () => {},
  Recorder = globalThis.MediaRecorder, fps = 30} = {}) {
  if (!Recorder || !canvas.captureStream)
    throw new Error("Video export needs a browser with canvas recording support.");
  const mimeType = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"]
    .find(type => Recorder.isTypeSupported(type));
  if (!mimeType) throw new Error("This browser cannot record WebM video.");
  let stream, recorder, stopped, failure;
  const chunks = [];
  const assertActive = () => {
    if (signal?.aborted) throw new DOMException("Video export cancelled.", "AbortError");
    if (failure) throw failure;
  };
  const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
  try {
    assertActive();
    await draw(plan[0]); // Canvas is populated before capture starts.
    stream = canvas.captureStream(fps);
    recorder = new Recorder(stream, {mimeType, videoBitsPerSecond: 5_000_000});
    stopped = new Promise(resolve => { recorder.onstop = resolve; });
    recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
    recorder.onerror = event => { failure = event.error || new Error("Video encoder failed."); };
    recorder.start(500);
    for (let index = 0; index < plan.length; index++) {
      assertActive();
      await draw(plan[index]);
      onProgress((index + 1) / plan.length);
      // Yield a real frame interval: MediaRecorder timestamps are wall-clock.
      await delay(1000 / fps);
    }
    assertActive();
    recorder.stop();
    let finishTimeout;
    try {
      await Promise.race([stopped, new Promise((_, reject) => {
        finishTimeout = setTimeout(() => reject(new Error("The video encoder did not finish. Try again.")), 10000);
      })]);
    } finally { clearTimeout(finishTimeout); }
    assertActive();
    const blob = new Blob(chunks, {type: "video/webm"});
    if (!blob.size) throw new Error("The browser returned an empty video.");
    return blob;
  } finally {
    if (recorder && recorder.state !== "inactive") recorder.stop();
    stream?.getTracks().forEach(track => track.stop());
  }
}
