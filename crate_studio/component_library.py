"""Curated, source-pinned components. Never executes user-supplied CAD code.

Hardware dimensions come from cq_warehouse; electronics are KiCad reference
solids. These are geometry assets, not electrical or strength simulations.
"""

from copy import deepcopy
import hashlib
from importlib.metadata import version
import math
from pathlib import Path
import tempfile
import urllib.request
import uuid

CQ_REV = "a57bb7a24762d367d66369f280a24c38a64e73dd"
KICAD_REV = "b8b3cfdfad88ba66f21002b3de51dc6f7d55ba5a"


def _hardware(ident, label, cls, standard, length=False):
    return {
        "id": ident,
        "name": label,
        "category": "Hardware",
        "generator": cls,
        "standard": standard,
        "source": "https://github.com/gumyr/cq_warehouse/tree/" + CQ_REV,
        "revision": CQ_REV,
        "license": "Apache-2.0",
        "license_url": "https://github.com/gumyr/cq_warehouse/blob/"
        + CQ_REV
        + "/LICENSE",
        "parameters": {
            "size": {
                "type": "choice",
                "choices": ["M3-0.5", "M4-0.7", "M5-0.8", "M6-1"],
                "default": "M3-0.5",
            },
            **(
                {
                    "length": {
                        "type": "number",
                        "min": 4,
                        "max": 80,
                        "default": 12,
                        "unit": "mm",
                    }
                }
                if length
                else {}
            ),
        },
        "scope": "Simplified unthreaded fit reference; nominal catalogue dimensions. Verify supplier tolerances and thread engagement separately.",
    }


def _electronic(ident, label, path, blob):
    return {
        "id": ident,
        "name": label,
        "category": "Electronics",
        "path": path,
        "git_blob": blob,
        "source": "https://github.com/KiCad/kicad-packages3D/blob/"
        + KICAD_REV
        + "/"
        + path,
        "revision": KICAD_REV,
        "license": "CC-BY-SA-4.0 with KiCad libraries exception",
        "license_url": "https://www.kicad.org/libraries/license/",
        "parameters": {},
        "scope": "Reference package geometry; no electrical behaviour, footprint or supplier tolerance verification.",
    }


CATALOG = [
    _hardware(
        "socket-screw",
        "Socket head screw · ISO 4762",
        "SocketHeadCapScrew",
        "iso4762",
        True,
    ),
    _hardware(
        "hex-screw", "Hex head screw · ISO 4017", "HexHeadScrew", "iso4017", True
    ),
    _hardware(
        "button-screw",
        "Button head screw · ISO 7380-1",
        "ButtonHeadScrew",
        "iso7380_1",
        True,
    ),
    _hardware("hex-nut", "Hex nut · ISO 4032", "HexNut", "iso4032"),
    _electronic(
        "usb-micro-b",
        "USB Micro-B · Molex 47346-0001",
        "Connector_USB.3dshapes/USB_Micro-B_Molex_47346-0001.step",
        "a0ee65305119c1566421acc48760b981372b031c",
    ),
    _electronic(
        "usb-mini-b",
        "USB Mini-B · Lumberg 2486",
        "Connector_USB.3dshapes/USB_Mini-B_Lumberg_2486_01_Horizontal.step",
        "85a113e1445d66e1bf52d8197d113f0ab438020d",
    ),
    _electronic(
        "dip-10",
        "DIP-10 · 7.62 mm package",
        "Package_DIP.3dshapes/DIP-10_W7.62mm.step",
        "7ffc075a14310bc2e5c7835508cc87c9df42b236",
    ),
]


def catalog():
    return [
        {
            k: deepcopy(v)
            for k, v in row.items()
            if k not in ("generator", "path", "git_blob")
        }
        for row in CATALOG
    ]


def definition(ident):
    for row in CATALOG:
        if row["id"] == ident:
            return deepcopy(row)
    raise ValueError("Unknown library component")


def parameters(row, values):
    if not isinstance(values, dict) or set(values) - set(row["parameters"]):
        raise ValueError("Unknown component parameters")
    out = {}
    for key, spec in row["parameters"].items():
        value = values.get(key, spec["default"])
        if spec["type"] == "choice":
            if value not in spec["choices"]:
                raise ValueError("Unsupported component " + key)
        elif (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not spec["min"] <= value <= spec["max"]
        ):
            raise ValueError("Component " + key + " is outside its supported range")
        out[key] = value
    return out


def materialize(ident, values, cache_dir, store_asset):
    """Called under CAD lock; cache verified source bytes and generated assets."""
    import cadquery as cq

    row = definition(ident)
    params = parameters(row, values)
    directory = Path(cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if "path" in row:
        source = directory / (row["git_blob"] + ".step")
        if source.exists():
            data = source.read_bytes()
        else:
            url = (
                "https://raw.githubusercontent.com/KiCad/kicad-packages3D/"
                + KICAD_REV
                + "/"
                + row["path"]
            )
            request = urllib.request.Request(
                url, headers={"User-Agent": "Forma-component-library/1"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read(15_000_001)
        if (
            len(data) > 15_000_000
            or hashlib.sha1(
                b"blob " + str(len(data)).encode() + b"\0" + data
            ).hexdigest()
            != row["git_blob"]
        ):
            raise ValueError("Pinned component source hash/size verification failed")
        source.write_bytes(data)
        solids = cq.importers.importStep(str(source)).solids().vals()
        runtime_version = "pinned STEP"
    else:
        from cq_warehouse import fastener

        runtime_version = version("cq-warehouse")
        # Hash key includes source revision, installed version and all parameters.
        import json

        key = hashlib.sha256(
            json.dumps(
                [row["id"], CQ_REV, runtime_version, params], sort_keys=True
            ).encode()
        ).hexdigest()
        source = directory / (key + ".step")
        if not source.exists():
            shape = getattr(fastener, row["generator"])(
                **params, fastener_type=row["standard"], simple=True
            )
            solids = list(shape.Solids())
            if not solids or any(not s.isValid() or s.Volume() <= 1e-9 for s in solids):
                raise ValueError(
                    "Library component produced invalid or empty native geometry"
                )
            with tempfile.TemporaryDirectory(dir=directory) as temp:
                target = Path(temp) / "component.step"
                cq.exporters.export(cq.Compound.makeCompound(solids), str(target))
                target.replace(source)
        solids = cq.importers.importStep(str(source)).solids().vals()
        data = source.read_bytes()
    if not solids or any(not s.isValid() or s.Volume() <= 1e-9 for s in solids):
        raise ValueError("Library component produced invalid or empty native geometry")
    # Read-back validation applies to cached and freshly generated bytes alike.
    reopened = cq.importers.importStep(str(source)).solids().vals()
    if len(reopened) != len(solids) or any(
        not s.isValid() or s.Volume() <= 1e-9 for s in reopened
    ):
        raise ValueError("Library component STEP read-back failed")
    asset = store_asset(data)
    return {
        "catalog_id": ident,
        "name": row["name"],
        "parameters": params,
        "asset_id": asset,
        "source": row["source"],
        "revision": row["revision"],
        "license": row["license"],
        "license_url": row["license_url"],
        "scope": row["scope"],
        "runtime_version": runtime_version,
        "solid_count": len(reopened),
    }


def insert(
    document, record, translation=(0, 0, 0), rotation=(0, 0, 0), feature_id=None
):
    doc = deepcopy(document)
    ident = feature_id or "component-" + uuid.uuid4().hex[:10]
    feature = {
        "id": ident,
        "type": "import_step",
        "name": record["name"],
        "params": {
            "asset_id": record["asset_id"],
            "translation": list(translation),
            "rotation": list(rotation),
        },
        "suppressed": False,
    }
    if feature_id:
        matches = [f for f in doc["features"] if f["id"] == ident]
        previous = doc.get("metadata", {}).get("component_instances", {}).get(ident)
        if (
            len(matches) != 1
            or not previous
            or matches[0]["type"] != "import_step"
            or previous["catalog_id"] != record["catalog_id"]
        ):
            raise ValueError("Selected feature is not this library component")
        feature["name"] = matches[0].get("name", feature["name"])
        feature["suppressed"] = matches[0].get("suppressed", False)
        doc["features"][doc["features"].index(matches[0])] = feature
    else:
        doc["features"].append(feature)
    doc.setdefault("metadata", {}).setdefault("component_instances", {})[ident] = (
        deepcopy(record)
    )
    # Existing review identities correctly become stale; never auto-certify mates/motion.
    return doc, ident


def instances(document):
    """Declared source instances; not a BOM of downstream patterns/booleans."""
    records = document.get("metadata", {}).get("component_instances", {})
    if not isinstance(records, dict):
        return []
    rows = []
    for feature in document.get("features", []):
        record = records.get(feature.get("id"))
        if (
            feature.get("type") != "import_step"
            or not isinstance(record, dict)
            or record.get("asset_id") != feature.get("params", {}).get("asset_id")
        ):
            continue
        rows.append(
            {
                **deepcopy(record),
                "feature_id": feature["id"],
                "feature_name": feature.get("name", "Component"),
                "suppressed": feature.get("suppressed", False),
            }
        )
    return rows
