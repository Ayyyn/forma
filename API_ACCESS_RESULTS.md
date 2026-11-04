# API access results — October 27, 2026

Real authenticated requests from the user's workstation, completed around 5:03 PM India time. No region-routing overrides or provider substitution were configured. Keys remain in local `.env`, excluded from Git. These are small capability checks, not a reliability or engineering-reasoning benchmark.

| Check | Meta `muse-spark-1.3` | Baseten `meta-models/muse-spark-open-1026` |
| --- | --- | --- |
| Authenticated model catalog | Passed, HTTP 200 | Passed, HTTP 200; requested slug listed |
| Text inference | Passed, `API_OK` | Passed, `API_OK` |
| Prompted JSON and local validation | Passed | Passed |
| JSON schema option accepted; output valid | Passed | Passed |
| Conflicting plain-text prompt with schema | Passed, required JSON returned | Passed, required JSON returned |
| Same conflicting prompt without schema | Passed, plain text returned | Passed, plain text returned |
| Actual model-selected function call | Passed | Passed |
| Locally computed tool result returned to model | Passed, area 600 mm² | Passed, area 600 mm² |
| Image understanding | Passed, correct left/right colors | Passed, correct left/right colors |

The authenticated text and vision calls succeeded without geographic errors for these models at this time. This does not establish availability from a future deployment host or for untested models.

## Findings affecting implementation

1. The handoff's blanket claim that direct Meta Model API cannot be used from India is contradicted by these successful calls. Both the direct Meta service and Baseten are usable for the tested capabilities.
2. Muse Image generation remains excluded: [Meta's current geographic policy](https://dev.meta.ai/legal/geographic-use-policy) explicitly restricts Muse Image in India. It was not called. Image input on Muse Spark is a separate capability and did work.
3. [Baseten's documentation](https://docs.baseten.co/inference/model-apis/overview) excludes Muse Spark Open from native structured output support, but the tested `-1026` endpoint accepted schema requests and followed them even against a conflicting user prompt. Preserve local validation and bounded recovery; a few successful probes do not prove decoding guarantees for every schema.
4. Reasoning counts toward the completion allowance. Meta vision exhausted the initial 768-token cap; a targeted repeat at 2048 succeeded, using 866 completion tokens. Budget future tasks according to complexity.
5. The original tool validator incorrectly required the text `600`; both models returned the correct numeric value `600.0`. The validator now checks numeric equivalence, and both real round trips passed on repeat.
6. The first run did not test SAM segmentation, voice transcription, or Muse Wonder; subsequent tests below now establish basic access to these models. Image editing, streaming, sustained rate limits, and deployment-host access remain untested. A catalog listing alone does not verify inference on a model.
7. API usage was returned, but account balances and dollar charges were not queried or verified. Personal credit-grant details are retained privately.

## Reproducible evidence

Local raw reports (ignored by Git):

- `artifacts/preflight/20261027T113148843473Z.json`: initial authenticated run; preserves the initial assertion and token-limit issues.
- `artifacts/preflight/20261027T113314816014Z.json`: targeted schema controls, tool round trips, and vision; all selected checks passed.

Commands:

```powershell
python scripts/api_preflight.py
python scripts/api_preflight.py --checks tool_round_trip vision schema_conflict_control schema_conflict
```

The API preflight prerequisite is met for a Meta-powered design-search system using text, tools, structured data, and image input. No product implementation has started.

## Additional models checked around 5:12 PM India time

| Model | Actual check | Result |
| --- | --- | --- |
| `muse-wonder-1.0` | Text response, exact marker | Passed, HTTP 200 |
| `muse-spark-1.2` | Text response, exact marker | Passed, HTTP 200 |
| `muse-spark-1.1` | Text response, exact marker | Passed, HTTP 200 |
| `muse-spark-1.3-contributor` | Text response, synthetic marker only | Passed, HTTP 200 |
| `muse-spark-1.2-contributor` | Text response, synthetic marker only | Passed, HTTP 200 |
| `sam-3.1` | Segment a generated red rectangle on white | Passed, HTTP 200; box aligned with the fixture and mask payload returned |
| `muse-voice-transcribe-1.0` | Transcribe a 4.5-second Windows synthetic-speech WAV | Passed, HTTP 200; correct sentence returned |
| Baseten `meta-models/muse-spark-open` (unversioned alias) | Text request | Failed, HTTP 403, `please check the api-key you provided` |

SAM returned a 256×256 source-frame box `(64,80)-(191,175)` around the known red rectangle. Its mask payload was present but not decoded; this does not validate mask pixel accuracy or video tracking.

Voice returned: “The red rectangle is 30 millimeters wide and 20 millimeters high.” The source was generated locally; no microphone was accessed. Streaming voice and speaker attribution were not tested.

The Contributor variants received only synthetic marker requests, with no project or user content. Their data-use terms differ from Standard mode; these successful calls do not change our default Standard model selection. [Model designations](https://dev.meta.ai/legal/geographic-use-policy).

The Baseten unversioned alias's 403 is an access/credential error, without an explicit geographic explanation. Use the successfully tested hackathon-specific `meta-models/muse-spark-open-1026` slug. Glimmer and Wonder Full were not present in the observed account catalogs and were not deployed or tested.

A follow-up with the same Baseten credentials reconfirmed successful text inference on `meta-models/muse-spark-open-1026`, isolating the observed failure to the unversioned alias. Evidence: `artifacts/preflight/20261027T114300138148Z.json`.

Raw evidence: `artifacts/preflight/20261027T114204012153Z-other-models.json`. Reproduce with `python scripts/other_meta_preflight.py`; its voice check requires the local synthetic WAV fixture. The older Spark versions, Contributor versions, and Wonder received only basic text checks, not the complete capability suite run on Spark 1.3.
