"""Read actual measurement CSV rows; blank rows remain unmeasured. No API calls."""
import argparse, csv, json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from continuum.geometry import Design
from continuum.measurements import compare_measurement

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--csv', type=Path, default=root/'output/paper/measurements.csv')
parser.add_argument('--manifest', type=Path, default=root/'output/paper/paper-model.json')
parser.add_argument('--output', type=Path, default=root/'output/paper/measurement-comparison.json')
args = parser.parse_args()
manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
design = Design(**manifest['design'])
with args.csv.open(newline='', encoding='utf-8-sig') as handle:
    rows = list(csv.DictReader(handle))
report = {'design_id': manifest['design_id'], 'source_csv': str(args.csv),
          'results': [compare_measurement(design, manifest['design_id'], row) for row in rows]}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
print(json.dumps({'output': str(args.output), 'counts': {status: sum(r['status'] == status for r in report['results'])
                  for status in ('unmeasured', 'compared', 'rejected')}}, indent=2))
