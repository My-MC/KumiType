#!/usr/bin/env python3
"""Compare every tracked output in a build snapshot with its original Cascadia."""
import argparse
import json
from pathlib import Path

from kumitype.artifacts import write_text
from kumitype.shaping import compare_shaping

parser = argparse.ArgumentParser()
parser.add_argument('--build-dir', type=Path, default=Path('build'))
parser.add_argument('--harfbuzz', default='hb-shape')
parser.add_argument('--base', action='append', help='Only compare selected base variants')
args = parser.parse_args()
results = []
for path in sorted(args.build_dir.rglob('*.ttf')):
    manifest_path = path.with_suffix('.json')
    if not manifest_path.exists():
        continue
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if args.base and manifest['target']['base'] not in args.base:
        continue
    result = compare_shaping(Path(manifest['sources'][0]['path']), path, args.harfbuzz)
    results.append({'path': str(path), **result})
report_name = 'shaping-report.json' if not args.base else 'shaping-report-' + '-'.join(args.base) + '.json'
write_text(args.build_dir / report_name, json.dumps(results, indent=2))
print(f"Compared {len(results)} outputs; passed: {sum(r['status'] == 'passed' for r in results)}")
raise SystemExit(0 if results and all(r['status'] == 'passed' for r in results) else 1)
