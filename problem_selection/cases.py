"""Constructed revision packets. No customer artifacts or physical measurements."""
from copy import deepcopy


def contract(width=600., thickness=1.2, material="steel", opening=594., basis="nominal", unresolved=()):
    return dict(width_mm=width, thickness_mm=thickness, material=material,
                min_opening_mm=opening, basis=basis, unresolved=list(unresolved))


def packet(case_id, text, desired, width=606., thickness=6., material="PETG", tolerances=None,
           source_role="customer", drawing_stale=False, bom_count=2, extra_messages=()):
    old=dict(width_mm=600., thickness_mm=1.2, material="steel", revision="A")
    proposed=dict(width_mm=width, thickness_mm=thickness, material=material, revision="B")
    drawing=deepcopy(old if drawing_stale else proposed)
    proposed["tolerances_mm"]=tolerances
    return {"id":case_id, "provenance":"synthetic development fixture; not a designer-reviewed case",
            "packet":{"previous_model":old,"previous_approved_contract":contract(),
                      "proposed_model":proposed,"drawing":drawing,
                      "bom":{"side_panel_count":bom_count,"material":material,"revision":"B"},
                      "sources":[{"id":"message-1","role":source_role,"text":text},*extra_messages]},
            "gold_contract":desired}


def cases():
    approve="Approve PETG side panels at 6 mm and an overall width of 606 mm. The clear opening must be at least 594 mm nominal."
    out=[
        packet("R01",approve,contract(606,6,"PETG")),
        packet("R02","Quote PETG at 6 mm with an overall width of 606 mm; this is a supplier suggestion, not an approved change.",contract(),source_role="supplier"),
        packet("R03","Approve 6 mm PETG sides. You may increase the outside width, but retain at least the actual nominal clear opening of the previous model, not merely the old minimum.",contract(None,6,"PETG",597.6)),
        packet("R04","Approve PETG sides at 6 mm and outside width 606 mm. Require at least 594 mm clear opening at worst-case supplied dimensional tolerances.",contract(606,6,"PETG",594,"worst_case"),tolerances={"width":.5,"thickness":.2}),
        packet("R05","Approve PETG sides at 6 mm and outside width 607 mm. Require at least 594 mm clear opening at worst-case supplied dimensional tolerances.",contract(607,6,"PETG",594,"worst_case"),width=607,tolerances={"width":.5,"thickness":.2}),
        packet("R06","We want to replace steel with plastic to save money, but have not selected or approved a grade or stock thickness. Do not guess these or treat the draft as approval.",contract(unresolved=["material_and_thickness"]),width=600,thickness=3,material="PP"),
        packet("R07","Approve PETG sides one quarter inch thick and an overall width of 24 inches. The minimum nominal clear opening is now 596 mm. These replace the old width, thickness, material and opening requirements.",contract(609.6,6.35,"PETG",596),width=609.6,thickness=6.35),
        packet("R08",approve,contract(606,6,"PETG"),drawing_stale=True),
        packet("R09","The outside width must remain 600 mm. This instruction has the same approval status and time as message-2; neither supersedes the other.",contract(unresolved=["approval_conflict"]),extra_messages=[{"id":"message-2","role":"customer","text":"The outside width must be 606 mm. Same approval status and time as message-1; neither supersedes the other."}]),
        packet("R10","No requirement changes. Regenerate the documents under revision B, keeping the existing approved dimensions and material.",contract(),width=600,thickness=1.2,material="steel"),
        packet("R11",approve,contract(606,6,"PETG"),bom_count=3),
        packet("R12","Approve 6 mm PETG sides and 606 mm overall width. Keep the old minimum opening requirement; matching the old model's larger achieved opening is unnecessary.",contract(606,6,"PETG")),
        packet("R13","Approve 6 mm PETG sides and 607 mm overall width. Guarantee at least 594 mm opening at worst-case manufacturing tolerances; the supplier has not provided any tolerances yet.",contract(607,6,"PETG",594,"worst_case",["tolerances"]),width=607),
    ]
    return out
