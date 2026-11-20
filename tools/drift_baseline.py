"""Create a station drift baseline from representative observation JSONL, not synthetic scores."""
import argparse,json
from pathlib import Path
from backend.drift import distribution
p=argparse.ArgumentParser();p.add_argument('observations');p.add_argument('--output',default='data/drift-baseline.json');args=p.parse_args()
rows=[json.loads(line) for line in Path(args.observations).read_text().splitlines() if line.strip()]
if len(rows)<100:raise SystemExit('At least 100 representative observations required')
scores=[max((d['confidence'] for d in row['detections']),default=0) for row in rows]
path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps({'drift_baseline':distribution(scores),'samples':len(scores)},indent=2))
print('Saved ten-bin confidence distribution. Set drift_baseline on the matching station; re-baseline only after engineering review.')
