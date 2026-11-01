# API availability before product implementation

The user reports $150 in Meta Model API credits and $100 in Baseten credits. Both accounts now pass authenticated inference checks from this workstation. Credit balance is separate and has not been verified. See [recorded results](API_ACCESS_RESULTS.md).

## Run

Put keys in the existing local `.env` file (ignored by Git):

```dotenv
MODEL_API_KEY=your_meta_key
BASETEN_API_KEY=your_baseten_key
```

Then run from this folder:

```powershell
python scripts/api_preflight.py
```

No dependencies to install. Optional: `--provider meta`, `--provider baseten`, or `--network-only` for unauthenticated DNS/HTTP checks with no inference requests. Environment variables take precedence over `.env`. `META_API_KEY` is accepted as an alias if `MODEL_API_KEY` is empty.

The default run makes at most six inference requests per configured provider, capped at 768 output tokens for text/tool checks and 2048 for vision, with no automatic retries. It records HTTP status, latency, reported token usage, selected public test outputs, and tool arguments. It does not request account balance or verify the credit grant. It does not log API keys or private reasoning. Cost remains unknown until current model pricing is verified. Reports are saved under `artifacts/preflight/` and ignored by Git.

Use `--checks` to select checks. Optional `schema_conflict_control schema_conflict` checks compare a conflicting plain-text instruction with and without a schema (at most two extra calls per provider). A selected `tool_round_trip` also runs its required tool-call step.

## Checks and interpretation

- Catalog: discover model IDs, where the endpoint supports it. A missing catalog endpoint alone does not establish failed inference.
- Text: request a fixed marker.
- Prompted JSON: parse and validate an exact small object. Success is not a guarantee of schema-constrained decoding.
- Strict schema: separately test the native `response_format` feature. Baseten's documentation excludes Muse Spark Open, but live calls to the `-1026` slug accepted the option and produced schema-valid output, including when the user prompt requested conflicting plain text. Keep runtime validation because these smoke tests do not establish universal schema guarantees.
- Tool calling: require an actual function call, validate its arguments, compute the rectangle area locally, and return the tool result to the model.
- Vision: submit a generated two-color PNG and check that the model identifies each side. This tests image input, not image generation or complex engineering perception.

A 401 indicates credentials; 402 billing; 403 access denied (not automatically geography); 404 model or route; 429 rate or quota. Explicit geographic error wording is recorded separately. Generic DNS/TLS/timeout failures do not establish a country restriction. A passed probe is evidence of access from this workstation at that time, not a guarantee of future or deployed-host access.

## Current geographic and capability findings

- Live workstation checks on October 27: both providers returned authenticated HTTP 200 responses for catalogs and all tested inference capabilities. HTTPS connectivity works outside the execution sandbox; sandbox DNS initially failed.
- Meta's geographic policy dated October 12, 2026 explicitly restricts **Muse Image in India**. No Muse Image request is made. Other models need real authenticated checks; India is not on the policy's blanket restricted-territory list.
- Muse Spark Open accepts image input and outputs text; it is not an image generator.
- Baseten documents tool calling for Model APIs, with Muse Spark Open excluded from native JSON mode and structured outputs. Live schema probes succeeded on the specific `-1026` slug; this discrepancy is recorded rather than assuming either universal support or failure.
- Baseten's requested slug `meta-models/muse-spark-open-1026` is now confirmed in the authenticated catalog and successful inference calls.
- SAM segmentation is a separate optional capability; it has not been tested or integrated.
- No other provider or model is silently substituted. No deployment or paid GPU resource is created.

Sources:

- [Meta geographic policy](https://dev.meta.ai/legal/geographic-use-policy)
- [Meta API/model overview](https://dev.meta.ai/docs/overview)
- [Baseten Model APIs](https://docs.baseten.co/inference/model-apis/overview)

The core text, tool, JSON, and vision preflight gate has passed. The subsequent local geometry studio and real Meta design-agent prototype are documented in `README.md`; image generation remains unavailable for this India-based workflow under the documented Muse Image restriction.
