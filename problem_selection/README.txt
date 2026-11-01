Problem-first revision feasibility screen (2026-10-30)

Start with output/problem-selection-brief/index.html.
Source findings: research/problem_selection_evidence.json.
Designer review: output/problem-selection-brief/designer-review.html.
Scored live run: output/problem-selection-v2-live/.

Offline verification, from C:\Users\LENOVO\meta_hack:
  python -m unittest discover -s tests -p test_problem_selection.py -v
  python -m problem_selection.study report --directory output/problem-selection-v2-live
  python research/audit_problem_selection.py
  python research/problem_selection_report.py

Fresh paid run (only when a new evaluation is justified):
  python -m problem_selection.study prepare --directory output/YOUR_NEW_STUDY
  python -m problem_selection.study run --directory output/YOUR_NEW_STUDY
Requires existing local MODEL_API_KEY. Never put credentials in the browser or reports.
run refuses an existing ledger; prepare refuses an existing directory.
Network access is required. Up to 26 requests and $5 conservative estimated cap.
Missing token usage consumes the full reservation. Estimated costs are not billing.

Results:
  26 actual successful Muse Wonder responses, 26 unique provider IDs.
  Provisional estimated cost $0.407136; no billed-balance verification.
  Both single-pass and feedback continuation: 12/13 exact frozen outputs.
  13/13 core numerical/material/basis fields correct, no false clearances.
  The only frozen-label disagreement: clarification versus blocking an unapproved
  supplier suggestion. Both withhold clearance; prompt/rubric ambiguity is disclosed
  in independent-audit.json. Frozen gold has not been revised to improve the score.
  Extra checker-feedback turn offered no improvement on these cases.

What the controls mean:
  Conservative baseline does all supplied record checks and sends freeform customer
  changes to a human. It is NOT the strongest possible commercial/agent competitor.
  Oracle-form control uses the correct gold contract as if a human entered it;
  perfect arithmetic is a ceiling, not observed human speed/accuracy.
  Feedback reuses the exact first response plus one extra call. It has a larger
  inference budget, explicitly not an equal-token method comparison.

Limitations:
  13 synthetic, correlated, development fixtures; no designer-reviewed cases yet.
  JSON record inputs only; no arbitrary drawing OCR, PDF/CAD import, SLDPRT editing,
  physical validation, strength/material qualification, prices or manufacturing approval.
  Geometry checks cannot prove the extracted contract is the customer's true intent.
  Exact source substrings prove provenance only, not faithful interpretation.
  No customer-time, willingness-to-adopt, prototype-saving, or winning claim.
  The capability screen merits a designer-reviewed case trial, not a full product build.

Provenance:
  New package/cases/checker/study/tests/research brief were built in this session.
  Reused scripts/api_preflight.py for transport and structure_lab/tool_protocol.py
  for strict JSON parsing. Both dependencies are snapshotted and hash-checked.
  v1 preparation had a Windows manifest-path bug before any API call.
  v2 sandbox attempt failed DNS before any model response. It is not scored as
  model behavior. v2-live used unchanged prepared code with network access.
  Earlier structure/CAD/benchmark directions were not edited or expanded.
