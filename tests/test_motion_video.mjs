import test from "node:test";
import assert from "node:assert/strict";
import {recordCanvasVideo, videoFramePlan, motionSettingsCurrent} from "../crate_studio/web/motion_video.mjs";

test("generic motion uses samples per transition, and changed settings are stale", () => {
  const generic = {family: "general_mechanism", spec: {samples_per_segment: 73}, config: {progress_max: 100}};
  assert.equal(motionSettingsCurrent(generic, "90", "73"), true);
  assert.equal(motionSettingsCurrent(generic, "90", "37"), false);
  const walls = {config: {max_angle_deg: 90, samples: 37}};
  assert.equal(motionSettingsCurrent(walls, "90", "37"), true);
  assert.equal(motionSettingsCurrent(walls, "80", "37"), false);
});

function recordingFixture() {
  const state = {stops: 0, recorder: null};
  const canvas = {captureStream: () => ({getTracks: () => [{stop: () => state.stops++}]})};
  class Recorder {
    static isTypeSupported(type) { return type === "video/webm;codecs=vp8"; }
    constructor(stream, options) { state.recorder = this; this.options = options; this.state = "inactive"; }
    start() { this.state = "recording"; }
    stop() {
      this.state = "inactive";
      this.ondataavailable?.({data: new Blob(["test encoder lifecycle only"])});
      this.onstop?.();
    }
  }
  return {state, canvas, Recorder};
}

test("video visits every checked pose forward and backward with both endpoints", () => {
  assert.deepEqual(videoFramePlan(4), [0,1,2,3,2,1,0]);
  for (const invalid of [0, 1, 2.5, 722, NaN]) assert.throws(() => videoFramePlan(invalid));
});

test("recording negotiates supported codec and releases tracks after completed data", async () => {
  const {state, canvas, Recorder} = recordingFixture(), seen = [];
  const blob = await recordCanvasVideo(canvas, index => seen.push(index), [0,1,0], {Recorder, fps: 1000});
  assert.ok(blob.size > 0);
  assert.equal(blob.type, "video/webm");
  assert.deepEqual(seen, [0,0,1,0]);
  assert.equal(state.recorder.options.mimeType, "video/webm;codecs=vp8");
  assert.equal(state.stops, 1);
});

test("cancellation never returns a download and releases the encoder/track", async () => {
  const {state, canvas, Recorder} = recordingFixture(), abort = new AbortController();
  await assert.rejects(recordCanvasVideo(canvas, () => {}, [0,1,0], {
    Recorder, fps: 1000, signal: abort.signal, onProgress: () => abort.abort(),
  }), {name: "AbortError"});
  assert.equal(state.stops, 1);
  assert.equal(state.recorder.state, "inactive");
});

test("changed-source drawing error is propagated and the stream is closed", async () => {
  const {state, canvas, Recorder} = recordingFixture();
  await assert.rejects(recordCanvasVideo(canvas, index => {
    if (index === 1) throw new Error("Source changed");
  }, [0,1], {Recorder, fps: 1000}), /Source changed/);
  assert.equal(state.stops, 1);
});

test("encoder failure is propagated rather than returning a partial successful video", async () => {
  const {state, canvas, Recorder} = recordingFixture();
  await assert.rejects(recordCanvasVideo(canvas, () => {}, [0,1], {
    Recorder, fps: 1000, onProgress: () => state.recorder.onerror({error: new Error("Encoder broke")}),
  }), /Encoder broke/);
  assert.equal(state.stops, 1);
});

test("unsupported browser fails before capture", async () => {
  const {state, canvas, Recorder} = recordingFixture();
  Recorder.isTypeSupported = () => false;
  await assert.rejects(recordCanvasVideo(canvas, () => {}, [0,1], {Recorder}), /cannot record/);
  assert.equal(state.recorder, null);
  assert.equal(state.stops, 0);
});
