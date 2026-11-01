"""Deterministic geometry/document checks. Never infer approvals from proposed CAD."""
import math
from copy import deepcopy

KEYS={"width_mm","thickness_mm","material","min_opening_mm","basis","unresolved"}
UNRESOLVED={"material_and_thickness","approval_conflict","tolerances"}


def validate_contract(c):
    if not isinstance(c,dict) or set(c)!=KEYS: raise ValueError("Exact contract keys required")
    for k in ("width_mm","thickness_mm","min_opening_mm"):
        v=c[k]
        if v is not None and (type(v) not in (int,float) or not math.isfinite(v) or v<=0):
            raise ValueError("Dimensions must be positive finite numbers or null")
    if c["material"] is not None and (not isinstance(c["material"],str) or not c["material"].strip()):
        raise ValueError("Material must be nonempty text or null")
    if c["basis"] not in ("nominal","worst_case"): raise ValueError("Unknown dimension basis")
    if not isinstance(c["unresolved"],list) or len(set(c["unresolved"]))!=len(c["unresolved"]) or not set(c["unresolved"])<=UNRESOLVED:
        raise ValueError("Invalid unresolved list")
    return c


def equivalent(a,b):
    validate_contract(a);validate_contract(b)
    for k in KEYS:
        x,y=a[k],b[k]
        if k=="unresolved":
            if set(x)!=set(y):return False
        elif k in ("width_mm","thickness_mm","min_opening_mm") and x is not None and y is not None:
            if not math.isclose(x,y,rel_tol=0,abs_tol=1e-7):return False
        elif x!=y:return False
    return True


def check(packet,c):
    validate_contract(c)
    model=packet["proposed_model"];drawing=packet["drawing"];bom=packet["bom"]
    opening=model["width_mm"]-2*model["thickness_mm"]
    tol=model["tolerances_mm"]
    worst=None if tol is None else opening-tol["width"]-2*tol["thickness"]
    flags=[]
    for k in ("width_mm","thickness_mm","material"):
        if c[k] is not None:
            match=math.isclose(c[k],model[k],abs_tol=1e-7,rel_tol=0) if k!="material" else c[k]==model[k]
            if not match:flags.append("requirement:"+k)
    relevant=opening if c["basis"]=="nominal" else worst
    if c["min_opening_mm"] is not None and relevant is not None and relevant+1e-7<c["min_opening_mm"]:
        flags.append("requirement:min_opening_mm")
    for k in ("width_mm","thickness_mm","material","revision"):
        if drawing[k]!=model[k]:flags.append("drawing:"+k)
    for k in ("material","revision"):
        if bom[k]!=model[k]:flags.append("bom:"+k)
    if bom["side_panel_count"]!=2:flags.append("bom:side_panel_count")
    unresolved=sorted(set(c["unresolved"]) | ({"tolerances"} if c["basis"]=="worst_case" and tol is None else set()))
    decision="clarify" if unresolved else "block" if flags else "geometry_and_records_pass"
    return dict(decision=decision,flags=sorted(flags),unresolved=unresolved,nominal_opening_mm=opening,
                worst_case_opening_mm=worst, scope="two parallel side panels; geometry and supplied records only; not strength, cost or manufacturing approval")


def conservative_baseline(packet):
    """Same-input no-NLP workflow: exhaust all checks, hold customer text for review.

    Strong on document consistency and fail-closed approvals, not a substitute for
    a commercial CAD workflow or human text interpretation. No substring tricks.
    """
    c=deepcopy(packet["previous_approved_contract"])
    result=check(packet,c)
    if any(s["role"]=="customer" for s in packet["sources"]):
        result["decision"]="clarify";result["unresolved"]=["human_change_request_review"]
    return result


def validate_submission(packet,submission):
    if not isinstance(submission,dict) or set(submission)!={"contract","evidence"}:raise ValueError("Expected contract and evidence")
    validate_contract(submission["contract"])
    evidence=submission["evidence"]
    if not isinstance(evidence,list) or not evidence:raise ValueError("Need source evidence")
    for e in evidence:
        if not isinstance(e,dict) or set(e)!={"source_id","quote"}:raise ValueError("Invalid evidence entry")
        source=next((s for s in packet["sources"] if s["id"]==e["source_id"]),None)
        if source is None or not isinstance(e["quote"],str) or not e["quote"] or e["quote"] not in source["text"]:
            raise ValueError("Citation must be an exact substring of an input source")
    return submission
